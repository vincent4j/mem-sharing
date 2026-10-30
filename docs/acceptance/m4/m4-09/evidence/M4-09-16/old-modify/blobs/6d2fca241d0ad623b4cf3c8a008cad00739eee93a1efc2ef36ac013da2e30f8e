# M1-02 规则基座装配 — 执行证据

- 执行者:突突兔;日期:2026-10-29;仓库 HEAD:a43e31c(main)
- 方案:见 [plan.md](plan.md);预检依据:docs/acceptance/m1-01/preflight.md

## 1. 门槛核对(进入执行前)

| 项 | 预检结论 | 本任务判定 |
|---|---|---|
| R/AGENTS.md、R/CLAUDE.md 基座 | "技术预检可放行,实际写入仍待授权" | 无阻断。两文件缺失、无 override、入口无冲突;写入授权来自主 Agent 派工消息(明确指令创建两文件并记录 diff),预检的"待授权"仅指预检会话自身不构成授权,非否定派工授权 |
| AGENTS.override.md | 根、祖先链、`~/.codex/` 均未见 | 本轮执行前后两次复查仓库根,确认不存在 |
| WorkBuddy 完整基座 | "暂不整体放行"(用户旧约定与顶部 bridge 冲突待裁定) | 与本任务边界一致:**未写 ~/.workbuddy/ 任何文件**,冲突记录见 §5,追加属 M1-04 |

## 2. 所有权清单

| 对象 | 操作前状态 | 操作 | 归属登记 |
|---|---|---|---|
| R/AGENTS.md | 不存在 | 新建(2026-10-29 18:42) | **created**(本工具创建) |
| R/CLAUDE.md | 不存在 | 新建(2026-10-29 18:42) | **created**(本工具创建) |
| ~/.workbuddy/MEMORY.md | 已有 | 只读核对,零写入 | untouched(reused,属用户) |
| docs/acceptance/m1-02/{plan,evidence}.md | 不存在 | 新建 | created(本任务产物) |
| docs/plan/m1-acceptance.md | 预检会话已修改 | 未触碰 | 他人产物(呱唧) |

## 3. 写入内容与指纹

两文件均为新建,无既有字节,不存在"块外字节"问题(未使用标记块,理由见 plan.md §3)。全文即 diff:

**AGENTS.md**(621 字节,16 行,SHA-256 `19cb9618d3143105afad563892d9dabbe0944c79cbeae0a9aa5a601faa035e12`):纯规则骨架——项目一句话说明(与 README.md 定位一致)+ 构建/测试占位 + 两条硬约定;**零记忆内容**。

**CLAUDE.md**(81 字节,3 行,SHA-256 `70afa4fc982436a3d7478874404a0455b8c2b6202a79ded7ad75a70c3e2d04a6`):首行裸 `@AGENTS.md` 引用 + 一行说明,无其他内容。

写后 `git status --porcelain --untracked-files=all` 新增仅 `?? AGENTS.md`、`?? CLAUDE.md`;未触碰任何已跟踪文件。未 commit、未 push。

## 4. 幂等复跑结果

复跑逻辑模拟 sync.py `put()` 的"内容相同不写"语义(cmp 全字节对拍,一致即跳过):

| 轮次 | AGENTS.md | CLAUDE.md |
|---|---|---|
| 复跑 1 | unchanged(no write) | unchanged(no write) |
| 复跑 2 | unchanged(no write) | unchanged(no write) |

mtime 前后均为 1793270531(两文件,两轮不变);哈希与首次写入一致。**重复执行无新 diff。**

## 5. WorkBuddy 约定只读核对(零写入)

- `~/.workbuddy/MEMORY.md`(SHA-256 `9cb55e36…`,3114 字节,与预检 §2 指纹一致,本轮未改动)现行约定在位:"项目规则、约定、事实的唯一来源是项目根目录的 AGENTS.md"。
- **漂移记录(留 M1-04 裁定,本轮不处理)**:该旧约定把"事实"也指向 AGENTS.md,与 DESIGN D1"记忆(事实)进 context-keeper 记录库"存在张力;且用户级文件未见共享 MEMORY.md 指针或 Keeper 条款(预检 §1 亦判定"WorkBuddy 三家完整基座暂不整体放行")。
- 本仓库 R/.workbuddy/ 及 R/.workbuddy/memory/MEMORY.md 均不存在,未创建(属 M1-03/04)。

## 6. 未验证范围与剩余风险

1. **静态装配 ≠ 运行时可达**:三执行器是否实际加载两入口,须 M1-06 新会话接力验收;本证据仅为文件级。
2. WorkBuddy 子目录盲区按 DESIGN §4.3 接受(本仓库现无子目录规则文件)。
3. ~/.workbuddy 约定冲突未裁定,M1-04 前不追加记忆条款。
4. M1-03 将由 Keeper 安装器在两文件追加 `<!-- context-keeper:start/end -->` bridge 块;届时块外字节以本轮哈希为基线。
5. 构建/测试占位待 M2 CLI 落地后回填。
