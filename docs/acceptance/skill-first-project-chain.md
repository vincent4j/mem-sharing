# Skill 优先项目记忆共享链验收

状态：项目主线源码与合成 Git 主 checkout 链通过；真实项目与原生新会话未验。日期：2026-11-03。分支 `refactor/skill-first-remaining`，基于四家切片之上，未提交。

## 审核与计时

首段起点 13:58:22 UTC、首满 14:13:22 UTC 后触发到时审核；巴克队长结论**修改后通过**（原执行者继续）：AGENTS 同文组默认保留整理不进待选、入口建立核验先于删源、disabled fail closed、排除需逐项去向、项目外零写、恢复材料位置明确。第二段实际恢复 14:17:18 UTC，初版交付后主验收未通过，14:31:28 停止，五项全部未修；用户明确续行后，14:40:39–14:55:39 首段修复，14:58:40 恢复第二段，15:10:50 最后修复，15:12 主复验关闭已知阻断。审核耗时（14:13:22–14:17:18 及之前审核往来）单列，不计入执行段。

## 范围

仅当前 Git 主 checkout（`project.py` 边界，拒绝 linked worktree）。独立文件去重计票：根 `AGENTS.md` 一个来源，`CLAUDE.md`、`.workbuddy/memory/MEMORY.md` 各一票；codex/dsh/zcode/opencode 项目规则均读根 AGENTS，不另计票。复用新核心原语与既有 Transaction；不依赖 installed registry/S/R；用户记忆与 HOME 正文不在写集（HOME 仅只读最小旧登记检查）。事务材料全部在 `<项目>/.mem-sharing/backups/`，最终计划与验收文档均明示该恢复位置。

要点：AGENTS 既有内容恒默认保留，同文重复默认整理、不进待选（`in_agents` 组不写 AGENTS）；排除既有项必须逐项绑定本项目已确认原生文件去向与插入位置，未给即拒绝；Claude 项目入口 `@AGENTS.md` 行、WorkBuddy 项目桥块（`mem-sharing:project-rules` 受管块，字节同 enable 冻结合同）在独立入口阶段全部建立并逐一核验，再精确删除来源；公共、入口、删源复用同一 phased Transaction；disabled/损坏/未知登记 fail closed（`project_disabled`/`disabled_unknown`）；归还与用户主线一致（consumed refs、keep_public、additions move；`remove_entries` 要求全部处置且 AGENTS 逐字节回到共享前原文，容至多一个工具分隔换行）。

## 已有证据

实际命令与结果（2026-11-03；历史初版与最终修复分列）：

| 命令 | 用例 | 退出码 |
| --- | --- | --- |
| `python3 -B -m unittest tests.unit.test_project_share` | 20（最终项目套件：层级换位负向、同级兄弟重置正例、父级不同负向、同栈同文重复拒绝、围栏假标题不污染、4 反引号围栏长度/缩进代码标题、显式 null 登记与悬空 registry symlink 拒绝、带语言开栏（```python/~~~ts）识别与关闭尾空白（该回归由主复验发现，失败先验后修复）；各轮均先在旧实现上确认新用例失败后修复全绿；嵌套 3 反引号病态源由冻结分段器整体拒绝，栈语义由函数级用例覆盖） | OK |
| `python3 -B -m unittest tests.unit.test_project_share tests.unit.test_memory_share tests.unit.test_memory_share_four_agents` | 28（修复前初版，其中项目用例断言含第2项错误合同，已被最终20项取代） | OK（历史） |
| `python3 -B -m unittest tests.unit.test_fusion_phases tests.unit.test_fusion_recovery tests.integration.test_m202_transactions` | 32（transaction 白名单改动后回归） | OK |
| `python3 -B -m unittest tests.unit.test_memory_share tests.unit.test_memory_share_four_agents tests.unit.test_fusion_phases tests.unit.test_fusion_recovery tests.integration.test_m202_transactions` | 54（白名单改动后合并回归） | OK |

新用例覆盖：合成临时 Git 主 checkout 上 CLI 预览/批准（5/0）；AGENTS 同文组默认整理、三份独立文件中仅后两份同文为待选、单家独有留原处；AGENTS 原字节保全（dedup 不写 AGENTS，新组完整原文追加一次、四处来源逐处记录）；`@AGENTS.md` 与项目桥块建立且删源后保留必要入口；CLI 全量归还（AGENTS 与两桥文件逐字节回到原文+一个分隔换行，入口剥离）；排除既有项无去向拒绝、绑定 CLAUDE.md 插入位置后进入清单；disabled/follow_ck/损坏登记三分支 fail closed 与放行；linked worktree 拒绝；hook 在删源写入失败后全量回滚且 manifest 留在项目内。

## 冻结与改动文件

| 文件 | 状态 | SHA256 |
| --- | --- | --- |
| `scripts/agm_core/project_share.py` | 本切片新增 | `62d6042d417ed28be53fd1d2679facfad45c06dd555a91b24e42163231ad652c`（语言围栏开栏回归修复终版） |
| `scripts/memory_share.py` | 薄 CLI 加项目命令路由（原用户链冻结 hash `1983fdf4…` 因此变更） | `d4d8f2b71a645fdcf4429e4117e65d9e4346655c20219054f7aba4a67faf5943` |
| `tests/unit/test_project_share.py` | 本切片新增 | `ebcd056dc436c43ab42b724df6b8d64e52077f2744ae235840ceaf92f6094026`（有效标题栈+语言围栏/登记边界终版，20 用例） |
| `SKILL.md` | 项目段更新（含四家切片既有改动） | `c9cee1c56fb3631e1af34cc42544f89650ff229c1bf50ed58254409b52b2f952` |
| `scripts/agm_core/memory_share.py`、`tests/unit/test_memory_share.py`、`tests/unit/test_memory_share_four_agents.py` | 复验修复段未改动 | 沿四家切片冻结值 |
| `scripts/agm_core/transaction.py` | 已授权最小白名单改动 | `d81073314874b218a2816723b83378fdb236fae4da033881250b439c63420410` |

复验退回与修复（2026-11-03 14:40:39–14:55:39 UTC 续行段）：初版五项合同阻断（入口与删源同写、覆盖分母漏计 AGENTS、in_agents 仅归一化匹配且变体被删、纯去重 StopIteration、未登记项目误拒）经巴克队长复现与本人核对成立；修复为 phased 真分阶段（公共→全部入口逐一核验→删源，含第一处删源前入口就绪与原文前缀完整的时序断言）、参与分母计入 AGENTS（仅部分独立文件同文进待选）、in_agents 要求逐字节相同且有效标题栈（project_share._heading_stack：遇级别 L 弹出≥L 再压入，忽略受保护行与围栏内行）完全一致且 AGENTS 侧恰一处匹配（多处/父级不同/末级同名/层级换位均拒绝自动复用）；memory_share._scope_titles 与用户链行为零改动（变体各份完整进公共并保留来源关系）、AGENTS 无变更的纯去重可执行、登记状态三分支区分。`transaction.py` 经已授权最小改动把 `share-project-memory` 加入 `phased_writes` 白名单（原冻结 hash `ebf9f1e3…` 因此变更）。

## 未完成范围

真实项目运行、六家原生新会话读取、DSH 自定义配置、Windows/Linux、旧安装真实兼容、项目专属硬崩溃恢复、插件外围对齐均待做。本切片未提交推送、未装/卸载、未改真实 HOME 或真实项目；`docs/context-keeper/` 由主 Agent 维护，本切片未触碰。
