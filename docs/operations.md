状态：文档版本 1.2；2026-10-31 公共记忆分层修订。命令形状以当前源码帮助为准，真实运行限制见验收总览。

# memSharing 操作手册

本手册供使用者与执行 Agent 使用，机制说明见 [系统架构](architecture.md)。
命令已核对 `scripts/agm.py --help`、各子命令帮助及 `scripts/install.py --help`。
示例中的绝对路径、完整 SHA 和版本号必须替换为实际核验值。

## 1. 环境与操作入口

当前实证平台为 macOS；Windows/Linux 不列为已验收平台。
需要 Python ≥3.9 和 Git，Python 无额外 pip 依赖。
缺失或版本不足时，执行 Agent 在安装汇总确认后用可用系统包管理器准备依赖。
Python CLI 本身只诊断，不负责自动安装 Python/Git。
包管理器缺失、权限受阻或依赖安装失败时停止，说明实际阻塞。

用户可直接说“安装 memSharing”，安装后可用 `/mem-sharing` 菜单或自然语言。
六个菜单入口为：添加新的 Agent、批量接入项目规则、整理用户记忆、健康检查、接入项目规则、整机卸载。
菜单由公共指南 `~/.mem-sharing/memories/topics/使用约定.md` 承载，各执行器用户文件只保留公共指针与自身规则，不要求安装 memSharing Skill；触发菜单或默认项目接入前先读指南。链接解析分两个根：索引 `MEMORY.md` 中的指南/主题相对链接以 `MEMORY.md` 所在目录解析；指南内部的链接以指南所在目录解析，或直接使用 C 内绝对路径（例如已安装产品脚本）；两个解析根不能混同。指南缺失时停止相关操作。
下文项目示例从源码根运行；已安装后可改用 C 中的脚本绝对路径。
C 为 `~/.local/share/mem-sharing`，R 为 `~/.mem-sharing`。

为什么这样设计：使用者表达意图，Agent 翻译为受控命令，不要求用户维护执行器差异。

## 2. 安装：五拍剧本与命令

1. 接收安装请求，说明先检查运行环境和本机 Agent。
2. 汇总 Python、Git、验证为已安装的 Agent 与待准备依赖，一次确认，回车开始。
3. 确认后静默获取、核验和安装；完成只报用户记忆中枢与实际接入名单。
4. 紧接着正向询问是否安装用户级 Context Keeper，回车同意，n 跳过。
5. 安装后提醒在所需项目使用 `/context-keeper`，首次按 Context Keeper 流程激活。

unknown 或仅有残留目录不列为已安装。
成功简报不罗列内部路径，不添加未安装 Agent 或新会话自检提示。

先使用核验过的干净本地 Git checkout 预览：

```bash
python3 scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
```

也可用 `--source-manifest /absolute/path/source.json` 提供固定来源对象。
它包含 `root/url/commit/version/files`，不要与 source/commit/version 混用。
不得 reset/pull 用户的 dirty checkout 来满足干净要求。
安装器只读判别全新、确认的 v0 内容复制、有效产品升级或异常停止。
v0 仅复制获准的 memories/references，旧目录 `~/.agents-group` 原地保留。

无批准时返回 `approval_plan`，不会安装。
Agent 展示完整计划并绑定真实确认，将计划连同 `confirmed_at/reference` 写入批准 JSON。
`confirmed_at` 使用真实 UTC 时间并以 `Z` 结尾，例如 `2026-10-31T02:23:47Z`（示例不得当作本次确认时间）；`reference` 指向真实确认。批准必须对应当前计划，不填写虚构确认，不将一次确认扩大成任意修改授权。

```bash
python3 scripts/install.py --approval-file /absolute/path/install-approval.json
```

支持 `codex/claude/workbuddy/dsh/zcode/opencode` 六家。机器安装、再次安装及升级默认接入全部已核验为 `installed` 的支持对象；`unknown/absent` 仅报告，不创建入口。安装可重复 `--agent codex --agent opencode` 限定目标，指定未核验安装的对象整单拒绝。公共布局迁移与新增接入合并在同一份外层精确计划内预览并一次批准；显式范围限制新增装配，既有公共依赖仍完整迁移。来源与现场漂移仍拒绝；同版不同来源替换仍不属于升级。

```bash
python3 scripts/install.py --source-manifest /absolute/path/source.json --agent dsh --agent zcode
```

`--project` 只用于报告后续项目命令，不表示安装时顺便启用项目。

为什么这样设计：先固定来源与现场再写入，安装请求能落实到可核对的精确变更。

## 3. 给单个项目启用记忆

进入未登记的 Git 主 checkout 时，用户级规则与公共指南驱动默认启用，由当前实际执行者以 `--agent <当前执行者>` 执行；不带 agent 参数按已安装事实处理，可能顺带补齐其他执行器已存在的原生目录，仅用于用户显式要求全体或批量接入，不改 CLI 语义。机器探测到执行器安装或原生目录存在，不等于当前执行者实际使用。这不是后台监听；非 Git 目录与 linked worktree 不触发。

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent <当前执行器>
```

新项目建立 `AGENTS.md` 骨架；已有规则正文保留，只补所需协议。
`AGENTS.md` 是共享项目规则基座，不依赖安装 Codex；只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立。
不带 `--agent` 的通用 enable 完全不触碰 `CLAUDE.md`，包括已有文件；Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `@AGENTS.md` 引用（兜底规则在 Claude 自身用户文件）；其它执行者默认流程不预建。Codex 原生读取无需兜底。
有意接入 Claude 时可显式执行 `enable-memory --project ... --agent claude`。
WorkBuddy 只在 `.workbuddy/memory/` 原生目录存在时补规则指针，不预建目录。
原生目录缺失表示待实际使用；静态桥接不等于运行时加载通过。

启用不调用 Context Keeper 安装器、不安装项目级 Skill、不创建其记录库。
未装 Context Keeper 仍可使用用户记忆与项目规则，只是没有项目经历能力。
若需精确非交互批准，先查看预览，再加 `--approval-file /absolute/enable-approval.json`。
项目启用 `--agent codex claude` 或 `--agent dsh zcode` 可一次选择多个唯一值；未显式选择时仍只在默认旧三家中按已安装事实处理。

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent dsh zcode
```

写前发现受管单元漂移则停止，批准文件不能强制覆盖漂移保护。

为什么这样设计：规则接入与项目经历激活分开，默认流程不为未使用的执行器创建文件。

## 4. 批量启用项目

在菜单选“批量启用项目记忆”，提供需要扫描的目录：

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects
```

递归扫描包含目录自身，不进入 `.git`，不跟随目录符号链接。
仅 Git 主 checkout 可入选，linked worktree 排除。
汇总预览每项目一行，集中批准全部新项目的精确计划，不逐项目重复询问。
已启用项目跳过；disabled 项目保持停用，必须单独显式恢复。

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/batch-approval.json
```

批准绑定扫描目录、完整清单、台账哈希和各项目计划，执行前锁内重新核对。
某项目执行失败即停止后续，已完成项目保留，未开始项目不会假报成功。

为什么这样设计：集中确认降低重复操作，同时保留每个项目的事务与故障边界。

## 5. 历史政策迁移与整机卸载

旧 `remove-memory`、`--memory`、`--no-memory` 已退役，新请求零写拒绝。历史 disabled 只作规则接入 tombstone，默认跳过、不重建；它不否决 Context Keeper 的自动规则，不表示 CK 已停用或入口已删除。使用 `migrate-policy [--project ABS]` 精确预览并批准后，仅退役产品自有且指纹匹配的旧控制与已知旧模板，保留私文、CK 设置和历史数据，不替用户启用 CK。

Claude 的 legacy import 若因独立 Context Keeper 块变化而触发 `Native import baseline drift`，普通 `migrate-policy` 继续拒绝。仅当已安装且核验匹配的内核包含此命令时，才可显式执行 `python3 -B scripts/agm.py reconcile-legacy-import --json` 获取零写预览（需批准时 exit 5，拒绝 exit 2）。此命令只接受本 HOME 产品备份内已 committed 的历史 public-memory-layout-v1 Transaction 与对应 committed journal：原计划 seal 只作完整性绑定，不作作者信任根：按冻结历史 pin `ea553738f37a5cc5befb34bf241d12da33f07b21` 核对全部 21 个 helper 的路径/字节/原模式（归档文件为0600）及 launcher，少、多、变均拒绝；再从历史 observations 与登记对象反推必需 targets，核对原批准计划、前后台账 schema/身份、完整事务输出范围、逐项历史 after 字节、台账对象变化、普通文件及模式、before 备份指纹，用冻结追加规则重建出登记的整文件基线；历史和当前必须各有唯一且独立的 CK 块，块外所有字节完全相同，旧兜底块必须仍是已拥有且指纹匹配的精确旧模板。无证据、私文变化、重复标记、symlink、未知 producer 或现场漂移均拒绝；不接受任意 baseline/adopt 参数。

审核预览中的证据、前后文件哈希、CK 范围、逐对象指纹变化与台账哈希后，将原样 `plan` 连同真实用户确认的 UTC `confirmed_at` 和 `reference` 保存为私有批准 JSON（顶层仅此三键），再执行 `python3 -B scripts/agm.py reconcile-legacy-import --approval-file /absolute/approval.json --json`。执行在锁内重建整单，并在每次写前精确重枚举全部候选（含未选中及未终态者）及闭包；仅排除本次已绑定且完整核对的 Transaction 自有 metadata。无需历史现场与当前产品版本或入口保持一致；缺少足够持久 after 证据的直接入口装配事务拒绝。当前仅支持有 before 备份证明的旧索引转换：topic 的 absent/旧模板必须写入、新模板为 no-op；旧 Codex/WorkBuddy 块必须转换、已登记新块仅在整文件为已知新模板时可证明 no-op，其他未证组合窄拒，不读取当前文件替代历史证据。随后复用原 Transaction 先写唯一 Claude 自有兜底块、最后提交登记指纹；事务备份与 manifest 位于产品 backups 内，失败按其状态处理，不手改登记或覆盖历史 CK。CK、私文、CRLF、引用位置、所有权和删除权限保持原样。完成后再次执行为零写 noop，随后仍须单独预览和批准 `migrate-policy`。本命令不修 Claude CLI 断链、不置顶入口、不执行政策迁移或 CK 操作；客户端新会话仍待验。未发行补丁不能直接替换已安装同版本异来源产品，须先完成另批的发行与升级流程。

整机卸载使用 `python3 -B scripts/agm.py uninstall-machine --backup-dir <全新外置目录>` 先预览，再以 `--approval-file` 精确批准。归还当前完整公共记忆给每个实际接入者的自身用户目录，再核验、清依赖、最后删除产品；不是恢复安装前。外置 manifest/recover.py 与独立解释器支持删除代码后的精确恢复。未知/漂移阻断，项目 AGENTS、有效 Claude/WB 桥接及 CK 默认保留。完整数据与门槛见[整机卸载方案](uninstall-design.md)。

CLI 的 `scope=standalone_declared`、`host_plugin=not_applicable` 仅声明调用范围；Paseo 为 `machine_and_paseo`，机器 completed 但插件仍在时 overall=partial。必须在插件移除前经外置入口独立绑定真实安装 ID/来源/CLI/daemon/live serverId，再用户 remove、同目标 full-list check 证实缺席，最后才可另选卸载 CK。disabled、查询错误、能力/版本错误均不算 removed；默认保留 CK，尾步另行精确批准。正式 payload 待干净提交与版本授权后生成，本轮源码/合成验证不等于实际宿主卸载或六家新会话加载验收。

## 6. 添加新的 Agent 与健康检查

先核验新 Agent 的安装事实，再通过机器安装入口的 `--agent` 接入用户记忆。
使用第 2 节安装预览流程限定目标；不是编辑 agents.json 来伪造安装事实。
已有项目需要该执行器时，可显式接入：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent claude
python3 scripts/agm.py check-memory --project /absolute/path/project
python3 scripts/agm.py check-memory --all
```

`--all` 读取已登记项目，不扫描整个磁盘寻找新项目。
check 只报告登记与现场缺口，不写锁、不备份、不修复、不触发安装。
入口字节、安装事实和执行器新会话加载应分别判定。
运行时验收仍需实际使用证据；WorkBuddy 无证据时保持 pending。

为什么这样设计：巡检可以安全重复，修复必须落实到另一次明确的写入计划。

### 桌面端默认根与验证边界

DeepSeek Harness（`dsh`）用户入口为 `~/.dsh/AGENTS.md`，ZCode（`zcode`）为 `~/.zcode/AGENTS.md`；均共用公共记忆索引，保留各自私文，项目原生读取根 `AGENTS.md`，无需额外桥接。默认项目接入仍由当前实际执行者显式使用自身 ID，不预建其他执行器入口，也不恢复 disabled。

OpenCode v2 用户入口为 `~/.config/opencode/AGENTS.md`，项目原生读取 `AGENTS.md`，不预建专属项目私文。第一版只支持默认配置根：`XDG_CONFIG_HOME` 与 `OPENCODE_CONFIG_DIR` 可未设置、为空白，或分别为规范化后等于 `<home>/.config`、`<home>/.config/opencode` 的绝对路径；相对路径、字面 `~` 与其他根均拒绝。`OPENCODE_CONFIG` 非空即拒绝。拒绝时整单零写，不回显变量原值。原生签名匹配可核验 installed，但没有静态版本证据仍如实标记版本 unknown。大文件不套用 Codex 的 32KiB 提醒，不代表客户端没有其他限制。

OpenCode 检测分别报告 CLI 与桌面 App 安装面。桌面核验 `OpenCode.app` 的固定产品名、`ai.opencode.desktop` 标识、`OpenCode` 可执行入口、非空且一致的 bundle 版本，以及 Apple 证书链与团队 `5NZ4Q7NXJ4` 签名。CLI-only 不表示桌面已安装；只有一个官方原生 CLI 与一个官方桌面 App 均通过、且无失败候选时允许并装，额外来源仍为 unknown。CLI 没有静态版本证据时保持版本 unknown。

章教授已交付桌面 2.2.5 安装、签名与默认规则读取逻辑的静态证据；本轮未重复操作真实环境。静态检测和临时 HOME 测试不能证明真实新会话已加载规则；memSharing 真实接入、新会话与模型调用验收由用户延后统一进行，均 pending。验收分层见[OpenCode 验证记录](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/opencode-adapter/verification.md)。

DSH 本次限默认 coding `cordis` preset 与默认根。接入规划自动检查 `DSH_HOME`，非默认根拒绝默认入口接入，错误不回传变量值。`DSH_AGENTS_HOME` 影响共享 Skill 根，目前不自动检测，也不承诺默认共享 Skill 目录已被客户端发现。显式插件配置也可能覆盖根，自定义配置与桌面进程实际环境未验证。`ZCODE_HOME` 不是 ZCode 规则根，不能用它推导规则位置。

静态读取逻辑支持 DSH 的 `~/.dsh/skills`、ZCode 的 `~/.zcode/skills`，以及两者共用的 `~/.agents/skills`；项目侧也有各自隐藏目录与 `.agents/skills` 发现逻辑。memSharing 不创建、复制或投影这些 Skill。静态发现与符号链接支持不等于桌面实际加载通过。

原生入口证据见[桌面合同（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/desktop-agent-contracts.md)。原生入口静态证据不代表运行时加载通过；两款桌面端新会话的用户规则、项目规则和 Skill 加载验收均为 pending。

## 7. 用户记忆整理与 Context Keeper 激活

“整理用户记忆”由 Agent 调用 `user_rules_organize.py` 的预览与执行 API。
当前 `agm.py` 没有整理子命令，不使用虚构的 organize CLI。
向导把公共候选、重复规则、执行器独有内容和归属不明内容分开展示。
分类只是建议，独有与归属不明内容锁定保留，不能并入公共源或删除。
一次确认完整逐条计划，原文指纹逐项绑定；批准前候选可改判保留。
公共内容与入口编辑使用可恢复事务，整理不修改活动台账 V。

为什么这样设计：公共规则需要人工语义判断，不能用自动分类扩大共享范围。

Context Keeper 是独立可选引擎，主安装完成后才产生独立批准封皮。
独立路由示例：

```bash
python3 scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper
python3 scripts/install.py --context-keeper --approval-file /absolute/ck-approval.json
```

源码须为持久、干净且符合固定 pin 的 checkout，目前不自动下载。
只有真实交互回车表示同意，空格、EOF 或非交互输入不算。
同意后为已接入的 Codex、Claude Code、WorkBuddy 安装用户级 Context Keeper，落位由其自有安装器负责。固定 pin 安装器仅支持旧三家的 flags；`dsh`、`zcode`、`opencode` 明确跳过用户级 CK 安装（`reason=upstream_unsupported`），混合时旧三家仍可安装，不影响它们的 memSharing 接入，不可宣称它们已安装 CK 或新会话已通过。
仅接入 `dsh/zcode/opencode` 中的执行器时，`--context-keeper` 输出 `status=skipped`、`reason=upstream_unsupported` 与 `skipped_upstream_agents`；交互安装尾步的 `context_keeper` 同样为 `status=skipped`、`reason=upstream_unsupported`，主安装保持 `status=completed`。混合接入执行时，`agents` 仅列受支持的执行器；跳过项列于 `skipped_upstream_agents`，每项为 `{"agent":"dsh或zcode或opencode","reason":"upstream_unsupported"}`（`agent` 取实际 ID）。`upstream_unsupported` 是原因，不是顶层状态。

缺源、失败或结果不明分别报告，主产品成功保留，结果不明不自动重放。
在需要的项目首次运行 `/context-keeper`，按其流程确认并初始化项目经历库。
后续保存、续接、查找与迁移门禁全部遵守 Context Keeper；需要迁移时先停止相关读写。

为什么这样设计：可选引擎独立授权，安装成功不冒充项目记录库已激活。

## 8. 常见问题与恢复入口

**锁冲突：** 保留锁与 journal，核对是否仍有写者，不自动删锁或抢锁。
**入口漂移：** 保留当前字节，检查报告路径与受管单元，重新评估计划；不要手改台账绕过保护。
**台账缺失或损坏：** 停止写入，不能凭入口文件猜测原授权或静默重建为全新。
**旧开发版或旧标记：** 保全后重装；schema=3 首发基线不承诺开发版迁移，不提供逆 schema 转换。
**升级中断：** 用报告所指固定恢复工具，避免运行混版 C 中的安装器。
机器恢复先预览，确认后执行同一计划：

```bash
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue --approval-file /absolute/recovery-approval.json
```

需要回滚时用 `--action rollback` 重新预览与批准；V 已提交且输出全为 after 时只收尾。
项目事务失败则按报告中的 manifest 与 recovery 指引处理，不套用机器 journal。
第三种字节、缺失材料或工具漂移一律停止，不覆盖未知修改。
为什么这样设计：恢复只能依据完整证据执行，重试不能把不确定结果放大。

### WorkBuddy 用户入口的接入边界

用户级 `~/.workbuddy/MEMORY.md` 的私人原文字节保留；精确批准计划后追加受管块，块内明确读取本机公共索引绝对路径及项目 `AGENTS.md`。已登记旧块仅在指纹匹配时，经精确批准更新；漂移、未登记旧块或不满足公共读取语义的共享用户块停止自动接入，交回原有治理路径。与当前模板完全相同的未登记块可保真登记为 reused，不取得删除权。安装器只拥有其新增受管块，不拥有私人全文；本次不提供机器卸载。

报告中的 installed 是安装探测，connected 是登记与实际入口语义的静态核验；缺口列于 `entry_status`，接入未全完成报告 partial。每项 `runtime_acceptance: pending` 仍需真实新会话证据。已有/noop 安装也重新核验静态入口，不凭应用存在宣称接入。同版同来源再次安装会按当前 installed 事实发现新 Agent，并将入口差异纳入精确预览与批准；显式 `--agent workbuddy` 可限定本次装配。Context Keeper 尾步继续检查主操作、登记对象与指纹，不绕过缺口。本修复不修改私人规则、不预建 WorkBuddy 原生项目目录，不扩大旧版本迁移承诺。

### 0.1.0 → 0.1.1 的 WorkBuddy 入口合同转换

此专用通道只接受 `workbuddy-public-index-v1`，旧版本必须为 0.1.0、结构版本1/schema3，旧来源必须与代码中的 `WORKBUDDY_PREDECESSOR` 完全一致；新版本固定0.1.1。`agents.json` 固定不变，`user_entries.py` 仅允许审定的前后 SHA256。调用必须显式 `--agent workbuddy`，目标 commit/tree 通过外部精确 conversion 与完整批准绑定。不允许把任意合同变更写成 `entries=preserve` 放行，也不支持该转换的成功发行降级。公共记忆分层引起的 `user_entries.py` 指纹变化不适用本通道，另见 [INSTALL](../INSTALL.md) 的公共记忆分层发行转换边界（0.1.3 候选，接口与恢复命令已回填）。

下面是外部 request 清单的生成方式。`<干净来源>` 必须是修复已提交后的干净 checkout；`<完整SHA>` 为该提交，不能用未提交工作树配旧SHA。清单写到独立暂存目录，不修改用户规则或安装态。生成过程中只有读取与输出JSON；仍需随后预览、核对并批准完整安装计划。

```sh
umask 077
WB_RELEASE_DIR=$(mktemp -d)
WB_RELEASE_OP="wb-public-index-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -B - '<干净来源>' '<完整SHA>' "$WB_RELEASE_OP" > "$WB_RELEASE_DIR/request.json" <<'PY'
import copy, importlib.util, json, sys
from pathlib import Path
source_root = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location('release_installer', source_root/'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
from agm_core import layout, paths, registry, upgrade, user_install
source = installer.checkout_source(str(source_root), sys.argv[2], '0.1.1')
canonical, _ = user_install._source({'source': source})
runtime = layout.resolve_layout(Path.home())
config = paths.select_platform(paths.load_agents_table(), sys.platform)
allowed = paths.allowed_user_paths(config, None, home=str(runtime.home))
data = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
product = data['product']
conversion = {
    'before': {'schema_version': data['schema_version'],
               'product_structure_version': product['product_structure_version'],
               'product_code_version': product['product_code_version'], 'source': product['source']},
    'after': {'schema_version': 3, 'product_structure_version': 1, 'product_code_version': '0.1.1',
              'source': {k: canonical[k] for k in ('url', 'commit', 'tree_sha256')}},
    'direction': 'upgrade', 'entries': copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION),
}
# Reject wrong predecessors/targets before emitting a purported supported request.
request = {'home': str(runtime.home), 'platform_config': config, 'source': source,
           'agents': ['workbuddy'], 'conversions': [conversion],
           'operation_id': sys.argv[3]}
installer.plan_machine(request)
print(json.dumps({'source': source, 'conversions': [conversion]}, ensure_ascii=False, indent=2))
PY

python3 -B <干净来源>/scripts/install.py --request-file "$WB_RELEASE_DIR/request.json" --agent workbuddy --operation-id "$WB_RELEASE_OP"
# 上一步 approval_plan 加真实 confirmed_at/reference，保存到精确批准JSON；不要用 request 代替批准
python3 -B <干净来源>/scripts/install.py --approval-file <精确批准JSON绝对路径>
```

外层批准含完整代码计划与精确入口 `entry_plan`，包括原文件/新文件指纹、受管对象变化、安装探测指纹。执行前重建并核对整单；代码阶段不修改用户入口，代码提交后再调用已有入口事务，原始私人字节与旧 Context Keeper 块保留。入口失败或期间外部文件变化时报告 partial，保留已成功升级的代码，不自动回退或覆写外部修改。此时用同一固定0.1.1来源、显式 `--agent workbuddy` **重新预览并批准**；代码为noop，入口独立补齐。旧外层批准不能重放。

代码阶段中断继续使用升级操作中固定的 `recover.py` 与 toolkit 做只读恢复预览，再批准 continue 或 rollback。未提交代码台账时可按既有原子恢复回退；台账已提交则只能完成代码收尾。专用转换的代码恢复结果明确 `scope=product_code`、`entry_phase=not_run_by_upgrade_core`，**不代表 WorkBuddy 接入完成**；恢复后仍要进行同版显式入口预览/批准。外部台账、已登记入口、代码出现第三态时仍拒绝覆盖。

成功完成代码与入口之后，不承诺通过该专用转换自动降级为0.1.0；保留旧代码版本、台账/入口事务备份及恢复材料。撤回已成功新增的用户块必须另行精确计划，不能以恢复旧整文件覆盖后续私人内容。本通道不创建项目原生目录、不新增机器卸载、不更新上游 Context Keeper。

## 独立退役旧 Paseo staging（未发行工具）

当旧宿主插件已通过官方命令移除，而遗留 staging 阻止核心卸载时，
可从另行审定、固定的 clean Git checkout 运行独立工具。它不替换已安装
0.1.6，不要求先安装新版插件，也不更改核心的退休回执消费门禁。
`--tool-commit` 是操作者审定的完整工具提交，不是工具内自引用的版本。
工具会逐个核对 scripts 下的受管文件与该 pin 的字节/模式。

```sh
python3 -B /absolute/trusted-checkout/scripts/retire_staging.py \
  --tool-commit FULL_REVIEWED_TOOL_COMMIT \
  --paseo-cli /absolute/official/paseo --cli-sha256 VERIFIED_CLI_SHA256 \
  --server-id VERIFIED_SERVER_ID --plugin-id memsharing-synthetic-dev \
  --evidence-dir /absolute/existing-private-evidence-directory
# preview exit 5; 将完整 approval_plan 原样放入下述 envelope：
# {"plan": <approval_plan>, "confirmed_at": "真实UTC时间Z", "reference": "真实用户批准依据"}
python3 -B /absolute/trusted-checkout/scripts/retire_staging.py \
  --approval-file /absolute/private-approval.json
```

证据目录须真实、0700、位于所有产品/卸载/恢复根之外；计划和批准包含
私有路径，保存0600且不在会话展示。官方 Paseo status/list/status 必须绑定
同一 HOME/serverId/PID，完整列表中精确插件 ID 不存在；disabled 不算移除。
工具核对已安装的固定0.1.6身份和完整代码；不同来源/版本不能搭乘此入口。

当前窄入口仅支持已知旧插件 ID memsharing-synthetic-dev；其它宿主身份拒绝。
当前窄格式只认每件独立的终态 operation（无 journal），以及已登记项目
的固定 enable-memory approval（仅首次 Codex 主 checkout 的 AGENTS.md 经历块 append，既有文件 update，无 rebuild/transition）。
该 approval 必须对应 follow_ck 登记、真实主 checkout/Git common-dir、精确登记对象及其 committed enable Transaction。
完整事务只允许目标文件与最后提交的 registry，原 before 备份必须精确匹配；按固定公共模板/append 规则独立重建目标 after 与完整 registry after，核准两个历史指纹。
历史 installation fingerprint 只是格式受限的原始观测，不作为作者或删除权信任根，也不拿当前检测结果冒充历史检测；认领依赖上述独立已登记对象/完整事务/固定 producer 输出闭包。
所有支持的 manifest、before 备份及事务目录闭包纳入 preview 与锁内/删除前漂移校验。
其它历史组合或证据不全继续拒绝，不为当前现场拓宽。每件均须本人所有、普通0600文件、精确
JSON schema，且超过既有600秒静默期；目录须0700，不跟随符号链接。
独立目录没有共同 operation 外键，不能凭相邻终态记录认领其它文件。
request、其它 approval、journal 恢复分支、未知/运行状态一律拒绝，不是
通用清理/adopt 接口。公开预览逐件列出 hash、mode、路径、目录子项和
宿主/产品身份；这不是声称旧 JSON 具有密码学作者签名。

精确批准后取得产品写锁并重建预览；先把所有原件完整外置、保留字节、
mode、mtime，fsync并核对归档，再复核宿主移除/产品身份/完整目录闭包。
逐文件最后复核后unlink，不递归删除。只在全部完成后写现有consumer
可校验的 host-receipt.json。外置 retirement-progress.json 记录批准与
执行阶段；任何失败保留归档及现场，禁止自动重试、造回执或手动补删。
中断后必须另行审阅实际剩余文件/归档并制定具体恢复方案，本入口不
声称自动断点恢复。备份不能替代归属、终态或无活动证明。

本工具只退役遗留宿主暂存，不执行核心卸载、归还、新装或 Context Keeper
操作。回执就绪后仍须公开 uninstall-machine 的新预览与精确批准。
