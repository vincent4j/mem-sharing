# Paseo 插件维护手册

本页维护现行适配约束，当前支持边界见[支持范围](../README.md)。产品本体的合同、事务和使用方法分别见[设计](../../DESIGN.md)、[系统架构](../architecture.md)、[操作手册](../operations.md)。面向插件用户的说明保留在[OVERVIEW](../../plugins/paseo/OVERVIEW.md)。Orca 未实现，不属于当前交付范围。

## 单仓与发行来源

新版交付、商店审核和用户更新按[插件更新工作流](paseo-update.md)执行；发行生成与验证细节仍以发行工具说明为准。

Python 业务只维护 `scripts/agm_core`，项目与机器入口分别为 `scripts/agm.py`、`scripts/install.py`。Node 公共代码只维护 `plugins/shared/src`，通过 `sync-to-plugins.mjs` 生成到 `plugins/paseo/server/shared/common`；许可披露同步进入插件目录。宿主子目录不依赖安装后的父仓库文件。

源码提交 S 必须干净且固定完整 SHA。生成器从 S 的八份受管文档与 scripts 集合生成 `payload/core`、`payload/release.json`、根 `release/core-release.json` 和 `server/shared/release-identity.ts`。R 仅包含允许的生成变化，S/R 的受管字节和模式必须相同。内核身份记录 S，获取来源记录 R；摘要校验只证明完整性，不自证官方来源。开发 identity 保持空哨兵，不能手填摘要使开发目录冒充发行。

生成、重生成和 CI 的准确步骤统一在[发行工具说明](../../tools/plugin-release/README.md)。普通 Git 安装与插件使用相同源身份和版本库存。版本来自获批发行输入，不从插件版本推断；同版异内容、未知前身、缺精确 conversion 或未来版本继续由原内核拒绝，不提供降级/同版覆盖捷径。修改受管文档也改变产品树，后续发行须重新生成与核验，不能继续使用旧 S/R。

## 宿主适配

最低 SDK/manifest 为 Paseo 0.13.2，界面、命令和typed RPC贡献以当前插件声明为准；前端只展示内核状态/批准流程，不复制业务规则或自动批准。workspace 命令提供项目路径，执行器由用户选择；Paseo 是宿主，不是新增 Python Agent 类型。linked worktree、非 Git 项目及 disabled 政策沿用内核，插件不能默默改写主 checkout 或恢复自动记忆。

### macOS 与 Windows 边界

插件后端在所选 Host 的 daemon 上运行，文件路径、Python/Git 和平台准入取该 Host 的系统。Paseo 应用所在电脑的系统不改变后端能力；Mac 应用连接 Windows Host，也不能沿用 macOS 的产品准入。客户端共用 React Native 界面源码，两端应用显示、确认、取消与 Host 切换仍须分别实际验收。

| 项目 | macOS Host | Windows Host |
| --- | --- | --- |
| Python/Git 探测 | 标准目录与 PATH，保留 CommandLineTools stub 保护 | 按分号拆分 PATH，查找 python.exe/python3.exe 与 git.exe；盘符、空格和中文路径已有合成测试；Python/Git 已在固定 DELL 实际探测与运行，一般 Windows 仍待验 |
| 缺依赖时的私有供应 | 已有固定 arm64/x86_64 资产，按原批准流程准备 | 无固定资产，不自动借用 macOS 包 |
| 插件发行载荷与普通安装 | 复用当前发行来源、原内核计划与批准 | 普通安装继续拒绝；独立预览载荷使用八文件闭包和包内生成摘要 |
| Windows 双端预览 | 不适用 | 开发候选在固定 DELL/Paseo 0.15.3 的隔离 HOME 已通过真实加载及状态/安装/新增/退出 SDK RPC；部分应用 UI 已验，其余分支见下文；v0.2.0 提供限定预览 |

Windows 公共记忆共享预览流程不经过 POSIX 模式的普通发行载荷校验或私有依赖供应，仅调用预览 Python 桥接，不执行 Git、下载器及其他子进程；可选 Context Keeper 是下述独立流程，会调用 Git 获取源码及 Python 上游安装器。独立清单核字节、大小、完整成员闭包，拒绝链接/硬链接和额外文件；实际文件父链、NTFS/reparse 与写保护复用原生预览内核。普通产品的权限校验和 darwin 保护不变。普通 Node 进程树取消与依赖供应仍未完成 Windows 适配，不因本预览绕开这些能力而宣称已解决。

限定预览只调用[Windows 双端首次预览](../platforms/windows-preview.md)既有内核，不获得普通融合、升级或项目接入能力；可选 Context Keeper 使用下述独立适配器与上游安装器。完整能力须另按[Windows 完整适配目标](../platforms/windows-support.md)完成内核与真实客户端验收。发行载荷须在源码适配和相应验证完成后，沿下述固定来源流程重新生成；不直接编辑旧 payload 或沿用同版覆盖。

### Windows 预览接线与候选准备

客户端先查询 `memsharing.host.platform`，按所选 daemon 路由，同一套界面可由 Mac/Windows 应用连接。Windows 公共记忆共享预览仅开放 `windows-preview.status/plan/confirm/cancel`，可选 Context Keeper 另开放下述 `windows-ck.plan/confirm/cancel/status`；直接调用普通生产 RPC 也会在读取配置或创建暂存前拒绝。项目/普通恢复命令显示范围说明，不落入普通安装。状态读取公共正文供用户查看，不启动 Agent；模型新会话读取仍单独验收。

桥接使用 Host PATH 中实际探测成功的 Python 3.9+，参数为 `-I -S -B -X utf8 -c`，固定程序从标准输入消费私有计划。Windows 11 x64 与原生文件系统准入仍由桥接/内核检查。安装、新增和退出均先调用原内核计划接口，完整计划只留服务端，界面展示目标路径、前后摘要、备份/导出和本次新增正文。确认 token 绑定当前 HOME/Host、解释器、环境与来源，十分钟过期且仅用一次；执行时原内核重生成方案，任何来源或现场漂移拒绝。

取消只撤销待确认方案；执行中返回 busy，等待内核事务结果。超时、截断或无法解析的执行结果保持 unknown，本 worker 阻止后续写入，先保留锁、备份与事务材料，再由独立预览包核对和 recover。退出保留空目录、备份与导出；不自动清空目录以允许重装。卸载插件不等于退出预览，未闭合事务前保留可用的独立预览包作为恢复来源。

Windows 独立源身份在 `server/shared/windows-preview-identity.ts`，开发值为空，不借用 macOS 0.1.11 的 manifest。候选准备使用已信任渠道的独立 ZIP、独立 SHA256 与完整 preview revision：

```sh
python3 -B tools/windows-preview/paseo.py --archive "$ARCHIVE" --sha256 "$ARCHIVE_SHA256" --commit "$PREVIEW_REVISION" --output "$OUTPUT"
```

`OUTPUT` 必须是源码外的新目录；工具复用独立预览包校验，生成 `plugins/paseo/windows-preview/` 和对应摘要常量，不安装、不改 checkout、不提交、不发布。正式候选将这两处作为同包受管生成物审核，Mac payload 仍沿原 S/R 流程。未经生成的开发目录不能安装 Windows 产品。源码/合成联调通过不等于候选已生成、插件 running 或两端应用 UI 验收通过。

当前真机证据限定为固定 DELL、Windows 11 x64、本地 NTFS。Paseo 0.15.3 的独立 HOME 真实 daemon/SDK RPC 已验证插件加载、取消、一次性确认、安装、新增、漂移拒绝和退出导出；导出字节、原生私文及 BOM/CRLF 均核对。日常 Host 已实际安装插件和独立预览，重开 Paseo 后可通过其实际环境中的 Python 读取状态。Python 必须在 daemon 启动环境的 PATH 中可用；WindowsApps stub 不算可用解释器，安装 Python 后旧进程可能需要重新打开应用才能取得环境。

Windows 应用的共用向导已实际完成状态展示、新增预览、拒绝后正文 hash 不变、确认新增仅一次及结果显示，并由所选宿主读回核对。Mac 应用已实际核对共用状态页、设置初始表单及已安装场景的预览入口；检测到已接入后直接显示完成，保护文件 hash 不变。Mac 全新安装、变更确认与退出等其他界面分支仍分别待验。当前候选已在固定 DELL 的 ZCode 与 WorkBuddy 原生新会话中读回同一公共验收标记；ZCode 聊天新增后，WorkBuddy 新会话也已读到新条目，且问题未预填答案。反向聊天写入按用户选择跳过，保持未验。Windows 退出预览与拒绝已实际核对，拒绝后仍为已接入、公共正文 hash 不变；实际退出导出与重新接入的界面闭环、不支持功能入口拦截仍待验。状态页的 busy 提示与刷新后恢复表单已观察，unknown/失败分支仍仅有合成证据。窄窗口下设置表单、状态页滚动与当前公共正文展开已核对；其他宽度、弹窗和主题不据此宣称通过。CUA 远程点击通道不可用时，用户操作与实际画面/宿主读回共同构成已做项目的证据，不能把后端通过扩大为完整 UI 通过。

Mac 与 Windows 共用状态页、向导页、主按钮、变更预览、确认弹窗与结果组件，不维护独立的 Windows 管理页。命令中心入口保持一致：“查看共享状态”只读；“设置记忆共享”与“卸载记忆共享”沿填写/选择 → 生成精确预览 → 核对计划 → 确认执行或返回并拒绝 → 结果的同一顺序。融合选择仍按原语义“选择即执行”，不额外增加确认。

差异只由能力与实际状态提供：macOS 保留现有环境/来源检查、参与者选择和融合/归还等流程；Windows 限定 ZCode/WorkBuddy 成对接入，已接入后的设置表单只提供明确新增，退出先导出再恢复入口。不支持的项目/恢复能力在原命令对应页面提示，不落入普通安装。版本与配置限制只在首次接入或按需详情出现；状态页不放新增或卸载表单。

宿主用受支持的 `context.paseo.config.get().config.plugins` 定位自身包；只消费 plugins，不记录其他配置。固定包 ID `memsharing` 与编译期 manifest 摘要、完整载荷字节/模式、唯一 canonical 来源共同绑定。CLI runtime 别名不等于包身份。每次 RPC 复验；来源/环境漂移闭锁并取消七类 flow，要求重载后重新预览，不重建 Orchestrator 来继承旧批准。

### Windows 可选 Context Keeper

此流程仅为固定 DELL 上的 ZCode 与 WorkBuddy 安装用户级 Context Keeper，使用独立的 `windows-ck.plan/confirm/cancel/status` RPC；普通生产 RPC 的 Windows 拒绝不变。需要 Host 上实际可用的 Python 3.9+ 与 Git，不自动下载 Windows 运行时，也不自动创建项目记录库。

操作顺序：

1. 预览官方 `main` 的获取位置，确认后在独立暂存目录获取并核验源码。
2. 获取完成后生成安装预览，核对实际支持/跳过的客户端、规则文件、Skill 目录联接及共享回执的变更。
3. 单独确认安装；后台执行时由页面只读查询状态。关闭再打开页面可查询本插件进程内的结果，不重复执行。插件重载会清除旧批准。
4. 不安装时拒绝计划。源码准备完成不等于安装完成；暂存源码不会因获取或拒绝安装而替换正在使用的技能。

每个新安装意图重新获取官方 `main`。已有源码与最新 `main` 的 HEAD 相同才复用；版本不同则停止并保留当前技能，提示单独审核升级，不支持通过重新安装原地更新，不回退到旧版本。Context Keeper 源码不打包进 memSharing，实际安装调用核验后的上游安装器。

安装与公共记忆共享预览共用写锁。确认 token 单次有效、十分钟过期，并绑定 Host/HOME、解释器、环境和源码字节；锁内重新核对精确计划。Windows 磁盘和文件标识用十进制字符串跨 RPC 传递，避免大整数舍入。提交前逐一要求批准计划中的 Skill 入口为指向批准源码的有效联接，缺失也进入失败恢复。

原生规则的私文快照仅保留在服务端及用户目录的 `.mem-sharing-ck-operations/<run_id>/journal.json`，不传给界面。失败时只恢复仍匹配本次预期的规则和回执，移除本次新增且仍指向所选源码的联接；外来修改保留。未知结果或未闭合日志会阻止继续安装，须保留材料核对，不自动抢锁或重放。

写入两家规则时，同步更新共享回执中的安装摘要和退出恢复快照。以后退出公共记忆共享会保留 Context Keeper 原生入口与联接，并完整导出公共记忆；退出共享或卸载插件均不等于卸载 Context Keeper。

当前验收边界：

| 场景 | 固定 DELL 的已验范围 |
| --- | --- |
| 实际安装 | 两端规则、共享回执匹配批准摘要，三个 Skill 联接入口与官方源码一致；公共记忆、原有共享 Skill 和 Paseo 配置保持原字节 |
| ZCode 新会话 | 实际读取 Context Keeper 与公共记忆；无项目记录时停止，没有初始化记录库。已有记录的续接/查找未在本轮验证 |
| WorkBuddy 原生客户端 | 实际加载技能；无记录时只读停止；从历史测试项目只读恢复进度；合成项目完成保存→独立新会话续接，恢复完成事项、决定、待办和来源 |
| 只读保护 | 历史恢复前后 50 个记录文件不变；合成项目续接前后四个记录文件不变；九个用户级关键文件摘要保持一致 |
| 收尾修复部署 | 两个已审核服务端文件部署并读回摘要一致；两个插件运行正常、共享仍已接入、Context Keeper 空闲；九个关键文件及原有 Context Keeper 源码摘要不变 |
| 尚未验证 | 修复后的重新安装与真实失败恢复、实际退出/重装、Mac 完整新安装与退出，以及一般 Windows 支持 |

WorkBuddy 的 Paseo 运行入口与原生客户端分别验收：前者的原始记录返回需要登录，Paseo 时间线未展示该认证错误；原生客户端的成功不代表 Paseo 运行入口已通过。保存→续接是实际客户端上的合成项目测试，项目日记也包含测试事实，因此不是排除其他记忆通道的盲测，更不代表测试项目的业务功能已验证。

收尾修复已通过插件测试、Python 适配测试、类型检查及巴克队长独立审核，并完成部署与状态读回；未重新执行客户端保存→续接或真实故障注入。v0.2.0 中的 Windows 能力按固定 DELL 已有配置的限定预览提供，不能据此宣称一般 Windows 支持。

## 接入与批准

用户目标是仅安装插件、在宿主内确认即可接入，不先普通安装、不另开终端。当前实现为命令驱动，不能承诺安装即自动发起向导。

1. 检查现有 Python≥3.9、Git、发行载荷与机器状态；缺工具时单独展示固定官方资产及目标路径，用户确认后准备私有依赖。
2. 从当前包调用原 `--release-request` 解析器；必要时独立批准持久 export，然后用返回的 `--source-manifest` 形成机器计划。历史 export 仅可作为恢复候选，不能绕过当前包验证。
3. 展示原内核精确计划、完整 JSON 和政策转换，确认后执行。相同计划的 digest 可相同；一次性 confirmationToken 另绑定 nonce、host/HOME、argv、内核树及资产场景，旧预览/跨 worker token 不可复用。
4. 项目接入复用原内核预览和批准。历史 disabled 仅作规则接入 tombstone，不表示 Context Keeper 停用；不把已退役 `remove-memory/--memory/--no-memory` 当作可用新请求。原生入口按当前 Agent 实际使用补齐。

拒绝计划不执行其业务写入；宿主可保留私有 request/operation 证据，不承诺整个文件系统绝对零写。机器状态只由原 R/C/V、库存、锁和 journal 管理，宿主辅助状态不是第二套台账。

## Python/Git 供应

固定来源真源是 `plugins/shared/src/production-assets.ts`；RPC 和用户环境不能覆盖 URL/hash。资产的版本、平台、大小、SHA256、解包树摘要与入口以该真源为准；目标存在不等于动态平台已验。

依赖存放于 HOME 内 `mem-sharing-runtimes`，不改系统 Python、全局 PATH 或 Git 配置。下载、容量、解包链接和完整树检查通过后还要实际 probe 才写 verified；漂移、未知所有权或冲突保全拒绝。取消仅处理自身 inode 匹配的 lease/暂存；保留可审核的中断材料，重试要新计划。许可与对应源码见[运行时披露](../../plugins/shared/THIRD_PARTY_NOTICES.md)，许可sidecar不代表完整transitive SBOM。

## 所有权、取消与恢复

R=`~/.mem-sharing`、C=`~/.local/share/mem-sharing`、V=`~/.mem-sharing/var/registry.json` 是唯一活动产品。载荷获批后导出至 `~/.local/share/mem-sharing-sources/<version>/<tree>/`；恢复不能依赖会被移除的插件目录。

运行取消终止本操作进程组，但不能承诺即时回滚；结果未知时保留原 journal。恢复仅选择与原 journal source/tools hash 匹配的 CLI/toolkit，再走原继续/回滚批准。V 提交后的收尾与成功安装后的主动降级不是同一操作，不自动抢锁或回放旧计划。插件卸载不删除产品、公共记忆、用户入口、持久源、已用运行时或 Context Keeper。

## Context Keeper

Context Keeper 是独立可选 Skill，每次从官方仓库 `main` 获取当前代码，不内置源码。来源获取与安装分别批准；使用独立暂存 checkout 获取并验证，已有技能源码不在获取阶段更新，同 HEAD 才复用，版本不同保护性停止。需要升级时另行审核，不能以获取或重新安装替代升级批准。拒绝/失败不回滚 memSharing，不自动建项目记录库。Windows 的具体范围见[可选安装流程](#windows-可选-context-keeper)。

按当次上游安装器实际能力核实六家支持范围；多个执行器共用的 Skill 目录只列一次。宿主 enabled、Skill 链接存在、原生新会话实际读取和首次命令/保存是不同证据。无项目聊天、disabled、linked worktree 和首次 `/context-keeper` 规则继续生效，不用插件 hook 模拟自动保存。更新/卸载插件不升级或接管 Context Keeper。

## 维护验证

只针对改动运行必要检查：公共代码/许可变更检查生成一致性，宿主变更运行相关Node测试与SDK typecheck；内核变更按Python测试验证。发行前执行source/release门禁，修改受管文档后也必须重新生成载荷并核验身份。插件running、文件接入、模型新会话读取和发行完成分别报告。

## 当前内核适配

重复安装的已核验成功无变更响应直接显示“已安装，已接入”，不重新启动融合或 Context Keeper。融合预览与写操作分别为 `fusion.preview`、`fusion.select`；后者将服务端保存的完整展示计划和本次选择交给内核校验后执行，查看和拒绝不执行迁移。内核返回无内容时直接进入尾步。

用户记忆流程结束后显示内核 `context_keeper.pending_selection` 的原问句、实际名单和安装/跳过选项；无响应保持待选择，选择安装后才准备当前上游 main 来源，来源与安装分别批准。项目规则融合不带此尾步。Agent 名单通过 `agents.detect` 复用内核探测，空目录不算安装，CLI/App 证据分别保留。

外层 Agent 完整阅读来源与公共正文后，可向 `fusion.propose` 提交本次 `equivalentSources` / `publicReuse` 完整提案及展示 token；工具核对旧场景并交内核校验原 context、全文基线、精确字节范围和原文哈希，返回重新编号的展示方案。前端不猜测等价，不把提案摘要视为信任来源。提案在 0700 临时目录、0600 文件传递并清理，选择执行复用同一提案。此接口面向外层 Agent，内部 JSON 不作为普通用户必填流程。

上述源代码适配不代表已重生成发行包或完成真实宿主 UI 验收；发行须另行授权生成并验证。
