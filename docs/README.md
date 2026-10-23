# 文档索引（docs/）

本目录是 font-matrix-merger 的**工程文档**（面向接手的工程师与 Agent）。对外介绍见 [README](../README.md) / [README.zh-CN](../README.zh-CN.md)，版本历史见 [CHANGELOG](../CHANGELOG.md)。

---

## 1. 文档地图

| 文档 | 读者 | 什么时候读 | 主要内容 |
| --- | --- | --- | --- |
| [HANDOVER.md](HANDOVER.md) | 新接手的人/Agent | **第一天** | 现状与能力边界、环境与测试字体准备、跑测试、发布流程、已完成/未完成、地雷与调试口诀、下一步建议 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 要改代码的人/Agent | 动手前 | 分层与依赖、合并主流程、关键不变量（OT/可变字体事实）、模块地图、合成子系统、布局合并、测试架构、性能、扩展点与架构债 |
| [CONVENTIONS.md](CONVENTIONS.md) | 所有贡献者 | 动手前 | 语言与文档风格、分层规则、代码风格、字体数据铁律、测试规范、Git 规范、评审清单、变更分级 |
| [AGENTS.md](AGENTS.md) | 多 Agent 团队 | 组队时 | 角色定义、任务板工作流、写作用域与并发、验证门、汇报契约、红线与冲突处理 |
| [../README.md](../README.md) / [../README.zh-CN.md](../README.zh-CN.md) | 使用者 | 了解功能 | 安装/用法/参数/已知限制（英文 + 中文两版） |
| [../CHANGELOG.md](../CHANGELOG.md) | 所有人 | 看变更 | 单文件双语变更日志（每条目先 `### English` 后 `### 简体中文`） |

---

## 2. 推荐阅读顺序

- **第一次接触（人或 Agent）**：HANDOVER → 跑一遍四套测试 → ARCHITECTURE 的「合并主流程 + 关键不变量」→ CONVENTIONS。
- **只想改一个小功能**：CONVENTIONS（分层 + 测试规范）→ ARCHITECTURE 对应子系统小节 → 动手。
- **组队并行**：AGENTS → 按写作用域拆任务 → 各自读 ARCHITECTURE/CONVENTIONS 的相关小节。
- **发版**：HANDOVER 的「发布流程」→ 四套测试全绿 → `build/make_release_zip.py` → tag + Release。

---

## 3. 文档维护规则

| 触发 | 必须更新 |
| --- | --- |
| 改了分层/主流程/关键不变量 | ARCHITECTURE 对应小节 |
| 改了编码/测试/Git/文档规范 | CONVENTIONS |
| 每次发布（版本号、发布流程变化） | HANDOVER 的「现状」「已完成」「已知问题」+ CHANGELOG |
| 多 Agent 协作方式变化（角色/任务板/验证门） | AGENTS |
| 新增/删除工程文档 | 本索引 |

约定：

- 工程文档统一**中文**；对外 README / CHANGELOG 才是双语。
- 文档中的结论要能**定位到代码**（文件 + 函数），不写无法验证的断言。
- 文档里不出现商业授权字体名，也不放字体文件；示例用中性占位（`Main-Serif.otf` 之类）。
- 文档变更与代码变更同一次提交（或紧随其后），避免"文档描述的是上一版行为"。

---

## 4. 硬约束速查（详见 AGENTS / CONVENTIONS）

1. 只依赖 fontTools；测试是 `def test_*` + `main()` 运行器，四套期望 **21 / 13 / 8 / 4** 全绿。
2. 仓库不放字体：测试字体在仓库外 `../test/`，授权字体经不入库的 `tests/local_fonts.py` 角色引用。
3. 不出现商业授权字体名；文档示例用中性占位。
4. 已发布 tag / Release 资产 / CHANGELOG 已发布条目不改写；新变更进 `[Unreleased]`。
5. git 写操作与发布动作只由 Lead 执行。
6. 失败要降级 + 告警，不许静默吞异常，也不许为了"变绿"放松自检。

---

## 5. 当前状态速览

- 版本：**v0.1.1**（`__init__.py` 的 `__version__`；两个 README 徽章同步）
- 分支/远端：`main` ↔ `origin/main`（GitHub: ChangGGcn/font-matrix-merger）
- 代码量：约 10.7k 行 Python（含 4 套测试与 3 个构建脚本）
- 测试：4 套 46 个用例（merger 21 / axis_mapping 13 / subset_merge 8 / cff2_compose 4）
- 发布产物：`dist/font-matrix-merger-v0.1.1.zip`（仅源码；由 `build/make_release_zip.py` 生成）
