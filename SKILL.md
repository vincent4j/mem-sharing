---
name: mem-sharing
description: memSharing，多 Agent 记忆共享与融合。提供用户记忆与项目规则的启用、检查、停用、主动接入与整理操作路由；项目经历交由 Context Keeper。
---

# memSharing 操作说明

唯一设计依据：[DESIGN.md](DESIGN.md) v1.14；最新替代关系以 [M4 决策 §14—§24（后续替代见 §25—§26）](docs/plan/decisions-m4.md) 为准。本文是仓库内操作说明，菜单由用户级规则文本承载，不创建产品 Skill 投影。旧版验收不自动证明本轮新命名、默认启用及 CK 集成已通过；当前案例见 [M4-09](docs/acceptance/m4/m4-09/cases.md)。

## 会话入口与六项菜单

用户输入 `/mem-sharing` 且未说明操作时展示以下六项；已表达明确意图时直接路由，不重复问菜单。菜单不是新增 CLI 子命令。

| 选项 | 操作路由 |
|---|---|
| 给项目启用记忆 | `python3 -B scripts/agm.py enable-memory --project <实际Git主checkout根>`；按默认启用与当前授权执行，不初始化 CK 记录库。 |
| 添加新的 Agent | 输入名字，映射到 `codex`、`claude` 或 `workbuddy`，核验 installed 后运行安装器同版通道，使用 `--agent <名字>` 与已核验来源。 |
| 健康检查 | `python3 -B scripts/agm.py check-memory --project <实际项目根>`；明确请求全量时使用 `--all`。始终只读。 |
| 停用记忆 | `python3 -B scripts/agm.py remove-memory --project <实际项目根>`，只撤允许撤销的受管单元，保留机器安装、用户级接入、规则正文与记录库。`enable-memory --no-memory` 的事后撤权沿 R1 语义。 |
| 整理用户规则 | 只读扫描，逐条分类与提议，允许批准前调整 decisions，一次批准完整计划后执行。 |
| 批量启用记忆 | 用户给目录，扫描 Git 主 checkout，每项目一行预览，一次批准后复用 enable 内核批量执行。 |

<!-- TODO（与代码侧核对）： 整理向导、批量启用的可执行入口及参数尚待集成冻结；不得自造 CLI。默认启用如何绑定规则授权、批量批准封皮及 --no-memory 的返回字段需对照新实现。 -->

后装 Agent 不自动发现、不自动提示；仅用户主动选“添加新的 Agent”后核验安装事实。名字、残留目录或 hint 不能代替 installed。absent 不创建入口，unknown 只报告不写。机器台账中的事实记录不驱动自动接入。

## 安装与项目默认启用

产品未安装时读 [INSTALL.md](INSTALL.md)，从已核验源调用 `python3 -B scripts/install.py`，补齐来源参数。先检查 Python、Git、已适配执行器，汇总一次确认；正常安装静默，最后简报后征询是否安装 CK。项目三命令不隐式安装或升级机器产品，check 不修复。

用户级规则驱动尚未启用的 Git 主 checkout 默认启用：建立 `AGENTS.md` 骨架与纯协议桥接，已有正文保留，不重复询问是否启用。非 Git 不触发，worktree 明确报告未支持，不自动启用。项目记忆是规则；项目经历的记录库按 CK 首次 `/context-keeper` 流程初始化，不由默认启用创建。

项目入口按实际使用驱动：Claude 首次在已启用项目实际使用且缺引用时幂等补 `CLAUDE.md` 引用；仅本机安装 Claude 不足以创建该文件。WorkBuddy 原生目录出现后才补顶部协议块，不预建目录。Codex 使用 `AGENTS.md`，无额外兜底入口。已有用户字节保留，受管单元漂移停写。

## 用户规则治理

Agent 独有内容永不并入公共源、永不删除；归属不明保持 keep。公共内容只写 `~/.mem-sharing/memories/` 的指定文件，不写入各家私有用户规则文件；独有内容留各自用户文件。

整理向导批准的是完整逐条计划加 `confirmed_at/reference`，一次确认，不使用 `item_confirmations`。每项绑定原文指纹；decisions 在批准前允许逐项改判，改判后的完整计划须重新匹配批准。删除、修改冗余或过时项只能提议，不能自动执行；独有/未知归属锁定 keep。旧整文件记录入口进入 `blocked_entries`，不扩大所有权，不先改后问。

## 三种记忆与 Context Keeper

用户记忆是跨项目习惯，位于 `~/.mem-sharing/memories/`；项目记忆是 `AGENTS.md` 规则；项目经历是 CK 的进度、决策、日志与积累，记录库默认位于项目 `docs/context-keeper/`，具体由 CK 定义。

装机尾步按安装页的固定正向问句征询 CK 用户级安装，回车同意，n 跳过。同意后由 CK 自有安装器为全部已接入执行器安装；其 Skill 落位由 CK 负责。未装 CK 不报产品错误，用户记忆和项目记忆照常工作。

项目 enable 不再调用 CK 安装器，不安装项目级 CK Skill。协议桥接首行说明记录库位置与 `/context-keeper` 入口。初始化与授权归 CK 首次命令，装后行为完全由 CK 定义，memSharing 不接管保存或查找流程。

## 检索与分层读取

检索＝索引精确查找（find），不做语义搜索。

- L0 恒读：`memories/MEMORY.md` 每行包含主题名、一句话当前结论、链接，上限 200 行／25KB。
- 需要时读 L1：主题文件开头几行概要，包含当前有效结论与待办。
- 仍不足读 L2：主题全文与 `references/` 手册。

沿用索引与主题文件，不新增文件类型，不自动生成摘要；Agent 整理时手写概要，固定预算不变成配置项。

## 执行与报告边界

机器批准采用完整 `approval_plan` 加真实确认出处，来源和现场变化必须重核；项目显式写操作遵守匹配计划，不自造批准。机器恢复使用 `--recover <journal绝对路径> --action continue|rollback`，执行另需 `--approval-file`，不能与普通安装混用。无 `--force/--repair`，不擅自删锁。

底层诊断保留状态、精确变化、错误和恢复位置；成功对话遵守安装页的极简报告，不倾倒路径或未安装名单，不添加新会话自检提示。失败或 partial 如实说明未完成，不能凭退出码 0 声称三家运行时均已生效。

<!-- TODO（与代码侧核对）： 新版项目 envelope、退出码与字段清单；CK 的内部状态不作为 memSharing 项目规则启用的成功标准。 -->

`AGENTS.md` 永不整文件删除；新建纯 CLAUDE 入口只在 created 证据完备时可删，有正文只撤允许撤销的单元，旧 reused 不追认删除权。记录库、私有记忆与其他 Skills/MCP 不由本产品删除。本轮不交付完整机器卸载。
