# 安装 memSharing

memSharing · 多 Agent 记忆共享与融合。把下面这句话交给正在使用的 Agent，与 README 一致：

```text
请从 https://github.com/vincent4j/mem-sharing 安装 memSharing（多 Agent 记忆共享与融合）。
```

本页供未安装产品的 Agent 直接使用，无须先有产品 Skill、v0 工具、Context Keeper 或项目配置。依据 [DESIGN](DESIGN.md) 与[系统架构](docs/architecture.md)。本页描述目标流程，执行状态以实际结果为准；M4-09 的本地范围与阻断项见[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)，真机项归 M4-10。

## 用户看到的安装对话

用户发出上面的安装请求后，按检查并集中确认、静默安装、两块共享选择、选定执行并简报、最后询问 CK 的顺序执行。

1. **环境检查。** 检查 Python >=3.9、Git 和六家实际安装事实，汇总：“环境检查完成。将为以下 Agent 安装 memSharing：〈实际名单〉。安装后，它们可以使用同一份公共用户记忆。按回车开始安装。”真实回车批准本次精确计划，不要求输入“确认安装”；EOF、非交互空输入不批准。内部计划、备份和锁内复核保留，不向用户解释台账、指纹或内部修改清单。
2. **静默安装。** 完成仅报告：“memSharing 已安装。公共用户记忆：~/.mem-sharing/memories。已接入：〈实际名单〉”。未完成融合不报融合成功。
3. **展示融合方案。** Agent 完整阅读语境后，展示“建议合并的相同规则”和“需要你确认是否合并”；空栏目不展示。每条列来源 Agent 和原生文件，一个规则只一个稳定编号；不同标题须经本次精确等价提案判断，不靠同文字自动合并。
4. **选择即执行。** “按默认方案”“不合并2”“再加入7”等按实际编号选择，直接执行并简报；查看零写、专属和未选保留。只有现场实质变化才停下，不二次确认。外层收到用户回车/选择后直接绑定内部计划执行，不再进入 TTY 重问。
5. **最后问 CK。** 公共整理完成或明确暂不整理后，才问：“为了让 Agent 在新会话中记住项目进度、决策和经验，接着上次的工作继续，需要另外安装 Context Keeper。是否为本机已安装的〈实际名单〉安装？回复‘安装’或‘跳过’。”只有“安装”批准；回车、EOF、跳过不准备 CK 安装计划。固定上游不支持者准确报告，安装完成再提醒 `/context-keeper`。


## 运行时准备

当前生产范围为 macOS。Python **≥3.9 的任意版本**直接放行，不强制替换为某个特定版本。Python 未安装或低于 3.9 时，经上述确认通过系统包管理器安装最新稳定版；Git 缺失同样安装，全部就绪后继续。检测、安装与重新核验属于外层安装编排，缺 Python 时不能声称 Python 安装器已运行。

使用现场可用的系统包管理器，例如 Homebrew；不为本文自行固定版本或远程脚本管道。包管理器不存在、权限不足、安装失败或安全验证受阻时如实暂停，不把依赖安装失败报作 memSharing 完成。网络任务仍遵守环境委派边界。

外层执行 Agent 负责环境汇总、确认与包管理器安装；当前 Python CLI 只诊断缺 Python/Git，不自行安装依赖。此对话合同不等于外层已完成自动化或真机验收。

## 来源与目录

来源为 `https://github.com/vincent4j/mem-sharing`，或用户提供并核验的本地 clean Git checkout。固定完整 commit、代码版本与逐文件清单，执行中不浮动跟随 HEAD，不 reset/pull 用户 dirty checkout。获取必须在请求与批准范围内；help、check、预览不 clone、不建缓存。外层获取与机器安装分别保留操作证据。

| 标识 | 路径或值 |
|---|---|
| R，用户记忆中枢 | `~/.mem-sharing` |
| C，唯一活动代码 | `~/.local/share/mem-sharing` |
| V，唯一活动台账 | `~/.mem-sharing/var/registry.json` |
| 版本库存 | `~/.local/share/mem-sharing-versions` |
| bootstrap 操作目录 | `~/.mem-sharing-install-<op>/` |
| product_id | `mem-sharing` |
| 受管标记前缀 | `mem-sharing:*` |
| v0 历史源 | `~/.agents-group`，只读来源，原地保留 |

中枢只包含 memories、references、backups、var，不建 skills/mcp，六家执行器按所选范围安装各自原生 `skills/mem-sharing/SKILL.md` 薄入口，指向持久安装核心，不占用公共 Skills 目录。旧标记与现网文件不能因改名被自动接管，按漂移处理，真实重建留 M4-10。运行中的本地 checkout 不在本次操作中改目录名。

四通道仍为：全新、确认的 v0 内容复制、有效产品升级（同版幂等）、异常停止。v0 从历史源复制到新 R，只纳入 memories/references；skills、mcp、旧脚本与状态原地保留，不运行、不接管。源目标天然分离，不改写旧源索引；旧索引作为原文与链接上下文保留，新索引只索引它。保留清单、恢复材料、逐字节验证与一次导入约束；同路径夹具的快照语义不等于真机必须改写旧源。

活动台账为 schema=3。旧 v1/v2 仅严格只读诊断与保全；旧开发版不承诺升级，旧标记视为漂移停止并指引保全后重装。不提供逆 schema 迁移；升级承诺自首个正式发行开始。真实 v0 memories/references 双目录导入仍保留。

## 支持的执行器

OpenCode 桌面 App 与 CLI 分面核验，CLI-only 不证明桌面存在；支持的原生 CLI 与 App 按各自本地静态证据识别，不要求 Agent 应用签名，详见[操作手册](docs/operations.md#桌面端默认根与验证边界)。真实新会话验收由用户延后统一进行。

支持 Codex、Claude Code、WorkBuddy、DeepSeek Harness（`dsh`）、ZCode（`zcode`）、OpenCode v2（`opencode`）六家。机器安装、再次安装与升级缺省接入支持对象中全部已核验 installed 者，显式重复 `--agent` 限定范围。后三家用户入口为 `~/.dsh/AGENTS.md`、`~/.zcode/AGENTS.md`、`~/.config/opencode/AGENTS.md`，项目均原生读取 `AGENTS.md`，不新增隐藏桥接或 Skill 投影。共用公共记忆索引，各自私文保留。项目命令缺省仍三家；当前实际执行者使用时显式指定自身 ID，不预建其他执行器入口，disabled 不恢复。

两家均仅有默认根的静态支持；DSH 限本次默认 coding `cordis` preset，非默认 `DSH_HOME` 拒绝默认入口接入，`DSH_AGENTS_HOME` 影响共享根，检查不回传变量值。自定义配置未验证；`ZCODE_HOME` 不是 ZCode 规则根。Skill 发现及验收边界见[操作手册](docs/operations.md#桌面端默认根与验证边界)。

Claude Code 的 macOS 原生 CLI 根据受支持的命令入口名、可读可执行文件与 Mach-O 结构记录本地安装事实，不启动二进制，也不把目录名作为产品版本。npm 安装仍按包名与入口核验。自动发现和显式 `--agent` 不调用 `codesign`，不因签名失败、签名标识不同或后端不可用拒绝；这不表示已验证发布者可信或运行成功。空残留配置目录仍仅为 hint，不判 installed；默认 PATH 中的断链、不可读、产品元数据不符或活动来源不明仍为 `unknown`。已核清活动安装时，可在精确请求中显式限定 `search_paths` 与 `user_candidates`，保留原有 PATH 和文件。

本次取消的是 Agent 应用签名硬门槛，CLI 参数不变；合法原生路径、原文与备份保全、精确批准、漂移和恢复保护，以及产品固定 S/R 的来源与内容完整性校验均保留。

## 给执行 Agent 的命令与批准合同

从已核验的活动 C 再次接入时，`scripts/install.py --agent <名字>` 不新增参数；仅在 C/V 与固定持久 export 收据、bytes、mode 全部校验通过时推导自身来源，缺失或漂移拒绝。只有 no-op、`entry_plan=null`、`changes=[]` 且真实静态连接均成立才只读返回 `completed/approval_required=false/approval_plan=null` 并续接 fusion；明确新增或其他变更仍须完整计划批准。

以下参数以当前源码 CLI help 为准；尖括号内容须替换为真实核验值。普通安装来源参数二选一；显式选择执行器的示例如下：

```text
python3 -B scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA>
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent codex --agent claude
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent dsh --agent zcode
```

干净固定源码安装默认读取被跟踪的 `scripts/core-version.json`，无须用户提供内部版本。显式 `--version` 必须与该核心元数据一致；历史无该元数据的源码仍可显式指定版本。发行来源使用发行 manifest 的版本，不借用插件版本，也不伪造发行收据。

`source.json` 含 `root/url/commit/version/files`，不与 source/commit/version 混用。无批准输出 `approval_plan`，批准文件为完整计划加真实 `confirmed_at/reference`，`confirmed_at` 须使用真实 UTC 的 `YYYY-MM-DDTHH:MM:SS[.小数]Z` 格式；不使用 `+00:00` 或本地时区。一次用户确认由执行编排绑定到精确计划，不额外制造逐项确认，也不伪造确认。锁内重核，计划外变化停止。

```bash
python3 -B scripts/install.py --approval-file /absolute/path/install-approval.json
```

`--operation-id` 可绑定操作，重复 `--agent` 限定目标，不豁免安装事实；`--request-file` 承载 conversions、legacy_registries、legacy_source_commits、evidence_files、legacy_identity；隔离演练还可显式传入 search_paths、app_directories、user_candidates，不能把合成探测结果当作本机安装事实。批准 envelope 绑定来源、三版本、现场指纹、精确 changes、R/C/V、请求与有效执行器、恢复路径及旧证据映射。

独立获取为 `--acquire --staging <绝对且不存在目录> --commit <完整SHA> --version <SemVer>`，先预览，批准后加 `--approval-file` 执行；不与普通安装或恢复参数混用。`acquired` 只表示获取完成，不表示产品安装完成。批量启用与 Context Keeper 独立入口见下文；整理使用 `organize-user-memory`，当前项目融合使用 `organize-project-memory --project <绝对路径>`，选择与批准合同见 [SKILL](SKILL.md)。

## Context Keeper 独立尾步

公共用户记忆流程结束（或用户明确暂不整理）后才生成独立 `command=install-context-keeper` 封皮，不在主批准中预填未来同意。交互中仅明确回复“安装”算同意；回车、空格、EOF、跳过或非交互输入均不算同意。独立预览与执行为：

```bash
python3 -B scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper
python3 -B scripts/install.py --context-keeper --approval-file /absolute/ck-approval.json
```

可用 `--operation-id <已完成主操作>` 绑定主操作；此路由与普通安装、获取、恢复互斥。封皮绑定已 committed 主日志、台账、全部实际接入者、Context Keeper pin、执行内容与目标指纹；主产品待恢复时拒绝。Context Keeper 来源须为既存、干净、固定 pin 的持久独立 checkout，可从唯一用户级别名发现或显式提供，目前不自动下载；缺源独立报告 unavailable，主产品保留成功。结果不明不自动重放，Context Keeper 自身回滚不由 memSharing 提供。

仅接入 `dsh/zcode` 时，`--context-keeper` 输出 `status=skipped`、`reason=upstream_unsupported` 与 `skipped_upstream_agents`；交互安装尾步的 `context_keeper` 同样为 `status=skipped`、`reason=upstream_unsupported`，主安装保持 `status=completed`。混合接入执行时，`agents` 仅列受支持的执行器；跳过项列于 `skipped_upstream_agents`，每项为 `{"agent":"dsh或zcode","reason":"upstream_unsupported"}`（`agent` 取实际 ID）。`upstream_unsupported` 是原因，不是顶层状态。

## 诊断报告与用户简报

完整底层报告保留给执行 Agent 和验收使用，不在成功对话中逐项倾倒。至少保留：状态与通道，R/C/V，代码/结构/schema 三版本及升级前后值，URL/commit/清单哈希，op 与恢复位置，已接入/absent/unknown/未选事实，复制/排除/冲突项，实际项目下一步，以及运行时验证状态。

既有字段包括 `status/layout/versions/source/operation_id/recovery/agents/copies/exclusions/project_commands/entry_status/connection_pending`（运行状态位于 `entry_status.<agent>.runtime_acceptance`），预览带 `approval_plan`。下载成功而入口失败必须 partial；无 installed 不得说各家已启用。静态入口读回与新会话表现分开记录，用户简报不添加自检要求。

主产品与 Context Keeper 分层报告：主产品完成后，Context Keeper 可为跳过（`skipped`）、unavailable、失败或 configured；其失败不回滚主产品，也不能合报全成功。configured 仅证明安装与字节读回，不证明执行器新会话已加载。

## 项目使用

进入未登记的 Git 主 checkout 时，用户级规则与公共指南默认接入项目记忆，保留原正文，只建立所需骨架与协议；非 Git 与 linked worktree 不触发。默认接入由当前实际执行者按指南以 `--agent <当前执行者>` 执行，避免不带 agent 参数时按安装事实顺带补齐其他执行器已存在的原生目录；用户显式要求全体或批量接入时仍按现行命令默认，不改 CLI 语义。机器探测到某执行器已安装或其原生目录存在，不等于该执行者当前实际使用。人工入口为 `/mem-sharing` 的“接入项目记忆”，底层示例使用实际项目根：

```bash
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" enable-memory --project /absolute/path/to/project --agent <当前执行者>
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" enable-memory --project /absolute/path/to/project --agent dsh zcode
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" check-memory --project /absolute/path/to/project
```

默认启用不初始化 Context Keeper 记录库、不调用其安装器、不安装项目级 Skill。项目经历初始化由首次 `/context-keeper` 流程负责。

接入完成后，外层执行 Agent 自动进入当前项目的只读融合预览并展示两块（“建议合并的相同规则”与“需要你确认是否合并”），明确“本次融合尚未修改记忆内容”，不能仅给一个可选后续命令就结束。以独立来源文件去重计票，同一 `AGENTS.md` 被多家读取只算一个来源；已有 `AGENTS.md` 条目归默认保留，排除时先逐条询问保留位置；用户选择共享的内容迁到根 `AGENTS.md`，对其他文件仅删除已完整迁移且入口核验后的对应片段。完整交互合同见 [SKILL](SKILL.md) 的“项目记忆融合”。

不带 `--agent` 的通用 enable 不触碰 `CLAUDE.md`，包括已有文件；Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `@AGENTS.md` 引用；其它执行者默认流程不预建，不因机器已装执行器而创建。该兜底规则位于 Claude 自身用户文件、不放公共索引。WorkBuddy 仅在原生目录存在时补桥接，不预建目录。`AGENTS.md` 是共享项目记忆基座，不依赖安装 Codex；只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立，缺失的执行器用户目录不预建。

旧 `remove-memory`、`--memory`、`--no-memory` 已退役，新请求零写拒绝。历史 disabled 只作规则接入 tombstone，默认跳过、不重建；它不否决 Context Keeper 的自动规则，不表示 CK 已停用或入口已删除。使用 `migrate-policy [--project ABS]` 精确预览并批准后，仅退役产品自有且指纹匹配的旧控制与已知旧模板，保留私文、CK 设置和历史数据，不替用户启用 CK。

批量入口先只读预览，待批准退出码为 5；一次批准完整清单后执行：

```bash
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/batch-approval.json
```

递归扫描含目录自身，不跟随目录符号链接，排除 linked worktree；已启用项目跳过，disabled 项目保持停用，须单独恢复。批准绑定目录、完整扫描清单、台账哈希和每项目精确计划；执行前重新核验。某项目失败即停止后续，已完成项目保留，不提供跨项目整体回滚。

## 故障恢复

以下是安装事务恢复。安装后记忆融合中断使用独立的 `recover-memory-fusion --manifest <当前HOME/.mem-sharing/backups/<tx>/manifest.json>`；项目事务加 `--project <当前项目根>`，先预览完整恢复计划，再加 `--approval-file` 精确批准回滚。接口与状态见操作手册第 7 节，核心执行者已回报临时 HOME 恢复测试通过，真实宿主恢复尚未验收；不复用安装批准，不把回滚当作融合完成。

中断现场停止普通安装，保留 journal、锁和材料，不自动删锁，不回到首装。独立预览和获批执行：

```bash
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue --approval-file /absolute/path/recovery-approval.json
```

选择回滚须改为 `--action rollback`，重新预览并批准。before/after 之外第三种字节、材料缺损或工具漂移即停；V 已提交且输出全 after 时只收尾。活动 C 混版时使用报告所指固定恢复工具，不依赖半替换的安装器。

固定升级工具包沿用 `recover.py preview <journal> continue` 与 `recover.py apply <批准计划JSON>`；其他场景入口待集成核对。日常主动版本回退是版本库存的新计划，不等同于故障 rollback，本安装 CLI 不增加未冻结降级参数。

### WorkBuddy 用户入口的接入边界

完整合同见[操作手册](docs/operations.md#workbuddy-用户入口的接入边界)：保留私人正文，按受管块/精确指纹批准接入；installed、静态 connected 与 runtime 分开报告。共享 user scope 入口不由机器安装器接管。

### 已审定 WorkBuddy 修复发行转换

0.1.0 → 0.1.1 支持一次窄范围 `workbuddy-public-index-v1` 合同转换：旧发行来源、前后 `user_entries.py` 指纹固定，`agents.json` 不变；目标来源由外部精确清单绑定，必须显式 `--agent workbuddy`。它不是通用合同升级许可。来源须先提交并固定为干净 checkout，入口子计划纳入整单批准，不能把未提交文件标成旧commit。

代码升级完成后才执行入口事务；入口失败报告partial，使用相同0.1.1来源重新预览、批准同版入口补齐，不重放旧批准。代码中断的固定toolkit恢复只证明代码恢复，结果明确入口尚未运行；不承诺成功发行后自动降回0.1.0。完整外部清单生成、预览/批准及恢复边界见[操作手册](docs/operations.md#010--011-的-workbuddy-入口合同转换)。

### 公共记忆分层发行转换（0.1.3 候选，本地限定验收通过）

以下为旧 0.1.3 公共布局的固定转换兼容合同：当时生成 `memories/topics/使用约定.md`；新安装不生成该指南，菜单与详细流程仅在 Skill。历史转换的固定处理器为 `scripts/agm_core/public_layout.py`，外部 conversion 的 `entries` 固定为 `{"type": "public-memory-layout-v1"}`，沿用既有 `_conversions` 四键 schema（`before/after/direction/entries`）。两个精确前身冻结在 `scripts/agm_core/upgrade.py` 常量：0.1.1（commit `04c32e24b9ab9504514908f2368cddca4356e478`）与 0.1.2 候选（commit `0f690ef7aabf747a23bacc7662c19bee34c4bf52`），各绑定核验过的 tree 哈希。目标版本 0.1.3 由 CLI `--version`／来源清单承载，无版本文件；SOURCE 历史前身身份与合同保持冻结；TARGET 合同三文件 `agents.json`、`user_entries.py`、`public_layout.py` 按当前六家字节冻结为精确 SHA256 字面量，门禁同时核对目标来源清单与运行模块字节一致，再冻结须显式声明并留测试证据。旧 0.1.2 的 `entries=preserve` 只对旧固定合同成立，`user_entries.py` 指纹变化后不能沿用。当前候选拼版共 32 文件，含共享发行解析器；此文件闭包数量不表示已发布。

正常流程一份外层批准绑定代码、公共布局迁移与新增入口装配；显式 `--agent` 仅限定新增接入范围，既有公共依赖仍完整迁移。新增入口按预测 V2 快照预览，执行后回到真实现场严格比较原批准。预览阶段即触发未登记读者门禁，零写拒绝可预见的失败升级：只有存在已登记公共依赖（import 引用或受管块消费者）的入口才迁移，无依赖私文仅观察保全、零更新；已登记但入口缺失拒整单；未登记的 Claude 读者被阻断并指引先显式 `--agent claude` 完成登记再重新预览，不暗中接入。代码已同版 0.1.3 而布局仍为旧状时，预览继续生成迁移子计划，布局与入口全新才是真零写 noop；其他版本的 noop 不派迁移。执行先完成代码与台账 V，再以同一批准运行迁移事务（公共 MEMORY、公共指南、全部已登记依赖用户入口，V2 最后提交）；只有 V2 读回才报告 completed，否则 partial 并给出 `migration_phase=pending/recovery_required`。

两阶段恢复入口分开。代码阶段沿用既有 `--recover <升级journal> --action continue|rollback` 与固定 toolkit；迁移阶段用 `--recover <迁移journal> --action continue|rollback`，标准动作映射为 `continue`=`finish`（仅 V2 已提交侧允许）、`rollback` 仅限 V1 侧，V1 状态只允许回滚，重做迁移必须新预览批准。固定 launcher 同样可用：`recover.py preview <journal> continue|rollback` 与 `recover.py apply <批准JSON>`。等值 V 以完整可信事务 manifest 状态 `committed` 为分界，非 committed 即拒绝收尾；非等值以 V2 读回判定；`last_operation_id` 不变；未尝试输出出现第三种字节即保全停止；准备阶段无任何 attempt 且全部 before 时可仅清场收尾。

外部 conversion 条目示例（占位值须替换为真实核验值；目标 `<完整SHA>` 为 0.1.3 真实提交后的完整值，不得用未提交工作树配占位 SHA 伪造）：

```text
{"before": {"schema_version": 3, "product_structure_version": 1,
            "product_code_version": "0.1.1 或 0.1.2",
            "source": {"url": "https://github.com/vincent4j/mem-sharing",
                       "commit": "<前身完整SHA>", "tree_sha256": "<前身tree>"}},
 "after": {"schema_version": 3, "product_structure_version": 1, "product_code_version": "0.1.3",
           "source": {"url": "https://github.com/vincent4j/mem-sharing",
                      "commit": "<目标完整SHA>", "tree_sha256": "<目标tree>"}},
 "direction": "upgrade", "entries": {"type": "public-memory-layout-v1"}}
```

将上述条目放入 request.json 的 `conversions` 数组（`{"conversions": [条目]}`）；source.json 必须是从最终干净来源核验得到的 source 对象。批准文件保存完整 `approval_plan`，并附严格 UTC Z 的 `confirmed_at` 与 `reference`，不改计划内容。预览与执行沿用普通安装入口，可用重复 `--agent` 限定新增接入范围，既有公共依赖仍完整迁移：

```bash
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --request-file /absolute/path/request.json
python3 -B scripts/install.py --approval-file /absolute/path/upgrade-approval.json
```

验证边界：本转换为已实现候选，证据为静态与合成测试——单元 557 项（556 过、1 error）、集成 74 项（72 过、2 失败）；修复后定向复测（单元 11 项与原失败的集成 2 项）均通过，全量未重跑，不宣称一次全绿。真实 HOME 未被改动，不覆盖 0.1.2 候选既有升级与验收证据。最终主验收结论与发行版本 hash 以[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)的权威记录收口，本节不另造重复报告。

## 整机卸载

整机卸载使用 `python3 -B scripts/agm.py uninstall-machine --backup-dir <全新外置目录>` 先预览，再以 `--approval-file` 精确批准。归还当前完整公共记忆给每个实际接入者的自身用户目录，再核验、清依赖、最后删除产品；不是恢复安装前。外置 manifest/recover.py 与独立解释器支持删除代码后的精确恢复。未知/漂移阻断，项目 AGENTS、有效 Claude/WB 桥接及 CK 默认保留。完整数据与门槛见[整机卸载方案](docs/uninstall-design.md)。

CLI 的 `scope=standalone_declared`、`host_plugin=not_applicable` 仅声明调用范围；Paseo 为 `machine_and_paseo`，机器 completed 但插件仍在时 overall=partial。必须在插件移除前经外置入口独立绑定真实安装 ID/来源/CLI/daemon/live serverId，再用户 remove、同目标 full-list check 证实缺席，最后才可另选卸载 CK。disabled、查询错误、能力/版本错误均不算 removed；默认保留 CK，尾步另行精确批准。正式 payload 待干净提交与版本授权后生成，本轮源码/合成验证不等于实际宿主卸载或六家新会话加载验收。

### 自然语言发起同一卸载流程

用户无需进入源码目录：已接入的 Agent 读到公共 L0 后，明确的“卸载 memSharing / 卸载 mem-sharing / 不想用这个共享记忆工具了，帮我卸载”会按公共索引的操作入口读取已核验 C 的 `SKILL.md` 与[完整卸载合同](docs/uninstall-design.md)，直接预览。路径与命令由安装时按 C 生成，使用 `python3 -B`；不凭路径存在信任代码，也不在预览创建备份目录。含糊的“卸载这个项目”先澄清，明确卸载请求也不替代看过精确计划后的批准。

不能因换 Agent 发起而省略 Paseo 宿主义务；沿现有来源与参数合同补齐，未知先停止。已卸载或代码缺失不自动重装。安装代码已具备当前兼容实现时，旧公共指南通过 `migrate-policy` 的精确模板迁移接入新路由；旧 C 不兼容时零写拒绝，须先按现有精确安装/升级流程更新代码（预览、批准、私文保留、未知定制拒绝、重复零写）；生成指南在真正归还时退休，original 原文保全，active 不再指向被删代码。六家真实模型触发仍 pending。

机器安装或当前项目启用返回 `status=completed` 时附带 `fusion`，包含 `status`、`automatic_continue`、`can_decline`、`command`、`project` 与 `preview`。`command` 分别为 `organize-user-memory` 或 `organize-project-memory`；用户阶段 `project=null`，项目阶段为当前项目绝对路径。正常 `pending_selection` 时 `automatic_continue:true/can_decline:true`，外层按 `fusion.preview.prompt` 保留完整展示骨架后继续选择，不以单表或命令替代；条目摘要不得写回原计划。`blocked` 时 `automatic_continue:false/can_decline:true`，明确报告实际阻塞原因、`preview.errors/blocked_entries` 和 `preview.next_action` 的下一步；`prompt/approval_plan` 仅供只读诊断，不称可继续选择或已融合、不执行修改。用户可保留现状并另起 `--decline` 预览，不伪造治理命令。入口接入可能已写入文件，提示限定为“本次融合尚未修改记忆内容”；安装或启用成功与融合完成分别报告，不复用接入批准执行融合。

### 逐 Agent 接入与全机卸载

显式 `--agent codex` 只安装 Codex 的记忆引用和原生 Skill，不预建 Claude 入口；之后 `--agent claude` 补接入 Claude，复用同一套 R/C/V。入口安装阶段不改公共 memories 文件集或正文。新 Agent 既有私文完整保留，随后提供单独批准的增量整理预览；同语境同字节的已有公共正文复用，各来源位置与次数分别记录。独有、未选、差异和冲突内容不静默搬移或覆盖。已接入 Agent 同版重复安装返回“已安装，已接入”，零写且不再次整理。

从任意 Agent 发起卸载均走同一 `uninstall-machine` 全机核心，按受管台账移除全部已安装 native Skill 与引用，归还当前公共正文；保护用户自建同名 Skill、其他 Skill 与私文。删除前仍须外置备份、零写预览、精确批准和宿主义务核验。原生目录布局证据不代表真实 `/mem-sharing` 调用通过。

新装公共索引只提示读取存在的用户规则与按需 Skill，不生成《使用约定》及索引条目，不硬编码用户个人规则。首次进入未登记 Git 主目录时按 Skill 自动接入，跳过 disabled、非 Git 和 linked worktree，保留已有内容。旧安装的指南仅按原台账与来源兼容处理，不由新安装无批准删除。


本轮安装交互：集中确认安装范围一次→静默安装→建议合并的相同规则/需要你确认是否合并两块→明确选择即执行并简报→最后 CK。选择直接绑定完整计划及真实消息，不再次询问确认；查看仍零写。CLI 用 `--selection-plan-file` 绑定展示时现场，用 `--selection-reference` 保存真实选择，漂移拒绝。CK 名单取全机实际安装者，不限本次接入者；固定旧上游不支持者明确跳过，不冒称安装成功。
