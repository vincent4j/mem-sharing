# agent-group-memory(多 Agent 记忆融合)设计方案

多 Agent 跨执行器共享记忆:**不重复造轮子**。项目规则统一到项目根 `AGENTS.md`,项目记忆直接复用 context-keeper;本仓库只做跨执行器的互通与编排,并定义清楚三套系统的分工边界。

- 版本:v1.2(2026-10-30,边界修正:`~/.agents-group` 为本产品用户级层,随产品安装创建;旧手工实现由产品替代,新增 M4)
- 覆盖执行器:**Codex、Claude Code、WorkBuddy**
- 历史沿革:v0.1 自建项目记忆已废弃(能力归 context-keeper);v0.2 起定位编排层;v1.1 按评审修订;v1.2 用户级层并入产品范围;v1.1 按评审修订:check 收敛为只读、状态文件更名、记录库授权四态、验收改为三执行器接力闭环、M1 范围收敛、跨平台收紧
- **本期范围不含 Skills/MCP 管理**(用户决定,留待后续;项目级 Skills/MCP 继续由旧 `project_manage.py` 负责)

---

## 0. 摘要

解决的问题:周一用 Codex、周二用 WorkBuddy 处理同一个项目,记忆和规则互不相通。方案一句话:**规则互通靠"项目根 AGENTS.md 单一源 + 各执行器入口打通"(零依赖基座);项目记忆靠自动安装的 context-keeper(可选档,默认推荐);本仓库是一个用户级工具(Skill 外壳 + 跨平台 Python 内核),负责装、拆、检查与联动。**

## 1. 问题与定位

### 1.1 问题

各家记忆与规则各存一处:

| 层级 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 用户级 | `~/.codex/AGENTS.md` + `~/.codex/memories/`(自动) | `~/.claude/CLAUDE.md` + `~/.claude/projects/*/memory/`(自动) | `~/.workbuddy/MEMORY.md` + 云端画像(自动) |
| 项目级 | 项目根 `AGENTS.md`(根→cwd 逐级链) | `CLAUDE.md` 系列(根常驻、子目录按需) | `<项目根>/.workbuddy/memory/` |

本产品覆盖**用户级与项目级两层**:用户级公共源落位 `~/.agents-group`(安装本产品时自动创建);项目级为编排层。本机既有的 `~/.agents-group` 手工实现是先行的自制品,**将被本产品替代**(内容迁移保留,脚本体系换代,见 §8 M4)。

### 1.2 三套系统分工边界(核心)

| 系统 | 职责 | 不做什么 |
|---|---|---|
| `~/.agents-group`(**本产品用户级层**,随产品安装创建) | 跨项目、跨执行器的用户级公共规则、共享 Skills/MCP 的公共源与入口装配 | 本机旧手工实现(manage/sync/project_manage)将被产品替代(M4 迁移);替代完成前过渡期并存 |
| **context-keeper**([github.com/vincent4j/context-keeper](https://github.com/vincent4j/context-keeper),项目记忆运行时,独立产品) | 项目记忆的一切:记录库(默认 `docs/context-keeper/`,支持自定义)、保存/继续/查找、按证据自我进化、Skill 安装器、Codex/Claude 已验收 bridge、迁移门禁 | 不感知 Group、不做跨执行器编排、不管用户级 |
| **agent-group-memory**(本仓库) | 编排:规则装配(基座)、记忆装配(安装/桥接/记录库授权/验收)、存量整理、联动 | 不存记忆、不定义记忆结构、不做蒸馏/进化/历史回溯、**不做 Skills/MCP(本期不做)**、不反向写私有记忆库 |

**边界判据**:记忆的*内容与结构*归 context-keeper;*谁在什么时机被装上、被触发*归本产品;*跨项目用户规则与用户级装配*归本产品的 `~/.agents-group` 层。

**耦合关系**:context-keeper 是项目记忆的**默认 provider,不是硬依赖**——规则基座完全不依赖它;不装只是没有记忆功能,随时可补装。"默认 provider"仅指 context-keeper,**不做通用 provider 插件框架**。历史回溯(装它之前的会话回填)若要做,属 context-keeper 的可选功能,不在本仓库。

## 2. 核心设计决策

**D1 规则/记忆/用户级三层,AGENTS.md 是项目规则唯一源**

- `AGENTS.md` = 项目硬规则(构建、规范、禁止事项),执行器无关,提交进 Git;
- 记忆(进度、事实、经验)→ context-keeper 记录库;用户级规则 → `~/.agents-group`;
- 各执行器对 AGENTS.md 的**可达性必须显式打通**:

| 执行器 | 可达性 | 打通方式 |
|---|---|---|
| Codex | 原生读根→cwd 链 | 无需处理 |
| Claude Code | 默认"有 CLAUDE.md 就不读 AGENTS.md" | CLAUDE.md 内放 `@AGENTS.md` import(原生支持) |
| WorkBuddy | 无原生支持 | 用户级约定引导(§5) |

**D2 项目记忆 = context-keeper**:跨执行器连续性由"记忆在项目里 + 三家被同一 Skill 规则驱动"保证。

**D3 记忆跟仓库走(两个不同的东西,分开表述)**:**记忆内容**提交进 Git,随分支与 clone 同步;**装配状态**(入口块、Skill 安装)是本机状态,新机器、新 clone 或新 worktree 须重新 `enable-memory` 建立。

**D4 私有记忆只出不进**:各家自动记忆库是黑盒生成物,保持原样,不做互通枢纽,验收也不越权约束它们。

**D5 静态配置不算数**:一切安装/修复必须新会话验收(§6)。

**D6 单一 CLI**:三个子命令一个入口;Skill 外壳 + 脚本内核(§4.6)。

**D7 check 只读、enable 才写**:巡检/check 类命令零写入,一切补装与修复统一由用户发起或确认的 enable 执行。

## 3. 三执行器接入矩阵

| 维度 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 项目 Skill 目录 | `.agents/skills`、`.codex/skills` | `.claude/skills` | `.workbuddy/skills`(context-keeper 安装器均支持) |
| 自动入口落点 | 项目 `AGENTS.md`(bridge 已验收) | 项目 `CLAUDE.md`(bridge 已验收) | `.workbuddy/memory/MEMORY.md` 顶部(本仓库桥接,**待运行时验收**) |
| 项目模型 | CLI:cwd 为中心,根→cwd 逐级拼接 AGENTS.md | CLI:根常驻、子目录按需加载 | 工作台应用:**打开哪个文件夹哪个就是项目**,记忆只挂根、应用注入,无子目录概念 |
| 嵌套(子目录)规则 | 逐级链,近者优先 | 按需加载 | **盲区**:子目录文件不感知 |
| 指令预算 | 沿途 AGENTS.md 共享 32KiB | CLAUDE.md 建议 <200 行 | 未见公开上限 |
| 验收手段 | 复述当前指令链(官方推荐) | `/context`、`/memory` | 新会话口头验证 |
| 特有风险 | `AGENTS.override.md` 劫持整链 | 有 CLAUDE.md 不读 AGENTS.md | "重置记忆"清空入口 |

## 4. 编排命令

```
enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...] [--memory|--no-memory]
remove-memory [--project <Git根>]
check-memory  [--project <Git根>|--all]
```

### 4.1 两档安装、缺省行为与所有权

- **基座(规则互通,总是执行)**:项目根 `AGENTS.md` 骨架;CLAUDE.md 含 `@AGENTS.md` 引用;核对 WorkBuddy 用户级约定(§5)。零依赖。
- **记忆档(仅 `--memory`)**,按序四步,并区分四个状态(**源码可用 / Skill 已安装 / bridge 已装配 / 记录库已授权可用**):
  1. 调 context-keeper `install.py` 装 Skill(漂移检查在调用安装器**之前**由本工具完成——安装器只认标记块不认指纹);安装器预览返回 `approval_required` 时,即使退出码为 0 也不算安装完成;
  2. Codex/Claude 执行已验收 `--ensure-bridge`;
  3. WorkBuddy 桥接块(§5);
  4. **记录库授权**:走 context-keeper init 流程由用户确认记录库位置(默认 `docs/context-keeper/`,支持自定义),实际路径写入状态文件——**没有第四态,不得向记录库写入任何内容**(§4.2 存量整理也以此为前置)。
- **缺省 = 询问推荐**:检测 context-keeper 未就绪时,先说明必要性(不装就没有项目记忆/跨 Agent 接力),**用户同意即装,明确说不装才跳过**;`--no-memory` 是非交互的显式退出;**已就绪则直接装配,不再询问**。
- **用户选择持久化**:状态文件记录本项目记忆授权(yes/no);区分"检测到 provider 可用"与"本项目已授权启用记忆"——曾明确拒绝的项目,巡检只提示不反复追问。
- **所有权记账**:状态文件逐项记录每个入口/Skill 是**本工具创建**还是**复用已有**;`remove-memory` 只撤销本工具创建的对象,记录库本体永不触碰(记忆是项目资产,删除必须用户显式做)。
- 全部幂等:操作前查 Git 状态、备份、指纹漂移检测;读回校验;提示新会话验收。

### 4.2 存量整理(只搬运不加工,前置四态)

不做任何内容加工——不蒸馏、不改写;后续消化若需要,由 context-keeper 自身功能处理。**前置条件:§4.1 四态满足且记录库实际路径已知**;搬运目标是**实际路径**下的 `worklogs/`(遵守 Keeper 日志格式),不是假设的固定路径。

**项目维度**(根与子目录的 AGENTS.md、CLAUDE.md、CLAUDE.local.md):预览 → 用户逐类确认 → 执行。

1. 扫描分类:规则 / 记忆类 / 装配内容(@import、bridge);
2. 归位:规则合并进(同级)AGENTS.md,**冲突条目并列展示原文由用户裁定**;记忆类**原样搬运**为 legacy worklog(注明来源与日期);个人偏好留在 CLAUDE.local.md(gitignore);
3. **可见性披露**:迁移预览必须逐项展示来源、目标、**Git 可见性变化**——本地或被忽略文件的内容搬进仓库即扩大可见范围,须用户逐项确认;执行器专属指令与个人内容默认保留原地;
4. 瘦身:CLAUDE.md 只剩 `@AGENTS.md` + bridge 块;AGENTS.md 只剩规则。

**用户维度**(`~/.codex/AGENTS.md`、`~/.claude/CLAUDE.md`、`~/.workbuddy/MEMORY.md`):通用规则并入 `~/.agents-group/memories/MEMORY.md`;专属留下;人格内容(SOUL、USER 等)一律不动;冲突用户裁定;各文件只剩专属规则 + 公共源指针。**独立于 M1 单独执行**(§8)。

全程时间戳备份 + 迁移报告。

### 4.3 子目录政策

一句话:**子目录 AGENTS.md 只写"要求";所有记忆不分出处,只存一份在项目根 context-keeper 库,用文件名标明归属。**

- 存量子目录 CLAUDE.md:"要求"并入同目录 AGENTS.md;"记忆"按 §4.2 搬至记录库 worklogs;**搬空后保留仅含 `@AGENTS.md` 的薄入口,不直接删除**——"删除后 Claude 是否按需读同目录 AGENTS.md"未经运行时证明,待实际子目录任务验收后再决定能否删;
- 增量:在子目录工作产生的新记忆记入 `worklogs/<日期>-<子目录>-<主题>.md`,不在子目录建记忆文件;
- WorkBuddy 子目录盲区:**M1 明确接受**(不提供未经验证的读取规则);对它重要的子目录要求在根 AGENTS.md 留摘要;
- 理由:WorkBuddy 读不到子目录;Codex 32KiB 只够短规则;context-keeper 的查找建立在单一记录库上。**归属是标签,不是位置。**

### 4.4 Group 与 context-keeper 的安装顺序联动

原则:**单向编排**——Group 检测并编排 Keeper,Keeper 不感知 Group;所有命令幂等,缺什么补什么。

- **先 Group 后 Keeper**:周一只装基座;此后 `check` 检测到 Keeper 已就绪时**只报告"可装配"**;实际装配由用户运行 `enable-memory` 完成(同意即装,不再重复询问要不要装 Keeper 本身);基座不动;
- **先 Keeper 后 Group**:检测到项目已有 Keeper 痕迹(记录库/已装 Skill/bridge)→ 不重装,**接管纳管**:逐项校验并把已有对象记账为"复用"(非本工具创建),只补缺口(WorkBuddy 桥接、AGENTS.md 基座、`@AGENTS.md` 引用),提示存量整理;
- **纳管状态(项目内零新增文件)**:全部状态集中在本工具安装目录的 `registry.json`(键:项目主 checkout 绝对路径;值:记忆授权 yes/no、四态、执行器清单、入口指纹、所有权记账)。**项目内不建任何状态文件**——`.agents-group/` 项目目录归旧 `project_manage.py`,本工具完全不碰,状态互踩风险随之消除。registry 损坏时 `check` 可从现场(入口块、Skill、记录库)重建装配事实;记忆授权选择无法从现场重建,重新询问一次即可;
- **迁移门禁联动**:Keeper 命令返回"需要迁移"(退出码 3)时,本工具立即停止相关读写并转告用户走 Keeper 迁移流程,不绕过门禁。

### 4.5 后装 Agent 的纳入与触发链

**接入(幂等,两层)**:

- 用户级(一次性):核对原生入口(WorkBuddy:`~/.workbuddy/MEMORY.md`)→ 写两条约定(公共源指针 +"项目规则读 AGENTS.md")→ 对其自带存量做用户维度整理 → 新会话验收。复用 `~/.agents-group` 既有的"新执行器接入"约定;
- 项目级(逐项目):`enable-memory --agent <name>` 补装 Skill 与入口;`check-memory --all` 维护"已纳管项目 × 已接入执行器"矩阵,发现缺口**只提示**。

**触发链(根只有两个,不无限递归)**:

```
根 1:用户说话 —— 对任意已接入 Agent 说"装/检查/接入";
     用户随口提到未接入执行器 → SKILL.md 规则让 agent 主动建议
根 2:定时器 —— 任意调度机制(系统 cron 或用户已有调度器)每周跑
     check-memory --all(只读巡检)→ 发现缺口 → 通知用户 → enable 修复
```

group 不是常驻进程,不存在"装机即感知"。**check 类只读、可自动运行(D7);enable 类有写入,永远由用户发起或经确认执行。**不做 OS 级安装监听。

**项目发现**:`--all` 直接基于 `registry.json`(它同时是纳管状态本身,见 §4.4——项目内不放状态,巡检依据天然在项目外);巡检核对登记与实际,项目移动/删除/重 clone 失配即报告,记忆随 Git 在,装配须重新 enable。

**继承旧体系的自动覆盖**:本工具 Skill 外壳经现有同步体系投影到共享 Skill 目录(`~/.agents/skills` 等),任何读这些目录的新执行器自动获得工具能力;用户级入口与项目入口的写入保持一次确认。

### 4.6 形态、分发与跨平台

先分清两个时态:**运行时**(AGENTS.md、`@AGENTS.md`、context-keeper Skill 与 bridge)是纯文本与原生机制;**工具时**(本仓库编排逻辑)需要跨平台。

- **内核**:跨平台 Python 脚本,仅标准库(≥3.9,零 pip 依赖);
- **外壳**:SKILL.md 告诉 agent 何时、如何调用与验收——用户说人话,agent 负责翻译成命令;
- **安装**:仓库 clone 到家目录为唯一源(落位 `~/.agents-group/skills/agent-group-memory/`;过渡期沿用旧同步体系投影到各执行器 Skill 目录,M4 后由本产品用户级层自身承担),首次运行自装用户级指针;M4 起安装即创建 `~/.agents-group` 全套结构;
- **跨平台承诺收紧**:**M1 限定 macOS**(当前唯一已验证平台)。Windows/Linux 依赖上游安装策略——context-keeper 安装器使用目录 symlink 且拒绝现有复制目录,本工具**不自建第二套降级安装逻辑**;平台矩阵(安装/重装/卸载/失败恢复)留到 M2 按真实验收扩展。通用编码纪律先行:路径 `pathlib` + `Path.home()`、执行器路径表(含安装信号)、文件 UTF-8、子进程只调 Python 解释器。

### 4.7 目录结构

**仓库(即安装源)**:

```
agent-group-memory/
  README.md                # 现行规则,简短,不堆历史
  DESIGN.md                # 本设计
  SKILL.md                 # Skill 外壳:agent 何时、如何调用与验收
  scripts/
    agm.py                 # 单一 CLI(enable-memory / remove-memory / check-memory)
    agents.json            # 执行器路径表:各 OS 入口路径 + 安装信号
    registry.json          # 运行时生成:项目登记 + 纳管状态(集中项目外,--all 巡检依据)
  docs/
    history/               # 历史决策记录
  tests/
```

**家目录(安装后)**:落位 `~/.agents-group/skills/agent-group-memory/`,由现有同步体系投影到各执行器 Skill 目录;不另建顶层目录。

**项目内产物(每个纳管项目)**:

```
<项目>/                                   # 本工具在项目内零新增状态文件(状态集中本机 registry)
  AGENTS.md                              # 规则唯一源(含 context-keeper bridge 块)
  CLAUDE.md                              # @AGENTS.md 引用 + bridge 块
  .workbuddy/memory/MEMORY.md            # 顶部 WorkBuddy 桥接块(待验收能力)
  docs/context-keeper/                   # 记录库(context-keeper 管理,提交进 Git;位置以 init 确认为准)
```

**用户级记忆结构(保留 memories/ 目录,定为"索引 + 主题文件")**:`memories/MEMORY.md` 只做**索引**——一主题一行、附链接,常驻注入,上限沿用 Claude 官方量化值 ≤200 行 / 25KB;记忆细节写入 `memories/<主题>.md`,由索引引用、按需读取,不占常驻预算。将来记忆增多,动作是**加主题文件,不是加长索引**(与 Claude auto memory 的"MEMORY.md 索引 + 主题文件"同构);`references/` 继续放操作手册类,与记忆分开放。此结构升级独立于 M1,由用户决定何时执行(当前单文件可先直接当索引用)。

## 5. WorkBuddy 桥接(上游已接管配置,待运行时验收)

M3 已将 WorkBuddy 桥接交由 context-keeper 安装器管理。AGM 从上游安装器读取模板,在事务内完成漂移检查与预写,再调用上游 install 和 `--ensure-bridge --workbuddy` 验证不变:

- **落点**:项目 `.workbuddy/memory/MEMORY.md` 顶部(WorkBuddy 唯一原生项目级挂载点;其每日日志机制照旧);
- **内容**:复用 context-keeper BRIDGE 规则语义(无项目聊天边界、限量历史检索触发、自然节点记录、追加式日志、事实边界、**迁移门禁:退出码 3 即停止读写**),以 `<!-- context-keeper:workbuddy:start/end -->` 标记块写入;
- **单一真源**:上游 `scripts/install.py` 持有模板;本仓库已删除私有模板。三处既有块与上游模板字节级兼容,marker 识别支持幂等更新,不新增重复块;接管证据见 `docs/acceptance/m3/`。WorkBuddy 真机新会话验收仍由用户选择,不以配置接管代替;
- **用户级配合**:`~/.workbuddy/MEMORY.md` 现行"项目规则唯一来源是 AGENTS.md"约定**保留**(它是 D1 可达性的一环),只**追加**记忆条款:"项目记忆用 context-keeper 记录库,由项目桥接块驱动"。

## 6. 验收协议(三执行器接力闭环)

前置:记录库已授权(§4.1 第四态)。目标是**证明"换执行器不失忆"**,不是各入口各自为政的可达性:

**正向闭环(在获授权的测试记录库上)**:

1. Codex 新会话:写入一条唯一测试事实(含特定标记与一个待办),确认落库;
2. Claude Code 新会话:**用普通续接请求**(不提示任何入口与记忆位置)恢复该事实并更新待办;
3. WorkBuddy 新会话:同样普通续接,恢复、更新并追加一条;
4. Codex 再开新会话,核对三轮累积结果完整。

全程保存证据:每次读写的来源路径、记录库实际变更、会话标识。

**负向用例**:

- "禁止保存"指令后,确认无新记录落库;
- 模拟迁移门禁触发(旧版目录结构),确认三家都停止读写并提示,不绕过门禁。

**入口可达探针(辅助,不替代闭环)**:Codex 复述当前指令链;Claude `/context`;WorkBuddy 口头验证。

**边界**:验收目标是共享库被正确读写;**不要求关闭、清空或约束各执行器自己的自动记忆**(D4,黑盒不可控)。一切验收必须使用新会话。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| `AGENTS.override.md` 劫持 Codex 整链 | 禁用;check 检测存在即告警 |
| Claude 有 CLAUDE.md 不读 AGENTS.md | 入口必进 CLAUDE.md;`@AGENTS.md` 引用 check 校验、enable 幂等补装 |
| WorkBuddy"重置记忆"清空入口 | 入口块带标记块与指纹;check 报告丢失,**enable 幂等重装**(check 不写) |
| registry 单点丢失/损坏 | 状态集中本机 `registry.json`(项目内零新增文件,不碰旧管理器目录);check 可从现场重建装配事实,授权选择重询一次 |
| bridge 块漂移/手改 | 本工具调用安装器**之前**自做指纹漂移检查(安装器只认标记块);漂移即停,人工核对 |
| 卸载误伤 | 所有权记账;remove 只撤销本工具创建的对象 |
| 项目规则双写漂移 | 规则唯一源 AGENTS.md;CLAUDE.md 只放引用+bridge;check 对非引用规则增长告警 |
| 32KiB / 200 行预算 | 入口块体积由模板控制;记忆永不进规则文件 |
| WorkBuddy 子目录盲区 | M1 明确接受;根 AGENTS.md 摘要重要子目录要求 |
| 子目录薄入口是否可删未证明 | 先保留仅含 @AGENTS.md 的薄入口;实测后决定 |
| 存量搬运扩大可见性(隐私) | 预览逐项展示 Git 可见性变化,用户逐项确认 |
| 跨平台未验收 | M1 限定 macOS;不自建第二套安装逻辑;M2 平台矩阵 |
| 双重入口打架(WorkBuddy 旧约定 vs 桥接) | §5 约定追加式改写;check 检测旧约定残留 |

## 8. 落地路线

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1 dogfood(**macOS、单仓库、三执行器接力闭环**) | 本仓库启用:基座 + 记忆档(含记录库授权)+ WorkBuddy 桥接 + 用户级约定追加;存量只做**一份已批准、可公开的样本** | §6 正向闭环 + 两个负向用例 |
| M1.5(独立) | 用户级全面整理;(如需)memories/ 升级为"索引 + 主题文件"结构 | 用户逐项确认的迁移报告 |
| M2 工具化 | 单一 CLI + 执行器路径表 + registry;平台矩阵(安装/重装/卸载/失败恢复,macOS 优先) | knowwind、poster-fit 复制,幂等重装通过 |
| M3 上游回传(工作区实现) | 上游已接管 WorkBuddy 模板/install/ensure;本仓库改读上游模板并调用安装器,私有模板已删除 | 旧块字节兼容、无双入口、三项目只读 check;证据见 docs/acceptance/m3。未 commit/push,真机新会话验收可选 |
| M4 用户级层产品化 | **安装即建 `~/.agents-group`**(公共源结构:memories 索引+主题、references、skills、mcp)+ 用户级入口指针装配 + **旧手工实现迁移替代**:内容(memories/references/skills/mcp)原样迁入,旧脚本(manage/sync/project_manage)退役归档;替代期间新旧并存、逐项切换 | 迁移报告逐项确认;三执行器用户级指针新会话验收 |
| 后续 | 项目级 Skills/MCP 管理纳入(旧 project_manage 职责);其余执行器按同模式逐家接入 | — |

## 9. 对既有 `~/.agents-group` 实现的借鉴与简化

既有实现(manage/sync/project_manage 等约 900 行 Python + 约 500 行测试)是本仓库前身。

**直接借鉴**:标记块+指纹+幂等(冲突/漂移即拒绝);写后读回+快照回滚(恢复失败报错并保留现场);操作前时间戳备份与 manifest 可逆恢复;进程锁;信任登记放项目外(registry 的先例);不自动吸收原生安装、无密钥纪律(本期虽不管理 Skills/MCP,纪律保留);"静态配置不算数"与自然语言操作约定;配单元测试。

**明确简化**:README 只留现行规则,历史决策进 `docs/history/`(旧实现 README 混成百来行操作日志);**单一 CLI 三子命令**(旧实现 5 个脚本);纳管状态收敛为本工具目录内**单一 registry**(旧实现五六套状态文件并存;新版项目内零状态文件);**执行器路径表**替代硬编码元组;入口块带标记块与指纹、**check 报告 + enable 幂等重装**(旧实现指针纯手编,重置即静默丢失);验收命令化即 `check-memory`(旧实现靠 README 散文纪律);备份与临时物带保留期限,如 90 天提醒清理。

---

附:调研依据——Codex 官方文档(memories、agents-md)、Claude Code 官方 memory 文档、WorkBuddy 官方设置文档与三层记忆机制文章;本机实测 `~/.codex/memories/`、`~/.claude/projects/`、`~/.workbuddy/`、poster-fit `.workbuddy/memory/`;context-keeper 仓库源码(SKILL.md、install.py 的 BRIDGE 模板与安装限制);`~/.agents-group` 全部脚本与 README 评审;巴克队长对 v1.0 的评审结论(10 项,已全部吸收:v1.1)。
