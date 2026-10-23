# AGENTS.md — 给自动化 Agent 的入口

本仓库（font-matrix-merger，Python 字体合并库）使用**多 Agent 协作**。开始任何工作前，先读：

1. **[docs/AGENTS.md](docs/AGENTS.md)** — 角色、任务板、写作用域、验证门、汇报契约、红线（**必读**）
2. **[docs/HANDOVER.md](docs/HANDOVER.md)** — 现状、环境、测试、发布、已知问题、地雷
3. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — 分层、主流程、关键不变量、模块地图
4. **[docs/CONVENTIONS.md](docs/CONVENTIONS.md)** — 代码/测试/Git/文档规范

文档总索引：[docs/README.md](docs/README.md)

---

## 硬规则（违反即回滚）

- **只有 Lead 执行 git 写操作**：`add/commit/push/tag/rebase/reset/checkout` 等；Writer 只改自己任务声明的作用域。
- **仓库不放字体**：测试字体在仓库外 `../test/`；授权字体经不入库的 `tests/local_fonts.py` 角色引用（模板 `tests/local_fonts.example.py`）。不要读取或复制其内容。
- **不出现商业授权字体名**：文档/注释/示例用中性占位（`Main-Serif.otf`、`Base-VF.otf` 之类）。
- **不改写已发布内容**：已发布 tag、Release 资产、CHANGELOG 已发布条目；新变更写进 `[Unreleased]`（双语）。
- **只依赖 fontTools**（无 pytest / uharfbuzz / pathops）；测试是 `def test_*` + `main()` 运行器。
- **不静默失败**：异常要打印 `[标签]` 告警并降级；不许裸 `except: pass`。
- **不放宽验证**：不改松断言、不删用例、不给 verify 加 try/except 来让套件变绿。

## 提交前必跑（四套，期望 21 / 13 / 8 / 4）

```bash
cd Typography/FontMerger
python3 tests/test_axis_mapping.py     # 13
python3 tests/test_merger.py           # 21
python3 tests/test_subset_merge.py     # 8
python3 tests/test_cff2_compose.py     # 4
```

缺字体时用例会打印 `SKIP (测试字体未就位)` —— 合法，但必须在汇报中列出。

## 发布（仅 Lead）

```bash
# 1) 版本号：__init__.py 的 __version__ + 两个 README 徽章
# 2) CHANGELOG.md 的 [Unreleased] 按双语约定补条目
python3 build/make_release_zip.py      # → dist/font-matrix-merger-v<版本>.zip（仅源码）
# 3) annotated tag + GitHub Release（资产名与 tag 对应；校验 sha256）
```

详见 [docs/HANDOVER.md](docs/HANDOVER.md) 的「发布流程」。
