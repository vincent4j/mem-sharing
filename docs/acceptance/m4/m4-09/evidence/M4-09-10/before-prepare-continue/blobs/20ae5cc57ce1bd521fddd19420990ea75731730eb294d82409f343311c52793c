# M1-02 规则基座装配 — 装配方案(工作笔记)

- 执行者:突突兔
- 日期:2026-10-29
- 依据:DESIGN.md v1.1(53314d7)§2 D1、§4.1、§4.3、§5;任务书 docs/plan/tasks.md M1-02 节;sync.py 标记块先例
- 状态:准备完成,等待 M1-01 预检门槛

## 1. 设计要点摘录

- **D1**:`AGENTS.md` = 项目硬规则(构建、规范、禁止事项),执行器无关,提交进 Git;记忆 → context-keeper 记录库;用户级规则 → `~/.agents-group`。三执行器可达性:Codex 原生读根→cwd 链;Claude 需 CLAUDE.md 内 `@AGENTS.md` import;WorkBuddy 靠用户级约定(§5)。
- **§4.1 基座**(零依赖,总是执行):项目根 `AGENTS.md` 骨架;CLAUDE.md 含 `@AGENTS.md` 引用;核对 WorkBuddy 用户级约定。基座无需 Keeper。
- **§4.3**:子目录政策——本仓库当前无子目录 AGENTS.md/CLAUDE.md,不涉及;根摘要暂无对象。
- **§5**:WorkBuddy 用户级配合 = `~/.workbuddy/MEMORY.md` 现行"项目规则唯一来源是 AGENTS.md"约定保留,M1-04 才追加记忆条款。M1-02 对它**只读核对**。
- **sync.py 先例**(block/put):
  - `put(path, value)`:内容相同返回 False 不写;符号链接拒绝替换;临时文件 + 原子 `os.replace`;保留既有 mode。
  - `block(text, body)`:标记块 `# agents-group:begin` / `# agents-group:end` 恰好一对;存在则整块替换,不存在则追加到文末(前置空行);块外字节不动。
  - `managed_span`:begin/end 必须各恰好一次,否则 ValueError("invalid managed block")。

## 2. 现状核查(2026-10-29,准备阶段)

| 检查项 | 结果 |
|---|---|
| 仓库根 `AGENTS.md` | 不存在 → 将新建(created) |
| 仓库根 `CLAUDE.md` | 不存在 → 将新建(created) |
| 仓库根 `AGENTS.override.md` | 不存在(无劫持风险) |
| `docs/acceptance/` | 目录不存在(m1-01 preflight 未产出) |
| `~/.workbuddy/MEMORY.md` | 存在;"项目规则、约定、事实的唯一来源是项目根目录的 AGENTS.md"约定在位,无缺失/漂移;**只读,不改写**(追加记忆条款属 M1-04) |
| Git 状态 | clean(main @ a43e31c) |
| `.gitignore` | `docs/acceptance/` 不被忽略,证据文件可正常纳入版本控制 |

## 3. 标记块决策

**AGENTS.md、CLAUDE.md 骨架均不使用 `# agents-group:begin/end` 标记块**,理由:

1. sync.py 的标记块语义是"共享 managed 源"——工具是块内内容的唯一主人,块外归用户。而 D1 定位 AGENTS.md 是**项目规则的唯一来源**,内容主人是项目本身;骨架只是起点,用户此后自由编辑全文,若包块,用户改块内规则会被漂移检查误拒,与"规则归项目"冲突。
2. DESIGN §4.2 瘦身终态:CLAUDE.md 只剩 `@AGENTS.md` + bridge 块、AGENTS.md 只剩规则——AGENTS.md 全文即规则,无装配内容需要块保护;CLAUDE.md 的引用行可由 check 按行检测(§7"CLAUDE.md 只放引用+bridge;check 对非引用规则增长告警"),无需块。
3. M1-03 起加入的 bridge 块使用 context-keeper 自己的标记格式(§5 `<!-- context-keeper:workbuddy:start/end -->` 同类),不由本任务预置。

**幂等实现**(替代标记块):执行前比对整文件内容——
- 文件不存在 → 写入下述精确文案;
- 文件存在且与预期文案完全一致 → 不动(无 diff);
- 文件存在但内容不同 → **不自动改写,停止并报告**(本轮预期两文件均不存在;出现即属预检遗漏或并行冲突,按任务边界"先报告"处理)。

## 4. 精确文案

### 4.1 根 AGENTS.md(新建,UTF-8,末尾单个换行)

````markdown
# agent-group-memory 项目规则

跨执行器(Codex / Claude Code / WorkBuddy)共享记忆的互通编排层:自动装配项目规则入口与 context-keeper 记忆库,换工具不失忆。本文件是本项目规则的唯一来源;记忆(进度、事实、经验)一律记入项目 context-keeper 记录库,不写入规则文件。

## 构建

(占位:M2 CLI 落地后补充实际命令)

## 测试

(占位:tests/ 就位后补充实际命令)

## 约定

- Git 提交、推送由用户亲自执行,工具与 Agent 不主动 commit/push。
- 不修改上游 context-keeper 与旧 ~/.agents-group 管理器的源码。
````

要点:一句话说明(与 README.md 定位口径一致)+ 构建/测试占位 + 两条硬约定(分别来自用户既有偏好与 DESIGN"所有任务共同反模式"),**零记忆内容**。不预置 dogfood 临时边界(属任务上下文,不是项目永久规则)。

### 4.2 根 CLAUDE.md(新建,UTF-8,末尾单个换行)

````markdown
@AGENTS.md

项目规则统一维护在 AGENTS.md,本文件仅作引用入口。
````

要点:第一行裸 `@AGENTS.md`(Claude Code 原生 import 语法,D1 表格指定方式)+ 一行说明;M1-03 装 bridge 块前保持仅此两行。

## 5. 执行步骤(门槛通过后)

1. 复核门槛:`docs/acceptance/m1-01/preflight.md` 存在且 M1-02 相关项无阻断(AGENTS.override.md 不存在、入口无冲突);有阻断 → 停在本方案并汇报。
2. 写前快照:`git status --porcelain`、根目录文件清单,记录所有权预期(两文件均 created)。
3. 按 §4 文案写入 AGENTS.md、CLAUDE.md。
4. 写后验证:`git diff` 采集两文件 diff;确认无其他文件被触碰;`AGENTS.override.md` 复查不存在。
5. 幂等复跑:对两文件重复执行写入逻辑(内容一致 → 不动),用 `git diff` 前后对比与 mtime 证明无新 diff。
6. 证据落盘 `evidence.md`:所有权清单(created/reused 逐项)、diff、幂等复跑结果、WorkBuddy 只读核对结论。
7. 汇报:完成内容、验证证据、剩余风险(如 WorkBuddy 子目录盲区保留、静态装配不等于运行时可达——后者属 M1-06)。

## 6. 边界自查清单

- [x] 只写项目 AGENTS.md、CLAUDE.md 与 docs/acceptance/m1-02/ 产物
- [x] 不写 ~/.workbuddy/ 任何文件(只读核对已完成,结论在 §2)
- [x] 不 commit、不 push
- [x] AGENTS.md 无记忆内容
- [x] 发现 AGENTS.override.md 即停(当前不存在)
- [ ] 幂等:执行后以复跑验证

## 7. 门槛状态记录

| 时间 | docs/acceptance/m1-01/preflight.md | 结论 |
|---|---|---|
| 2026-10-29 准备阶段 | 不存在 | 继续等待;准备产物已完备 |
| 2026-10-29 18:41 | 已产出 | 核对通过:R/AGENTS.md、R/CLAUDE.md"技术预检可放行"(缺失、无 override、无冲突);WorkBuddy 部分与本任务只读边界一致。进入执行,结果见 [evidence.md](evidence.md) |
