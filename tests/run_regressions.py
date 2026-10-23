"""统一回归入口：保留逐套退出码、真实 SKIP 数与完整临时日志。"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile


BASE = ["test_axis_mapping", "test_merger",
        "test_subset_merge", "test_cff2_compose"]
SYNTHETIC = ["test_cmap_regressions", "test_layout_regressions",
             "test_transform_regressions", "test_metadata_regressions",
             "test_naming_regressions", "test_invariants",
             "test_subset_regressions"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true",
                        help="只跑不依赖外部字体的合成回归")
    parser.add_argument("--engines", action="store_true",
                        help="追加现有 HarfBuzz/FreeType 系统库测试，不安装依赖")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    logs = Path(tempfile.mkdtemp(prefix="fontmerger-regressions-"))
    suites = ([] if args.synthetic_only else BASE) + SYNTHETIC
    if args.engines:
        suites.append("test_engine_regressions")
    passed = total = skips = failed = 0
    print("[回归] 完整日志：%s" % logs, flush=True)
    for suite in suites:
        run = subprocess.run([sys.executable, str(root / (suite + ".py"))],
                             cwd=str(root.parent), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True)
        output = run.stdout
        (logs / (suite + ".log")).write_text(output, encoding="utf-8")
        result = re.findall(r"Results:\s*(\d+)/(\d+)\s+passed", output)
        skipped = [line.strip() for line in output.splitlines()
                   if "SKIP" in line]
        skips += len(skipped)
        if result:
            good, count = map(int, result[-1])
            passed += good
            total += count
        else:
            good, count = 0, 0
        ok = run.returncode == 0 and bool(result) and good == count
        failed += int(not ok)
        print("[回归] %s: %d/%d，退出码 %d，SKIP %d%s" %
              (suite, good, count, run.returncode, len(skipped),
               "" if ok else "，FAILED"), flush=True)
        for line in skipped:
            print("  " + line)
        if not ok:
            print(output, flush=True)
    print("[汇总] %d/%d passed（其中 SKIP %d），失败套件 %d" %
          (passed, total, skips, failed))
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
