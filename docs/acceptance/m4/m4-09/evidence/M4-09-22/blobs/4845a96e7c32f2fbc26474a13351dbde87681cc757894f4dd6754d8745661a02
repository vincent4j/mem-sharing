# M1-05 事实源原始对照(不作验收判定)

worklog `docs/context-keeper/worklogs/2026-10-29-仓库创建与设计演进.md` 中每条事实的原始出处。本文件只转录原始材料,不作验收判定;判定由主 Agent 独立给出。采集命令与时间见 evidence.md。

## 1. git log(完整,2026-10-29 采集,`--date=iso`)

```text
0d402e8 2026-10-29 19:07:08 +0800 feat(m1): memory tier assembly - keeper store, executor bridges, workbuddy gateway + acceptance evidence
a422ec8 2026-10-29 18:52:30 +0800 feat(m1): rule base assembly + preflight - root AGENTS.md/CLAUDE.md, interface freeze report
a43e31c 2026-10-29 18:37:19 +0800 docs: kickoff preparation - architecture, 16-task breakdown, M1 acceptance plan, repo scaffolding
53314d7 2026-10-29 18:12:28 +0800 docs: v1.1 design per review - check read-only, centralized registry, record-store authorization, relay acceptance; scope excludes Skills/MCP
0262c4e 2026-10-29 17:45:12 +0800 docs: v1.0 design - restructure, directory layout, trigger chain, lessons from existing impl
f141ca3 2026-10-29 17:04:26 +0800 docs: rewrite subdirectory policy with concrete file-level steps
d3ec5b5 2026-10-29 16:57:15 +0800 docs: verbatim-only migration with user-level scope; rewrite nesting policy in plain terms
1b51dfb 2026-10-29 16:45:16 +0800 docs: add legacy content migration and nested rules file policy
2aac43e 2026-10-29 16:35:43 +0800 docs: add project AGENTS.md as single rules source with per-agent reachability
144117b 2026-10-29 16:29:40 +0800 docs: reposition as orchestration layer reusing context-keeper
60310dc 2026-10-29 16:05:18 +0800 docs(memory): add cross-agent session memory lifecycle to design
252d53c 2026-10-29 11:31:57 +0800 Initial commit
```

推送状态:`git branch -vv` → `* main 0d402e8 [origin/main]`;`git rev-parse origin/main` → `0d402e8bb1160611c16e61e67eb3900d8316eefa`(== HEAD)。remote:`https://github.com/vincent4j/agent-group-memory.git`。

## 2. 关键提交原文摘录(逐字)

### 252d53c(Initial commit)README.md 全文

```markdown
# agent-group-memory

多 agent 协作的共享记忆(Shared memory for agent groups)。
```

文件构成:`.gitignore` 13 行、`README.md` 3 行。

### 60310dc DESIGN.md 头部(v0.1)

> - 版本:v0.1(2026-10-29)
> - 状态:设计定稿,待 M1 试点验证

README 同版:"设计方案见 DESIGN.md:单一公共源 + 原生入口指针 + 蒸馏管道(自蒸馏 → 批量收割 → 定期压缩),全部提交进 Git。""用户级互通已由 ~/.agents-group 解决,本仓库只负责项目级与蒸馏能力。"

### 144117b DESIGN.md 头部(v0.2)

> - 版本:v0.2(2026-10-29,重构:项目记忆改为复用 context-keeper)
> - 历史版本 v0.1 曾设计自建项目记忆结构(journal/索引/蒸馏管道),已废弃——该能力由 context-keeper 承担

README 同版:"**不自建项目记忆**——项目记忆直接复用 context-keeper:本仓库负责自动安装、入口配置与未验收执行器(WorkBuddy)的桥接。"

### 53314d7 DESIGN.md 头部与附录(v1.1)

> - 版本:v1.1(2026-10-29,按评审修订)
> - 历史沿革:v0.1 自建项目记忆已废弃(能力归 context-keeper);v0.2 起定位编排层;v1.1 按评审修订:check 收敛为只读、状态文件更名、记录库授权四态、验收改为三执行器接力闭环、M1 范围收敛、跨平台收紧
> - **本期范围不含 Skills/MCP 管理**(用户决定,留待后续;项目级 Skills/MCP 继续由旧 project_manage.py 负责)

附录(调研依据段末句):

> 巴克队长对 v1.0 的评审结论(10 项,已全部吸收:v1.1)。

### a43e31c docs/history/2026-10-29-design-baseline.md 全文主句

> 2026-10-29,本次准备以 DESIGN.md v1.1、提交 53314d77d08070973d935509123247c4230c3541 为唯一设计依据。

### 0d402e8 与入口文件

`git show 0d402e8 --stat -- AGENTS.md CLAUDE.md` 为空(两文件在本提交未变);`git show a422ec8:AGENTS.md | grep -c "context-keeper:start"` = 1。当前 AGENTS.md/CLAUDE.md SHA-256 为 1daf0ff0…/86416f63…,与 round3 handoff 的操作后指纹一致。`.workbuddy/memory/MEMORY.md` 13 行随 0d402e8 新增。

## 3. M1-01~04 事实的仓内证据出处

- M1-01:docs/acceptance/m1-01/preflight.md(run_id `m1-01-20261029T103841Z`,Keeper 源 HEAD `a8e584159b3853b11f96b0ec89036d04ce29dce2`、三文件哈希、install/probe 实际接口、Python 3.14.3/3.9 边界、init 退出码语义)。
- M1-02:commit a422ec8;docs/acceptance/m1-02/(evidence.md、plan.md)。
- M1-03 三轮:docs/acceptance/m1-03/evidence.md(第一轮失败点 backup_file 比较缺陷与停止顺序偏差、第二轮 marker 字符串误判与自动恢复同错、库保留、第三轮协议);20261029T105740Z-retry/(m1-03-passed.json 等);20261029T110112Z-round3/handoff.md(00–12 步 rc=0、无判定脚本、未调用 store 探针)。
- M1-04:docs/acceptance/m1-04/(evidence.md、round3 09–11 步回执;项目 MEMORY.md 13 行、用户级 3114→3661 字节 ab 追加)。

## 4. 两条派工转述事实(非 git 可核验)

- 改名往返、最终定名 agent-group-memory:来源为 M1-05 派工消息转述;git 公开历史初始提交即此名,仓内无改名 diff,无法在仓库内独立核验,worklog 中已按此标注。
- v0.2 转向系用户决定:同上派工消息转述;DESIGN v0.2 原文仅写重构事实,未写决策主体,worklog 中已按此标注。
