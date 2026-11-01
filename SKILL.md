---
name: mem-sharing
description: memSharing，多 Agent 记忆共享与融合。提供公共用户记忆共享、项目规则接入、检查、整理与整机卸载路由；支持明确自然语言卸载意图，项目经历由 Context Keeper 独立管理。
---

# memSharing 操作说明

唯一设计依据：[DESIGN.md](DESIGN.md) 与[系统架构](docs/architecture.md)。本文是仓库内操作说明，菜单与详细使用约定由公共指南 `~/.mem-sharing/memories/topics/使用约定.md` 承载，各执行器用户文件只保留公共指针与自身规则；不创建产品 Skill 投影。旧版验收不自动证明本轮新命名、默认启用及 Context Keeper 集成已通过；M4-09 的本地范围与阻断项见[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)。

## 会话入口与六项菜单

用户输入 `/mem-sharing` 且未说明操作时展示以下六项；已表达明确意图时直接路由，不重复问菜单。菜单不是新增 CLI 子命令。

| 选项 | 操作路由 |
|---|---|
| 添加新的 Agent | 核验 installed 后同版接入 → `scripts/install.py --agent <名字>`，来源参数见 INSTALL。 |
| 批量接入项目规则 | 扫目录、集中预览批准 → `scripts/agm.py enable-memory-batch --directory <目录>`。 |
| 整理用户记忆 | 逐条计划、一次批准 → 下文“用户记忆治理”的模块 API 流程。 |
| 健康检查 | 只读检查当前项目 → `scripts/agm.py check-memory --project <根>`，全量用 `--all`。 |
| 接入项目规则 | `scripts/agm.py enable-memory --project <根> --agent <当前执行器>`；历史停用登记默认跳过。 |
| 整机卸载 | 归还公共用户记忆并外置恢复材料 → `scripts/agm.py uninstall-machine --backup-dir <全新外置目录>`，预览后精确批准。 |

以上脚本均以 `python3 -B` 从已核验产品代码目录执行。详细安装、批准与恢复只在需要时读 [INSTALL.md](INSTALL.md)，批量边界与详细操作读[操作手册](docs/operations.md)。

旧 `remove-memory`、`--memory`、`--no-memory` 已退役，新请求零写拒绝。历史 disabled 只作规则接入 tombstone，默认跳过、不重建；它不否决 Context Keeper 的自动规则，不表示 CK 已停用或入口已删除。使用 `migrate-policy [--project ABS]` 精确预览并批准后，仅退役产品自有且指纹匹配的旧控制与已知旧模板，保留私文、CK 设置和历史数据，不替用户启用 CK。

支持 `codex`、`claude`、`workbuddy`、`dsh`、`zcode`、`opencode` 六家。机器安装、再次安装与升级缺省接入全部已核验 `installed` 的支持对象，`unknown/absent` 只报告；显式重复 `--agent` 限定机器目标，指定对象未核验为 installed 时整单拒绝。升级中的公共布局迁移与新增接入在同一外层精确计划内预览并一次批准，不推迟到执行后再确认。项目命令缺省仍为前三家，当前执行者使用时显式选择自身；项目启用 `--agent dsh zcode opencode` 为一次多值。后三家用户入口为 `~/.dsh/AGENTS.md`、`~/.zcode/AGENTS.md`、`~/.config/opencode/AGENTS.md`，均保留私文且原生读取项目 `AGENTS.md`。OpenCode 支持独立核验桌面 App 与 CLI 安装面，CLI-only 不证明桌面存在；官方原生 CLI 与 App 并装采用受限身份校验。OpenCode v2 第一版 default-root-only，环境重定向整单停写，错误不回显原值；详见[操作手册](docs/operations.md#桌面端默认根与验证边界)。真实新会话加载仍待验收。

后装 Agent 可通过“添加新的 Agent”限定接入；重新运行机器安装器也会按当前安装事实发现并预览全部支持对象。名字、残留目录、hint 或历史台账不能代替当前 installed；absent 不创建入口，unknown 只报告不写。

## 自然语言卸载入口

在任何已接入且读到公共索引的 Agent 中，说“卸载 memSharing”“卸载 mem-sharing”或“不想用这个共享记忆工具了，帮我卸载”，直接进入同一只读卸载预览，无须 `/mem-sharing`，也无须进入源码目录。入口链为原生用户文件 → 公共 `MEMORY.md` 的短触发 → 《使用约定》的完整路由 → 已核验安装 C 的本文件与[完整卸载合同](docs/uninstall-design.md)。公共路由由 `user_entries.natural_language_uninstall_text()` 单源生成，不复制六套流程、不新增 Skill 投影。

“卸载这个项目”“停用项目记忆”不足以确定产品，只澄清目标；不得删当前项目。明确的产品卸载意图仍不批准未展示的精确计划。先核验安装台账、代码来源与实际安装形态，提议全新外置路径（预览不创建目录），用已核验 C 的绝对路径调用 `python3 -B <C>/scripts/agm.py uninstall-machine --backup-dir <外置绝对路径> --json`。展示归还、保全、删除范围与恢复材料，获得精确批准后才加 `--approval-file` 执行。

跨 Agent 发起不改变 Paseo 宿主义务。已有 Paseo 来源须沿既有 RPC 或完整宿主参数合同；来源或目标不明先补证，不能默认独立 CLI、伪造 absent 或扫全 HOME。Paseo 仍按外置 bind→官方 remove→同 daemon 缺席核验→CK 尾步；全部声明范围成功后才单独问是否卸载 CK，默认保留，另行预览与批准。已卸载或 C 缺失只报告状态或使用已核验外置恢复入口，不自动重装。安装代码已具备当前兼容实现时可只迁公共指南；不兼容旧 C 先沿现有精确安装/升级流程更新代码，迁移门禁零写拒绝新指针配旧执行器。六家静态读取链可合成验证，真实模型理解与新会话触发仍 pending。

## 安装与项目默认启用

产品未安装时读 [INSTALL.md](INSTALL.md)，从已核验源调用 `python3 -B scripts/install.py`，补齐来源参数。先检查 Python、Git、已适配执行器，汇总一次确认；正常安装静默，最后简报后征询是否安装 Context Keeper。项目命令不隐式安装或升级机器产品，check 不修复。

用户级规则与公共指南驱动未登记的 Git 主 checkout 默认启用：建立 `AGENTS.md` 骨架与纯协议桥接，已有正文保留，不重复询问是否启用。默认接入由当前实际执行者按指南以 `--agent <当前执行者>` 执行；不带 agent 参数按已安装事实处理，可能顺带补齐其他执行器已存在的原生目录，仅用于用户显式要求全体或批量接入，不改 CLI 语义。非 Git 不触发，worktree 明确报告未支持，不自动启用。项目记忆是规则；项目经历的记录库按 Context Keeper 首次 `/context-keeper` 流程初始化，不由默认启用创建。

不带 `--agent` 的通用 enable 不创建或补写 `CLAUDE.md`，已有文件原样保留。Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `CLAUDE.md` 引用；兜底规则位于 Claude 自身用户文件；其它执行者默认流程不预建，仅本机安装 Claude 或其原生目录存在不足以创建该文件。WorkBuddy 原生目录出现后才补顶部协议块，不预建目录。`AGENTS.md` 是共享项目规则基座，任何实际使用的已接入执行者都可按政策默认建立，不依赖安装 Codex；只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立，缺失的执行器用户目录不预建。已有用户字节保留，受管单元漂移停写。

## 用户记忆治理

目前无整理 CLI 子命令。执行 Agent 按 `scripts/agm_core/user_rules_organize.py` 的 `plan_organize(request)` / `run_organize(request)` 或 `run(request)` 调用；request 显式提供 `home/platform_config`，以完整计划加真实 `confirmed_at/reference` 批准。调用细节按需读[操作手册](docs/operations.md)，不自行虚构菜单 CLI。

Agent 独有内容永不并入公共源、永不删除；归属不明保持 keep。公共内容只写 `~/.mem-sharing/memories/` 的指定文件，不写入各家私有用户文件；独有内容留各自用户文件。

整理向导批准的是完整逐条计划加 `confirmed_at/reference`，一次确认，不使用 `item_confirmations`。每项绑定原文指纹；decisions 在批准前允许逐项改判，改判后的完整计划须重新匹配批准。删除、修改冗余或过时项只能提议，不能自动执行；独有/未知归属锁定 keep。旧整文件记录入口进入 `blocked_entries`，不扩大所有权，不先改后问。

## 三种记忆与 Context Keeper

用户记忆是跨项目习惯，位于 `~/.mem-sharing/memories/`；项目记忆是 `AGENTS.md` 规则；项目经历是 Context Keeper 的进度、决策、日志与积累，记录库默认位于项目 `docs/context-keeper/`，具体由 Context Keeper 定义。

装机尾步按安装页的固定正向问句征询 Context Keeper 用户级安装，回车同意，n 跳过。同意后走 `scripts/install.py --context-keeper` 独立路由与 `install-context-keeper` 封皮，由 Context Keeper 自有安装器为已接入的 Codex、Claude Code、WorkBuddy 安装；固定 pin 的安装器仅支持这三家的 flags，`dsh`、`zcode`、`opencode` 明确跳过（`reason=upstream_unsupported`），混合接入时旧三家仍可安装，不影响它们的 memSharing 接入。其 Skill 落位由 Context Keeper 负责。EOF、非交互或空格不视为同意；缺源或失败独立报告，不回滚主产品。来源与批准细节按需读 INSTALL。未装 Context Keeper 不报产品错误，用户记忆和项目记忆照常工作。

项目 enable 不再调用 Context Keeper 安装器，不安装项目级其 Skill。协议桥接首行说明记录库位置与 `/context-keeper` 入口。初始化与授权归 Context Keeper 首次命令，memSharing 不接管保存或查找流程。历史 disabled 仅保留为规则接入 tombstone，默认不重建过去撤掉的入口；不否决 Context Keeper 的自动规则。Context Keeper 开启后的记录、续接与检索按其自身规则运行，memSharing 不写其开关，也不借迁移自动恢复入口。

## 检索与分层读取

检索只用索引精确查找（find），不使用 search 或语义搜索。

- L0 恒读：`memories/MEMORY.md` 只保留短读取契约、200 行／25KB 预算、公共治理要点、按需指南指针与真实主题索引；每主题一行，含主题名、一句话当前结论、链接。
- 需要时读 L1：主题文件开头几行概要，包含当前有效结论与待办。
- 仍不足读 L2：主题全文、`topics/使用约定.md` 详细维护规则与 `references/` 手册。

六项菜单与详细 L0/L1/L2 维护规则集中在 `memories/topics/使用约定.md`，索引不重复全文，也不回圈指向菜单。触发 `/mem-sharing` 及同义操作、默认项目接入前，先按指针读公共指南；索引中的相对链接以 `MEMORY.md` 所在目录解析，指南内链接以指南所在目录解析；指南缺失时停止相关操作。沿用索引与主题文件，不新增文件类型，不自动生成摘要；Agent 整理时手写概要，固定预算不变成配置项。该分层为本轮实现目标，运行验证以验收总览为准。

## 执行与报告边界

机器批准采用完整 `approval_plan` 加真实确认出处，来源和现场变化必须重核；项目显式写操作遵守匹配计划，不自造批准。机器恢复使用 `--recover <journal绝对路径> --action continue|rollback`，执行另需 `--approval-file`，不能与普通安装混用。无 `--force/--repair`，不擅自删锁。

底层诊断保留状态、精确变化、错误和恢复位置；成功对话遵守安装页的极简报告，不倾倒路径或未安装名单，不添加新会话自检提示。失败或 partial 如实说明未完成，不能凭退出码 0 声称所有执行器运行时均已生效。

项目写操作无批准先预览；批量待批准退出码 5，`next_action` 提供完整批量封皮模板，变更 `applied=false` 不表示已写入。schema=3 为活动合同，旧 v1/v2 仅只读诊断，旧开发版与旧标记不做迁移；详情按需读 INSTALL。

本次卸载保留项目 `AGENTS.md`、有效 Claude `@AGENTS.md` 与 WorkBuddy 原生桥接；只清理已证明产品自有、指纹吻合且引用待删产品路径的失效依赖，不延续旧 remove 的整容器删除权。记录库、私有记忆与其他 Skills/MCP 不由本产品删除。完整机器卸载按下述独立合同执行。

## 整机卸载与独立尾步

整机卸载使用 `python3 -B scripts/agm.py uninstall-machine --backup-dir <全新外置目录>` 先预览，再以 `--approval-file` 精确批准。归还当前完整公共记忆给每个实际接入者的自身用户目录，再核验、清依赖、最后删除产品；不是恢复安装前。外置 manifest/recover.py 与独立解释器支持删除代码后的精确恢复。未知/漂移阻断，项目 AGENTS、有效 Claude/WB 桥接及 CK 默认保留。完整数据与门槛见[整机卸载方案](docs/uninstall-design.md)。

CLI 的 `scope=standalone_declared`、`host_plugin=not_applicable` 仅声明调用范围；Paseo 为 `machine_and_paseo`，机器 completed 但插件仍在时 overall=partial。必须在插件移除前经外置入口独立绑定真实安装 ID/来源/CLI/daemon/live serverId，再用户 remove、同目标 full-list check 证实缺席，最后才可另选卸载 CK。disabled、查询错误、能力/版本错误均不算 removed；默认保留 CK，尾步另行精确批准。正式 payload 待干净提交与版本授权后生成，本轮源码/合成验证不等于实际宿主卸载或六家新会话加载验收。
