# agent-group-memory 设计方案

多 Agent 跨执行器共享记忆:**不重复造轮子**。项目记忆直接复用 context-keeper,本仓库只做跨执行器的互通与编排,并定义清楚三套系统的分工边界。

- 版本:v0.2(2026-10-29,重构:项目记忆改为复用 context-keeper)
- 覆盖执行器:**Codex、Claude Code、WorkBuddy**
- 历史版本 v0.1 曾设计自建项目记忆结构(journal/索引/蒸馏管道),已废弃——该能力由 context-keeper 承担

---

## 1. 问题

同一个人在同一个项目上交替使用多个 Agent:周一 Codex、周二 WorkBuddy。各家记忆各存一处(Codex `~/.codex/memories/`、Claude `~/.claude/projects/*/memory/`、WorkBuddy `.workbuddy/memory/` + 云端画像),换工具即失忆。

用户级互通已由 `~/.agents-group` 解决。项目级互通**已有现成实现:[context-keeper](https://github.com/vincent4j/context-keeper)**——保存/继续/查找三入口、append-only 工作日志、按证据自我进化,覆盖了项目记忆的全部需求。

因此本仓库不自建项目记忆,定位为:**把 context-keeper 自动、可靠地铺到所有执行器上的互通编排层**。

## 2. 三套系统的分工边界(本方案的核心)

| 系统 | 职责 | 不做什么 |
|---|---|---|
| `~/.agents-group`(用户级,已建成) | 跨项目、跨执行器的公共短规则、共享 Skills/MCP;各家用户级入口指针 | 不管任何项目内部的事 |
| **context-keeper**(项目记忆运行时) | 项目记忆的一切:记录库结构(`docs/context-keeper/`:memory-keeper.md、plans/、worklogs/、evolution/)、保存/继续/查找路由、按证据自动沉淀与进化、Skill 安装器(7 家)、Codex/Claude 已验收的自动入口(bridge) | 不管跨执行器编排、不管用户级;其余 5 家的自动入口待逐家运行时验收 |
| **agent-group-memory**(本仓库,互通编排层) | ①本方案与边界文档;②"为项目启用项目记忆"的编排命令(自动安装 context-keeper skill + 配置各执行器入口);③**WorkBuddy 等未验收执行器的自动入口桥接与运行时验收**,验收结论回传 context-keeper 解除其安装器限制 | 不存任何记忆、不定义记忆结构、不做蒸馏/进化、不做历史回溯、不反向写任何私有记忆库 |

**边界判据(一句话)**:记忆的*内容与结构*归 context-keeper;*谁在什么时机被装上、被触发*归 agent-group-memory;*跨项目的用户规则*归 `~/.agents-group`。

**历史回溯**(装 context-keeper 之前的历史、漏记会话的回填):**不属于本仓库**。该需求若要做,作为 context-keeper 的可选功能实现(用户自行选择是否回溯),不在此处设计。

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ 用户级:~/.agents-group(已建成,独立运行)                    │
│   跨项目短规则 + 共享 Skills/MCP;各家用户级入口已接指针     │
├──────────────────────────────────────────────────────────────┤
│ 项目级:context-keeper(项目记忆运行时,复用,不改其内核)    │
│                                                              │
│   <项目>/docs/context-keeper/   ← 记忆本体(提交进 Git)    │
│     memory-keeper.md · plans/ · worklogs/ · evolution/       │
│                                                              │
│   触发入口(bridge 标记块):                                 │
│     Codex  → 项目 AGENTS.md   (context-keeper 已验收 ✅)    │
│     Claude → 项目 CLAUDE.md   (context-keeper 已验收 ✅)    │
│     WorkBuddy → 项目 .workbuddy/memory/MEMORY.md(本仓库桥接)│
├──────────────────────────────────────────────────────────────┤
│ 编排层:agent-group-memory(本仓库)                          │
│   enable-memory 命令:per 项目自动安装 context-keeper skill │
│   到三家 Skill 目录 + 配置入口;WorkBuddy 桥接验收          │
└──────────────────────────────────────────────────────────────┘
```

关键决策:

1. **项目记忆 = context-keeper**。周一 Codex 会话按其规则写 worklogs;周二 WorkBuddy 通过"继续"入口恢复——跨执行器连续性由"记忆在项目里 + 三家都被同一 Skill 规则驱动"保证。
2. **记忆跟着仓库走**:记录库在 `<repo>/docs/context-keeper/` 且提交进 Git,worktree 天然继承、多设备天然同步(Paseo worktree 场景已由 context-keeper 该设计覆盖)。
3. **规则与记忆分层**(与 Codex/Claude 官方口径一致):必须始终生效的硬规则仍写 AGENTS.md/CLAUDE.md 本体;进度、事实、经验是记忆,走 context-keeper 记录库,由 bridge 触发规则驱动。
4. **私有记忆只出不进**:Codex/WorkBuddy/Claude 各自的自动记忆库是黑盒生成物,保持原样,不做互通枢纽。

## 4. 三执行器接入矩阵

| 维度 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 项目 Skill 目录 | `.agents/skills`、`.codex/skills`(context-keeper 安装器支持) | `.claude/skills`(支持) | `.workbuddy/skills`(支持) |
| 自动入口落点 | 项目 `AGENTS.md`(bridge 已验收 ✅) | 项目 `CLAUDE.md`(bridge 已验收 ✅) | **`.workbuddy/memory/MEMORY.md` 顶部(本仓库设计,待验收)** |
| 指令预算 | AGENTS.md 链默认 32KiB,bridge 块已控制体积 | CLAUDE.md 建议 <200 行 | 未见公开上限 |
| 验收手段 | 复述当前指令链(官方推荐) | `/context`、`/memory` | 新会话口头验证 |
| 特有风险 | `AGENTS.override.md` 会劫持整个 AGENTS.md(装入口前检测) | 有 CLAUDE.md 时不读 AGENTS.md(入口必须进 CLAUDE.md) | "重置记忆"清空 `.workbuddy/memory/`(需幂等重装入口) |

## 5. 编排命令

```
enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...]   # 默认三家
remove-memory [--project <Git根>]
check-memory  [--project <Git根>]
```

`enable-memory` 的动作(全部幂等,操作前查 Git 状态、备份、指纹漂移检测):

1. 调用 context-keeper 的 `install.py` 把 Skill 装进所选执行器的项目 Skill 目录(`--all` 语义,同名冲突即停,不覆盖);
2. Codex/Claude:执行其已验收的 `--ensure-bridge`(`--codex` / `--claude` 各自的规则文件);
3. WorkBuddy:写入本仓库定义的 WorkBuddy 桥接块(§6);
4. 读回校验 + 提示"新会话验收"(§7)。

`check-memory`:检测三家入口块存在/漂移、`AGENTS.override.md` 劫持风险、记录库位置与迁移门禁状态。

`remove-memory`:仅移除入口块与 Skill 链接,不动 `docs/context-keeper/` 记录本体(记忆是项目资产,删除必须用户显式做)。

## 6. WorkBuddy 自动入口桥接(本仓库的主要新增工作)

context-keeper 的 install.py 对 WorkBuddy 刻意停写:"自动入口尚未完成运行时验证,停止写入规则文件"。本仓库补齐这一环:

- **落点**:项目 `.workbuddy/memory/MEMORY.md` 顶部(WorkBuddy 原生加载该文件;其每日日志机制照旧,不冲突)。
- **内容**:复用 context-keeper 的 BRIDGE 规则语义(无项目聊天边界、限量历史检索触发、自然节点自动记录、追加式日志、事实边界),以 `<!-- context-keeper:workbuddy:start/end -->` 标记块写入,措辞适配 WorkBuddy 记忆文件语境。
- **验收通过后**:把 WorkBuddy 桥接模板与验收证据回传 context-keeper 仓库,解除其 install.py 对 WorkBuddy 的写入限制——**桥接的终局是消失**:一旦 context-keeper 原生支持,本仓库编排命令只调它,不再维护私有模板。
- 一次性的用户级配合改动:把 `~/.workbuddy/MEMORY.md` 中现行的"项目规则唯一来源是项目根 AGENTS.md"约定改写为"项目记忆用 context-keeper 记录库;硬规则仍可写 AGENTS.md",避免两套约定打架。

## 7. 验收协议(静态配置不算数)

每个执行器启用后必须**新会话**实测,双方向:

1. **读/触发**:给出"继续上次工作"类指令,应触发 context-keeper 的继续路由并恢复进度,而不是凭空开始。
   - Codex:`codex "Summarize the current instructions."` 复述中应出现 context-keeper 入口规则;
   - Claude:新会话 `/context` 确认 CLAUDE.md 加载;
   - WorkBuddy:新会话问"读一下本项目记忆入口"应能按桥接块行动。
2. **写/沉淀**:制造一次自然收尾节点(明确纠正或完成一个阶段),检查新记录落在 `docs/context-keeper/worklogs/`(而非任何执行器私有记忆文件)。
3. 运行中的会话不生效,须重开;三家均无指令缓存。

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| WorkBuddy"重置记忆"清空入口 | enable/check 幂等重装;重置后重跑 |
| `AGENTS.override.md` 劫持 Codex 入口 | check 检测并告警;本仓库永不使用 override 机制 |
| bridge 块漂移/被手工编辑 | 标记块指纹校验(沿用 context-keeper 幂等逻辑);漂移即停,人工核对 |
| 与 context-keeper 版本脱节 | 本仓库不复制其规则文本为第二真源——WorkBuddy 桥接验收后立即回传上游,只保留临时副本并注明来源版本 |
| 双重入口打架(WorkBuddy 老约定 vs 桥接) | §6 的用户级约定改写;check 检测旧约定残留 |
| 32KiB / 200 行预算 | 入口块体积由 context-keeper 模板控制;本仓库不再往规则文件追加任何记忆类内容 |

## 9. 落地路线

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1 dogfood | 本仓库自身启用:安装 context-keeper(三家)+ Codex/Claude bridge + WorkBuddy 桥接块 + 改写 WorkBuddy 用户级旧约定 | §7 双探针 ×3 |
| M2 工具化 | `enable-memory` / `remove-memory` / `check-memory` | 在 knowwind、poster-fit 复制,幂等重装通过 |
| M3 上游回传 | WorkBuddy 桥接模板 + 验收证据提交回 context-keeper,解除其安装器限制;本仓库删除私有模板 | context-keeper 原生安装 WorkBuddy 入口成功 |
| 后续 | 其余执行器(ZCode、DeepSeek Harness 等)按同模式逐家桥接验收 | — |

---

附:调研依据——Codex 官方文档(memories、agents-md)、Claude Code 官方 memory 文档、WorkBuddy 官方设置文档与三层记忆机制文章;本机实测 `~/.codex/memories/`、`~/.claude/projects/`、`~/.workbuddy/`;context-keeper 仓库源码(SKILL.md、scripts/install.py 的 BRIDGE 模板与安装限制)。
