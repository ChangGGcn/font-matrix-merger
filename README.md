# font-matrix-merger

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![FontTools](https://img.shields.io/badge/fontTools-%E2%89%A54.49-important.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)]()

**English** | [简体中文](README.zh-CN.md)

font-matrix-merger is a Python font-merging library built on [FontTools](https://github.com/fonttools/fonttools). Its CID handling draws on ideas from [AFDKO](https://github.com/adobe-type-tools/afdko), which is not a dependency. The library uses the [MIT License](LICENSE). See [CHANGELOG.md](CHANGELOG.md) for release history.

Full usage, parameters and implementation notes are in the [technical documentation](doc/README.md).

## Key features

- **16 merge combinations**: main and base fonts are classified by static/variable data and glyf/CFF outlines, including CFF2. Inputs can be TTF, OTF or WOFF/WOFF2.
- **Multi-level fallback**: two or more fonts fill codepoints in priority order.
- **Scale and baseline offset**: transforms preserve coordinates and variation topology while updating metrics and vertical origins. Non-identity transforms explicitly remove unsafe hinting and pixel caches.
- **CID fonts**: dual-CID merging uses CID offsets and materialized CharStrings. CID/name-keyed conversion handles mixed inputs.
- **Variable fonts**: variable output retains the main font's variability. Shared axes keep the main range by default; base-only axes are added. A shared-range union is configurable.
- **Cross-design-space composition**: supported base variation data is reparameterized into the merged space and checked on a grid. Failures warn and fall back; supported cases are defined in the technical documentation.
- **OpenType features**: GSUB/GPOS/GDEF are pruned to retained glyphs, then merged with lookup and glyph-name remapping. Conflicts favor the main font.
- **Same-source subset union**: unicode-range slices of one variable font can be reunited while retaining their supported variation and layout data.
- **Merge verification**: source and merged outlines and metrics are compared at sampled axis positions, alongside codepoint, feature, layout and container checks.
- **Save guard**: `save_font()` clears the output flavor and checks sfnt magic, preventing WOFF2 data from being saved as a desktop font merely named `.ttf`.

## Directory structure

```text
FontMerger/
├── FontMerging.py           # interactive CLI
├── __init__.py              # public API exports
├── CHANGELOG.md             # release history
├── core/                    # orchestration, glyph injection, conflicts and naming
├── format/                  # conversion, axes, transforms, subsets and webfonts
├── tables/                  # table registry and OpenType layout merging
├── doc/                     # public bilingual technical documentation
├── tests/                   # matrix generators and tests
└── build/                   # PyInstaller and source ZIP tooling
```

## Quick start

### Installation

Requirements: **Python ≥ 3.8**, **FontTools ≥ 4.49**.

```bash
git clone https://github.com/ChangGGcn/font-matrix-merger.git FontMerger
cd FontMerger
pip install "fonttools>=4.49"
```

### Interactive CLI

```bash
python FontMerging.py
```

Enter the main font, its scale percentage and baseline offset, then each base level. Enter `Y` to finish. Warnings are informational; an incompatible pair requires `y`/`N` confirmation. The default output name is `<main font>_mod.{otf|ttf}`.

### Library API

```python
from FontMerger import merge_fonts, save_font

result = merge_fonts("Main.otf", ["Base-One.otf", "Base-Two.ttf"])
save_font(result, "Merged.otf")

# Explicitly choose static output; answers override non-interactive defaults.
result = merge_fonts(
    "Main-VF.otf", ["Base.otf"], answers={"vOTF_sOTF": "静态"}
)
```

`merge_fonts()` returns a font without writing it. See the [merging API](doc/en/merge-api.md) for level-by-level control, ownership and every parameter. When using the source tree, put the parent of `FontMerger` on Python's search path.

### Same-source subsets (`merge_subsets`)

For N webfont slices of one variable font, the union path avoids instancing and axis union. It retains the slices' supported glyph, variation and lookup data.

```python
from glob import glob
from FontMerger import merge_subsets, verify_merge

paths = sorted(glob("webfont/ja-v2/*.woff2"))
merged = merge_subsets(
    paths, out_path="Merged-JP.ttf", tag="ja",
    complete_name_table=True, fix_head_flags=True
)
report = verify_merge(
    paths, merged, glyph_map=merged.subset_merger.glyph_map()
)
assert report["ok"], report["failures"]
gmap = merged.subset_merger.glyph_map()
```

Or enable the built-in check:

```python
merged = merge_subsets(paths, out_path="Merged.ttf", tag="ja", verify=True)
```

See [subsets and verification](doc/en/subsets-and-verification.md) for full examples and parameters. The runtime ZIP includes `doc/`, but not the repository-only `tests/` and `build/` directories.

## Known limitations

1. **CID CFF2 as the main font**: the merge can complete, but saving may leave incomplete format-4 cmap references for base Latin glyphs. The matrix generator uses a static-instanced fallback. True variable output remains a separate CID/CFF2 namespace problem.
2. **Cross-design-space variation** has four boundaries:
   - (a) Main and base variation data must use the same supported outline technology.
   - (b) A user interval collapsed by the main avar cannot be recovered pointwise in that normalized space. The code warns and preserves the main behavior.
   - (c) Layout VariationIndex deltas are integers. Reparameterization and rounding can leave kerning or anchor differences of approximately 1 font unit.
   - (d) Main VarStores are reparameterized only when the axis space changes. A constant region carries the default-point contribution.
3. **OpenType layout**: referenced glyphs must exist in the merged font. Same-tag features are combined within a Script/LangSys, not across scripts.
4. **VORG**: default-position instancing has defined values; other axis positions require additional handling.
5. **Repeated levels** can add redundant lookups when previously merged features are encountered again.
6. **Packaging**: the repository root is the Python package. Pip installation from a clone is not implemented.
7. **CFF2 subset union** requires compatible VarStore and GlobalSubrs structures. FDArray differences are handled by FD-level union.
8. **Automatic glyph names** receive aliases across slices. This can duplicate a no-codepoint glyph, trading file size for source identity.

The [limitations guide](doc/en/limitations.md) separates unsupported cases, intentional fallbacks and verification coverage.

## License

[MIT License](LICENSE)

Copyright (c) 2026 cHAnGe
