# agent-group-memory 设计方案

多 Agent 跨执行器共享记忆:**不重复造轮子**。项目规则统一到项目根 `AGENTS.md`,项目记忆直接复用 context-keeper;本仓库只做跨执行器的互通与编排,并定义清楚三套系统的分工边界。

- 版本:v1.0(2026-10-29,定稿重整)
- 覆盖执行器:**Codex、Claude Code、WorkBuddy**
- 历史沿革:v0.1 曾设计自建项目记忆(journal/索引/蒸馏管道),已废弃——该能力由 context-keeper 承担;v0.2 起定位为编排层

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

用户级互通已由 `~/.agents-group` 解决;项目级是本方案的范围。

### 1.2 三套系统分工边界(核心)

| 系统 | 职责 | 不做什么 |
|---|---|---|
| `~/.agents-group`(已建成) | 跨项目、跨执行器的用户级公共规则、共享 Skills/MCP | 不碰任何项目内部 |
| **context-keeper**([github.com/vincent4j/context-keeper](https://github.com/vincent4j/context-keeper),项目记忆运行时,独立产品) | 项目记忆的一切:记录库(`docs/context-keeper/`)、保存/继续/查找、按证据自我进化、Skill 安装器、Codex/Claude 已验收 bridge | 不感知 Group、不做跨执行器编排、不管用户级 |
| **agent-group-memory**(本仓库) | 编排:装/拆/检查、入口打通、WorkBuddy 桥接与验收、存量整理、联动 | 不存记忆、不定义记忆结构、不做蒸馏/进化/历史回溯、不反向写私有记忆库 |

**边界判据**:记忆的*内容与结构*归 context-keeper;*谁在什么时机被装上、被触发*归本仓库;*跨项目用户规则*归 `~/.agents-group`。

**耦合关系**:context-keeper 是项目记忆的**默认 provider,不是硬依赖**——规则基座完全不依赖它;不装只是没有记忆功能,随时可补装。历史回溯(装它之前的会话回填)若要做,属 context-keeper 的可选功能,不在本仓库。

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

**D3 记忆跟仓库走**:记录库提交进 Git,worktree 天然继承、多设备天然同步。

**D4 私有记忆只出不进**:各家自动记忆库是黑盒生成物,保持原样,不做互通枢纽。

**D5 静态配置不算数**:一切安装/修复必须新会话验收(§6)。

**D6 单一 CLI**:吸取既有实现教训(§9),三个子命令一个入口;Skill 外壳 + 脚本内核(§4.6)。

## 3. 三执行器接入矩阵

| 维度 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 项目 Skill 目录 | `.agents/skills`、`.codex/skills` | `.claude/skills` | `.workbuddy/skills`(context-keeper 安装器均支持) |
| 自动入口落点 | 项目 `AGENTS.md`(bridge 已验收) | 项目 `CLAUDE.md`(bridge 已验收) | `.workbuddy/memory/MEMORY.md` 顶部(本仓库桥接,待验收) |
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

### 4.1 两档安装与缺省行为

- **基座(规则互通,总是执行)**:项目根 `AGENTS.md` 骨架;CLAUDE.md 含 `@AGENTS.md` 引用;核对 WorkBuddy 用户级约定(§5)。零依赖。
- **记忆档(仅 `--memory`)**:调 context-keeper `install.py` 装 Skill → Codex/Claude 执行已验收 `--ensure-bridge` → 写 WorkBuddy 桥接块(§5)。
- **缺省 = 询问推荐**:检测 context-keeper 未就绪时,先说明必要性(不装就没有项目记忆/跨 Agent 接力),**用户同意即装,明确说不装才跳过**;`--no-memory` 是非交互的显式退出;**已就绪则直接装配,不再询问**。
- 全部幂等:操作前查 Git 状态、备份、指纹漂移检测;读回校验;提示新会话验收。
- `remove-memory` 只移除入口块与 Skill 链接,**不动记录库本体**(记忆是项目资产,删除必须用户显式做)。

### 4.2 存量整理(首次启用,项目级 + 用户级,只搬运不加工)

不做任何内容加工——不蒸馏、不改写;后续消化若需要,由 context-keeper 自身功能处理。

**项目维度**(根与子目录的 AGENTS.md、CLAUDE.md、CLAUDE.local.md):预览 → 用户逐类确认 → 执行。

1. 扫描分类:规则 / 记忆类 / 装配内容(@import、bridge);
2. 归位:规则合并进(同级)AGENTS.md,**冲突条目并列展示原文由用户裁定**;记忆类**原样搬运**为 `worklogs/legacy` 日志(注明来源与日期);个人偏好留在 CLAUDE.local.md(gitignore,不进团队可见文件);
3. 瘦身:CLAUDE.md 只剩 `@AGENTS.md` + bridge 块;AGENTS.md 只剩规则。

**用户维度**(`~/.codex/AGENTS.md`、`~/.claude/CLAUDE.md`、`~/.workbuddy/MEMORY.md`):

1. 分类:跨执行器通用规则 / 执行器专属 / 人格与私人内容;
2. 归位:通用规则并入 `~/.agents-group/memories/MEMORY.md`(唯一源);专属留下;人格内容(SOUL、USER 等)一律不动;冲突用户裁定;
3. 瘦身:各用户级文件只剩专属规则 + 公共源指针。

全程时间戳备份 + 迁移报告。

### 4.3 子目录政策

一句话:**子目录 AGENTS.md 只写"要求";所有记忆不分出处,只存一份在项目根 context-keeper 库,用文件名标明归属。**

- 存量子目录 CLAUDE.md:"要求"并入同目录 AGENTS.md;"记忆"按 §4.2 原样搬至 `docs/context-keeper/worklogs/<日期>-legacy-<子目录>.md`;搬空即删(Claude 会落到按需读同目录 AGENTS.md);
- 增量:在子目录工作产生的新记忆记入 `worklogs/<日期>-<子目录>-<主题>.md`,不在子目录建记忆文件;
- 理由:WorkBuddy 读不到子目录;Codex 32KiB 只够短规则;context-keeper 的查找建立在单一记录库上。**归属是标签,不是位置。**

### 4.4 Group 与 context-keeper 的安装顺序联动

原则:**单向编排**——Group 检测并编排 Keeper,Keeper 不感知 Group;所有命令幂等,缺什么补什么。

- **先 Group 后 Keeper**:周一只装基座;此后任何 `enable/check` 检测到 Keeper 已就绪,**直接装配记忆档,不询问**(询问只用于"装不装 Keeper"的决策);基座不动;
- **先 Keeper 后 Group**:检测到项目已有 Keeper 痕迹(记录库/已装 Skill/bridge)→ 不重装,**接管纳管**,逐项校验,只补缺口(WorkBuddy 桥接、AGENTS.md 基座、`@AGENTS.md` 引用),提示存量整理;
- **纳管状态**: `<项目>/.agents-group/state.json`(gitignore)记录档位、执行器清单、入口指纹;check 对照检测漂移与缺口。

### 4.5 后装 Agent 的纳入与触发链

**接入(幂等,两层)**:

- 用户级(一次性):核对原生入口(WorkBuddy:`~/.workbuddy/MEMORY.md`)→ 写两条约定(公共源指针 +"项目规则读 AGENTS.md")→ 对其自带存量做用户维度整理 → 新会话验收。复用 `~/.agents-group` 既有的"新执行器接入"约定;
- 项目级(逐项目):`enable-memory --agent <name>` 补装 Skill 与入口;`check-memory --all` 维护"已纳管项目 × 已接入执行器"矩阵,发现缺口提示。

**触发链(根只有两个,不无限递归)**:

```
根 1:用户说话 —— 对任意已接入 Agent 说"装/检查/接入";
     用户随口提到未接入执行器 → SKILL.md 规则让 agent 主动建议
根 2:定时器 —— 任意调度机制(系统 cron 或用户已有调度器)每周跑
     check-memory --all(只读巡检)→ 发现缺口 → 通知用户
```

group 不是常驻进程,不存在"装机即感知";**check 类只读可自动运行,enable 类有写入,永远由用户发起或经确认执行**。不做 OS 级安装监听(常驻、权限、跨 OS 复杂度,与收益不成比例)。

**继承旧体系的自动覆盖**:Skill 外壳经现有同步体系投影到共享 Skill 目录(`~/.agents/skills` 等),任何读这些目录的新执行器**自动获得工具能力,无需逐家安装**——这是旧体系"后装 Agent 自动纳入"的真实机制(旧 README 明确:用户级指针仍需显式接入,不因安装在本机就自动读取);用户级入口与项目入口的写入保持一次确认。

### 4.6 形态、分发与跨 OS

先分清两个时态:**运行时**(AGENTS.md、`@AGENTS.md`、context-keeper Skill 与 bridge)全是纯文本与原生机制,零 OS 依赖;**工具时**(本仓库编排逻辑)才需要跨 OS。因此:

- **内核**:跨平台 Python 脚本,仅标准库(≥3.9,零 pip 依赖);
- **外壳**:SKILL.md 告诉 agent 何时、如何调用与验收——用户说人话("给这个项目装记忆/检查装配"),agent 负责翻译成命令;
- **安装**:仓库 clone 到家目录为唯一源,Skill 入口走现有同步体系,首次运行自装用户级指针;
- **跨 OS 策略**:路径一律 `pathlib` + `Path.home()`;**执行器路径表**(macOS/Linux/Windows 分列,含"安装信号"用于执行器发现;Windows 下 WorkBuddy `.workbuddy` 位置实测后入表,列为验收项);文件一律 UTF-8;桥接块直接写入**不依赖 symlink**(确需链接的场景在 Windows 降级为复制+指纹);子进程只调 Python 解释器。已知联动注意:context-keeper 安装器若在 Windows 依赖 symlink,属其仓库议题。

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
  templates/
    workbuddy-bridge.md    # WorkBuddy 桥接模板(回传上游后删除)
  docs/
    history/               # 历史决策记录
  tests/
```

**家目录(安装后)**:仓库经现有 `manage.py install-skill` 纳入公共源,落位 `~/.agents-group/skills/agent-group-memory/`,由同步体系投影到各执行器 Skill 目录;**不另建顶层目录**。

**项目内产物(每个纳管项目)**:

```
<项目>/
  AGENTS.md                    # 规则唯一源(含 context-keeper bridge 块)
  CLAUDE.md                    # @AGENTS.md 引用 + bridge 块
  .workbuddy/memory/MEMORY.md # 顶部 WorkBuddy 桥接块
  .agents-group/state.json     # 纳管状态(gitignore)
  docs/context-keeper/         # 记忆本体(context-keeper 管理,提交进 Git)
```

**用户级记忆路径(建议,待用户决定)**:现行 `~/.agents-group/memories/MEMORY.md` 的目录层目前只装一个文件;用户级哲学是"单一短文件 + 细节下沉 `references/`",按此哲学 memories/ 目录**将来不会也不需要再放东西**(需要拆多文件时,正确动作是压缩或下沉 references/,不是加文件)。因此建议扁平化为 `~/.agents-group/MEMORY.md`,与 README、references/ 平级,指针路径更短;该改动涉及旧体系三处用户级指针的同步更新,列入存量整理,由用户决定是否执行。

## 5. WorkBuddy 桥接(本仓库主要新增工作)

context-keeper 的安装器对 WorkBuddy 刻意停写("自动入口尚未完成运行时验证"),本仓库补齐:

- **落点**:项目 `.workbuddy/memory/MEMORY.md` 顶部(WorkBuddy 唯一原生项目级挂载点;其每日日志机制照旧);
- **内容**:复用 context-keeper BRIDGE 规则语义(无项目聊天边界、限量历史检索触发、自然节点记录、追加式日志、事实边界),以 `<!-- context-keeper:workbuddy:start/end -->` 标记块写入;
- **终局是消失**:验收通过后,模板与证据回传 context-keeper,解除其安装器限制;本仓库删除私有模板,不留第二真源;
- **用户级配合**:`~/.workbuddy/MEMORY.md` 现行"项目规则唯一来源是 AGENTS.md"约定**保留**(它是 D1 可达性的一环),只**追加**记忆条款:"项目记忆用 context-keeper 记录库,由项目桥接块驱动"。

## 6. 验收协议(双方向,新会话)

1. **读/触发**:给出"继续上次工作"类指令,应触发 context-keeper 继续路由并恢复进度:
   - Codex:`codex "Summarize the current instructions."` 复述含入口规则;
   - Claude:新会话 `/context` 确认 CLAUDE.md 加载;
   - WorkBuddy:新会话问"读本项目记忆入口"应按桥接块行动;
2. **写/沉淀**:制造一次自然收尾节点(明确纠正或阶段完成),检查新记录落在 `docs/context-keeper/worklogs/` 而非任何私有记忆文件;
3. 运行中的会话不生效,须重开;三家均无指令缓存。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| `AGENTS.override.md` 劫持 Codex 整链 | 禁用;check 检测存在即告警 |
| Claude 有 CLAUDE.md 不读 AGENTS.md | 入口必进 CLAUDE.md;`@AGENTS.md` 引用 check 校验、enable 幂等补装 |
| WorkBuddy"重置记忆"清空入口 | 入口块带标记块与指纹;check 检测丢失,幂等重装 |
| bridge 块漂移/手改 | 指纹校验,漂移即停,人工核对 |
| 项目规则双写漂移 | 规则唯一源 AGENTS.md;CLAUDE.md 只放引用+bridge;check 对非引用规则增长告警 |
| 32KiB / 200 行预算 | 入口块体积由模板控制;记忆永不进规则文件 |
| WorkBuddy 子目录盲区 | 根 AGENTS.md 摘要重要子目录要求,或显式接受边界 |
| 双重入口打架(WorkBuddy 旧约定 vs 桥接) | §5 约定追加式改写;check 检测旧约定残留 |
| 蒸馏产物/记忆带出隐私 | 存量整理只搬运不加工;写入纪律沿用 context-keeper(不存凭据) |

## 8. 落地路线

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1 dogfood | 本仓库自身启用:基座 + 记忆档 + WorkBuddy 桥接 + 用户级约定追加;存量整理走一遍 | §6 双探针 ×3 |
| M2 工具化 | 单一 CLI(enable/remove/check)+ 执行器路径表 + state.json | knowwind、poster-fit 复制,幂等重装通过 |
| M3 上游回传 | WorkBuddy 桥接模板与验收证据回传 context-keeper,解除其限制;本仓库删私有模板 | context-keeper 原生安装 WorkBuddy 入口成功 |
| 后续 | 其余执行器按同模式逐家接入(路径表加行 + 桥接验收 + 回传) | — |

## 9. 对既有 `~/.agents-group` 实现的借鉴与简化

既有实现(manage/sync/project_manage 等约 900 行 Python + 约 500 行测试)是本仓库前身。

**直接借鉴**:标记块+指纹+幂等(冲突/漂移即拒绝);写后读回+快照回滚(恢复失败报错并保留现场);操作前时间戳备份与 manifest 可逆恢复;进程锁;信任登记放项目外;不自动吸收原生安装、MCP 无密钥约束;"静态配置不算数"与自然语言操作约定(不说范围先问两个维度);配单元测试。

**明确简化**:README 只留现行规则,历史决策进 `docs/history/`,一次性迁移工具用完归档(旧实现 README 混成百来行操作日志);**单一 CLI 三子命令**(旧实现 5 个脚本各管一段);纳管状态收敛为**一个 state 文件**(旧实现五六套状态文件并存);**执行器路径表**替代硬编码元组(旧实现接新执行器要改代码);入口块带标记块与指纹、check 幂等重装(旧实现指针纯手编,重置即静默丢失);验收命令化即 `check-memory`(旧实现靠 README 散文纪律);备份与临时物带保留期限,如 90 天提醒清理(旧实现 tmp/、backups/ 只进不出)。

---

附:调研依据——Codex 官方文档(memories、agents-md)、Claude Code 官方 memory 文档、WorkBuddy 官方设置文档与三层记忆机制文章;本机实测 `~/.codex/memories/`、`~/.claude/projects/`、`~/.workbuddy/`、poster-fit `.workbuddy/memory/`;context-keeper 仓库源码(SKILL.md、install.py 的 BRIDGE 模板与安装限制);`~/.agents-group` 全部脚本与 README 评审。
