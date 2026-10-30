# 安装 memSharing

memSharing · 多 Agent 记忆共享与融合。把下面这句话交给正在使用的 Agent，与 README 一致：

```text
请从 https://github.com/vincent4j/mem-sharing 安装 memSharing（多 Agent 记忆共享与融合）。
```

本页供未安装产品的 Agent 直接使用，无须先有产品 Skill、v0 工具、Context Keeper 或项目配置。依据 [DESIGN v1.14](DESIGN.md) 与 [M4 决策](docs/plan/decisions-m4.md)，冲突时采用后续 §14—§24（后续替代见 §25—§26） 裁定。本页描述目标流程，执行状态以实际结果为准；[M4-09 案例](docs/acceptance/m4/m4-09/cases.md) 尚待执行。

## 用户看到的安装对话

先回复：“我来安装 memSharing，先检查运行环境和本机 Agent。”随即执行以下流程。

1. **先检查，集中确认。** 检查 Python、Git、本机已适配 Agent，汇总哪些环境就绪、哪些依赖待安装、检测到哪些 Agent，并明确将为这些 Agent 安装入口。一次确认，回车即开始；不把 unknown 或残留目录列为已安装。
2. **确认后静默执行。** 准备依赖、获取固定来源、核验、安装和接入正常情况下不逐步播报、不重复询问。冲突、漂移、v0 身份不明或实际权限阻塞时停止，说明具体现场与所需处置；一次确认不授权覆盖未知内容。
3. **完成后极简报告。** 例如：“已创建用户记忆中枢，已为 Codex、Claude Code 启用用户记忆入口。”名单必须来自实际结果。不报产品代码路径，不提未安装执行器，不加新会话自检提示，也不加“将来新装 Agent”提示句。后装接入说明在 [README](README.md)。失败或 partial 不套用成功句式。
4. **紧接着询问 CK。** 使用以下固定正向话术，回车同意，输入 n 跳过：

> 最后：为了让你的所有项目都能记住并续接工作经历，我们将为已接入的每个 Agent 安装项目经历引擎 Context Keeper（用户级）——它与本产品出自同一作者。同意吗？

同意后由安装器编排 CK 自有安装器，为**全部已接入执行器**完成用户级安装，Skill 落位由 CK 负责。只有明确的交互回车才算同意；无响应、非交互 EOF 不等于同意。装后只提醒：“在任意需要的项目里使用 `/context-keeper`。首次使用按它的流程创建项目记录库，记录库随 Git 走，各家 Agent 共用。”到此结束。

跳过 CK 不影响用户记忆与项目记忆。装 CK 不等于所有项目立即创建记录库；项目经历按项目首次命令激活。装后 CK 的命令、记录格式、保存与查找行为均由 CK 自行定义，memSharing 只保留桥接文本协议。

## 运行时准备

当前生产范围为 macOS。Python **≥3.9 的任意版本**直接放行，不强制替换为某个特定版本。Python 未安装或低于 3.9 时，经上述确认通过系统包管理器安装最新稳定版；Git 缺失同样安装，全部就绪后继续。检测、安装与重新核验属于外层安装编排，缺 Python 时不能声称 Python 安装器已运行。

使用现场可用的系统包管理器，例如 Homebrew；不为本文自行固定版本或远程脚本管道。包管理器不存在、权限不足、安装失败或安全验证受阻时如实暂停，不把依赖安装失败报作 memSharing 完成。网络任务仍遵守环境委派边界。

<!-- TODO（与代码侧核对）： 系统检查、一次确认、Python/Git 自动安装的外层执行入口、包管理器选择及不存在时的处理；不得把当前 Python CLI 的缺依赖诊断分支当作已实现自动安装。 -->

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

<!-- TODO（与代码侧核对）： 分离源/目标后的 v0 阅读包、索引与恢复材料实际路径，以及旧产品标记/旧台账到新 product_id 的拒绝或迁移识别；不把改名当作覆盖旧现场的授权。 -->

## 给执行 Agent 的命令与批准合同

以下为既有参数面，新版集成时复核；尖括号内容须替换为真实核验值。普通安装预览二选一：

```text
python3 -B scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent codex --agent claude
```

`source.json` 含 `root/url/commit/version/files`，不与 source/commit/version 混用。无批准输出 `approval_plan`，批准文件为完整计划加真实 `confirmed_at/reference`，一次用户确认由执行编排绑定到精确计划，不额外制造逐项确认，也不伪造确认。锁内重核，计划外变化停止。

```bash
python3 -B scripts/install.py --approval-file /absolute/path/install-approval.json
```

`--operation-id` 可绑定操作，重复 `--agent` 限定目标，不豁免安装事实；`--request-file` 承载既有 conversions、legacy_registries、legacy_source_commits、evidence_files、legacy_identity 输入。批准 envelope 绑定来源、三版本、现场指纹、精确 changes、R/C/V、请求与有效执行器、恢复路径及旧证据映射。

独立获取为 `--acquire --staging <绝对且不存在目录> --commit <完整SHA> --version <SemVer>`，先预览，批准后加 `--approval-file` 执行；不与普通安装或恢复参数混用。`acquired` 只表示获取完成，不表示产品安装完成。默认启用、整理向导、批量启用和 CK 安装的新接口未冻结部分不得自造参数。

## 诊断报告与用户简报

完整底层报告保留给执行 Agent 和验收使用，不在成功对话中逐项倾倒。至少保留：状态与通道，R/C/V，代码/结构/schema 三版本及升级前后值，URL/commit/清单哈希，op 与恢复位置，已接入/absent/unknown/未选事实，复制/排除/冲突项，实际项目下一步，以及运行时验证状态。

既有字段包括 `status/layout/versions/source/operation_id/recovery/agents/copies/exclusions/project_commands/runtime_acceptance/connection_pending`，预览带 `approval_plan`。下载成功而入口失败必须 partial；无 installed 不得说各家已启用。静态入口读回与新会话表现分开记录，用户简报不添加自检要求。

<!-- TODO（与代码侧核对）： 新报告中的 CK 同意/跳过/失败、依赖准备结果、partial 成功子项、无 installed 分支及不再使用的历史字段清理。保留诊断完整性，不恢复已取消的用户路径播报。 -->

## 项目使用

进入未启用的 Git 主 checkout 时，用户级规则默认启用项目记忆，保留原正文，只建立所需骨架与协议；非 Git 不触发。人工入口为 `/mem-sharing` 的“给项目启用记忆”，底层示例使用实际项目根：

```bash
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" enable-memory --project /absolute/path/to/project
python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" check-memory --project /absolute/path/to/project
```

默认启用不初始化 CK 记录库、不调用 CK 安装器、不安装项目级 Skill。项目经历初始化由首次 `/context-keeper` 流程负责。CLAUDE 引用与 WorkBuddy 桥接按执行器在该项目实际使用创建，不因机器已装执行器而预创建。

`remove-memory --project ...` 只停用指定项目允许撤销的受管单元，保留机器入口、规则正文与记录库；没有完整机器卸载命令。项目命令不隐式安装或升级机器产品。

## 故障恢复

中断现场停止普通安装，保留 journal、锁和材料，不自动删锁，不回到首装。独立预览和获批执行：

```bash
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue --approval-file /absolute/path/recovery-approval.json
```

选择回滚须改为 `--action rollback`，重新预览并批准。before/after 之外第三种字节、材料缺损或工具漂移即停；V 已提交且输出全 after 时只收尾。活动 C 混版时使用报告所指固定恢复工具，不依赖半替换的安装器。

固定升级工具包沿用 `recover.py preview <journal> continue` 与 `recover.py apply <批准计划JSON>`；其他场景入口待集成核对。日常主动版本回退是版本库存的新计划，不等同于故障 rollback，本安装 CLI 不增加未冻结降级参数。
