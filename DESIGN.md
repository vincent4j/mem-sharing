# agent-group-memory 设计方案

多 Agent 跨执行器共享记忆:让 Codex、Claude Code、WorkBuddy 在同一个项目里共用一份记忆,换工具不失忆。

- 版本:v0.1(2026-10-29)
- 状态:设计定稿,待 M1 试点验证
- 覆盖执行器:**Codex、Claude Code、WorkBuddy**(ZCode、DeepSeek Harness 暂不覆盖,见 §10)

---

## 1. 问题

同一个人在同一个项目上交替使用多个 Agent。每个 Agent 的记忆各存一处:

| 层级 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 用户级 | `~/.codex/memories/`(自动)+ `~/.codex/AGENTS.md` | `~/.claude/CLAUDE.md` + `~/.claude/projects/*/memory/`(自动) | `~/.workbuddy/MEMORY.md` + 云端画像(自动) |
| 项目级 | 项目根 `AGENTS.md`(指令链) | `CLAUDE.md` 系列 + auto memory 目录 | `.workbuddy/memory/`(MEMORY.md + 每日日志) |

结果:用 Codex 攒下的项目经验,Claude 看不见;WorkBuddy 蒸馏的结论,Codex 看不见。用户级互通已由 `~/.agents-group` 解决(公共源 + 各家原生入口指针);**项目级记忆互通是本方案要补的缺口**。

另外,三家都有"从会话中自动提取/蒸馏记忆"的原生能力,但这些产物全部落在各自私有存储里。共享库目前没有任何自动写入能力——这是本方案要建设的**蒸馏管道**(§7)。

## 2. 目标与非目标

**目标**

1. 项目级记忆单一公共源:一个项目一份,三家 Agent 共读共写。
2. 指针化接入:各 Agent 原生入口只放极短指针,不存记忆本体。
3. 蒸馏能力:让共享库也能像各家原生记忆一样,从会话中提取、压缩记忆——分三阶段建设(§7)。
4. 记忆跟着仓库走:提交进 Git,worktree 天然继承、多设备天然同步。

**非目标**

- 不替代、不关闭任何一家的原生自动记忆;只做单向收割。
- 不反向写入任何私有记忆库(`~/.codex/memories/`、`~/.claude/projects/*/memory/`、WorkBuddy 云端)。
- 不做云端服务,全部本地 + Git。
- ZCode、DeepSeek Harness 本期不接入(扩展方法见 §5.4,照抄指针模式即可)。

## 3. 总体架构

```
┌────────────────────────────────────────────────────────────┐
│ 第 1 层:用户级(已建成,~/.agents-group,不在本仓库改动范围)│
│   memories/MEMORY.md 短规则 + references/ + skills/ + mcp/  │
│   指针已通:~/.codex/AGENTS.md、~/.claude/CLAUDE.md(@)、    │
│            ~/.workbuddy/MEMORY.md                            │
├────────────────────────────────────────────────────────────┤
│ 第 2 层:项目级共享源(本方案核心)                          │
│                                                            │
│   <项目根>/.agents-group/memories/                          │
│     PROJECT-MEMORY.md   ← 蒸馏后的稳定结论索引(常驻注入)  │
│     journal/YYYY-MM-DD.md ← 每日追加日志(原始事实,按需)  │
│     references/*.md     ← 长参考(按需)                    │
│   (全部提交进 Git)                                         │
│                                                            │
│   指针块(§6):项目根 AGENTS.md(Codex)                    │
│              项目根 CLAUDE.md(Claude Code)                │
│              项目 .workbuddy/memory/MEMORY.md(WorkBuddy)  │
├────────────────────────────────────────────────────────────┤
│ 第 3 层:蒸馏管道(§7,本方案新建能力)                      │
│                                                            │
│   会话转录(三家私有)→ distill → journal → compact → 索引 │
│   自蒸馏(会话内 agent 自记)作为零基建补充                 │
└────────────────────────────────────────────────────────────┘
```

设计原则(三家官方实践 + 已验证经验):

1. **单一公共源**:每个范围内记忆只有一份,永不双写;各原生入口只放指针。
2. **间接层规避注入预算**:Codex 指令链全局默认 32KiB 硬上限;记忆本体走文件按需读取,不占链。AGENTS.md/CLAUDE.md 里的指针 ≤5 行。
3. **记忆跟着仓库走**(Claude auto memory 的仓库键控同款思路,更彻底:连跨设备都靠 Git):这也解决了 Paseo worktree 场景——gitignore 的记忆文件只存在于单个 worktree,会分叉丢失。
4. **日志→蒸馏生命周期(借鉴 WorkBuddy,本方案记忆管理的主机制)**:写入与沉淀分离——会话中随手追加当日志(`journal/YYYY-MM-DD.md`,append-only、不要求精炼、零心理负担),日志满约 30 天后按主题蒸馏成稳定结论进 `PROJECT-MEMORY.md` 索引并删除过期碎片。原始积累与策展知识分层,各自有明确的生命周期。
5. **私有记忆只出不进**:各家自动记忆是黑盒生成物(Codex 文档原话 "generated state"),只做单向收割,不做互通枢纽。
6. **静态文件不算数,新会话验收**(§8)。

## 4. 三执行器现状矩阵(调研结论,标注实测)

| 维度 | Codex | Claude Code | WorkBuddy |
|---|---|---|---|
| 用户级手写入口 | `~/.codex/AGENTS.md`(已放公共源指针) | `~/.claude/CLAUDE.md`(@import 公共源) | `~/.workbuddy/MEMORY.md`(已有"项目规则走 AGENTS.md"约定,M1 需改写,见 §9) |
| 项目级原生入口 | 项目根 `AGENTS.md`,Git 根→cwd 逐级拼接,近者优先 | 项目根 `CLAUDE.md`(提交)/`CLAUDE.local.md`(个人,gitignore)/`.claude/rules/`;子目录文件按需加载 | `.workbuddy/memory/MEMORY.md` + 每日日志 `YYYY-MM-DD.md` |
| AGENTS.md 态度 | 原生主入口 | **默认"无 CLAUDE.md 才读 AGENTS.md"**;不读 `AGENTS.override.md`/`AGENTS.local.md` | 靠用户级记忆约定引导读写(实测有效) |
| 原生自动记忆 | `~/.codex/memories/` 全局库,条目按 `applies_to: cwd=绝对路径` 标注;后台小模型空闲时抽取;每会话 `/memories` 开关 | `~/.claude/projects/<repo>/memory/`,按 git 仓库键控(同仓库 worktree 共享);MEMORY.md 索引 + 主题文件;开场注入索引前 200 行/25KB | 云端画像(自动)+ 本地日志 30 天自动蒸馏进 MEMORY.md |
| 会话转录(蒸馏原料) | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`(实测含 cwd 元数据) | `~/.claude/projects/<项目slug>/*.jsonl`(实测) | `~/.workbuddy/sessions/<uuid>/`(实测存在,格式 M3 逆向) |
| 注入预算 | 指令链默认 32KiB(`project_doc_max_bytes`) | CLAUDE.md 建议 <200 行;auto memory 索引 200 行/25KB 强制 | 未见公开上限 |
| 写前备份 | 记忆库自带 git | — | 记忆文件自动 `.bak`(实测) |
| 验收手段 | 让它复述当前指令链 | `/context`(列出已加载文件)、`/memory` | 新会话口头验证(无官方探针) |

## 5. 项目级记忆规范

### 5.1 目录布局(全部提交进 Git)

```
<项目根>/
  .agents-group/
    memories/
      PROJECT-MEMORY.md     # 蒸馏后的稳定结论索引:一主题一节,每条 ≤2 行,总计 ≤200 行 / 25KB
      journal/
        2026-10-29.md       # 每日追加日志,append-only,会话中随手记,是记忆写入的主通道
      references/           # 长参考文档(部署手册、领域笔记),按需读取
```

- **journal 是主通道**:agent 干活过程中把事实、决策、踩坑随手追加进当天日志——**不要求精炼、不怕碎片、不挑时机**,记的成本降到最低(这是 WorkBuddy 机制的核心:先把原始积累无痛存下来)。
- **条目必须带来源头(session 维度记忆的载体)**:

  ```markdown
  ## 14:30 重构会话记忆接口(source: codex, task: session-api-v2)
  - 决定:journal 条目统一带来源头,新会话先读索引 + 近 3 天日志
  - 溯源:Codex 转录 ~/.codex/sessions/2026/10/26/rollout-xxx.jsonl
  ```

  `source` 标明哪个执行器产生,`task` 是任务标识,溯源行给原始会话文件路径——任何执行器都能回挖完整上下文。跨执行器的会话连续性靠它,而不是靠读取彼此的私有记忆库。
- **接手规则**:会话开始先读索引;任务是接手近期工作时,另读最近 3 天 journal。
- **索引只放蒸馏产物**:PROJECT-MEMORY.md 的条目来自 compact 蒸馏(§7.2),平时不直接往里堆,避免膨胀。
- 体积纪律(采纳 Claude Code 官方量化上限):索引 ≤200 行/25KB;超限触发 compact,不是删内容,是蒸馏进 references/ 或压缩措辞。
- 索引条目格式:`- <主题>: <结论一句话>(journal:2026-10-29)`——索引可独立读懂,细节可回溯日志。
- 私人层(可选,后置):`PROJECT-MEMORY.local.md` + `.gitignore`,放不便进仓库的个人偏好;默认不启用,有明确需要再开(CLAUDE.local.md 同款定位,且同样有 worktree 局限)。

### 5.2 写入纪律(写进指针块,防膨胀)

不记录以下内容(Claude auto memory 同款原则):

- 可从代码/现有文档直接推导的;
- 已在 AGENTS.md/CLAUDE.md/仓库文档里的;
- 密钥、令牌、凭据、个人隐私。

### 5.3 Git 策略

- 共享记忆**提交进仓库**:worktree 从分支继承,合并时自然汇合;多设备靠 Git 同步。
- 提交习惯:记忆变更与代码变更可分开提交,commit message 用 `memory(<项目>): <摘要>`。

### 5.4 新执行器扩展方法(本期不实施)

核对其实际支持的项目级入口文件 → 在该文件放同款指针块 → 新会话验收读写两个方向。接入前先读 §4 矩阵补一行调研。

## 6. 指针块规范

### 6.1 统一模板(标记块机制沿用 `project_manage.py` 的 begin/end 约定)

```markdown
<!-- agents-group-memory:begin -->
- 任务开始先读并遵守 `.agents-group/memories/PROJECT-MEMORY.md`(读不到须说明);接手近期工作时另读 `journal/` 最近日志,长细节按需读 `references/`。
- 项目级事实/决策/踩坑随手追加到 `.agents-group/memories/journal/当日.md`(无则新建,不要求精炼);任务收尾前确认当天日志已覆盖本次关键结论。
- 用户明确要求长期记住的约定,或已验证的稳定结论,才写入 PROJECT-MEMORY.md(一主题一条;超 200 行先按主题压缩)。不写本文件、不写任何 Agent 原生记忆文件。
- 不记:可从代码推导的、已在仓库文档中的、密钥/凭据/隐私。
<!-- agents-group-memory:end -->
```

### 6.2 每家落点与注意

| 执行器 | 落点 | 注意 |
|---|---|---|
| Codex | 项目根 `AGENTS.md` | 占 32KiB 链预算,指针 ≤5 行;**绝不使用** `AGENTS.override.md`(会劫持整个 AGENTS.md,且 Claude 不读它) |
| Claude Code | 项目根 `CLAUDE.md` | 有 CLAUDE.md 时默认不读 AGENTS.md → 必须单独放;不要用 `.claude/rules/`(那是原生规则层,保持单一指针点) |
| WorkBuddy | 项目 `.workbuddy/memory/MEMORY.md` 顶部 | 该文件原生加载;其每日日志机制照旧运行,不冲突 |

### 6.3 安装/卸载

- `init-memory` 子命令:校验目标文件无漂移 → 备份 → 幂等写入标记块 → 读回校验。安装前检测并告警:项目根存在 `AGENTS.override.md`、`CLAUDE.md` 与 `AGENTS.md` 只装了一处、Git 工作区脏。
- `remove-memory` 子命令:仅删除标记块区间,指纹校验,不碰其他内容。
- 用户级约定同步改写(WorkBuddy):`~/.workbuddy/MEMORY.md` 中现行的"项目规则唯一来源是项目根 AGENTS.md"改写为"项目记忆唯一来源是 `.agents-group/memories/`,AGENTS.md/CLAUDE.md/.workbuddy 只放指针"。

## 7. 记忆生命周期:记录 → 蒸馏(核心机制,借鉴 WorkBuddy)

**现状差距**:三家原生自动记忆的提取/蒸馏都发生在各自私有管道内(Codex 后台小模型、Claude auto memory、WorkBuddy 云端+30 天日志蒸馏),共享库没有等价能力。

**解法:把 WorkBuddy 的"每日日志 + 到期蒸馏"生命周期原样搬到共享库**,用指针块规则驱动 agent 执行,配合工具定期压缩。记忆的"提取器"就是干活的那只 agent 本身,不需要独立的后台管线。

### 7.1 记录:会话内自记日志(主通道,零基建)

指针块写入规则(§6.1)要求 agent:干活过程中把项目级事实、决策、结论**随手追加**到 `journal/YYYY-MM-DD.md`。

- 为什么这是主通道:零基建、三家行为一致、即时生效;append-only + 不要求精炼,把"记"的成本降到最低,agent 遵从度高。
- 会话收尾兜底:指针块要求任务结束前检查当天日志是否已覆盖本次关键结论,漏了补记。
- 局限:依赖 agent 遵守指令(非硬约束),超长会话可能漏记——由 §7.3 的批量收割补齐。

### 7.2 蒸馏:`compact` 把日志变结论(WorkBuddy 30 天机制)

- journal 中**超过约 30 天**的条目按主题蒸馏进 PROJECT-MEMORY.md 索引,删除已蒸馏的过期碎片;WorkBuddy 同款生命周期:原始积累有保鲜期,稳定结论才常驻注入。
- 蒸馏出的长文可下沉 `references/`;索引保持 ≤200 行/25KB。
- 操作前时间戳备份(WorkBuddy `.bak` 同款纪律)。
- **执行者可插拔,优先零基建**:
  1. 会话内:指针块加一条"若索引超 200 行或日志超期,先执行压缩再继续任务"——任何一只 agent 都能当蒸馏器,随 M1 生效;
  2. 工具:`compact` 子命令(时间驱动的确定性压缩,支持 headless `codex exec` / `claude -p` 或 OpenAI 兼容小模型做文本蒸馏);
  3. 定时:Paseo schedule 每周对纳管项目跑 `compact`。

### 7.3 补充:`distill` 批量收割会话转录(可选,补漏记 + 收历史)

对已存在但从未进共享库的会话,批量补蒸馏:

- **原料**(§4 矩阵):Codex rollout jsonl、Claude projects jsonl、WorkBuddy sessions(格式先逆向);另有第四源——**Codex 已汇总的私有记忆**(`~/.codex/memories/MEMORY.md` 按 `applies_to: cwd` 过滤),适合回填历史上已沉淀但共享库缺失的结论。
- **运行时机**:定时(每周)之外,**切换执行器接手同一项目前**显式跑一次——周一 Codex 会话若漏记,周二 WorkBuddy 接手前 distill 即可补齐。
- **归属过滤**:按转录中的 cwd 字段匹配项目根(含其 Paseo worktree 路径,以主 checkout Git 根归并)。
- **水位线**:`.agents-group/.distill-state.json`(gitignore)记录每源已处理位置,增量运行不重复蒸馏。
- **跳过**过短、失败且无结论的会话;蒸馏提示词强制**脱敏**(不输出密钥/令牌/凭据)。
- **输出**:仅追加 `journal/<会话日期>.md`(标注 `source:codex/claude/workbuddy`),不直接改索引——索引统一由 compact 维护,避免双写。
- 定位:一次性回填与兜底,**不承担日常记录**(日常靠 §7.1)。

### 7.4 方向纪律

只从私有库/转录流向共享库;绝不反向写入 `~/.codex/memories/`、`~/.claude/projects/*/memory/`、WorkBuddy 记忆(生成物会被其后台整理覆盖,不可靠)。

## 8. 验收协议(静态文件不算数)

每个执行器安装后必须新会话实测,双方向:

1. **读探针**:确认指针生效并能读到共享库。
   - Codex:`codex "Summarize the current instructions."`(官方推荐方式),复述中应出现共享库路径;
   - Claude Code:新会话 `/context` 应列出项目 CLAUDE.md;再让它复述"本项目长期记忆来源";
   - WorkBuddy:新会话问"本项目的长期记忆在哪,读给我听"。
2. **写探针**:让 agent"记住一条本项目结论",检查落点必须是 `journal/当天.md`(而非 CLAUDE.md/AGENTS.md 本体、而非其原生记忆文件)。
3. 运行中的会话不生效,须重开;三家均无缓存(指令链每次重建)。

## 9. 迁移与风险

| 风险 | 对策 |
|---|---|
| Claude 有 CLAUDE.md 就不读 AGENTS.md | 两处都装指针块(§6.2) |
| `AGENTS.override.md` 劫持 Codex 指令链 | 禁用;init 检测存在即告警 |
| 32KiB 指令链上限 | 指针 ≤5 行;记忆不进链 |
| worktree 记忆分叉 | 全部提交进 Git;worktree 归档不丢 |
| WorkBuddy"重置记忆"清空用户级约定 | init 幂等重装;重置后重跑 |
| 索引/日志膨胀 | §5.2 写入纪律 + compact 200 行硬线 |
| 蒸馏产物带出隐私/凭据 | 提示词强制脱敏 + 落库前纪律;个人项目也照此执行 |
| 与 `~/.agents-group` 用户级规则冲突 | 用户级管跨项目,项目级管本项目;同文冲突时项目级后注入、优先(两家拼接序一致) |
| 现行 WorkBuddy 约定指向 AGENTS.md 为唯一源 | M1 改写为指向 `.agents-group/memories/`(§6.3) |

## 10. 落地路线

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1 试点 | 本仓库 dogfood:建 `.agents-group/memories/`(含首条记忆)+ 三处指针块 + 改写 WorkBuddy 用户级约定 | §8 双探针 ×3 执行器 |
| M2 工具 | `init-memory` / `remove-memory` / `check`(漂移与体积检测) | 在 knowwind、poster-fit 复制,幂等重装通过 |
| M3 收割 | `distill`(三家转录,WorkBuddy 格式逆向) | 抽样核对蒸馏条目与原会话一致 |
| M4 自动化 | `compact` + Paseo 周任务(+可选事件钩子) | 索引连续 4 周 ≤200 行 |
| 后续 | ZCode、DeepSeek Harness 接入(§5.4) | — |

---

附:调研依据——Codex 官方文档(memories、agents-md 两页)、Claude Code 官方 memory 文档、WorkBuddy 官方设置文档 + 三层记忆机制文章;本机实测 `~/.codex/memories/`、`~/.claude/projects/`、`~/.workbuddy/` 与 poster-fit 项目 `.workbuddy/memory/`。
