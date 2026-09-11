#!/usr/bin/env python3
"""生成 16 种类型矩阵 + 复杂混合字体

v2 (真路径版): C/D 组直接传原始 VF, 保留可变性输出 + Axis 并集。

字体说明:
- OFL 公开字体 (LibreCaslonText / LXGW WenKai TC / Source Serif / Source Han / Zed Text)
  直接按文件名定位 (目录位于仓库外, 本地需自备)。
- 商业授权字体 (CJK 静态/可变等) 路径通过 tests/local_fonts.py 配置 (该文件不入库);
  任一字体缺失时本脚本整体跳过并打印缺失项。
"""
import os, sys, copy, time
_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_script_dir)
_project_dir = os.path.dirname(_repo_dir)
_test_dir = os.path.join(_project_dir, "test")
_output_dir = os.path.join(_test_dir, "samples", "matrix")
sys.path.insert(0, _project_dir)
sys.path.insert(0, _repo_dir)   # 使 tests.local_fonts 在"直接运行脚本"模式下也可导入

from FontMerger import *
from fontTools.ttLib import TTFont

#: 公开 OFL 字体: 角色 -> 相对 _test_dir 的路径 (可给多个候选名)
OPEN_FONTS = {
    "sOTF_latin":  "OpenType/LibreCaslonText-Regular.otf",
    "sTTF_latin":  "TrueType/LXGWWenKaiTC-Regular.ttf",
    "vOTF_serif":  "otf_variable_fonts/SourceSerif4Variable-Roman.otf",
    "vOTF_cjk_jp": "otf_variable_fonts/SourceHanSansJP-VF.otf",
    "vTTF_cjk":    ("ttf_variable_fonts/ZedTextSCVF.ttf",
                    "ttf_variable_fonts/ZedTextJapaneseVF.ttf"),
}

#: 本地授权字体角色 (真实路径见 tests/local_fonts.py, 未配置时 None)
LOCAL_ROLES = {
    "sOTF_cjk": "cjk_static_otf",
    "sTTF_cjk": "cjk_static_ttf",
    "vTTF_helv": "vf_ttf_helvetica",
}


def L(rel):
    """打开相对 _test_dir 的字体 (rel 可为候选名列表)；不存在返回 None"""
    for r in (rel if isinstance(rel, (list, tuple)) else [rel]):
        p = os.path.join(_test_dir, r)
        if os.path.exists(p):
            return TTFont(p)
    return None


def LC(role):
    """本地授权字体（tests/local_fonts.py 配置）；未配置/不存在返回 None"""
    try:
        from tests.local_fonts import LOCAL_FONTS
        rel = LOCAL_FONTS.get(role)
    except ImportError:
        rel = None
    if not rel:
        return None
    return L(rel)


P = {}
for _role, _rel in OPEN_FONTS.items():
    P[_role] = L(_rel)
for _role, _lrole in LOCAL_ROLES.items():
    P[_role] = LC(_lrole)

_missing = [k for k, v in P.items() if v is None]
if _missing:
    print("缺少测试字体, 跳过矩阵生成:", ", ".join(_missing))
    print("  - OFL 字体请放入 test/ 对应目录 (见 README 'Tests')")
    print("  - 商业授权字体请配置 tests/local_fonts.py (见 local_fonts.example.py)")
    sys.exit(0)

ots = []
def mg(label, m, b, extra="", mem=None):
    merger = FontMerger()
    merger.mem = {"sOTF_sTTF": "OTF", "sTTF_sOTF": "TTF"}
    if mem:
        merger.mem.update(mem)
    # 深拷贝输入, 避免 axis_union/variable_to_static 就地修改污染 P 字典
    m = copy.deepcopy(m)
    b = copy.deepcopy(b)
    try:
        r = merger.merge_two(m, b)
    except Exception as e:
        print(f'  {label}: MERGE FAIL - {e}')
        return None
    # 主字体原始可变性 (记录合并前 var 状态)
    was_variable = is_variable(m)
    cr = get_copyrights(m, b)
    r = apply_naming(r, get_family(m), cr)
    ext = ".otf" if is_cff(r) else ".ttf"
    fp = os.path.join(_output_dir, f'{label}{extra}{ext}')
    try:
        from FontMerger.utils.save import save_font
        save_font(r, fp)
    except Exception as e:
        print(f'  {label}: SAVE FAIL - {e}')
        return None
    n = len(r.getGlyphOrder()); kb = os.path.getsize(fp)/1024; a = n - len(m.getGlyphOrder())
    var_flag = "VAR" if is_variable(r) else "sta"
    upm_m = m["head"].unitsPerEm; upm_b = b["head"].unitsPerEm
    axes = ""
    if is_variable(r):
        axes = "[" + ",".join(f"{ax.axisTag}:{ax.minValue:.0f}-{ax.maxValue:.0f}"
                              for ax in r["fvar"].axes) + "]"
    print(f'  {label:40s} {type_label(r):6s} {var_flag:3s} {n:>6d}g (+{a:>5d}) {kb:>7.0f}KB  UPM:{upm_m}/{upm_b} {axes}')
    ots.append((label, n, kb, a, is_variable(r)))
    return r

t0 = time.time()
print("=" * 75)
print("  Final Font Merge Matrix v2 (真路径, 保留可变性)")
print("=" * 75)

# === A: Static+Static ===
print('\n-- A: Static + Static --')
mg("A1_sOTF_sOTF", P["sOTF_latin"], P["sOTF_cjk"], "_latin_x_cjk")
mg("A2_sOTF_sTTF", P["sOTF_latin"], P["sTTF_cjk"], "_latin_x_cjk")
mg("A3_sTTF_sOTF", P["sTTF_latin"], P["sOTF_cjk"], "_latin_x_cjk")
mg("A4_sTTF_sTTF", P["sTTF_latin"], P["sTTF_cjk"], "_latin_x_cjk")

# === B: Static + Variable (merger 内部实例化打底 → 静态输出, 保语义) ===
print('\n-- B: Static + Variable (打底自动实例化) --')
mg("B1_sOTF_vOTF_Serif", P["sOTF_latin"], P["vOTF_serif"], "_serif_x_vf")
mg("B2_sOTF_vTTF_Helv",  P["sOTF_latin"], P["vTTF_helv"],  "_helv_x_vf")
mg("B3_sTTF_vOTF_Serif", P["sTTF_latin"], P["vOTF_serif"], "_serif_x_vf")
mg("B4_sTTF_vTTF_Helv",  P["sTTF_latin"], P["vTTF_helv"],  "_helv_x_vf")

# === C: Variable + Static (保留可变性) ===
print('\n-- C: Variable + Static (真路径, 输出可变) --')
# C1 (JP CID CFF2 主): 静态路径 (CID 空间合并稳定, v1 已验证)
mg("C1_vOTF_JP_sOTF", variable_to_static(P["vOTF_cjk_jp"]), P["sOTF_latin"], "_jp_x_latin")
mg("C2_vOTF_Serif_sTTF", P["vOTF_serif"], P["sTTF_latin"], "_serif_x_latin", mem={"vOTF_sTTF": "可变", "vOTF_sTTF2": "OTF"})
mg("C3_vTTF_Helv_sOTF", P["vTTF_helv"],  P["sOTF_latin"], "_helv_x_latin", mem={"vTTF_sOTF": "可变"})
mg("C4_vTTF_Helv_sTTF", P["vTTF_helv"],  P["sTTF_latin"], "_helv_x_latin", mem={"vTTF_sTTF": "可变"})

# === D: Variable+Variable (保留可变性 + Axis 并集) ===
print('\n-- D: Variable + Variable (真路径, 输出可变 + Axis 并集) --')
# D1 (JP CID CFF2 主): 静态路径
mg("D1_vOTF_JP_vOTF_Serif", variable_to_static(P["vOTF_cjk_jp"]), variable_to_static(P["vOTF_serif"]), "_jp_x_serif")
mg("D2_vOTF_Serif_vTTF_Helv", P["vOTF_serif"], P["vTTF_helv"], "_serif_x_helv", mem={"vOTF_vTTF": "OTF"})
mg("D3_vTTF_Helv_vOTF_Serif", P["vTTF_helv"], P["vOTF_serif"], "_helv_x_serif", mem={"vTTF_vOTF": "TTF"})
mg("D4_vTTF_Helv_vTTF_Helv", P["vTTF_helv"], P["vTTF_helv"], "_helv_x_helv")

elapsed = time.time() - t0
print(); print("=" * 75)
print(f"Done in {elapsed:.0f}s | {len(ots)} files")
total = sum(o[3] for o in ots)
nvar = sum(1 for o in ots if o[4])
for l, n, kb, a, v in ots:
    print(f'  {l:45s} {n:>6d}g (+{a:>5d}) {kb:>7.0f}KB {"VAR" if v else "static"}')
print(f'  Total added glyphs: {total} | 可变输出: {nvar}/16')
print("=" * 75)
