# 安装 memSharing

memSharing · 多 Agent 记忆共享与融合。把下面这句话交给正在使用的 Agent，与 README 一致：

```text
请从 https://github.com/vincent4j/mem-sharing 安装 memSharing（多 Agent 记忆共享与融合）。
```

本页供未安装产品的 Agent 直接使用，无须先有产品 Skill、v0 工具、Context Keeper 或项目配置。依据 [DESIGN](DESIGN.md) 与[系统架构](docs/architecture.md)。本页描述目标流程，执行状态以实际结果为准；M4-09 的本地范围与阻断项见[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)，真机项归 M4-10。

## 用户看到的安装对话（五拍）

第一拍：用户发出上面的一句安装请求。Agent 回复：“我来安装 memSharing，先检查运行环境和本机 Agent。”随后第二拍检查汇总与回车确认，第三拍静默安装并给结论，第四拍正向询问 Context Keeper，第五拍只提醒它的用法。具体如下。

1. **先检查，集中确认。** 检查 Python、Git、本机已适配 Agent，汇总哪些环境就绪、哪些依赖待安装、检测到哪些 Agent，并明确将为这些 Agent 安装入口。一次确认，回车即开始；不把 unknown 或残留目录列为已安装。
2. **确认后静默执行。** 准备依赖、获取固定来源、核验、安装和接入正常情况下不逐步播报、不重复询问。冲突、漂移、v0 身份不明或实际权限阻塞时停止，说明具体现场与所需处置；一次确认不授权覆盖未知内容。
3. **完成后极简报告。** 例如：“已创建用户记忆中枢，已为 Codex、Claude Code 启用用户记忆入口。”名单必须来自实际结果。不报产品代码路径，不提未安装执行器，不加新会话自检提示，也不加“将来新装 Agent”提示句。后装接入说明在 [README](README.md)。失败或 partial 不套用成功句式。
4. **紧接着询问 Context Keeper。** 使用以下固定正向话术，回车同意，输入 n 跳过：

> 最后：为了让你的所有项目都能记住并续接工作经历，我们将为已接入且受支持的 Agent（Codex、Claude Code、WorkBuddy）安装项目经历引擎 Context Keeper（用户级）——它与本产品出自同一作者。同意吗？

同意后由安装器编排 Context Keeper 自有安装器，为**已接入的 Codex、Claude Code、WorkBuddy**完成用户级安装，Skill 落位由 Context Keeper 负责。只有明确的交互回车才算同意；无响应、非交互 EOF 不等于同意。装后只提醒：“在任意需要的项目里使用 `/context-keeper`。首次使用按它的流程创建项目记录库，记录库随 Git 走，各家 Agent 共用。”到此结束。

固定 pin 的 Context Keeper 安装器仅支持旧三家的 flags；DeepSeek Harness（`dsh`）与 ZCode（`zcode`）跳过用户级 CK 安装（`reason=upstream_unsupported`）。混合接入时旧三家仍可安装，不影响新两家的 memSharing 接入；不可把两家报告为 CK 已安装。

跳过 Context Keeper 不影响用户记忆与项目记忆。装 Context Keeper 不等于所有项目立即创建记录库；项目经历按项目首次命令激活。装后 Context Keeper 的命令、记录格式、保存与查找行为均由其自行定义，memSharing 只保留桥接文本协议。

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

中枢只包含 memories、references、backups、var，不建 skills/mcp，不创建 memSharing Skill 投影；菜单 `/mem-sharing` 由用户级规则块承载。旧标记与现网文件不能因改名被自动接管，按漂移处理，真实重建留 M4-10。运行中的本地 checkout 不在本次操作中改目录名。

四通道仍为：全新、确认的 v0 内容复制、有效产品升级（同版幂等）、异常停止。v0 从历史源复制到新 R，只纳入 memories/references；skills、mcp、旧脚本与状态原地保留，不运行、不接管。源目标天然分离，不改写旧源索引；旧索引作为原文与链接上下文保留，新索引只索引它。保留清单、恢复材料、逐字节验证与一次导入约束；同路径夹具的快照语义不等于真机必须改写旧源。

活动台账为 schema=3。旧 v1/v2 仅严格只读诊断与保全；旧开发版不承诺升级，旧标记视为漂移停止并指引保全后重装。不提供逆 schema 迁移；升级承诺自首个正式发行开始。真实 v0 memories/references 双目录导入仍保留。

## 支持的执行器

支持 Codex、Claude Code、WorkBuddy、DeepSeek Harness 桌面端（`dsh`）与 ZCode 桌面端（`zcode`）。缺省目标仍为 `codex/claude/workbuddy`，新增两家须显式选择；用户入口分别为 `~/.dsh/AGENTS.md`、`~/.zcode/AGENTS.md`，项目均原生读取 `AGENTS.md`，不新增隐藏桥接或 Skill 投影。共用公共记忆索引，各自私文保留。默认项目接入由当前实际执行者显式使用自身 ID，不预建其他执行器入口，disabled 不恢复。

两家均仅有默认根的静态支持；DSH 限本次默认 coding `cordis` preset，非默认 `DSH_HOME` 拒绝默认入口接入，`DSH_AGENTS_HOME` 影响共享根，检查不回传变量值。自定义配置未验证；`ZCODE_HOME` 不是 ZCode 规则根。Skill 发现及验收边界见[操作手册](docs/operations.md#桌面端默认根与验证边界)。

## 给执行 Agent 的命令与批准合同

以下参数以当前源码 CLI help 为准；尖括号内容须替换为真实核验值。普通安装来源参数二选一；显式选择执行器的示例如下：

```text
python3 -B scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent codex --agent claude
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent dsh --agent zcode
```

`source.json` 含 `root/url/commit/version/files`，不与 source/commit/version 混用。无批准输出 `approval_plan`，批准文件为完整计划加真实 `confirmed_at/reference`，`confirmed_at` 须使用真实 UTC 的 `YYYY-MM-DDTHH:MM:SS[.小数]Z` 格式；不使用 `+00:00` 或本地时区。一次用户确认由执行编排绑定到精确计划，不额外制造逐项确认，也不伪造确认。锁内重核，计划外变化停止。

```bash
python3 -B scripts/install.py --approval-file /absolute/path/install-approval.json
```

`--operation-id` 可绑定操作，重复 `--agent` 限定目标，不豁免安装事实；`--request-file` 承载 conversions、legacy_registries、legacy_source_commits、evidence_files、legacy_identity；隔离演练还可显式传入 search_paths、app_directories、user_candidates，不能把合成探测结果当作本机安装事实。批准 envelope 绑定来源、三版本、现场指纹、精确 changes、R/C/V、请求与有效执行器、恢复路径及旧证据映射。

独立获取为 `--acquire --staging <绝对且不存在目录> --commit <完整SHA> --version <SemVer>`，先预览，批准后加 `--approval-file` 执行；不与普通安装或恢复参数混用。`acquired` 只表示获取完成，不表示产品安装完成。批量启用与 Context Keeper 独立入口见下文；整理向导目前提供模块 API，不得自造 CLI 子命令。

## Context Keeper 独立尾步

主安装完成后才生成独立 `command=install-context-keeper` 封皮，不在主批准中预填未来同意。交互中仅真实回车同意，空格、EOF 或非交互输入均不算同意。独立预览与执行为：

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

进入未登记的 Git 主 checkout 时，用户级规则与公共指南默认启用项目记忆，保留原正文，只建立所需骨架与协议；非 Git 与 linked worktree 不触发。默认接入由当前实际执行者按指南以 `--agent <当前执行者>` 执行，避免不带 agent 参数时按安装事实顺带补齐其他执行器已存在的原生目录；用户显式要求全体或批量接入时仍按现行命令默认，不改 CLI 语义。机器探测到某执行器已安装或其原生目录存在，不等于该执行者当前实际使用。人工入口为 `/mem-sharing` 的“给项目启用记忆”，底层示例使用实际项目根：

```bash
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" enable-memory --project /absolute/path/to/project --agent <当前执行者>
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" enable-memory --project /absolute/path/to/project --agent dsh zcode
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" check-memory --project /absolute/path/to/project
```

默认启用不初始化 Context Keeper 记录库、不调用其安装器、不安装项目级 Skill。项目经历初始化由首次 `/context-keeper` 流程负责。不带 `--agent` 的通用 enable 不触碰 `CLAUDE.md`，包括已有文件；Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `@AGENTS.md` 引用；其它执行者默认流程不预建，不因机器已装执行器而创建。该兜底规则位于 Claude 自身用户文件、不放公共索引。WorkBuddy 仅在原生目录存在时补桥接，不预建目录。`AGENTS.md` 是共享项目规则基座，不依赖安装 Codex；只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立，缺失的执行器用户目录不预建。

`remove-memory --project ...` 撤销指定项目允许撤销的受管入口与桥接，保留机器安装、用户级接入、规则正文和全部数据；项目登记 disabled，默认流程不会重新启用。重新启用须显式 `enable-memory --project ... --memory` 并批准精确计划。没有完整机器卸载命令，项目命令不隐式安装或升级机器产品。

进阶 `enable-memory --project ... --no-memory` 保留规则入口，登记 disabled，禁止自动项目经历记录与初始化；它与菜单“给项目停用记忆”的撤入口结果不同。已有 Context Keeper 自动规则不能覆盖该政策；这是 Agent 遵守的规则，不是 Context Keeper 脚本的硬拒写接口。

批量入口先只读预览，待批准退出码为 5；一次批准完整清单后执行：

```bash
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/batch-approval.json
```

递归扫描含目录自身，不跟随目录符号链接，排除 linked worktree；已启用项目跳过，disabled 项目保持停用，须单独恢复。批准绑定目录、完整扫描清单、台账哈希和每项目精确计划；执行前重新核验。某项目失败即停止后续，已完成项目保留，不提供跨项目整体回滚。

## 故障恢复

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

公共记忆分层把六项菜单与详细维护规则集中到公共指南 `memories/topics/使用约定.md`，`MEMORY.md` 瘦身为读取契约与真实主题索引，各执行器用户文件只保留公共指针与自身规则。该转换已在 0.1.3 候选实现：固定处理器为 `scripts/agm_core/public_layout.py`，外部 conversion 的 `entries` 固定为 `{"type": "public-memory-layout-v1"}`，沿用既有 `_conversions` 四键 schema（`before/after/direction/entries`）。两个精确前身冻结在 `scripts/agm_core/upgrade.py` 常量：0.1.1（commit `04c32e24b9ab9504514908f2368cddca4356e478`）与 0.1.2 候选（commit `0f690ef7aabf747a23bacc7662c19bee34c4bf52`），各绑定核验过的 tree 哈希。目标版本 0.1.3 由 CLI `--version`／来源清单承载，无版本文件；目标合同三文件（`agents.json` 不变，`user_entries.py` 与新增 `public_layout.py` 的精确 SHA256）为冻结字面量，门禁同时核对目标来源清单与运行模块字节一致，再冻结须显式声明并留测试证据。旧 0.1.2 的 `entries=preserve` 只对旧固定合同成立，`user_entries.py` 指纹变化后不能沿用。当前候选拼版共 31 文件。

正常流程一份外层批准绑定两阶段，且请求不得带 `--agent`（携带即拒绝该转换）。预览阶段即触发未登记读者门禁，零写拒绝可预见的失败升级：只有存在已登记公共依赖（import 引用或受管块消费者）的入口才迁移，无依赖私文仅观察保全、零更新；已登记但入口缺失拒整单；未登记的 Claude 读者被阻断并指引先显式 `--agent claude` 完成登记再重新预览，不暗中接入。代码已同版 0.1.3 而布局仍为旧状时，预览继续生成迁移子计划，布局与入口全新才是真零写 noop；其他版本的 noop 不派迁移。执行先完成代码与台账 V，再以同一批准运行迁移事务（公共 MEMORY、公共指南、全部已登记依赖用户入口，V2 最后提交）；只有 V2 读回才报告 completed，否则 partial 并给出 `migration_phase=pending/recovery_required`。

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

将上述条目放入 request.json 的 `conversions` 数组（`{"conversions": [条目]}`）；source.json 必须是从最终干净来源核验得到的 source 对象。批准文件保存完整 `approval_plan`，并附严格 UTC Z 的 `confirmed_at` 与 `reference`，不改计划内容。预览与执行沿用普通安装入口，不得附加 `--agent`：

```bash
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --request-file /absolute/path/request.json
python3 -B scripts/install.py --approval-file /absolute/path/upgrade-approval.json
```

验证边界：本转换为已实现候选，证据为静态与合成测试——单元 557 项（556 过、1 error）、集成 74 项（72 过、2 失败）；修复后定向复测（单元 11 项与原失败的集成 2 项）均通过，全量未重跑，不宣称一次全绿。真实 HOME 未被改动，不覆盖 0.1.2 候选既有升级与验收证据。最终主验收结论与发行版本 hash 以[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)的权威记录收口，本节不另造重复报告。
