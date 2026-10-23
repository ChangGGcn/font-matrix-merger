# 使用指南

本页给出安装、命令行、库调用与同源分片合并的可运行示例。参数默认值以源码为准。完整参数见[完整源码签名索引](parameter-index.md)，合并策略见[合并 API](merge-api.md)，同源分片与验证细节见[同源分片与验证](subsets-and-verification.md)，支持边界见[支持边界](limitations.md)。

## 1. 环境与目录

### 1.1 运行依赖

| 依赖 | 要求 | 说明 |
| --- | --- | --- |
| Python | ≥ 3.8 | 语法基线。 |
| fontTools | ≥ 4.49 | 唯一必需的第三方依赖。 |
| brotli | 可选 | 读写 WOFF2 时需要；WOFF 与 TTF/OTF 不需要。 |
| AFDKO | 不需要 | 运行库不 import AFDKO，PyInstaller spec 也不收集。 |
| pytest、uharfbuzz、pathops | 不需要 | 测试是普通脚本；验证不依赖这些库。 |

安装：

```bash
pip install "fonttools>=4.49"
# 需要 WOFF/WOFF2 时
pip install brotli
```

### 1.2 源码仓库

克隆时把目标目录指定为 `FontMerger`：

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git FontMerger
cd FontMerger
python3 FontMerging.py
```

包名来自目录名。`FontMerging.py` 会把父目录加入 `sys.path`，再执行 `from FontMerger import ...`。目录名不是 `FontMerger` 时（例如保留了默认 clone 名），这个导入会失败。请把目录重命名为 `FontMerger`，或创建一个指向该目录的 `FontMerger` 入口。在 CLI 之外导入库时，还要把该父目录加入导入路径。

库调用需要父目录在导入路径中：

```bash
cd ..
python3 -c "import FontMerger; print(FontMerger.__version__)"
```

### 1.3 运行 ZIP

发布 ZIP 的根目录是 `FontMerger/`。解压后：

```bash
python3 FontMerger/FontMerging.py
```

库导入：

```bash
cd <解压目录>
python3 -c "import FontMerger; print(FontMerger.__version__)"
```

运行 ZIP 含运行库、CLI 与公开文档。`tests/` 与 `build/` 只在源码仓库提供，见[模块与脚本参考](script-reference.md)。

## 2. 交互式 CLI

```bash
python3 FontMerging.py
```

CLI 不读取命令行位置参数，全部输入来自终端提问。需要脚本化调用时使用 `merge_fonts()` 或 `FontMerger.merge_two()`，见第 3 节与[合并 API](merge-api.md)。

### 2.1 输入顺序

| 顺序 | 提问 | 默认 | 单位 | 作用 |
| --- | --- | --- | --- | --- |
| 1 | 主字体路径 | 无 | 路径 | 主字体；其字形与映射优先保留。 |
| 2 | 缩放倍率(%) | 100 | 百分比 | 对主字体轮廓与度量做 `(x*s, y*s)`。 |
| 3 | 基线偏移 | 0 | 字体设计单位（FU） | 缩放后沿 y 平移，向上为正。 |
| 4+ | 第 n 级打底字体路径 | 无 | 路径 | 每级一次；输入 `Y` 结束。 |
| 5 | 每级打底的缩放倍率、基线偏移 | 100、0 | 同上 | 与主字体分开设置。 |
| 末 | 输出路径 | `<主字体目录>/<主字体名>_mod.otf` 或 `.ttf` | 路径 | 可直接回车；扩展名决定容器。 |

- 路径首尾的单引号或双引号会被去掉，带空格的路径可以粘贴后加引号。
- 主字体一个，打底字体一个或多个；打底按输入顺序逐级合并。
- 输入 `Y`（不区分大小写）结束打底列表。

### 2.2 缩放与基线偏移

- `100` 表示不缩放，`110` 表示 1.1 倍。非有限正数会抛出 `ValueError`。
- 基线偏移以字体设计单位解释，先缩放再平移：`y' = s*y + offset`。正 offset 向上移动。
- 主字体与每一级打底分别应用这两个参数。变换在内存中的 `TTFont` 上就地生效，不会改写输入文件。
- 非恒等变换会移除不安全的 hinting 与像素缓存（cvt、cvar、fpgm、prep、gasp、hdmx、LTSH、VDMX、DSIG），并逐项打印告警。UPM 保持不变。
- 含 VARC 的字体暂不支持基线变换，变换会抛出 `ValueError`。

### 2.3 兼容性警告与提问

加载完成后，CLI 按输入顺序检查相邻字体，打印 `[警告]` 项：

| 情况 | 输出 | 是否要求确认 |
| --- | --- | --- |
| 混合轮廓格式（CFF 与 glyf） | 将自动转换打底字体 | 否 |
| 打底为可变字体 | 将先实例化为静态再合并；同源分片建议改用 `merge_subsets()` | 否 |
| 主字体为可变字体 | 默认保留主字体可变性，打底字形按默认实例并入 | 否 |
| UPM 不一致 | 将自动缩放打底字体 | 否 |
| 双 CID 字符集高度重叠 | 合并后新增字形可能为 0 | 是，输入 `y` 或 `N` |

导出格式问题（TTF/OTF）只记录答案，不改变输出轮廓格式。输出格式由主字体决定，打底轮廓会转换到主格式。只有“可变/静态”这一问会改变代码路径。所有回答记在 `FontMerger.mem` 中，后续级别复用。

### 2.4 输出

- 默认文件名为 `<主字体目录>/<主字体名>_mod.otf` 或 `.ttf`，扩展名由合并结果的轮廓类型决定：CFF 结果用 `.otf`，glyf 结果用 `.ttf`。
- 最后一步提示输出路径，直接回车使用默认值。
- 输出路径以 `.woff` 或 `.woff2` 结尾时，CLI 通过 `default_flavor_for()` 选择 web 容器。输出 WOFF2 需要 brotli。
- 保存失败时打印异常并以退出码 1 结束；正常完成返回 0。

## 3. 非交互调用：merge_fonts

### 3.1 完整调用

```python
from FontMerger import merge_fonts, save_font

# 静态输入：不会产生交互询问。
merged = merge_fonts("Main.otf", ["Base-One.otf", "Base-Two.ttf"])
save_font(merged, "Merged.otf")

# 可变主字体：强制输出静态字体，而不是保留 VF。
merged = merge_fonts(
    "Main-VF.otf", ["Base.otf"],
    answers={"vOTF_sOTF": "静态"},
)
save_font(merged, "Merged-Static.otf")
```

`merge_fonts()` 返回新的 `TTFont`，不写文件。保存请走 `save_font()`，它会清除 `flavor` 并校验桌面容器魔数。

### 3.2 参数

| 参数 | 类型 | 默认 | 含义 | 输入所有权 |
| --- | --- | --- | --- | --- |
| `main_font` | 路径或 `TTFont` | 必填 | 主字体。 | 路径先加载；传入对象时内部会深拷贝后再合并。 |
| `base_fonts` | 序列 | 必填 | 一个或多个打底字体，按顺序逐级合并。 | 路径先加载；传入对象时内部可能转换或实例化。 |
| `interactive` | `bool` | `False` | `False` 时用 `DEFAULT_ANSWERS` 预填所有询问；`True` 时缺失的询问会走 `input()`。 | 无。 |
| `answers` | `dict` 或 `None` | `None` | 覆盖 `DEFAULT_ANSWERS` 的键值；键是内部询问 key。 | 不修改传入 dict。 |

常见答案：

- `{"vOTF_sOTF": "静态"}`：可变主字体先实例化再合并。
- `{"vOTF_sOTF": "可变"}`：保留主字体可变性，这是默认行为。
- `{"sOTF_sTTF": "OTF"}`：静态 OTF 主字体与静态 TTF 打底时的导出格式询问，只记录。

默认值：`DEFAULT_ANSWERS` 对“可变主字体 + 静态打底”选择 `"可变"`。完整键与默认值表见[完整源码签名索引](parameter-index.md)。

### 3.3 返回值与副作用

- 返回 `TTFont`，已经过 `apply_naming()` 命名，`flavor` 已清空，可直接交给 `save_font()`。
- 不写文件；`interactive=False` 时不弹出询问。
- 输入文件不会被修改。传入的 `TTFont` 对象在内部可能被转换或实例化；需要继续使用原对象时先 `copy.deepcopy`。
- 命名使用 `get_family(main_font)` 与 `get_copyrights(main_font, *bases)`，见第 6 节。

## 4. 可变字体组合

`merge_two()` 按“静态/可变 × OTF/TTF”分为 16 种情况。行是主字体，列是打底字体。

| | 静态 OTF 打底 | 静态 TTF 打底 | 可变 OTF 打底 | 可变 TTF 打底 |
| --- | --- | --- | --- | --- |
| **静态 OTF 为主** | 合并 CFF 字形 | 打底转 CFF 后合并 | 打底按默认实例化后合并 | 打底实例化、转 CFF 后合并 |
| **静态 TTF 为主** | 打底转 glyf 后合并 | 合并 glyf 字形 | 打底实例化、转 glyf 后合并 | 打底按默认实例化后合并 |
| **可变 OTF 为主** | 询问可变/静态；保留主 VF 或实例化主字体 | 同左，并将打底转 CFF | 尝试 CFF2 合成；自检失败则回退 | 跨轮廓合成不支持；打底实例化或转换，保留主 VF |
| **可变 TTF 为主** | 询问可变/静态，并将打底转 glyf | 询问可变/静态；保留主 VF 或实例化主字体 | 跨轮廓合成不支持；打底实例化或转换，保留主 VF | 尝试 gvar/HVAR 合成；自检失败则回退 |

规则：

- 静态主字体加可变打底：打底先用 `variable_to_static()` 实例化到默认轴位置，再走静态流程。
- 可变主字体加静态打底：选择“可变”时保留主 VF，打底字形并入主字体默认 master；选择“静态”时先实例化主字体。
- 可变主字体加可变打底：先尝试跨设计空间合成。合成要求两边的可变数据位于同一轮廓技术内：glyf 组合要求两边都有 gvar，CFF2 组合要求两边都有带 VarStore 的 CFF2。不满足条件或网格自检失败时，打印 `[合成] 回退到默认实例合并`，改走轴并集与打底默认实例路径。
- CFF2 打底只并入 HVAR。VVAR 与 Private hint 变化不搬。布局变化数据会搬入，但整数取整会留下约 1 单位以内的偏差（实测 0.70 单位，UPM 1000）。
- glyf 与 CFF2 混搭、打底自己的 FeatureVariations、JP CID CFF2 作主字体、pip 安装等边界，见[支持边界](limitations.md)。
- 策略参数（`compose_variations`、`compose_range`、`compose_fit`、`avar_mode`、`verify_compose`、`compose_layout`）的默认值见[完整源码签名索引](parameter-index.md)，原理见[轴映射与可变数据合成](variation-model.md)。

示例：

```python
from FontMerger import FontMerger, load_font, save_font

merger = FontMerger(compose_variations=True, compose_range="main+extra", avar_mode=0)
merged = merger.merge_two(load_font("Main-VF.ttf"), load_font("Base-VF.ttf"))
save_font(merged, "Merged-VF.ttf")
```

`merge_two()` 不自动命名，也不落盘。需要 CLI 同等命名时，再调用 `apply_naming()`，见第 6 节。

## 5. 同源 webfont 分片并集

### 5.1 完整调用

```python
from glob import glob
from FontMerger import merge_subsets, verify_merge, save_font

paths = sorted(glob("webfont/ja-v2/*.woff2"))
merged = merge_subsets(paths, tag="ja")

report = verify_merge(
    paths, merged,
    glyph_map=merged.subset_merger.glyph_map(),
    axis_positions="grid",
)
if not report["ok"]:
    raise SystemExit("verify_merge failed: %s" % report["failures"][:3])

save_font(merged, "Merged-JP.ttf")
# save_font(merged, "Merged-JP.woff2", flavor="woff2")  # 需要 brotli
```

一次调用完成内置验证：

```python
merged = merge_subsets(paths, out_path="Merged.ttf", tag="ja", verify=True)
```

`verify_merge()` 在默认轴位置与首轴两端逐字形比对轮廓与度量，并检查码位并集、特性、布局索引与容器元数据。轴位置可用 `axis_positions="grid"` 扩大，`sample` 可限制每个分片比对的字形数。它不替代 HarfBuzz、FreeType 或 Windows 栅格测试。

### 5.2 参数

| 参数 | 类型 | 默认 | 含义 | 所有权与副作用 |
| --- | --- | --- | --- | --- |
| `subsets` | 序列，路径或 `TTFont` | 必填 | 分片列表，顺序即合并顺序；`subsets[0]` 是基底。 | 基底就地修改，并作为结果继续追加字形。 |
| `out_path` | 路径或 `None` | `None` | 输出路径；`None` 时只返回字体。 | 写入文件；扩展名决定缺省容器。 |
| `tag` | `str` | `"s"` | 别名前缀，例如 `ja007.glyph00123`。 | 无。 |
| `output_flavor` | `None`、`"woff"` 或 `"woff2"` | `None` | 输出容器；`out_path` 非空时生效，`None` 时按 `out_path` 扩展名推断。 | `out_path` 非空时设置返回字体的 `flavor`。 |
| `complete_name_table` | `bool` | `True` | 补 nameID 16/17/25 与实例 PostScript 名。 | 修改返回字体。 |
| `fix_head_flags` | `bool` | `True` | 清 `head.flags` 的 WOFF2 残留位。 | 修改返回字体。 |
| `verify` | `bool` | `False` | 合并后运行 `verify_merge()`，失败抛 `AssertionError`。 | 无文件副作用。 |
| `verbose` | `bool` | `True` | 只控制 `SameSourceSubsetMerger.log()` 的输出。`False` 不控制底层函数与 `verify_merge()` 的日志输出，见下方说明。 | 无。 |
| `verify_kwargs` | `dict` | 无 | 透传 `verify_merge()`，例如 `axis_positions`、`sample`。 | 无。 |

`merge_subsets(verify=True)` 调用 `verify_merge()` 时不会转发 `verbose`，验证日志仍按 `verify_merge()` 自己的默认值输出。要控制这些日志，请单独调用 `verify_merge()` 并传它的 `verbose`。不要把 `verbose` 放进 `verify_kwargs`：它已经是 `merge_subsets()` 的形参，显式传 `verbose=` 同时又经 dict 传入同名键会抛 `TypeError`。

### 5.3 约束

- 输入应来自同一个可变字体：传入多个分片时，全部可变、轴空间一致、轮廓格式一致，判定函数是 `is_same_source()`。异源输入抛出 `ValueError`，应改用 `merge_two()`。
- CFF2 分片必须共享同一 VarStore 与 GlobalSubrs 结构。结构被重构过的分片会明确报错，不会写出坏字体。FDArray 差异由 FD 级并集处理。CFF 与 CFF2 混合分片不支持。
- `merge_subsets()` 不做实例化，不做轴并集。它保留各分片的 `gvar` 或 CFF2 blend、HVAR/VVAR、布局 lookup 与 GDEF 变化数据；保留项与边界见[同源分片与验证](subsets-and-verification.md)。
- 结果是可变字体。`glyph_map()` 返回 `{分片标签: {源字形名: 合并后 GID}}`，键与输入顺序对应。

## 6. 命名、版权与输入所有权

CLI 与 `merge_fonts()` 会自动命名，`merge_two()` 不会。手写流程时：

```python
from FontMerger import (FontMerger, apply_naming, get_family,
                        get_copyrights, load_font, save_font)

main = load_font("Main.ttf")
base = load_font("Base.ttf")
merged = FontMerger().merge_two(main, base)
merged = apply_naming(merged, get_family(main), get_copyrights(main, base))
save_font(merged, "Merged.ttf")
```

`apply_naming()` 的行为：

- 各语言的族名改成 `<原族名> mod`。更新 nameID 1/3/4/6/16/17，nameID 2 只在缺失时补齐。重复调用不会叠加第二个 ` mod`。
- 版权按语言合并，段落之间用空行分隔。只有打底存在的语言也会保留，不生成英文翻译。
- PostScript 名由 Unicode 名清洗后加哈希摘要生成，避免清洗或截断造成重名。
- 版本、厂商、商标、授权与 fvar/STAT 名称不改。
- 原地修改并返回传入的字体对象。

输入所有权：

- `merge_fonts()` 对主字体先做 `copy.deepcopy`，返回新字体，不写输入文件。
- `merge_two()` 在合成路径会深拷贝主字体；回退或旧轴并集路径可能就地扩展主字体。需要保留原对象时先复制。
- `merge_subsets()` 会就地修改 `subsets[0]`。
- `apply_naming()` 与 `save_font()` 都会修改传入的字体对象。

## 7. 输出容器

```python
from FontMerger import save_font

save_font(font, "Merged.ttf")                    # 桌面 sfnt
save_font(font, "Merged.woff2", flavor="woff2")  # web 容器，需要 brotli
```

| 调用 | 输出 | 说明 |
| --- | --- | --- |
| `save_font(font, path)` | sfnt（TTF/OTF） | 保存后读前 4 字节并断言 sfnt 魔数。 |
| `save_font(font, path, flavor="woff")` | WOFF | 设置 `font.flavor` 后保存。 |
| `save_font(font, path, flavor="woff2")` | WOFF2 | 需要 brotli；缺失时 fontTools 抛导入错误。 |
| `default_flavor_for(path)` | 按扩展名推断 | `.woff2` 返回 `woff2`，`.woff` 返回 `woff`，其余返回 `None`。 |
| `merge_subsets(..., output_flavor=...)` | 同上 | `None` 时按 `out_path` 推断。 |

不要直接调用 `font.save()` 处理从 WOFF/WOFF2 载入的字体。`TTFont.flavor` 会保留原容器，可能写出扩展名为 `.ttf`、魔数为 `wOF2` 的文件。所有落盘点统一走 `save_font()`。

## 8. 路径、格式与常见错误

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'FontMerger'` | 仓库目录名不是 `FontMerger`，或父目录不在 `sys.path`。 | 按 1.2 重命名目录或设置 `PYTHONPATH`。 |
| CLI 提示“请先将字体集解包 (TTC/OTC)” | 输入是字体集合。 | 先拆成单个 TTF/OTF。 |
| CLI 提示“不支持该格式” | 扩展名不在 `.ttf`、`.otf`、`.woff`、`.woff2` 内。 | 转换格式后再输入。 |
| WOFF2 保存报缺失模块 | 未安装 brotli。 | 安装 brotli，或输出 TTF/OTF。 |
| 输出文件在 Windows 无法安装 | 直接 `font.save()` 保留了 WOFF2 flavor。 | 改用 `save_font()`。 |
| 合并后打底字形不随轴变化 | 走了默认实例化或回退路径。 | 查看日志中的 `[合成]` 行；边界见[支持边界](limitations.md)。 |

更多边界与排错见[支持边界](limitations.md)，脚本与测试入口见[模块与脚本参考](script-reference.md)。

## 9. 继续阅读

文档索引：[../README.zh-CN.md](../README.zh-CN.md)。相关页面：[合并 API](merge-api.md)、[辅助 API](helper-api.md)、[同源分片与验证](subsets-and-verification.md)、[轴映射与可变数据合成](variation-model.md)、[合并流程与数据不变量](architecture.md)、[支持边界](limitations.md)、[完整源码签名索引](parameter-index.md)。仓库 README：[../../README.zh-CN.md](../../README.zh-CN.md)、[../../README.md](../../README.md)。
