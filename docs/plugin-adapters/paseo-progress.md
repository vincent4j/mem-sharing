# Paseo 插件开发进度

2026-10-31：用户已批准 Paseo 单平台开发及必要共享代码，Orca 冻结。G1 为技术证据门槛，同范围实现不重复征求许可。真实用户 HOME、主 daemon 安装/重启、版本调整、提交推送和发布未授权。

使用 do 技能编排；其自动 commit/push 步骤被项目禁止。paseo-progress 全局工具已由主 Agent 实测缺 zod，使用本文替代，不修全局插件。

| 范围 | 状态 | 执行者与证据 |
| --- | --- | --- |
| PA-00 / 03 官方 API、私有依赖来源 | API 已核查；供应阻断 | 章教授规定路线耗尽，缺固定双架构资产/hash/许可；不继续同路重试 |
| PA-01 / 06 / 07 SDK、Node 依赖层与宿主实现 | shared v5 通过；host20源码/合成独立通过 | 突突兔 54ba84c6-4f0f-4352-9df0-9012dd7c2d92，实际 zcode / GLM-5.3、yolo、high 已读回 |
| PA-02 / 04 / 05 发行身份与核心接入 | 核心已集成，合成与独立审核通过；宿主接线未验收 | 呱唧 5c8d7fb7-8eca-4a66-9e3a-a68f3f9e8816，实际 codex / gpt-6.1-sol、full-access、medium 已读回 |
| PA-09 CK 可选尾步 | 本地固定pin获取及原CLI安装已合成验证，网络/新会话pending | 固定来源、独立批准、不改上游、不模拟自动保存 |
| PA-10 / 11 整合验证与可 review 交付 | 源码/合成收口；供应阻断、真实宿主 pending | 不代表真实安装或发布授权 |
| Orca 全部任务 | 本轮不执行 | 不创建或修改 plugins/orca，不做探针/调查 |

独立 worktree：`../tututu-paseo-adapter`（tututu/paseo-adapter）、`../guaji-paseo-release`（guaji/paseo-release）。两者只读本目录未提交规划；文件所有权分别为插件/Node 层与 Python/发行层。禁止提交；整合按明确文件清单和 hash，保留主工作区 CK dirty。主 Agent 单点维护 CK 记录，本协调者不写 CK。

派发时证据：Profile 与 title/create/readback 已完成，开发任务已实际派发。当前结果以上表与下方追加的阶段证据为准。

## 首阶段发现

- 呱唧静态核查：`--source-manifest` 可复用；库存 marker 严格绑定来源 URL、S 与树 hash。恢复仍依赖原 source.root，不能仅使用可随插件删除的 payload。正在实现/验证独立批准的持久 export，再调用原安装器，不另造机器台账。
- 章教授官方核查：Paseo 无独立 confirm() API；Command Center + typed RPC + 受控 Modal/一次性面板为可实现组合。目录使用 workspace.directory 或实际 agent.cwd，provider 使用 agent.provider；交互组合尚需类型检查与真实宿主验证。
- Python 供应候选为 python-build-standalone install_only；精确 release 资产/SHA 清单的 agent-reach 读取失败 UPSTREAM_BROKEN，已要求按规定链继续核查固定稳定发行。Git 在 daemon 必然可用未证实。不得编 URL/hash；可测试供应协议，不能标记依赖即用通过。
- 当前阶段 API/源码静态证据与合成实现并行推进，真实隔离宿主仍 pending；Orca 范围保持冻结。

## 首批代码与合成验证

呱唧工作区已实现 `scripts/agm_core/plugin_release.py`、`tools/plugin-release/release.py`、`scripts/install.py` 的 `--release-request`、`user_install.py/upgrade.py` 的锁内来源复验、`tests/unit/test_plugin_release.py`。尚未复制到主工作区，等待稳定文件 hash。

执行者报告：新发行测试 10/10 通过（持久 acquisition receipt 版 37.781s），原 installer 22/22 通过（2.710s）。覆盖 S/R 一致、两入口同源、同版零写、dirty/pin/载荷模式与额外节点/软链接篡改拒绝、同版异内容和无 conversion 拒绝、插件源移除后中断恢复。全量回归在跑，尚不标通过。供应研究按规定链耗尽，未取得可发布私有 Python/Git 固定资产清单；已有解释器路径与缺失依赖拒绝继续实现，不以预装产品作为回退。

## 核心整合与审查

定向增强版 12/12（66.569s）、冷进程 1/1（3.103s）已报告通过。首次全量出现库存 rollback 的只读模式误判：已改用 upgrade 自身库存来源校验，非放宽 hash；冻结后全量重新执行，结果待回传。新增编译期 `CORE_RELEASE_MANIFEST_SHA256` 生成文件合同，客户端不能覆盖。

8 文件已按 [paseo-core-files.json](paseo-core-files.json) 校验源 hash、目标 HEAD 基线后整合，未提交。只读独立呱唧 `33be2cf8-f3fa-4400-afec-f34b417ef548` 审查来源、精确批准、锁与恢复，Profile/title 已读回。主 Agent 的 CK dirty 未改。GLM 的 Node/客户端代码仍在独立 worktree 编写，尚未集成。

独立审查已通过（仅上述 8 文件）：前后 SHA 一致；export/首装拿锁时篡改源的两个临时 HOME 探针均拒绝且目标未落地；删除历史源后的库存 rollback 定向 1 项通过；未弱化 S/R、同版/conversion、锁与恢复门禁。该结论不覆盖 Node/Paseo 集成或真实宿主。全量首轮失败明细已保留：旧闭合文件数断言、库存 rollback 分支、修改源码期间 toolkit 漂移；修复后冻结重跑结果仍待回传。

冻结版全量 integration 已通过：75 tests / 212.509s / exit 0。全量 unit 尚在运行。全部是临时 Git/HOME 与已有解释器验证，不是宿主实装。GLM 已落盘公共 Node 源码及测试（进程、JSON、摘要、Python/Git 探测、供应清单、下载和 tar 安全解包）；未报告测试通过，不提前整合。

冻结版全量最终结果：unit 598/598，463.570s；integration 75/75，212.509s，均 exit 0。执行者原始工具回执：unit 启动 `1f0832` / session `97188` / 最终 `37f2d0`，integration 启动 `4c859f` / session `75545` / 最终 `af0e2f`。stdout/stderr 当时由工具合并捕获，没有独立日志文件；未为取证重跑。证据汇总保存在 [paseo-core-evidence.json](paseo-core-evidence.json)，协调者再次核对整合后 8 hash 全部一致。核心静态与合成门槛通过；GLM 插件层和真实宿主仍未据此通过。

## GLM 共享层整合

`plugins/shared` 真源、测试、同步脚本及 `plugins/paseo/server/shared/common` 生成副本已按 [paseo-shared-files.sha256](paseo-shared-files.sha256) 整合。清单实际 31 项（执行者自报 32 已纠正，首次复制在数量断言时零写停止，随后按完整清单逐项核验后复制）。开发 identity 为空串并拒绝 bootstrap，不是假发行 hash。

原始 [Node 测试日志](paseo-shared-test.log)：57/57、fail 0、约 1.93s，Node v22.22.3；合成/本地 HTTP 夹具，不代表真实供应就绪。只读 reviewer 33be2cf8 继续审进程、下载、tar、供应与生成边界，未覆盖尚未整合的 Paseo 界面/编排。GLM 继续真实 CLI 桥接和类型检查。

共享层独立审查退回，6 项待 GLM 修复：tar rename 失败误删既有目标；扩展头/硬链接复制绕过容量限制；tar 执行位丢失；超时仅杀直接 child 而孙进程持管道；下载非法重定向/早期写盘错误未捕获；Git 缺 CLT 前检与版本输出校验。前三类最小探针已复现；不可将 57 测试通过等同审查通过。禁止清理任何既有非本操作目标。该批代码未安装运行于真实 HOME。

联调另发现原 CLI 的非 TTY remove 前置门不暴露 JSON 计划、enable 已登记修补可能免新批准写入。已授权核心作者窄补 enable/remove `--preview` 只读接口（默认语义不变、与批准互斥、不扩 batch），插件必须用显式预览而非假定普通调用零写。新增内核差异将独立验证，不沿用原 8 文件的全部通过结论。

`--preview` 三文件已按 [paseo-preview-files.json](paseo-preview-files.json) 核验源 SHA 与目标 HEAD 后整合。作者定向 6 套 178/178：preview 8、cli 106、m204_enable 29、m406_cli 7、m406_lifecycle 20、review_r2_r3 8；原 8 文件仍全 hash 一致。预览用例检查全 HOME/项目字节、模式、mtime 不变并禁止写锁；批准后漂移拒绝允许原锁的目录 mtime 变化，仅要求字节与类型模式保全。未把前次 598/75 当新改动全量结果。已交同一独立 reviewer 核查该窄差异。

preview 独立复核限定通过：3 文件与原 8 文件 hash 均未漂移；附加临时 HOME 探针验证已有锁、缺失台账、symlink 冲突、未登记项目 remove noop 等分支零写。该结论不覆盖 shared 修复。共享层仍是退回状态，GLM 修复中。

共享层 v2 已收到并按 31 项新 hash 与目标旧 hash 精确整合；旧清单/失败证据不覆盖。新 [清单](paseo-shared-files-v2.sha256)、[日志](paseo-shared-test-v2.log)：69/69，新增 12 项审查对应测试，fail 0，约 1.44s。6 项修复待独立 reviewer 重放，不以作者测试代替复审。Paseo UI、SDK typecheck、真实 CLI 桥接、恢复/CK 尾步继续由 GLM 完成。

共享层 v2 独立复验仍不通过（31 hash 前后相同，未重复整套）：容量/PAX/硬链接计量、执行位/X_OK、Git CLT/版本/候选回退及非法重定向已通过最小探针；仍有 4 项阻断：可预测暂存目录或 O_EXCL 失败后的 foreign part 被清理、传输期间出现的目标被最终 rename 覆盖、直接 child close 提前取消进程组 KILL 升级导致孙进程继续写入、drain Promise 未等待而失去背压。已退回 GLM 按独占暂存所有权、原子不覆盖发布、完整进程组终止及串行写入最小修复；69 项作者测试不视为验收。Paseo 编排继续开发，供应与真实宿主仍 pending。

共享层 v3 冻结清单已逐项核验源 hash 与主区 v2 hash 后整合 31 文件，变化限 tar/process/download 真源、其生成副本及对应测试。作者完整日志75/75、fail0、72.633s，报告 npm 实际退出码0；见 paseo-shared-files-v3.sha256 与 paseo-shared-test-v3.log。独占暂存、原子无替换发布、进程组 KILL 升级和实际背压已补竞争用例，仍待独立重放，不提前标验收通过。v3调试曾有 async/await 遗漏和占位收回所有权问题，已由作者修正；旧失败记录保留。

v3 独立复验：原四项竞争/背压路径已关闭，真实慢盘2MiB快速HTTP响应最大排队130944 bytes、无listener警告；忽略TERM且stdio ignore孙进程timeout/abort后无晚写；foreign stage/part和下载目标保全。仍退回2项：process取消后主超时timer残留可二次向旧PID发信号并改写取消原因；tar占位bool未绑定dev/ino，foreign空目录替换后可被覆盖/清理。已交GLM最小v4与定向fixture，31hash审前审后一致，未复跑75整套。

v4 已按源冻结31hash与目标v3hash核验后整合。作者79/79、npm exit0，日志paseo-shared-test-v4.log；清单paseo-shared-files-v4.sha256。幂等终止/首次原因/全timer清理与tar占位身份复核已补定向测试，download part清理同标准。最终检查至rename的非协作进程竞态边界明确保留，不声称绝对免竞态。已交独立review先防退四已闭合路径，再核验两项及相关不变量，尚未验收。

v4 独立复验关闭 process 全timer清理/首次原因/取消跨旧deadline与无额外signal、tar占位inode替换保全，旧四路径也通过。唯一剩余P1：download在link后才查part身份，传输期间替换part导致未验证foreign字节进入final，catch又删foreign part。已退最小v5，仅download及生成副本/针对hash匹配与失败两fixture；要求发布前和所有清理前复核regular dev/ino，漂移不创建final且保全foreign。31hash审前审后一致，未重复79整套。

v5按31hash整合：download发布前/全部清理身份复核及两fixture；另python.ts一行不存在的StatsLike类型改为fs.Stats，生成副本同步，process/tar未动。定向download+python 22/22 exit0，见paseo-shared-test-v5.log；独立复验待定。作者另报告宿主SDK0.13.2 typecheck exit0、假runner15/15，尚未冻结宿主文件或整合，真实CLI临时HOME桥接进行中，不能据此标宿主通过。

v5 独立复验限定shared通过，无剩余具体阻断。31hash审前后匹配，清单SHA256 4ec1ec36caa40dadcae354d37c4bac6e3a2d0efbb378000a129f7ed4ca7a162d；10生成副本一致。hash匹配/不匹配时传输期part替换均保全foreign且final不存在，final竞争不覆盖，自有part失败可清理；真实慢盘2MiB逐字节一致/maxQueuedBytes130944。process/tar沿用v4已验hash不重跑，Python确认纯类型差异。最终身份检查至系统调用的同权限非协作窗口沿用已声明边界。此结论不包含供应资产、客户端编排、实际宿主加载安装；继续Paseo SDK/临时HOME真实CLI及四WIP收口。

## 额度故障后的串行接管

2026-10-31 22:35，突突兔54ba84c6收到明确ZCode1308错误：5小时使用上限，重置2026-11-01 02:02:54。按已授权Profile紧邻前者规则，重新读取配置后派呱唧b67b0bec-4147-4e0a-b4dc-0cea3de3614b接管（codex/gpt-6.1-sol、full-access、medium，title为呱唧 | Paseo 宿主联调额度接管）。这是原GLM停止后的串行继承，沿用tututu-paseo-adapter工作区/分支保护未提交成果，不新开重复实现。shared v5冻结不动；继续宿主四WIP、真实文件漂移/运行中取消恢复、CK可选获取、SDK及冻结交接。此前15项只是假runner；两preview替换与reject不冒充内核文件漂移和运行中cancel。manifest已按实际SDK证据调整>=0.13.2，无addHook。未扩大真实HOME/daemon/版本/Orca/提交发布授权。

宿主接管基线：/tmp/ms-host-baseline.log初见17项10pass/7fail，最终exit尚待执行者收取。6项假runner fixture仍使用旧活动内核/持久core布局；真实桥接两次相同preview内容digest相同，旧确认可消费新pending，需宿主封装nonce及host/kernel绑定（不修改Python精确计划）。未发现原GLM遗留测试进程，无清理。GLM宿主源码及hash已备份/tmp/ms-host-glm-baseline，后续可逐文件区分接管改动。此前15项通过是历史报告，不作当前基线通过。

宿主接管实证节点（最终冻结待交）：作者报告真实after_output固定暂停→cancel RPC→cli_canceled→原journal保留→删除插件且无active installer→新worker核原source/tools hash并从匹配durable来源恢复completed，见/tmp/ms-host-v3.log；确认封装使用独立confirmationToken绑定nonce/host/HOME/argv/kernel，planDigest保持原精确计划摘要。定向17/17 exit0见/tmp/ms-host-focused-v6.log，涵盖本地Git固定CK pin获取/clean复用/foreign保全、跨worker独占证据、取消与unknown、旧token拒绝；typecheck作者已收取exit0。真实registry字节漂移与最终npm套件仍在收敛，尚未冻结host或独立验收。shared31不变。

## 宿主冻结整合

19个host文件按paseo-host-files.sha256及paseo-host-files.json的源/目标before逐一核验后整合，均为主区新增；core11/shared31再核不变。冻结清单SHA256 5ceaefd1cdc4f2f3d4e5dbf5d1b4bce20e1f4efbc42b5e861554de62115888fc。最终npm22/22、无skip、46.986s、实际exit0；SDK0.13.2 typecheck exit0；两份原始日志SHA校验并保存paseo-host-test.log/typecheck.log，证据见paseo-host-evidence.json，实际GLM/GPT差异见paseo-host-provenance.json。GPT接管改GLM7文件、新增2文件，无shared变更。

四WIP已取得作者合成证据：独立一次性confirmationToken不修改planDigest；独占0700/0600证据；实际after_output中断后cancel及unknown、删除插件无active后按journal原source/tools hash恢复；真实AGENTS私文/registry字节漂移拒绝；CK固定URL/pin获取批准与原CLI安装批准分离，本地Git传输fixture实际执行。已交原独立reviewer33be限定host审查，暂不标通过。真实Paseo加载/Modal/RPC断连/新会话、CK官方网络获取、固定Python/Git供应仍pending或阻断；未知CK lock failclosed，不自动抢锁。

宿主19独立审查暂不通过，3项具体阻断已退接管者：正常接入任意历史export即ready使新版插件误用旧installer（需绑定当前release目标，与恢复扫描分离）；UI无memory三态无法显式解除disabled（补保留/启用/禁用并展示政策预览）；staging在symlink检查前recursive mkdir导致foreign目录拒绝前已有写入（需逐级验证再创建及结构化拒绝）。19hash前后匹配，core11/shared31与10生成不变；未重复22整套。其余token/精确批准/取消与固定journal恢复/CK独立批准/API未见本轮具体阻断，但不替代真实宿主验收。

宿主三项修复已按20host新清单与主区before hash整合（6修改、1新增owned-paths），记录paseo-host-files-r2.sha256/.json，清单SHA467de242608ac2ef3b50f170e4749d90601eb0bd76a227b927c951b41c1c50fe；core11/shared31现场核验不变。最终26/26无skip85.557s exit0、typecheck exit0，原始日志及SHA与paseo-host-evidence-r2.json一致。真实多库存测试证明B新发行先导出再由原conversion拒绝、C同版异树拒绝、A选自身且receipt漂移不回退别库；不声称B升级成功。真实记忆三态保持原disabled语义。7个祖先symlink用例拒绝且foreign字节/模式/mtime/目录零写。已交同一独立审核复验，未标宿主通过。新增fixture曾误断言rules_only，已纠正为原disabled并保留旧失败日志，未放宽内核。

宿主host-r2独立复验限定源码/合成通过，R1/R2/R3关闭；20hash前后匹配、core11/shared31不变、10common一致。reviewer实际重放新B/旧A选路绑定、记忆三态CLI参数与原转换保留、staging/CK祖先链接foreign零写，未重跑26整套、未声称UI点击或B升级成功。来源/供应与原生验收边界仍保留。收口检查发现发行S→生成→R操作与可接CI一致性命令尚缺成文入口，已让原发行作者仅补tools/plugin-release说明及必要只读检查入口，不改冻结核心/插件，不执行正式生成或提交发布。

## 本轮源码交付收口

发行check.py与README按2新增hash整合，见paseo-ci-files.json；复用既有common测试与release verifier，无远程CI供应商配置。五个临时Git场景符合预期（S正常/漂移、缺正式产物冒充R、完整R/漂移），含.git全fixture字节/模式/mtime不变，证据paseo-ci-evidence.json；协调者静态核对薄调用、阶段选择和README命令，无新产品写路径。最终64个唯一实现/测试/说明文件hash现场一致，见paseo-final-files.sha256；git diff --check通过、无plugins/orca。原CK dirty保留，未写CK。

当前可交付的是未提交的源码与合成验证候选，不是可发布/即装即用验收。固定Python/Git资产URL/hash/完整许可未核实，自动私有供应尚未启用；真实Paseo安装/Modal/provider/workspace/断连/新会话与CK官方网络仍pending；正式S/R提交与载荷未生成发布。细分交付与后续门槛见delivery.md。
