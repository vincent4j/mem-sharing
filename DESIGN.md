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
3. **规则与记忆分层,项目规则的唯一源是项目根 `AGENTS.md`**:
   - `AGENTS.md` = 项目硬规则(构建命令、代码规范、禁止事项),与执行器无关,提交进 Git;
   - 进度、事实、经验是**记忆**,走 context-keeper 记录库,由 bridge 触发规则驱动;
   - `~/.agents-group` = 用户级跨项目规则。三层互不抢地盘。
   - **各执行器对 AGENTS.md 的可达性**(必须显式打通,否则规则只对部分 Agent 生效):
     | 执行器 | 可达性 | 打通方式 |
     |---|---|---|
     | Codex | 原生读取 Git 根→cwd 链 | 无需处理 |
     | Claude Code | **默认"有 CLAUDE.md 就不读 AGENTS.md"** | CLAUDE.md 内放 `@AGENTS.md` import(原生支持) |
     | WorkBuddy | 无原生支持 | 用户级约定引导(§6,保留现行"项目规则读 AGENTS.md"条款) |
4. **私有记忆只出不进**:Codex/WorkBuddy/Claude 各自的自动记忆库是黑盒生成物,保持原样,不做互通枢纽。

## 4. 三执行器接入矩阵

| 维度 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 项目 Skill 目录 | `.agents/skills`、`.codex/skills`(context-keeper 安装器支持) | `.claude/skills`(支持) | `.workbuddy/skills`(支持) |
| 自动入口落点 | 项目 `AGENTS.md`(bridge 已验收 ✅) | 项目 `CLAUDE.md`(bridge 已验收 ✅) | **`.workbuddy/memory/MEMORY.md` 顶部(本仓库设计,待验收)** |
| 嵌套(子目录)规则文件 | 根→cwd 逐级 AGENTS.md,拼接、近者优先(共享 32KiB) | 子目录 CLAUDE.md/AGENTS.md 在该目录工作时按需加载 | **无嵌套机制**,仅项目根 `.workbuddy/memory/`;子目录规则不可达(盲区,§5.2) |
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

1. **确保项目规则基座**:项目根 `AGENTS.md` 存在(无则创建骨架);`CLAUDE.md` 存在时确认含 `@AGENTS.md` 引用(§3 决策 3 的可达性打通);
2. 调用 context-keeper 的 `install.py` 把 Skill 装进所选执行器的项目 Skill 目录(`--all` 语义,同名冲突即停,不覆盖);
3. Codex/Claude:执行其已验收的 `--ensure-bridge`(`--codex` / `--claude` 各自的规则文件);
4. WorkBuddy:写入本仓库定义的 WorkBuddy 桥接块(§6);
5. 读回校验 + 提示"新会话验收"(§7)。

`check-memory`:检测三家入口块存在/漂移、CLAUDE.md 的 `@AGENTS.md` 引用存在、CLAUDE.md 内非引用规则增长、`AGENTS.override.md` 劫持风险、记录库位置与迁移门禁状态。

`remove-memory`:仅移除入口块与 Skill 链接,不动 `docs/context-keeper/` 记录本体(记忆是项目资产,删除必须用户显式做)。

### 5.1 存量整理(首次启用时,覆盖项目级与用户级两个维度)

装本系统之前各处已积累的内容,首次 `enable-memory` 进入存量整理阶段:**预览 → 用户逐类确认 → 执行**,不做盲移,也**不做任何内容加工**——只搬运归位,不蒸馏、不改写(后续消化若需要,由 context-keeper 自身功能处理,不属于本层)。

**项目维度**(根与各子目录的 `AGENTS.md`、`CLAUDE.md`、`CLAUDE.local.md`):

1. 扫描分类:规则 / 记忆类(进度、事实、经验)/ 装配内容(@import、bridge 块);
2. 归位:
   - 规则 → 合并进(同级)`AGENTS.md` 唯一源;两文件冲突或漂移的条目**并列展示双方原文,由用户裁定**;
   - 记忆类 → **原样搬运**为 context-keeper `worklogs/` 的一条 legacy 日志(注明来源文件与日期),不蒸馏、不改写;
   - 个人偏好 → 留在 `CLAUDE.local.md`(gitignore 层),不并入团队可见的 AGENTS.md;
3. 瘦身:CLAUDE.md 只剩 `@AGENTS.md` 引用 + bridge 块;AGENTS.md 只剩规则。

**用户维度**(各执行器用户级入口:`~/.codex/AGENTS.md`、`~/.claude/CLAUDE.md`、`~/.workbuddy/MEMORY.md`):

1. 扫描分类存量内容:跨执行器通用规则 / 执行器专属规则 / 人格与私人内容;
2. 归位:通用规则 → 合并进 `~/.agents-group/memories/MEMORY.md`(用户级唯一源,压缩为短规则);专属规则 → 留在各自原生文件;人格/私人内容(SOUL、USER 等)一律不动;冲突条目用户裁定;
3. 瘦身:各用户级文件只保留专属规则 + 指向公共源的指针。

全程时间戳备份 + 迁移报告(什么内容、从哪个文件、去了哪里、用户裁定记录)。分类由 agent 执行、用户确认;工具只做扫描、预览、备份与读回校验。

### 5.2 子目录的规则和记忆怎么处理

一句话:**子目录的 AGENTS.md 只写"要求";所有记忆——不管哪个子目录产生的——都只存一份,放项目根的 context-keeper 记录库,用文件名标明出处。**

背景:三家机制不同。Codex 把 Git 根到当前目录**沿途每个 AGENTS.md 拼接**加载;Claude 的根 CLAUDE.md 常驻、子目录 CLAUDE.md/AGENTS.md 在处理该目录时**按需**加载;WorkBuddy 是"打开哪个文件夹哪个就是项目",记忆只挂项目根,**子目录任何文件它都不感知**。

**存量:已有的子目录 CLAUDE.md(如 `services/api/CLAUDE.md`)里的内容分两堆搬走:**

| 内容 | 搬到哪 | 例子 |
|---|---|---|
| 要求(一直生效的规则) | 并入 `services/api/AGENTS.md` | "本服务用 pnpm,测试跑 pytest" |
| 记忆(进度、踩坑、结论) | 原文搬到 `docs/context-keeper/worklogs/2026-10-29-legacy-services-api.md` | "token 校验放错中间件,正确位置是 auth.ts" |

搬完 CLAUDE.md 空了就删——Claude 在该目录工作时会自动读同目录 AGENTS.md,不受影响。

**增量:以后在某个子目录工作时产生的新记忆(如在 `services/api/` 排了个错)**,记进 context-keeper 的 worklog,**文件名带上子目录名**:`docs/context-keeper/worklogs/2026-10-29-services-api-token排错.md`;不在 `services/api/` 下新建任何记忆文件。

**为什么记忆不留在子目录、非要集中到根?**

1. WorkBuddy 读不到子目录文件——放根库,三家才都读得到;
2. Codex 沿途所有 AGENTS.md 共享 32KiB 预算——只够放短规则,放不下记忆;
3. context-keeper 的"继续/查找"建立在单一记录库上——记忆散进目录树就没法统一检索。

类比:**要求是贴在部门门口的告示**(子目录 AGENTS.md,在该目录干活的人才需要看);**记忆是归档进档案室的案卷**(context-keeper 库,档案袋上写清楚是哪个部门的事)。**归属是标签,不是位置。**

## 6. WorkBuddy 自动入口桥接(本仓库的主要新增工作)

context-keeper 的 install.py 对 WorkBuddy 刻意停写:"自动入口尚未完成运行时验证,停止写入规则文件"。本仓库补齐这一环:

- **落点**:项目 `.workbuddy/memory/MEMORY.md` 顶部(WorkBuddy 原生加载该文件;其每日日志机制照旧,不冲突)。
- **内容**:复用 context-keeper 的 BRIDGE 规则语义(无项目聊天边界、限量历史检索触发、自然节点自动记录、追加式日志、事实边界),以 `<!-- context-keeper:workbuddy:start/end -->` 标记块写入,措辞适配 WorkBuddy 记忆文件语境。
- **验收通过后**:把 WorkBuddy 桥接模板与验收证据回传 context-keeper 仓库,解除其 install.py 对 WorkBuddy 的写入限制——**桥接的终局是消失**:一旦 context-keeper 原生支持,本仓库编排命令只调它,不再维护私有模板。
- 一次性的用户级配合改动:`~/.workbuddy/MEMORY.md` 中现行的"项目规则唯一来源是项目根 AGENTS.md"约定**保留规则条款**(WorkBuddy 靠它读 AGENTS.md,这是 §3 可达性打通的一环),只**追加记忆条款**:"项目记忆(进度/事实/经验)用 context-keeper 记录库,由项目 `.workbuddy/memory/MEMORY.md` 的桥接块驱动"——规则走 AGENTS.md、记忆走 context-keeper,两不打架。

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
| 双重入口打架(WorkBuddy 老约定 vs 桥接) | §6 的用户级约定补记;check 检测旧约定残留 |
| 项目规则双写漂移(AGENTS.md 与 CLAUDE.md 各存一份规则) | 规则唯一源 AGENTS.md;CLAUDE.md 只放 `@AGENTS.md` 引用 + bridge 块;check 对 CLAUDE.md 中非引用的规则增长告警 |
| `@AGENTS.md` import 被误删(Claude 断 rules) | check 校验 CLAUDE.md 引用行存在;enable 幂等补装 |
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
