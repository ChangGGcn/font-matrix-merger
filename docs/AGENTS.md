# 多 Agent 协作指南

> 适用范围：任何参与本项目的 Agent（以及人类协作者）。本文定义**角色、任务板工作流、写作用域、验证门、汇报契约与禁止事项**。
> 配套文档：[架构](ARCHITECTURE.md) · [开发规范](CONVENTIONS.md) · [交接](HANDOVER.md) · [索引](README.md)

---

## 0. 为什么需要这份文档

font-matrix-merger 的改动经常横跨「数学（轴映射）→ 字体表（gvar/CFF2/GDEF）→ 合并流程 → 自检」多层，单人串行开发容易在回归上翻车。多 Agent 并行的收益来自**写作用域互不重叠 + 验证门统一**；风险则集中在：同一文件并发写、验证被降级、字体/授权类红线被突破、以及"各自以为对方验证过"。

本指南的硬性目标：

1. 任何时刻，**一个文件只有一个写者**；
2. 任何提交，**验证门可复现**（命令 + 期望数字）；
3. 任何结论，**能落到代码/实测**（不接受"应该没问题"）；
4. 任何破坏性动作，**只有 Lead 能执行**。

---

## 1. 角色

| 角色 | 由谁担任 | 职责 | 写权限 |
| --- | --- | --- | --- |
| **Lead** | 1 人（团队负责人） | 拆任务、建任务板、spawn 成员、评审、统一跑回归、git 操作、发布、对用户汇报 | 全部；但业务代码优先交给 Writer |
| **Writer** | N 人，按任务划分 | 在声明的作用域内实现/写文档，自测，按契约汇报 | 仅任务声明的 `write_scopes` |
| **Reviewer / Fact-checker** | 1 人（可复用 Writer 空档） | 只读交叉验证：文档结论 vs 代码事实、实现 vs 规范、回归是否真的跑了 | 无（只写汇报，不改文件） |
| **Test-runner**（可选） | 1 人 | 跑回归/矩阵/基准，产出可复现数据（命令 + 输出摘要） | 无源码写权限（可写测试产物到临时目录） |

约定：

- **Lead 是唯一能执行 git 写操作的人**（`add/commit/push/tag/rebase/reset/checkout` 等）。Writer 只改工作区文件。
- **Reviewer 不得顺手改文件**。发现问题 → 汇报 → Lead 决定由谁改。
- 同一时刻 Lead 只保留**一个**"进行中的发布/提交"动作，避免 git 索引被并发污染。

---

## 2. 任务板工作流（Lead ↔ Writer）

### 2.1 Lead 建任务

每个任务在共享任务板上有一条记录，包含四要素：

- **subject**：一句话（动词开头，如"撰写 docs/ARCHITECTURE.md"）
- **description**：背景、必读文件、章节大纲、验收标准
- **write_scopes**：仓库相对路径（如 `docs/ARCHITECTURE.md`、`format/`），用于冲突预警
- **blocked_by**：必须先生效的任务 id（无依赖留空）

> 任务粒度建议：**一个文件**或**一个函数族**，预估 ≤ 半天；跨 2 个以上文件的改动拆成多个任务，或把任务标成"独占"由 Lead 串行安排。

### 2.2 Writer 认领

Writer 拿到任务 id 后的固定动作：

1. `team_task_get({task_id})` 取最新 revision 与 write_scopes；
2. `team_task_update({task_id, expected_revision, action: "claim"})`；
3. 若 `write_scope_warnings` 非空（与他人重叠）→ **停下**，先向 Lead 确认再动手；
4. 开始工作，只在声明的范围内写文件；
5. 自检（见 §4），然后 `action: "complete"`；
6. `send_message` 给 Lead，按 §5 契约汇报。

### 2.3 Lead 评审

- 读 diff / 读产物，检查：验收标准、验证门、红线（字体/授权/依赖）、文档一致性；
- 通过 → 由 Lead 统一 commit（必要时多个任务合并成一次提交，但提交信息要能对回任务）；
- 不通过 → `action: "reopen"`，附具体修改意见（引用文件 + 行号 + 期望行为），不要只说"再改改"。

### 2.4 任务状态语义

| 状态 | 含义 |
| --- | --- |
| `pending` | 未认领 / 已 reopen 等待重做 |
| `in_progress` | 已认领，Writer 正在做 |
| `completed` | Writer 自检完成并已汇报；**不等于 Lead 已验收** |
| `blocked`（blocked_by 非空） | 依赖未完成，不可开工 |

---

## 3. 写作用域与并发规则

### 3.1 一个文件一个写者

- 声明式作用域是**建议性**的（不是锁）：Lead 必须自己保证不把两个任务派到同一文件上。
- 共享文件默认 **Lead 独占**：`README.md`、`README.zh-CN.md`、`CHANGELOG.md`、`__init__.py`、`core/merger.py`、`.gitignore`、`.gitattributes`、`build/`。
  这些文件改动频繁且影响面大，由 Lead 在收口时统一改。
- 例外：某个任务本身就是"重构 core/merger.py"时，Lead 把该文件**独占**给一个 Writer，并在任务描述里写明期间其它任务不得触碰。

### 3.2 并行与串行

| 可以并行 | 必须串行 |
| --- | --- |
| 只读：读代码、查资料、跑只读检查、写**不同**文件 | 同一文件的编辑；任何 git 写操作；发布动作；改 `__init__.py` 导出面 |
| 各自作用域内的文档/测试文件 | 修改共享文件（README/CHANGELOG/merger.py）与其它任务的前置 |

### 3.3 并发写冲突的处理

- 文件工具报 `FS_STALE_VERSION`（文件已被他人改动）：**重新 read 当前内容 → 把你的意图 rebase 到新内容 → 重试**；不要用内存里的旧内容整体覆盖。
- 用 bash 脚本/格式化工具改过文件后，必须**重新 read** 再继续用 edit/write，避免绕过版本守卫造成覆盖。
- 出现无法合并的分叉（两人改了同一段）：**以语义更完整的一方为准**，另一方重新 read 后再补；仍不确定 → Lead 裁决。

---

## 4. 验证门（按改动类型）

> 原则：**验证强度与风险成正比**；任何"降低验证强度"的动作都必须显式声明并获得 Lead 同意。

| 改动类型 | 必跑 | 额外要求 |
| --- | --- | --- |
| 纯文档（docs/*.md） | 无测试；做事实核查 | 结论必须能定位到代码（文件 + 函数）；不编造数字 |
| `format/`、`tables/`、`core/` 代码 | `python3 tests/test_axis_mapping.py`、`tests/test_merger.py`、`tests/test_subset_merge.py`、`tests/test_cff2_compose.py`（21/13/8/4 全绿） | 涉及可变数据合成时，额外确认 `verify_composition` 的自检断言仍生效（不得关 `verify_compose` 来"通过"） |
| 测试代码/夹具 | 同上 + 被改套件单独跑通 | 新增用例必须带可量化的断言（数值 + 单位），不得只断言"不抛异常" |
| 发布（版本号/CHANGELOG/zip/tag/release） | 四套全绿 + `python3 build/make_release_zip.py --out /tmp/x.zip` | 校验 zip 内容（仅 py + README×2 + LICENSE + CHANGELOG）与 sha256；确认未移动已发布 tag |
| CLI/交互（FontMerging.py） | 四套全绿 + 手工冒烟（非交互预填答案） | 交互路径要保持"问一次、后续复用"的既有行为 |

**字体缺失是合法 SKIP**：测试会打印 `SKIP (测试字体未就位)`；Writer 汇报时必须列出哪些用例被跳过、为什么。

**回归数字是唯一门槛**：不许把断言改松、不许删用例、不许给 `verify` 加 `try/except` 吞掉失败来让套件变绿。

---

## 5. 汇报契约（Writer → Lead）

> 时长控制在 10~20 行；数字带单位；结论可复现。

```
任务: task-N（subject）
改动: <文件列表；新增/修改分开>
读过的关键文件: <最多 8 个>
验证: <命令> → <结果摘要，如 21/21 passed；若 SKIP，列出原因>
实测/关键结论: <2~5 条，尽量带数字>
风险/存疑: <发现的不一致、未覆盖路径、性能顾虑>
需要 Lead 决策: <选项化，最多 3 条；没有就写"无">
```

**禁止**：

- "已完成"但没有命令/结果；
- 把"实现思路"当"实现结果"；
- 未验证就声称"应该没问题"；
- 隐瞒 SKIP、警告或回退（`[合成] 回退到默认实例合并` 这类日志出现时必须说明原因）。

---

## 6. 禁止事项（红线）

1. **不提交字体文件**：仓库只放源码；`.gitignore` 已拦截字体二进制与 `*.ttx`。测试字体在仓库外 `../test/`。
2. **不出现商业授权字体名**：授权字体一律通过不入库的 `tests/local_fonts.py` 角色引用（模板 `tests/local_fonts.example.py`）；文档用中性占位（如 `Main-Serif.otf`）。不要读取/复制 `tests/local_fonts.py` 的内容。
3. **不改写已发布内容**：已发布的 tag、Release 资产、CHANGELOG 已发布条目都不改；新变更记到 `[Unreleased]`。
4. **不加依赖**：只用 fontTools（无 pytest/uharfbuzz/pathops）。测试是纯函数 + `main()` 运行器。
5. **不静默失败**：异常必须打印带 `[标签]` 的告警并降级到安全路径；禁止裸 `except: pass`。
6. **不动 release 资产**：资产由 `build/make_release_zip.py` 生成；发布动作仅 Lead 执行。
7. **不擅自改默认策略**：`compose_range/compose_fit/avar_mode/verify_compose/compose_layout` 等默认值是用户拍板的，改默认必须先问。
8. **不 force-push、不 `reset --hard` 到别人的提交、不删分支**。

---

## 7. 冲突与异常处理

| 情况 | 处理 |
| --- | --- |
| 测试字体缺失 | 合法 SKIP；汇报中列出；不得因此改测试逻辑 |
| 测试失败 | 先判断是否自己改动引起；能定位就修，不能定位就回滚自己改动并汇报 |
| 与队友的 diff 冲突 | 停手 → 汇报 Lead → Lead 决定以谁为准，再 rebase 重做 |
| 需求/验收标准歧义 | 停手 → 向 Lead 提问（带 2~3 个选项）；Lead 汇总后问用户 |
| 发现代码 bug / 文档与代码不一致 | 不顺手改；写进汇报，由 Lead 决定是否单开任务 |
| 破坏性操作（删除、重写历史、改发布） | 必须 Lead 执行，且有用户确认 |

---

## 8. 知识传递

- **文档即共享记忆**：接手先读 [HANDOVER](HANDOVER.md)，改动前读 [ARCHITECTURE](ARCHITECTURE.md) 与 [CONVENTIONS](CONVENTIONS.md)。
- **代码变更同步文档**：改了分层/流程 → 更新 ARCHITECTURE；改了风格/流程 → 更新 CONVENTIONS；每次发布 → 更新 HANDOVER 与 CHANGELOG。
- **CHANGELOG 由 Lead 统一维护**（双语、单文件、每条目先 `### English` 后 `### 简体中文`）。
- **任务板是过程记录**：任务文本本身要能复盘（写清"为什么"而不只是"做什么"）。

---

## 9. 一个完整的并行示例（本仓库实际做法）

> 目标：补齐 docs/ 下的三份工程文档。

1. Lead 盘点仓库 → 建 3 个任务（write_scopes 分别指向三个文件）→ 同时 spawn 3 个 Writer（`context: fresh`，prompt 里带 task id、必读文件、章节大纲、验收标准）。
2. Writer 各自 `claim` → 读代码 → 写文档 → 自检 → `complete` → 按契约汇报。
3. Lead 同时写 `docs/AGENTS.md`、`docs/README.md` 与根 `AGENTS.md`（共享文件独占）。
4. 全部完成后，Lead 派 1 个 `Reviewer`（只读）交叉验证三份文档的事实，产出问题清单。
5. Lead 逐条修 → 四套测试全绿 → 统一提交 → 推送。

要点：**写作用域互不重叠**、**验证门在 Lead 手里**、**汇报可复现**。
