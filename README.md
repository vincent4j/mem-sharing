# agent-group-memory · 多 Agent 记忆共享

> Multi-Agent Memory Sharing —— 周一用 Codex、周二用 WorkBuddy,同一个项目,同一份记忆。

跨执行器(Codex / Claude Code / WorkBuddy)共享记忆的**互通编排层**:一条命令把项目规则入口与
[context-keeper](https://github.com/vincent4j/context-keeper) 记忆库装配到三个执行器,换工具不失忆。

本仓库**不自建项目记忆**——项目记忆直接复用 context-keeper 记录库;本工具只负责安装、入口配置、
授权记账与所有权卸载。三套系统(本工具 / context-keeper / 各执行器原生配置)的分工边界见
[DESIGN.md §1.2](DESIGN.md)。

## 平台支持

| 平台 | 状态 |
|---|---|
| macOS(arm64) | 安装/重装/卸载/失败恢复四项已验收([docs/acceptance/m2-platforms.md](docs/acceptance/m2-platforms.md)) |
| Windows / Linux | **not-run**:无环境、路径表未收录,不声称支持 |

仅依赖 Python ≥3.9 标准库;无第三方依赖、无全局安装。

## 快速开始

**方式一(推荐):经 agent 说人话。** 在装有本仓库的项目里对任一执行器说"帮我装配跨执行器记忆",
由 agent 按 [SKILL.md](SKILL.md) 路由执行;预览与批准由它转述给你确认。

**方式二:直接 CLI。** 在目标项目里执行(路径填本仓库 checkout):

~~~bash
# 1) 预览(只读):返回 5 时 stdout 的 next_action 就是待确认的精确计划
python3 /path/to/agent-group-memory/scripts/agm.py enable-memory --project <目标项目Git根> --memory

# 2) 把 next_action JSON 存成文件,补上 confirmed_at(UTC,形如 2026-10-29T14:06:16Z)
#    与 reference(本次确认的出处说明),即为批准文件
python3 /path/to/agent-group-memory/scripts/agm.py enable-memory --project <目标项目Git根> \
    --memory --approval-file plan.json
~~~

装配内容:项目四条 Skill 符号链接(指向你确认过的 context-keeper checkout)、AGENTS.md/CLAUDE.md
桥接块、WorkBuddy 项目桥接(经 context-keeper 安装器 `--workbuddy` ensure 写入与维护——上游已正式
接管,M3 回传完成)与用户级例外条款、`docs/context-keeper/` 记录库。只触碰上述受管对象;
你的既有规则字节原样保留。

## 三命令与退出码

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `enable-memory` | 经授权装配/补装规则基座与记忆档 | `--project` `--agent codex\|claude\|workbuddy…`(缺省三家)`--memory\|--no-memory` `--approval-file` |
| `check-memory` | 只读巡检现场状态与缺口,不修复 | `--project`(缺省当前)或 `--all`(全部已登记项目) |
| `remove-memory` | 仅撤销本工具创建的对象;记录库永不删除 | `--project` `--approval-file` |

| 退出码 | 含义 |
|---|---|
| 0 | 完成(check 全绿 / 幂等无变更) |
| 1 | check 发现缺口(只报告,不修复) |
| 2 | 参数、schema、路径冲突、执行或恢复失败 |
| 3 | context-keeper 迁移门禁:立即停止读写,先看迁移预览 |
| 5 | 待授权:需要批准文件(或在交互终端确认) |

stdout 恒为单个 JSON envelope(`status/projects/changes/warnings/errors/approval_required/next_action`),
stderr 是人读摘要。

## 批准文件

写命令(enable/remove)的变更计划必须经用户确认:预览返回 5 时,`next_action` 给出**精确计划**
(目标身份、源码指纹、库位置、逐路径前后指纹)。把它落盘、填上 `confirmed_at`(UTC ISO8601,必须以
`Z` 结尾)与 `reference`(确认出处,不保存对话正文),再用 `--approval-file` 提交。CLI 与内核会逐项
核对计划与锁内现场,任何不符整体拒绝。注意:remove 的精确计划预览需在交互终端获取(非交互无批准时
只返回门禁提示);幂等补装(现场与登记一致)不需要新批准。

## 已知限制

- **created 对象被外部改动无自动修复**:登记指纹漂移时 enable 拒绝写入(`drift`),需人工还原字节,
  或另行批准 remove 后重装;批准文件不能越过该保护。
- **remove→重装不是字节无损**:受管块内容不变,但块间连接符换行会重排;WorkBuddy 项目
  MEMORY.md 每个完整周期文件尾多一个换行(详见
  [docs/acceptance/m2-platforms.md](docs/acceptance/m2-platforms.md) §3)。
- **Claude Code 读回已验证,但未显式走 Skill/resume 的程序化验收**;WorkBuddy 桥接已由上游
  context-keeper 接管(`--workbuddy` ensure,既有块幂等接管已验证),**真机新会话接力验收待做**。
- **registry 与备份是本机文件**(`scripts/registry.json`、`scripts/backups/`,已 gitignore):
  不随仓库分发,换机器/新 clone 须重新 `enable-memory` 重建登记;记录库内容则随项目提交。
- 用户级共享 `~/.agents-group` 已独立建成,不在本仓库范围;本期不做 Skills/MCP 管理。

## 文档导航

| 文档 | 内容 |
|---|---|
| [DESIGN.md](DESIGN.md) | 设计方案 v1.1:三系统分工边界、核心决策、验收协议 |
| [docs/plan/architecture.md](docs/plan/architecture.md) | 实现架构:模块、registry/路径表 schema、CLI 合同 |
| [docs/plan/decisions-m2.md](docs/plan/decisions-m2.md) | M2 五项用户裁定与依据 |
| [docs/plan/tasks.md](docs/plan/tasks.md) | 16 项任务书(M1/M2 已全部执行完毕,含验收指向) |
| [docs/acceptance/](docs/acceptance/) | 全部验收证据:M1 dogfood 四环接力、M2 矩阵与两项目复制、平台矩阵、M3 上游接管 |
| [docs/history/](docs/history/) | 设计定稿过程记录 |
| docs/context-keeper/ | 本仓库自己的项目记忆(吃自己的狗粮,记录全部里程碑) |

## 开发

~~~bash
python3 -m unittest discover -s tests/unit          # 228 项
python3 -m unittest discover -s tests/integration   # 53 项
~~~

设计:[DESIGN.md](DESIGN.md);实现合同:[docs/plan/architecture.md](docs/plan/architecture.md);
验收证据:[docs/acceptance/](docs/acceptance/)(M1 dogfood、M2 工具化矩阵、平台矩阵、M3 上游回传)。
Git 提交与发布由用户亲自执行,本工具不主动 commit/push。
