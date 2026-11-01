# Paseo / Orca 插件适配方案

状态：两项产品取舍已获用户确认，2026-10-31；方案与任务拆分已完成，尚未批准实施验证、实现、安装、迁移、改版本或发布。任务书见 [tasks.md](tasks.md)。

## 1. 目标与已定边界

用户只安装 Paseo 或 Orca 插件，在宿主内完成必要确认后即可使用 memSharing。首次机器接入由插件自动编排，不要求预装 memSharing、不让用户另开终端、不要求用户手工安装 Python。上一轮“先普通安装再用插件”的建议已被否决，本方案不采用。

同一原仓库继续供 Codex 等 Agent 按 Git 地址安装；`scripts/agm_core` 是唯一 Python 业务真源，`scripts/agm.py` 是项目 CLI，`scripts/install.py` 是机器安装入口。插件分别位于 `plugins/paseo`、`plugins/orca`，不复制仓库、不维护第二套安装或记忆内核。首版无独立管理页面，只保留命令、报告和必要确认。

首版支持经过实测的本地 macOS 宿主环境。远程主机、Windows/Linux、批量启用、插件内编辑公共记忆、跨机同步、常驻新服务、自动修复未知状态均不在首版。arm64 / x86_64 和最低 macOS 版本在运行时验证后冻结，不凭文档猜测覆盖范围。

精确批准、锁内复验、私有文件保全、disabled、linked worktree、恢复与 CK 独立边界继续生效。规划文档不修改现行规则，也不自动升级当前产品版本。

## 2. Phase 0：已核查合同与缺口

本方案由一位巴克队长编写；用户要求不再派审核或实现 Agent，故不执行 make-plan 技能中的默认子 Agent 调研流程。使用本地源码及主 Agent / 章教授取得的公开文档缓存，未自行联网。

| 层次 | 已核查内容 | 来源与限制 |
| --- | --- | --- |
| 用户已定 | 单仓、双插件目录、唯一内核、插件独立完成接入、无独立管理页 | 当前委派；旧的预装依赖建议失效 |
| Paseo 官方缓存 | client/server 至少其一；Node 后台；Git 子目录；`server.addHook` 从 0.14 提供；命令入口可由薄 client 提供 | `/tmp/paseo-plugin-docs/{reference,publishing,hooks}.md`；未实装 |
| Orca 官方缓存 | format 2、trusted-worker、`activate(orca)`、可选 `deactivate()`、`orca.commands.register`、`orca.events.on` | `/tmp/orca-plugin-docs/{authoring,manifest}.md`；未实装 |
| Orca 发布 | catalog `source.path` 支持子目录，内容 hash 和安装范围限该目录 | `catalog.md`；直接 Git 子目录语法及 Community 嵌套自动发现仍未证实 |
| Orca API 缺口 | `workspace.readContext` 只返回 branch/displayName/terminals，未含绝对项目路径；`notifications.show` 只返回 delivered，无确认按钮回调 | `/tmp/orca-plugin-docs/host-api.md`；不能据此实现精确批准和路径绑定 |
| 现有安装器 | 已有 `--source-manifest`，底层接受校验过的 export；普通 checkout 路线验证完整 pin 与 clean | `scripts/install.py` 的 parser/run/checkout_source、`user_install._source`、`tests/unit/test_m408_installer.py` |
| 现有状态 | 固定 R/C/V、库存、装机锁与产品锁、精确计划和恢复 | `layout.py`、`versions.py`、`transaction.py`、`user_install.py`、`upgrade.py` |
| 运行可行性 | Node 调 Python、私有解释器、宿主内完整报告和确认、真实安装包资产保留 | 设计推断；必须先做最小验证 |

修正上轮审核：CLI 并非缺少 export 入口；缺的是插件发行物的可信绑定、安装编排及多入口身份一致性。现有 `--source-manifest` 不能单凭“JSON 格式有效”证明文件确实来自官方发行。

允许使用的宿主接口以以上缓存签名为起点。Paseo 新适配不复制技能中的旧 `server.before/on` 示例。Orca `contributes.hooks` 必须为空；不得发明 `dialog.confirm`、通知 actions、隐藏项目路径或事件字段。缺失能力由主 Agent 交章教授核查最新文档与示例，再做真机验证。

官方来源：[Paseo reference](https://paseo.sh/docs/plugins/reference)、[publishing](https://paseo.sh/docs/plugins/publishing)、[hooks](https://paseo.sh/docs/plugins/hooks)；[Orca authoring](https://github.com/stablyai/orca/blob/main/docs/reference/plugin-authoring.md)、[manifest](https://github.com/stablyai/orca/blob/main/docs/reference/plugin-manifest.md)、[catalog](https://github.com/stablyai/orca/blob/main/docs/reference/plugin-catalog.md)、[host API](https://github.com/stablyai/orca/blob/main/docs/reference/plugin-host-api.md)。缓存有时效性；实现任务必须先重新核对适用宿主版本。

## 3. 单仓目录与维护成本

以下为拟新增结构，不代表已实现：

```text
scripts/agm.py                       原项目 CLI
scripts/install.py                   原机器安装 CLI
scripts/agm_core/                    唯一 Python 业务实现；增加必要发行校验
tools/plugin-release/                确定性载荷生成器、发行核验；不进入普通产品载荷
plugins/shared/                      极薄 Node 进程/依赖准备公共代码真源
plugins/paseo/
  paseo-plugin.json / OVERVIEW.md
  index.client.tsx / index.server.ts
  client/ server/ shared/            宿主适配；公共 Node 代码生成到 server 内
  payload/core/                      自动生成的完整普通产品文件集合
  payload/release.json               自动生成的发行描述
plugins/orca/
  orca-plugin.json / README.md
  src/ / dist/                       Node worker；构建输出必须在目录内
  payload/core/ / payload/release.json
release/core-release.json            根入口与插件共同使用的生成发行描述
docs/plugin-adapters/design.md
docs/plugin-adapters/tasks.md
```

原有受管文件清单是七份文档加 `scripts/`，以 `install._managed_source` 为准；不是只复制 Python 文件。排除运行态、CK 工作日志、备份和凭据。生成物标注禁止手改，两个 payload 逐文件一致；Python 与共享 Node 源各只维护一份。普通 Agent 安装不引入 Node 依赖，插件不重新实现登记、批准、升级、恢复、记忆写入。

宿主不直接 import 仓库外层文件。Paseo 的 Node 模块放在其 server 运行目录，客户端不触及 Node。Orca 的 `main` 指向已生成、已提交的目录内文件，不假定 Orca 安装时运行 npm 构建。

## 4. 固定 Git 发行与身份合同

推荐同仓生成发行提交，不建立第二仓库、长期分叉或人工双写。

1. 实现与测试先形成干净源码提交 **S**。产品版本只使用用户批准的版本；没有版本决定时只做验证，不发布同版本新内容。
2. 发布生成器从 S 的跟踪文件读取受管集合，产生确定性 `payload/core`、Node 构建输出和发行描述。描述记录官方仓库、S、产品版本、文件路径/字节 hash/模式、规范树 hash、支持平台、依赖固定版本/hash、适配协议与兼容范围。绝对路径在安装时绑定，不固化开发机路径。
3. 将生成物及根 `release/core-release.json` 纳入同仓发行提交 **R**。R 与 S 在受管产品文件集合上必须完全相同；R 只加入或更新发行/适配生成物。不得在生成后顺便修改 `scripts/` 或受管文档，否则回到新 S 重新生成。
4. CI 在干净 checkout 验证 S 到 R 的受管字节一致、两个 payload 一致、重生成零差异、无外部路径/软链接逃逸、清单闭合。生成清单不嵌入自身最终 R，避免提交 hash 自引用；R 由宿主固定来源和 catalog/release 记录绑定。
5. Paseo 以已核查的子目录入口安装固定 R；Orca 自定义 catalog 固定 R、`source.path=plugins/orca` 与该目录 contentHash。目录内载荷随 Git 实际分发，不能只生成在 CI 临时目录或只上传附件。正式发行时再验证 selector/ref 的准确语法，不在这里臆造命令。

**身份必须分两层。** 内核身份是 `(官方来源, S, 产品版本, 受管树 hash)`；发行安装来源是 `(同仓 R, 插件目录, 内容 hash)`。两者都有记录，但 V 的产品来源采用前者，不能把 R 伪装成源码 S。宿主固定来源是发行信任根，CI 提供 S/R 对应证据；清单内 hash 只证明完整性，不自证作者身份。开发目录安装标为开发来源，不冒充官方包。

**与原 Git 安装共存需要窄范围改造，不能假设现在已支持。** 普通 checkout 路线仍先要求用户指定/观测的 HEAD=R 且全树 clean。检测到受跟踪的发行描述后，校验当前产品文件与描述逐字一致，再由统一发行解析器准备不带 `.git` 的受控 export，身份绑定 S，交给现有 `--source-manifest` 路线。获取 pin R 与内核 source pin S 分字段记录，不能静默改变 `--commit` 的 checkout 校验含义。无发行描述的现有源码 checkout 继续走原合同。

插件在自身目录内验证描述与完整载荷，准备相同 export，再调用相同安装器；不伪造 `.git`，不放宽 `checkout_source` 的 clean/pin 检查。export 存在产品操作暂存或持久恢复来源区，不能仅依赖会被插件升级/卸载删除的目录。根入口和插件入口对同一发行必须得到完全相同的内核 source identity 和库存 marker，否则不得进入大实现。这是验证任务 PA-02 的硬门槛。

对于发行前的普通安装：兼容的活动内核可直接复用，不强制更换来源；真正升级必须具有现行精确 conversion 合同。未知旧版、同版本不同内容、未来版本均停止升级；不新增同版重装例外，不以插件版本大小推导产品升级权。

## 5. 用户只安装插件的接入流程

```text
安装/启用宿主插件 → 核查宿主与依赖、载荷和机器现场
  → 已有兼容活动内核：核验并复用
  → 缺少运行依赖：宿主内说明来源/体积/目录，明确同意后自动准备
  → 首次/受支持升级：产生机器精确预览 → 宿主确认 → 原安装器执行
  → 成功报告；可选 CK 独立确认；项目操作在同一宿主内完成
```

安装接入由首次启用自动发起；若宿主此刻没有交互客户端，则保持“等待确认”，在宿主下次可交互时继续，不在后台默认同意。必要的“继续接入”命令只是恢复同一流程，不是让用户另做普通安装。任何步骤失败都给宿主内重试/恢复入口，不交付终端命令作为唯一完成路径。

依赖下载发生前需要明确同意，符合 Paseo publishing 中 activation 也适用的要求。因为 Python 准备完成前无法运行现有内核生成精确机器计划，不承诺所有场景一次确认：依赖准备授权与真实机器计划批准可以是同一宿主向导中的两个阶段。已有依赖时不重复要求下载许可。不能先由 Node 猜测业务写入集、得到同意后再替用户批准另一份计划。

首次安装预览列明实际接入的 provider 客户端及用户文件，保留未识别/未安装项，不把 Paseo/Orca 新增成 Python agents 表里的执行器。不得默认接入宿主提供但用户未使用的所有 provider。无受支持 provider 时报告范围限制，不虚报完成。插件安装许可不授权修改所有用户文件。

已有同版且兼容的机器核验后复用；旧版且支持升级时插件在原流程内提供精确升级计划；已有更高兼容版直接使用，不降级。超出兼容范围、私文冲突、遗留迁移、损坏台账进入内核现有诊断/恢复分支。用户拒绝升级时保留原活动内核和状态。

## 6. 依赖策略：Python 与 Git

| 路线 | 收益与成本 | 裁定建议 |
| --- | --- | --- |
| 仅要求系统 Python | 最小包，但用户未装就不能用，且 macOS 不保证可用 | 不作为默认；不满足用户硬要求 |
| 每个 Git 插件内附双架构 Python 二进制 | 初次可离线；Git 体积大、两目录重复、平台签名和更新成本高 | 备选，仅在明确需要离线首装时采用 |
| 验证已有解释器，缺失时自动准备固定私有运行时 | 插件 Git 包较小；首次缺依赖需联网与确认；运行时安全更新仍需维护 | **用户已接受**；不安装 Homebrew/Xcode，不修改系统 Python/PATH |

推荐路线由 Node 完成无 Python 的依赖引导：优先使用已有产品私有解释器，再检查可执行的兼容系统解释器；不执行会触发开发工具安装弹窗的占位程序。检查版本、架构、必要标准库导入与运行行为；最低版本以代码及验证矩阵为准，不只看 `python3 --version`。

缺失时下载经过授权的固定版本可重定位 CPython 发行包到产品自有目录，例如 `~/.local/share/mem-sharing-runtimes/<runtime-id>/<arch>/`。运行时供应者、macOS 最低版本、许可证、签名/公证、镜像地址、实际体积及两架构可用性由 PA-03 取得证据后冻结；目前没有已选定并验证的供应者，不能以推荐架构冒充可分发事实。优先复用成熟预构建发行，不自建 CPython 编译维护链。

插件内跟踪的依赖清单固定 URL、版本、SHA-256、解压上限与入口；下载到未生效暂存区，校验后安全解包并原子就绪。拒绝绝对路径、`..`、逃逸软/硬链接及额外文件；合法运行时内部链接按清单验证。失败只清理本次拥有的未使用暂存，允许宿主重试，不改全局环境，不执行任意远端安装脚本。所有子进程使用 argv、明确 HOME/cwd 和无字节码模式。

**Git 也是现有依赖。** `install.run`、`user_install.plan_install` 和项目身份解析都需要 Git。PA-03 同时验证宿主可供调用的真实 Git；缺失时采取同样的受控私有依赖准备，或将“宿主实际提供可调用 Git”列为实测支持环境硬条件。不得假设 `/usr/bin/git` 就能工作，更不能要求用户手工装 Xcode。若两者均不可交付，该环境不满足插件即用验收，必须在实施门槛处修订支持范围，而非安装后才甩给用户。

首版不保证无网络且无依赖机器的首装；已完成依赖准备的机器在无网络时应能检查与执行本地操作。下载器与私有依赖就绪锁只负责工具资产，不拥有第二份产品台账；不增加常驻进程。

## 7. 单一活动内核、版本与并发

R=`~/.mem-sharing`、C=`~/.local/share/mem-sharing`、V=`~/.mem-sharing/var/registry.json` 保持不变，沿用现有版本库存。插件自带 payload 是安装/恢复材料，不是第二个活动内核。正常业务命令由核验后的 C 执行；首次接入或升级才调用发行安装器。

两插件分别声明宿主版本范围、适配协议、内核兼容范围及目标发行；兼容性必须检查实际台账结构、来源与入口能力，不能仅比较 SemVer。旧插件面对较新内核可以在明确兼容时继续使用，否则只报告，不能降级。

同一 HOME 的普通 CLI、两个插件都受现有 `.mem-sharing-install.lock`、`.agm.lock` 和事务子锁约束。先规划、用户确认、再由内核拿锁重新核查；不在等确认期间持锁。不新增绕开 Python 的业务写锁，不让两插件各自登记机器状态。核实锁获取顺序，测试装机/升级与项目命令交叉执行。首次两个插件同时接入只能一个提交，另一个重新检查并复用，不重复初始化。

批准还须绑定执行内核身份。活动版本在预览后切换、载荷变化或 provider/HOME/项目身份变化，均拒绝旧批准并重新展示计划。不能因成功启动了旧 Python 进程就假定它仍有权写当前 V。命令完成后按内核 JSON 状态和退出码报告，不仅看进程退出 0。

## 8. 无管理页面的命令、报告与批准

首版建议命令：检查当前项目、启用当前项目、停用当前项目，以及仅异常时出现的继续接入/恢复。恢复和升级沿用各自精确计划，不提供一键清空记忆。首次接入报告自动出现，不要求用户记住安装命令。

预览须展示目标宿主与 HOME、规范项目路径、Git 身份、实际 provider、政策前后值、文件变更与保留项、当前/目标内核身份、下载来源及必要恢复影响。完整详情可展开，摘要不得省去有风险的变更。确认记录绑定原始规范计划摘要、用户动作、时间与宿主会话；不可由自然语言模型自由生成或由命令参数直接冒充用户动作。

Paseo：薄 client 命令入口调用 server RPC，承载一次性确认交互；不注册独立管理页。具体确认组件及结果展示按当前 SDK 文档/示例核验。后台 hooks 不自动代答权限请求。

Orca：优先使用经证实的宿主原生交互。当前缓存不足以证明 worker 可以完成完整报告、确认回调和可靠项目路径获取。PA-01 必须拿到明确方法签名和真实操作证据；通知送达、日志输出、命令被调用、terminal.sendText 均不能代替用户已阅读并确认某份计划。不向终端注入自动批准命令。

若原生通道不满足，用户已接受使用只显示本次计划、确认后关闭的临时交互面板；它不管理设置、不列项目、不成为常驻页面。该确认解决产品形式取舍，不代表面板 API、项目路径和确认链路已经验证，也不自动授权实施。无法实现可靠确认时 Orca 发布仍阻断，不能降级成“请打开终端”或宣称只读插件已满足即用目标。

## 9. 生命周期与项目政策

首版宿主事件只触发去重后的检查/提示，不自动写入项目或安装 CK。Paseo `workspace.create.after` 为非等待通知；Orca `workspace.created/removed`、`agent.status.changed` 不是通用前置 hooks。两者都不保证首个 Agent 启动前规则已就绪。

现行默认接入政策仍由实际执行器在主 checkout 使用时遵守；插件不另建一套自动启用政策。插件启用命令采用原内核批准；没有项目时不建库、不检查项目状态、不询问建库。非 Git 目录和 linked worktree 不触发默认接入；linked worktree 仅可做明确的只读诊断，不自动跳转写主 checkout。disabled 必须保留，解除需用户显式选择及精确批准。

插件/工作区关闭、archive、removed 事件都不等于项目删除或撤销授权，不执行 remove-memory，不删公共入口。事件订阅应可清理，重复通知不重复弹窗或写入。

## 10. 所有权、取消与恢复

插件拥有自己的 manifest、适配代码和宿主缓存；memSharing 安装器拥有产品库存、活动代码和已登记受管对象；用户私文保持原所有权。私有 Python/Git 的所有权归产品依赖准备，不依附某个可卸载插件目录。

卸载某个或全部插件不删除公共记忆、V、活动内核、provider 入口、CK 或仍供普通 CLI 使用的运行时。产品清理属于另一个明确用户操作，本版不做自动垃圾回收，不用复杂消费者引用计数来决定删除用户状态。

确认前取消零业务写入；依赖准备中取消只处理本操作暂存。安装/升级一旦开始写入，不承诺 UI 取消可立即回滚：请求安全停止，未知退出/宿主强杀保留 journal 与锁，重启后展示当前现场和现有继续/回滚预览，再明确批准。恢复材料必须位于不随插件删除的位置，能由另一个插件或普通 CLI 调用同一恢复内核。不得通过重试重做已完成副作用，不自动删除疑似陈旧锁。

## 11. Context Keeper 的特殊处理

需要做安装入口与加载验证适配，不改 CK 内核，也不把它嵌进插件业务生命周期。CK 仍是独立可选 Skill；主产品成功后在同一宿主流程内单独展示 CK 选项，拒绝/跳过/失败都不回滚 memSharing，不自动建项目记录库。

现有 `ck_install.py` 固定 pin 并调用上游自己的安装器，要求独立持久、干净 checkout；`LABELS/ROOTS/RULES` 目前只覆盖 Codex、Claude Code、WorkBuddy。Paseo/Orca 是宿主，不是新增执行器标签；识别实际 provider、运行用户/HOME、原生 Skill 路径后才确定支持。DSH/ZCode 不能因 memSharing 已接入就宣称 CK 支持。

插件不得要求用户手工准备 CK 源。可复用经核验的既有持久 checkout；没有时，独立告知固定上游来源与 pin，用户同意后自动获取到独立持久目录（拟为 `~/.local/share/context-keeper-sources/<pin>/`，最终按上游合同验证）。不放在插件包、产品活动代码、版本库存或操作临时目录。保留 `ck_install._source` 全部验证，自动获取只是前置编排，不在 `ck_install` 内悄悄加入下载副作用。

源获取与上游安装批准分层：下载前同意来源；取得源后运行官方预览，展示实际 Skill/规则目标，独立批准其精确计划后再执行 `--approved`。若缺源导致无法提前形成完整计划，不能承诺一次点击包办全部批准。拒绝前不下载；下载后拒绝安装时保留或清理仅本次未引用源须有明确所有权，不删除既有 checkout。

既有 Skill 指向同一受信 pin 时复用并核验；其他来源或冲突报告，不覆盖，不改用户独有规则。升级 CK 必须单独 pin/兼容与批准，不能随插件更新。插件卸载不动 CK 源、Skill 链接和项目经历；不接管上游所有权。

自动记录由实际 Agent 读取 CK Skill 后按用户/项目政策执行，不用插件 turn/agent hook 模拟保存，不双重记录。无项目聊天不启动保存/建库；disabled 禁止自动记录与初始化；linked worktree 不新增自动入口，已有 CK 使用按其合同，不强行跳到主 checkout；首次 `/context-keeper` 才按上游流程处理记录库与授权。主产品安装绝不等同于项目 CK 初始化。

验收分四层：源与安装静态校验、真实宿主启动的实际 provider 的 Skill 发现、新 Agent 会话实际读回 SKILL.md、授权项目中的首次命令/保存规则验证。插件 enabled 或文件链接存在不能代替后两层。不受上游支持的 provider 标记 skipped；支持但未真测的标记 pending。若需上游新增适配，单列待核实任务/阻断范围，不修改上游或伪造支持。

## 12. 发布门槛与已确认的产品取舍

先完成 PA-00～PA-03 最小验证，再批准大实现；合成夹具不能替代 macOS 真机宿主证据。Orca 确认与路径、运行时分发、S/R 身份一致性任一未闭合，相关平台不得宣称插件即用。

用户于 2026-10-31 回复“同意都接受”，确认以下两项产品取舍：

1. 缺依赖时首次联网，在宿主内确认后自动准备私有运行时，不修改系统环境；不要求无依赖机器离线首装。此为产品流程选择，实际下载仍须展示具体来源和精确准备计划。
2. Orca 原生确认接口不足时，允许一次性、确认后关闭的计划面板；保留无独立管理页面的边界。实际 API、路径与确认链路仍需先验证。

其他技术项由验证任务给证据后收敛，不把供应者、hash、锁顺序等实现决策逐项抛给用户。批准此方案也不自动授权实际改版本、生产迁移、提交推送或发布。
