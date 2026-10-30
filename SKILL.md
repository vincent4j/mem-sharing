---
name: mem-sharing
description: memSharing，多 Agent 记忆共享与融合。提供用户记忆与项目规则的启用、检查、停用、主动接入与整理操作路由；项目经历交由 Context Keeper。
---

# memSharing 操作说明

唯一设计依据：[DESIGN.md](DESIGN.md) v2.0 与[系统架构](docs/architecture.md)。本文是仓库内操作说明，菜单由用户级规则文本承载，不创建产品 Skill 投影。旧版验收不自动证明本轮新命名、默认启用及 keeper 集成已通过；M4-09 已通过(见[验收总览](docs/acceptance/index.md))。

## 会话入口与六项菜单

用户输入 `/mem-sharing` 且未说明操作时展示以下六项；已表达明确意图时直接路由，不重复问菜单。菜单不是新增 CLI 子命令。

| 选项 | 操作路由 |
|---|---|
| 给项目启用记忆 | 建立或显式恢复当前项目入口 → `scripts/agm.py enable-memory --project <根> --memory`。 |
| 添加新的 Agent | 核验 installed 后同版接入 → `scripts/install.py --agent <名字>`，来源参数见 INSTALL。 |
| 健康检查 | 只读检查当前项目 → `scripts/agm.py check-memory --project <根>`，全量用 `--all`。 |
| 停用记忆 | 撤入口、保数据并登记 disabled → `scripts/agm.py remove-memory --project <根>`。 |
| 整理用户规则 | 逐条计划、一次批准 → 下文“用户规则治理”的模块 API 流程。 |
| 批量启用记忆 | 扫目录、集中预览批准 → `scripts/agm.py enable-memory-batch --directory <目录>`。 |

以上脚本均以 `python3 -B` 从已核验产品代码目录执行。详细安装、批准与恢复只在需要时读 [INSTALL.md](INSTALL.md)，批量边界与详细操作读[操作手册](docs/operations.md)。

停用记忆下的进阶指引：仅禁止自动项目经历记录与初始化而保留入口，使用 `enable-memory --project <根> --no-memory`；它不执行 remove。两者均登记 disabled，默认启用与批量均不翻转；解除需显式 `--memory` 并批准精确计划。

后装 Agent 不自动发现、不自动提示；仅用户主动选“添加新的 Agent”后核验安装事实。名字、残留目录或 hint 不能代替 installed。absent 不创建入口，unknown 只报告不写。机器台账中的事实记录不驱动自动接入。

## 安装与项目默认启用

产品未安装时读 [INSTALL.md](INSTALL.md)，从已核验源调用 `python3 -B scripts/install.py`，补齐来源参数。先检查 Python、Git、已适配执行器，汇总一次确认；正常安装静默，最后简报后征询是否安装 keeper。项目命令不隐式安装或升级机器产品，check 不修复。

用户级规则驱动未登记的 Git 主 checkout 默认启用：建立 `AGENTS.md` 骨架与纯协议桥接，已有正文保留，不重复询问是否启用。非 Git 不触发，worktree 明确报告未支持，不自动启用。项目记忆是规则；项目经历的记录库按 keeper 首次 `/context-keeper` 流程初始化，不由默认启用创建。

项目缺省启用不创建或补写 `CLAUDE.md`，已有文件原样保留；显式 `enable-memory --agent claude` 可接入。项目兜底入口按实际使用驱动：Claude 首次在已启用项目实际使用且缺引用时幂等补 `CLAUDE.md` 引用；仅本机安装 Claude 不足以创建该文件。WorkBuddy 原生目录出现后才补顶部协议块，不预建目录。Codex 使用 `AGENTS.md`，无额外兜底入口。已有用户字节保留，受管单元漂移停写。

## 用户规则治理

目前无整理 CLI 子命令。执行 Agent 按 `scripts/agm_core/user_rules_organize.py` 的 `plan_organize(request)` / `run_organize(request)` 或 `run(request)` 调用；request 显式提供 `home/platform_config`，以完整计划加真实 `confirmed_at/reference` 批准。调用细节按需读[操作手册](docs/operations.md)，不自行虚构菜单 CLI。

Agent 独有内容永不并入公共源、永不删除；归属不明保持 keep。公共内容只写 `~/.mem-sharing/memories/` 的指定文件，不写入各家私有用户规则文件；独有内容留各自用户文件。

整理向导批准的是完整逐条计划加 `confirmed_at/reference`，一次确认，不使用 `item_confirmations`。每项绑定原文指纹；decisions 在批准前允许逐项改判，改判后的完整计划须重新匹配批准。删除、修改冗余或过时项只能提议，不能自动执行；独有/未知归属锁定 keep。旧整文件记录入口进入 `blocked_entries`，不扩大所有权，不先改后问。

## 三种记忆与 Context Keeper

用户记忆是跨项目习惯，位于 `~/.mem-sharing/memories/`；项目记忆是 `AGENTS.md` 规则；项目经历是 keeper 的进度、决策、日志与积累，记录库默认位于项目 `docs/context-keeper/`，具体由 keeper 定义。

装机尾步按安装页的固定正向问句征询 keeper 用户级安装，回车同意，n 跳过。同意后走 `scripts/install.py --context-keeper` 独立路由与 `install-context-keeper` 封皮，由 keeper 自有安装器为全部已接入执行器安装；其 Skill 落位由 keeper 负责。EOF、非交互或空格不视为同意；keeper 缺源或失败独立报告，不回滚主产品。来源与批准细节按需读 INSTALL。未装 keeper 不报产品错误，用户记忆和项目记忆照常工作。

项目 enable 不再调用 keeper 安装器，不安装项目级 keeper Skill。协议桥接首行说明记录库位置与 `/context-keeper` 入口。初始化与授权归 keeper 首次命令，memSharing 不接管保存或查找流程。disabled 优先禁止自动经历，已有 keeper 自动规则不得覆盖；keeper 脚本本身不读取该政策，不能宣称硬拒写。手动 keeper 操作仍按明确请求与 keeper 自身门禁处理。

## 检索与分层读取

检索只用索引精确查找（find），不使用 search 或语义搜索。

- L0 恒读：`memories/MEMORY.md` 每行包含主题名、一句话当前结论、链接，上限 200 行／25KB。
- 需要时读 L1：主题文件开头几行概要，包含当前有效结论与待办。
- 仍不足读 L2：主题全文与 `references/` 手册。

沿用索引与主题文件，不新增文件类型，不自动生成摘要；Agent 整理时手写概要，固定预算不变成配置项。

## 执行与报告边界

机器批准采用完整 `approval_plan` 加真实确认出处，来源和现场变化必须重核；项目显式写操作遵守匹配计划，不自造批准。机器恢复使用 `--recover <journal绝对路径> --action continue|rollback`，执行另需 `--approval-file`，不能与普通安装混用。无 `--force/--repair`，不擅自删锁。

底层诊断保留状态、精确变化、错误和恢复位置；成功对话遵守安装页的极简报告，不倾倒路径或未安装名单，不添加新会话自检提示。失败或 partial 如实说明未完成，不能凭退出码 0 声称三家运行时均已生效。

项目写操作无批准先预览；批量待批准退出码 5，`next_action` 提供完整批量封皮模板，变更 `applied=false` 不表示已写入。schema=3 为活动合同，旧 v1/v2 仅只读诊断，旧开发版与旧标记不做迁移；详情按需读 INSTALL。

`AGENTS.md` 永不整文件删除；新建纯 CLAUDE 入口只在 created 证据完备时可删，有正文只撤允许撤销的单元，旧 reused 不追认删除权。记录库、私有记忆与其他 Skills/MCP 不由本产品删除。本轮不交付完整机器卸载。
