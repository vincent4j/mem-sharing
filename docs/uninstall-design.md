# memSharing 职责收敛与整机卸载

源码候选已实现本文的职责收敛与卸载机制，完整运行验收以本轮最终日志为准，尚未宣称已发行或真实卸载通过。本文记录 2026-11-01 已确认的职责、数据归还、旧政策迁移与卸载合同及验证边界。正式发行 payload 仍待干净提交与新版本授权后由既有发行工具生成；没有生成新正式 payload，不代表已安装插件已经获得这些功能。

## 任意已接入 Agent 的自然语言入口

用户说“卸载 memSharing”“卸载 mem-sharing”或“不想用这个共享记忆工具了，帮我卸载”，已加载公共索引的 Agent 直接进入只读预览，无需 `/mem-sharing` 或源码 cwd。原生用户入口仍只放公共指针与自身规则；L0 的短触发让它按需读取主题《使用约定》，由单一生成函数提供完整自然语言路由，指向已核验安装 C 的绝对 `SKILL.md`、本方案与 `python3 -B <C>/scripts/agm.py uninstall-machine`。完整操作说明见 [SKILL](../SKILL.md)，模板、迁移与归还分别见 [user_entries.py](../scripts/agm_core/user_entries.py)、[policy_migration.py](../scripts/agm_core/policy_migration.py)、[uninstall.py](../scripts/agm_core/uninstall.py)。不加自然语言分类器、额外 Skill 投影或项目文件，也不把流程复制六份。

“卸载这个项目”“停用项目记忆”只触发目标澄清，不代表删除 cwd；明确产品退出则不重复菜单。请求本身不批准未展示的精确删除计划。先核验台账、安装代码来源和机器实际安装形态，提议一个全新外置备份位置而不先创建目录；读取完整合同后只读预览，展示完整归还、保全、删除、宿主义务和恢复材料，获精确批准才执行。已卸载或代码缺失只报告状态或使用已核验外置恢复入口，不自动重装。

从 Codex/Claude 等发起不改变 Paseo 来源：沿既有 RPC，或以真实安装 ID、来源和 config record 走既有核心宿主参数合同；来源/目标不明先补证，不默认 standalone，不伪造 absent，不扫描全 HOME。Paseo 完成机器部分后仍显示 `machine_assets=completed / host_plugin=pending / overall=partial`，再按外置 bind→官方 remove→同一 daemon status/serverId 与 full-list 缺席核验→CK 尾步接续。独立 CLI 的 `standalone_declared` 只是调用范围声明，不证明其它宿主无残留。只有声明范围完整成功后才单独询问 CK、默认保留，并另行预览批准；失败不改写主产品完成事实。

只有安装代码已具备当前兼容实现时，才可只迁指南；否则先按现有精确安装/升级流程更新代码。迁移预览复用 C/台账来源校验，并精确核对当前 Skill、卸载合同、入口与路由/归还能力文件，将观察绑定批准及锁内复核；不兼容或缺失零写拒绝，不能生成新指针配旧执行器。新增路由前的公共 header/topic 已冻结为精确前身字节，`migrate-policy` 可预览、批准并替换已知生成正文，保留私有索引尾与用户文件字节，未知定制拒绝，重复执行零写。安装/公共布局迁移使用同一新模板，升级 handler 的精确目标 hash 同步；历史 before/predecessor 合同不改。真正归还时，前后两版已知生成指南和 L0 产品路由都退休；active 副本不再含“以后卸载请读已删除 C/SKILL”的指令，original 保留完整历史原文，用户自己的主题逐字节保全。

验证层次：`tests/unit/test_natural_uninstall_route.py` 在临时 HOME 安装真实内核与文档，核对六家入口→L0→topic→绝对 SKILL/合同/CLI，并在非源码 cwd 执行真实只读预览、核对零写；覆盖未接入入口不创建、冻结前身迁移/私文/幂等/未知定制拒绝及前后两版实际归还的 active/original。配合公共布局、升级 entry projection 和发行文档闭包定向回归。上述是静态与合成执行证据，六家真实模型对自然语言的理解、触发及新会话读取仍 pending，不能记作理解率验收。

## 背景与目标

memSharing 负责公共用户记忆共享、项目规则入口和执行器差异适配。Context Keeper（CK）独立负责项目经历的记录、首次建库、续接、历史检索与经验整理。此前的项目经历开关把两个产品的职责混在一起，甚至让 memSharing 的 denied 文字否决 CK 的自动规则；旧版也没有完整机器卸载，只能撤某个项目入口。

本次退役 `remove-memory`、`--memory` 和 `--no-memory`。新请求不能通过旧参数改变 CK。项目 `AGENTS.md` 仍是共享规则基座；Claude 的 `@AGENTS.md`、WorkBuddy 有效桥接及 CK 本身保留。历史 disabled 仅是规则接入 tombstone：默认流程跳过，不自动重建旧入口，不代表 CK 停用，也不证明入口已经移除。重新接入不能借退役参数实现，须另有明确接入计划。

整机卸载的目标是把**卸载时的完整公共记忆**交回每个实际接入过的 Agent，并删除本产品管理的机器资产；不是恢复安装前的旧记忆，也不是保留一个六家继续依赖的共享目录。

## 用日常语言理解这几个文件

`AGENTS.md` 是一个项目的共同办事规则，例如“修改后跑哪些检查”；它跟着仓库走，换 Agent 仍用同一份。用户入口是各家 Agent 自己的说明页，例如 `~/.claude/CLAUDE.md`，承载该家独有规则和“去哪里读公共资料”的指针。指针像地址，不是资料正文；把地址改对也不等于已实测每家新会话都按它阅读。

公共用户记忆跟着人，例如偏好中文回答、旅行时优先高铁；公共文件保存一份，各入口平时指向它。项目经历则是“上次做到哪里、为什么这样决定”，由 CK 的项目记录库管理，不应塞进常驻规则。卸载 memSharing 需要归还公共资料、改掉失效地址；不应顺手删除项目规则或 CK 经历。

| 责任方 | 负责 | 边界 |
| --- | --- | --- |
| memSharing | 公共用户记忆共享、各家用户入口与项目规则接入、精确迁移、归还与产品清理 | 不再开关 CK 经历，不控制 CK 自动行为 |
| Context Keeper | 项目经历记录、首次建库、续接、历史检索、经验整理及自己的安装卸载 | 自身规则和宿主范围由真实上游流程决定 |
| 用户与各家独有规则 | 私有习惯、各家专用说明、手写限制和项目规则正文 | 不并入公共、不自动删除；本次精确批准不扩大为其它授权 |

举例：假设六家都已实际接入，公共资料里新增“旅行优先高铁”；Claude 自己文件另有“此账号用英文写邮件”，且带私有备注和 CRLF。卸载前六家入口依赖 R，公共偏好只在 R。卸载后六家各自持有完整公共副本，均包含**当前**高铁偏好；Claude 公共引用仅指向自己的副本，英文邮件规则、备注和换行原字节保留。R/C 删除后各副本互不依赖，也不再共享后续编辑；项目 AGENTS 和 CK 历史照旧。这不是把旅行偏好回滚成安装当天的旧版本。

## 目录与卸载前后数据

| 对象 | 卸载前 | 完成后的处置 |
| --- | --- | --- |
| R | `~/.mem-sharing`，memories/references/backups/var | 精确盘点、外置保全、归还核验后删除 |
| C | `~/.local/share/mem-sharing`，产品代码 | 最后删除；执行与恢复不能依赖它 |
| V | `R/var/registry.json` | 与 R 一起删除，完整原字节在外置 manifest |
| 版本库存 | `~/.local/share/mem-sharing-versions` | 来源身份、清单和模式匹配才计划删除 |
| 来源与私有工具 | `mem-sharing-sources`、`mem-sharing-runtimes` | 仅固定归属、完整清单和哈希匹配者进入删除计划；未知或 lease 阻断 |
| 历史安装/升级证据 | `~/.mem-sharing-install-*/journal.json` | 只有终态且归属明确才可保留为恢复证据；预览与结果列路径、原因、非活动性证据 |
| 旧管理器与源码 | `~/.agents-group`、用户源码 checkout | 默认不删 |
| 项目与 CK | 项目规则、CK Skill、记录库 | 默认保留；失效产品依赖仅按归属证据清理 |
| 外置备份 | 用户指定的全新目录 | manifest、独立 recover.py、必要的独立解释器与恢复字节永久留给用户；没有自动到期删除 |

实际接入者由台账和已登记入口共同确定，不能只看当前 installed 探测；应用卸载了但入口仍依赖公共资料的 Agent 也要归还。仅有一个未登记私有文件不会自动取得修改权，陌生读者与来源不明依赖应阻断。

## 六家的候选归还位置与读取合同

每家在自身用户入口旁的 `memsharing-return/` 持有完整独立副本：`memories/`、`references/` 为 active 可读资料；`original/` 为公共资料和历史包的确切原字节证据。每家都完整，不按当前会话“用到多少”裁剪。

| Agent | 自身入口 | 独立副本位置 | 读取合同与待验项 |
| --- | --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.codex/memsharing-return/` | 自身入口引用归还索引；新会话实际加载 pending |
| Claude | `~/.claude/CLAUDE.md` | `~/.claude/memsharing-return/` | 已登记 import 可精确重定向；新会话加载 pending |
| WorkBuddy | `~/.workbuddy/MEMORY.md` | `~/.workbuddy/memsharing-return/` | 自身规则指向归还索引；有效项目桥接保留；新会话 pending |
| DeepSeek Harness | `~/.dsh/AGENTS.md` | `~/.dsh/memsharing-return/` | 默认根合同；不假定附属目录自动发现；新会话 pending |
| ZCode | `~/.zcode/AGENTS.md` | `~/.zcode/memsharing-return/` | 默认用户入口；新会话 pending |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.config/opencode/memsharing-return/` | 默认配置根合同；新会话 pending |

active 资料闭包必须独立可读：内部绝对公共链接重映射到同一副本；相对引用、空目录和目录链接保全；symlink 严格解析，循环、缺失、最终逃出资料资产均阻断。历史包不能因为标为历史就漏掉 active 阅读资料链。`original/` 可保留原始链接文本作为历史证据，不把原文证据误称为独立可读 active 闭包。未证明的产品命令依赖不得“改个路径”蒙混。

保全用户独有字节、模式、CRLF 与无末尾换行。Claude 的窄例外必须同时满足：已登记 `kind=import`、marker=null、ownership=reused、整文件指纹吻合、唯一精确公共 `@` 引用行；本轮精确批准只重定向目标行路径，其余字节不变。不把旧 kind=file 收编成 import，不改变所有权，不删整文件；歧义、漂移、未登记均阻断。入口不承载全部正文，独立目录的存在也不证明宿主自动加载。

## 旧政策的精确迁移

`migrate-policy [--project ABS] [--approval-file JSON]` 默认只读预览。明确 project 必须是规范绝对路径且命中登记 main/checkout，未命中零写 invalid_target。有效 project 的计划仍明确包括全机用户治理正文迁移，不能让批准者误以为只改一个项目文件。

迁移仅删除有创建证据和匹配指纹的产品 denied/control；识别冻结的旧公共治理、使用约定、用户 fallback 模板并替换成新职责模板，私文前后字节保留，更新对应指纹。未知定制与来源不明内容停止，不把它洗成用户限制。真正独立手写限制、外部受管块与 CK 设置保留。旧 disabled 可留作 tombstone，不渲染任何否决 CK 的新指令，不重新打开 CK、不初始化、不重建旧 remove 撤掉的入口。

批准绑定 observations 的字节与模式；锁内复核与事务 expected 仍引用获批快照，不能在构建事务时把新现场偷偷采纳为 expected。漂移拒绝而非覆盖。

## 核心流程与删除门槛

入口：`python3 -B scripts/agm.py uninstall-machine --backup-dir ABS`；执行追加 `--approval-file ABS`。`--backup-dir` 必须是已有真实父目录下的新目录，与所有待删根互不包含。批准是 `{plan:<精确预览摘要>,reference:<真实确认出处>,confirmed_at:<真实UTC>}`，不能复用别的命令批准。

1. 有界精确盘点：台账、入口、项目依赖、运行资产、升级标记、安装锁/事务锁与插件 staging。未知、活动、指纹不符均停止；不扫描整个 HOME 私文。
2. 展示计划：每项路径、归属、before/after 哈希与 stage，归还名单、解释器身份、残留恢复证据。未写入的预览不是已完成。
3. 批准后重建、锁内复核；漂移零覆盖，不能用新观察替换已批准状态。
4. 创建外置 manifest 与独立 recover.py，保存原字节/模式/链接清单；先静态校验可恢复材料，再实际运行恢复预览探测。
5. 先归还副本和资料闭包核验，再精确清理产品依赖，最后按清单逐项删除 R/C/版本/来源/私有工具。只 unlink 已核验工件、rmdir 空目录，不递归吞删新文件。
6. 结果输出 scope、machine_assets、host_plugin、overall、manifest、保留证据与 runtime pending。产品内部完成状态不能替代宿主插件移除证明。

项目 AGENTS.md 不整文件删除；原生 Claude/WB 桥接与 CK 归属明确保留。若 CK link/受管块依赖待删产品来源，应阻断要求独立迁移，不能借清失效依赖默认删除 CK。

静态字节保全、资料闭包、精确批准、漂移检查和恢复探测任何失败都阻断删除。宿主新会话是否读取归还副本、官方私有 CPython 裸机重定位尚未执行时可报告 pending，不能用“未跑”掩盖已知失败。

## 独立解释器与恢复

若解释器/stdlib 来自待删 mem-sharing-runtimes，只能对已核验官方资产整体复制到外置 `python-runtime/`，绑定完整清单、路径、模式、哈希。复制后以同一个批准计划绑定的解释器实际探测 recover.py；失败时 R/C/versions 零删除。未知解释器依赖停止，不能只复制一个 .py 就宣称裸机可恢复。

实际删除由外置解释器 `-I -S -B` 子进程执行，隔离 PYTHONPATH 与用户 site。解释器位置从**批准摘要或 manifest.plan.recovery_runtime.interpreter** 读取，不声称完成 envelope 含顶层 recovery_runtime。

产品代码删除后仍可独立执行：

```bash
'<独立解释器>' -I -S -B '<外置目录>/recover.py' --manifest '<外置目录>/manifest.json' --action restore
'<独立解释器>' -I -S -B '<外置目录>/recover.py' --manifest '<外置目录>/manifest.json' --action resume
```

默认恢复预览，另用 `--approval-file` 批准当前精确恢复现场；正常入口 `recover-uninstall --manifest ABS` 等价转交独立引擎。断点重试幂等，陌生第三状态不覆盖；不擅自抢活锁，未知锁不删。恢复与 CK 各有自己的批准。

## Paseo 插件义务与完成范围

CLI 未声明宿主义务时，`scope=standalone_declared`、`host_plugin=not_applicable`，completed 仅覆盖调用方声明的机器范围；这不是扫描 HOME 后证明没有插件。Paseo 为 `scope=machine_and_paseo`：机器资产可 completed，但插件仍在时 `host_plugin=pending/disabled`、`overall=partial`。disabled 不是 removed。

插件侧从 config.plugins 与自身真实加载来源匹配唯一安装记录，绑定真实安装 ID、source_dir、源码树哈希及编译期 manifest 摘要；包内产品常量不能代替安装别名。多 alias（包括 disabled 残留）歧义阻断；无已知记录不能绑定原宿主。托管 Git 安装在 config 中发布 source=directory 加载目录，CLI installation.identity 可为 git provenance，两个字段不要求相等；准确 ID、顶层 path、树哈希仍相等，完整 identity 进批准。未知 provenance 拒绝。

机器处理后，插件本体仍安装时使用外置入口完成四步，不从运行中的插件同步自杀等待，也不删除插件目录：

1. **bind**：`recover.py --manifest ABS --bind-host-plugin --paseo-cli REAL_ABS (--paseo-home ABS | --paseo-host ENDPOINT)`。只读 status 必须 connectedDaemon=reachable，full-list 中准确 ID、来源路径/identity 匹配，status/list/status 的 live serverId 一致。先预览，再独立 `--host-binding-approval-file` 精确批准，将 CLI 路径/哈希、daemon 目标、serverId、原插件行写入 manifest 同级 `host-binding.json`。首次空列表不能绑定；省略后续参数不能取消 manifest 原有义务。
2. **remove**：用户在独立终端执行 `paseo plugin remove '<准确ID>' --json`，明确使用与 binding 相同的 `--home` 或 `--host`。其返回构造的 disabled 对象不算移除证明。
3. **check**：外置 `recover.py --manifest ABS --check-host-plugin`，只读已批准 binding，不允许重选 target。再次确认可达且原 serverId 不变、完整列表成功且准确 ID 缺席，同来源其他 alias 不存在，才是 removed。列表错误、权限/版本/能力错误、新 daemon、disabled 或未预绑定就已移除，都保持 pending；无自动人工降级或虚构 SDK 管理 API。
4. **CK 选择**：已证实 removed 后才接受 CK 卸载预览。默认保留仅只读查当前 host 状态并返回 retained，不写；已 removed 则 overall completed，查询失败仍 partial。独立终端的接续命令不依赖已移除插件。

## 宿主 staging 与中断限制

staging 在固定 `HOME/.local/share/mem-sharing-plugin-staging`。宿主独立清理必须另起只读预览→精确批准→外置→核验→逐项删除；uninstall 预览不自动清理。新 uninstall 与 CK 后续不在待删 staging 创建自身运行记录；主执行返回后宿主不重建产品路径。

每个 op 目录独立认领，不用相邻 operation 给 request/approval 目录授权。operation.json 只接受已知 7/8 键（journal 可省略视 null），既存 op 必须真实目录、非 symlink；没有声称已检查其 uid 或 mode 必然0700。外置根与 op 目录创建0700；工件 mode 进计划、复制保留并删前复核。

只认已知 flow/工件；in-memory running 拒绝。原记录 running/unknown 只有固定归属的原 kernel journal 实读 committed/rolled_back、布局与状态吻合才可归结；receipt 可记 derived recovered，但历史 operation 原字节不改。未知/非终态/不归属 journal 删除前阻断。无 operation 的工件须全部超过十分钟 TTL，外置保留原 mtime 后由 core 实核并绑定 mtime_ns；未知内容拒绝。

核心只接受 staging 根**实际仅剩**0600 `host-receipt.json`；不存在 staging_after 字段。receipt 绑定外置 `backup_root/op-XXXX/<工件>` 平铺树、完整 digest、独立批准与终态证据；artifacts 精确 `{name,sha256}`，内部 plan 的 mode 不泄漏为 receipt 字段。core 实读字节/模式/mtime/目录闭包，外置证据只保留和观察，不授任意路径删除权。

外置或 fsync 在首删前失败可保证零源删除；失败外置树也保留（可能包含未知新增或部分证据），不递归回收，报告路径并要求重试使用新证据目录。开始逐 unlink 后如中断、出现新文件或 rmdir 失败，可能已有部分获批工件删除，但已外置保全；未知新文件保留，无成功 receipt，核心仍阻断。宿主清理没有通用独立事务 resume/restore，不能承诺所有故障都零删或自动重试收口。此时保留源与外置证据、报告 partial/pending 并诊断，不能盲删或覆盖既有备份。

## Context Keeper 的独立卸载

主 manifest completed 且本次完成现场核验通过后，另行选择；Paseo 还须宿主 removed 已实证。此入口用于本次即时尾步，用户后来正常编辑归还记忆会使现场失配；它不是日后通用 CK 管理器。

默认 `--ck-choice retain` 不写。明确 uninstall 必须提供独立 canonical CK 源码与明确 `--ck-agent` 范围，可重复选择 codex/claude/cursor/workbuddy/hermes/opencode/openclaw；不杜撰 dsh/zcode，不自动 --all，不自动获取网络源码。源码候选只是候选，显式选择后需 Git/来源清单身份与源码树/installer 哈希核验。

包装器实际运行上游 `scripts/install.py --<宿主> --uninstall` 只读预览，绑定源码树/工具/目标/结果，再另用 `--ck-approval-file` 精确批准后加 `--approved`。主批准不能复用。共享安装根必须按真实上游宿主边界整体处理，不能自动扩大范围或绕过上游拒绝。

上游 rc0 不是完成证明：须解析实际结果合同并现场核 Skill 缺席、桥接移除与私有字节保全。失败只记 CK 子流程失败，主 completed 不改写。失去该 Skill 自动记录、续接、历史检索、经验整理能力；项目规则及历史经历数据保留。六家 memSharing 支持范围与 CK 宿主范围不同。

## 生命周期、影响与验收

Python 真源为 scripts/，Node 共用真源为 plugins/shared/src/；生成副本遵既有 sync/release 工具，不手改 payload/server/shared。新增卸载/恢复/政策迁移三模块，删除 remove 模块；CLI、批量、check、模板、用户接入/升级与测试均按职责调整。文档发行清单唯一来源 plugin_release.SHIPPED_DOCS，install 直接引用；本方案随清单发行，本地链接必须在实际受管文件集合内闭合，不能靠硬编码总数。

定向证据分层：临时 HOME 核心字节/漂移/恢复测试、六个 os._exit 断点场景、复制真实 CK installer 到临时 fixture、Node fake CLI/runner 与实际 Python bridge，各说明来源。生产 Node stagingCleanup 产物直接由 Python parser 实读，通过普通7/8键、orphan TTL、原journal committed/rolled_back；非终态保持零删阻断，递增1ms时钟合同已验证。它们不是实际宿主卸载验收。

状态白名单与 durable export 最后窄修前的主区完整基线为 unit 699项、525.972s、OK（显式真实 CK 复制 fixture，无 skip）和 integration 64项、211.260s、OK；日志分别为 `/tmp/memsharing-uninstall-unit-final.log` 与 `/tmp/memsharing-uninstall-integration-final.log`。后续窄修由受影响 staging/库存/实际 bridge 与插件测试补齐，不把这份全量基线说成已包含最后源码。插件测试/typecheck 结果由最终交付日志记录；旧套件适配必须保留私文、漂移、恢复、锁与来源断言。真实 Paseo UI/移除、官方私有 CPython 重定位和六家新会话读取归还副本均 pending；已知失败必须阻断，不能写成未跑。

统一新流程退出码：approval_required=5；failed/recovery_required/pending=2；completed/restored/retained=0。core 批准不匹配是 failed=2，不能写成5；project check 的 gaps=1 另按既有合同。上游 CK rc0预览由外置包装转成5。界面同时读取 JSON 状态和 scope/overall，不能只凭退出码、插件 running 或机器 completed 宣称全卸载。

## 使用者实际看到的流程

以下为交互措辞与参数形状示例，路径、哈希和确认时间必须来自本次现场，不是可复用批准。

**预览**：“将把当前完整公共记忆归还给台账中的这些 Agent；每家保留独立副本。将逐项删除已证明归属的机器资产，项目规则、CK 历史及用户独有内容保留。外置备份位置与解释器如下；历史恢复证据若保留逐项列原因。尚未执行。”界面展示路径、before/after 哈希、stage 和真实待验项，展开计划时不倾倒私有 hex 字节。

**批准**：“确认后只执行当前精确计划；现场变化将停止。是否确认？”点击确认对应单次服务端 token 与计划，拒绝不写。Paseo 机器步骤成功后展示：

```json
{"scope":"machine_and_paseo","machine_assets":"completed","host_plugin":"pending","overall":"partial"}
```

随即说明：“机器资产已处理；Paseo 插件移除尚未证实。请保存外置命令，在插件仍安装时先绑定原 daemon，再从独立终端移除并查询证明。不要把 remove 返回的 disabled 当成完成。”按钮不会暗中去卸载插件或 CK。

外置四步的真实命令形状为：

```bash
'<独立解释器>' -I -S -B '<外置目录>/recover.py' --manifest '<外置目录>/manifest.json' --bind-host-plugin --paseo-cli '<真实CLI绝对路径>' --paseo-home '<原daemonHome绝对路径>'
# 上一命令独立预览并取得本次确认后，原参数追加 --host-binding-approval-file '<独立绑定批准JSON>'。
'<同一CLI绝对路径>' plugin remove '<准确安装ID>' --json --home '<同一daemonHome绝对路径>'
'<独立解释器>' -I -S -B '<外置目录>/recover.py' --manifest '<外置目录>/manifest.json' --check-host-plugin
'<独立解释器>' -I -S -B '<外置目录>/recover.py' --manifest '<外置目录>/manifest.json' --ck-choice retain
```

目标也可明确选择 `--host endpoint`，但不能在移除后临时换目标；check 与 CK 读取原 binding，不再传新 target。未证明 removed 时只能保留 CK 或停止，不开放 CK 卸载。

默认选择卡完整措辞：“**保留 Context Keeper（默认）**。本次不会卸载它，也不会替你开启、初始化或改变它的设置。memSharing 的公共记忆已按本次范围归还，项目规则与 CK 历史继续保留。如果你明确选择卸载 CK，将先展示它真实上游的独立预览，再另行确认宿主范围和源码身份；卸载后失去该 Skill 的自动记录、续接、历史检索与经验整理能力，规则与历史数据仍保留。”

失败示例：“原宿主查询失败，host_plugin=pending，overall=partial；未执行 CK。保留外置 manifest、recover.py、host-binding.json 与源现场，修复连接后重查原目标。”staging 逐项删除阶段中断则说明“已核验工件可能部分外置/删除，未知新文件已保留；没有成功 receipt，机器卸载仍阻断”，不显示“清理完成”。

## 实施文件与迁移顺序

| 范围 | 文件与作用 |
| --- | --- |
| CLI 与项目职责 | [agm.py](../scripts/agm.py)、[enable.py](../scripts/agm_core/enable.py)、[batch_enable.py](../scripts/agm_core/batch_enable.py)、[check.py](../scripts/agm_core/check.py)：退役经历参数/命令，只维护规则接入与历史兼容 |
| 模板与旧正文 | [user_entries.py](../scripts/agm_core/user_entries.py)、[public_layout.py](../scripts/agm_core/public_layout.py)、[policy_migration.py](../scripts/agm_core/policy_migration.py)：生成新职责模板，已知旧字节精确迁移，未知定制停止 |
| 卸载与恢复 | [uninstall.py](../scripts/agm_core/uninstall.py)、[uninstall_recovery.py](../scripts/agm_core/uninstall_recovery.py)：归还、清理、外置恢复、宿主证明与 CK 独立尾步 |
| 安装、升级、发行清单 | [install.py](../scripts/install.py)、[upgrade.py](../scripts/agm_core/upgrade.py)、[plugin_release.py](../scripts/agm_core/plugin_release.py)：既有安装/升级保护不放宽，单源文档清单与源码闭包同步 |
| Paseo 手写源 | `plugins/paseo/server/orchestrator.ts`、`server/payload.ts`、`shared/contracts.ts`、`index.server.ts`、`index.client.tsx`、`client/flow.tsx` 与结果展示 helper：独立预览/确认、真实安装别名、staging、三层状态与外置接续；不是第二套 Python 内核 |
| 文档与测试 | [SKILL](../SKILL.md)、[安装页](../INSTALL.md)、[操作手册](operations.md)、[架构](architecture.md) 及单元/集成/插件套件同步；测试路径只作仓库定位，不进入产品发行链接 |

迁移先后：先使生成器与 CLI 新合同一致；再给旧 denied/公共模板提供独立 migrate-policy 精确计划，保持 tombstone 与私文；再部署有相同代码身份的源码候选并验证安装/升级生命周期；需要卸载时独立处理可认领 staging，核心执行归还与删除；最后证实 Paseo 插件移除，再单独处理 CK。既存用户不必先盲目全升级才能预览旧政策迁移。正式发行必须等 clean S、明确版本与既有生成/闭包门禁，不把工作树源码或合成发行包冒充已发布版本。

## 关键测试矩阵与剩余门槛

| 场景 | 期望 | 证据层 | 剩余/待验 |
| --- | --- | --- | --- |
| 六家归还与私文字节 | 完整副本、模式/CRLF保全、Claude唯一行重定向；未知/漂移拒绝 | 临时 HOME Python 卸载套件 | 六家新会话实际读取 pending |
| active 资料闭包 | 绝对/相对公共链重映射、空目录与正常目录link保留；循环/逃逸/缺失拒绝 | Python 静态与临时文件 | 不冒称通用 Markdown 解释器 |
| 精确批准/事务竞态 | 参数、来源、解释器、字节或模式漂移零覆盖 | Python 定向与进程故障测试 | 真实 HOME 未执行 |
| 六个进程断点 | 归还/清依赖/删除阶段硬退出后独立恢复或继续，陌生第三状态拒绝 | `tests/integration/test_uninstall_process.py` 真实临时进程 | 无真实卸载 |
| staging producer→consumer | 实际 Node 清理输出由 Python实读；时间同stamp、TTL/mode/digest/原journal终态正确 | `plugins/paseo/test/staging-cleanup.test.ts` 与生产函数临时产物 | 逐unlink中断无通用自动恢复 |
| 宿主证明 | 原ID/加载来源/完整provenance、CLI hash、reachable serverId、完整列表缺席；错daemon/disabled/别名/失败pending | fake CLI真实子进程、Node实际 argv→Python桥接 | 真实 Paseo remove/UI pending |
| CK 独立选择 | 默认保留零写、主批准不能复用、未知源/共享范围拒绝、假rc0与无效果拒绝 | fake installer＋复制真实上游installer到临时fixture | 不改上游；真实宿主卸载pending |
| 完整回归 | 退役接口适配且保留私文、漂移、恢复保护 | 主区 integration 64项，211.260s，exit0；日志 `/tmp/memsharing-uninstall-integration-final.log` | 主区 unit 699项、525.972s、OK且无skip；这两份全量均为最后白名单/导出库存窄修前基线 |
| 发行与文档 | 新三模块/remove缺席、实际受管文件与文档相对链接闭合 | `tests/unit/test_release_closure.py` | 正式 payload 未生成、版本未改 |

非目标：不扫描全 HOME、不删除旧管理器和源码、不逐项目 remove、不恢复安装前记忆、不替用户打开 CK、不在已移除插件内继续运行管理流程、不修改其他插件/daemon/CK上游，不 commit/push/发布/保存项目记忆。后续技术核实仍是官方私有解释器重定位、真实 Paseo UI 与移除、六家原生新会话加载、正式源码与发行身份闭包；已知失败要阻断，未做才写 pending。

最后窄修补验：插件全套 54 个测试（53 通过、0 失败、1 跳过），93695.89025ms，退出0，日志 `/tmp/ms-guaji-plugin-frozen.log`。跳过仅为可选固定 pin CK 安装子测试：本地 checkout HEAD 与固定 pin 不符；真实 Node→当前 Python 的临时 HOME 卸载、三层 partial、删除代码后的外置恢复主 bridge 已通过，不能把该跳过解释为主 bridge 未跑。受影响核心/库存/文档 11项、5.526s、OK，日志 `/tmp/ms-guaji-python-frozen.log`；SDK typecheck 退出0，日志 `/tmp/ms-guaji-tsc-frozen.log`。两者与此前主区全量基线分开报告；没有操作真实 Paseo 插件移除或用户 HOME。
