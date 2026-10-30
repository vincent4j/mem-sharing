# 批量启用 CLI 交接

基线：`ca0c7417c8c72198f8de43c2e5f3edac1251b032`，开工工作区干净。任务与主 Agent 补充裁定均已批准；本交付未 commit、未 push。

## 命令与批准

```sh
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/approval.json
# 与单项目相同的显式接入语义：
python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects --agent claude
```

首条只读预览，待批准时退出码 5，stdout 为既有 JSON envelope。`projects` 每项目一行，含 `path/state/action/notes/enable_plan`；`changes[].applied=false` 表示计划，不能当作已写入。`next_action` 是可供外层收集确认的完整批量批准模板；外层填入真实 UTC `confirmed_at` 和确认出处 `reference`，一次批准后传回。TTY 模式一次确认整批，不逐项目提问；拒绝或 EOF 不执行。

批量批准封皮 schema=1、command=`enable-memory-batch`，绑定规范化目录、`agents` 选择（缺省为 null）、完整扫描清单、原台账 SHA-256，以及每个新项目的完整 enable 精确计划。子计划复用既有 enable 批准结构校验；不接受批量全局重建或 disabled→follow_ck 计划。重复 JSON 键、未知字段、非法时间、重复路径、越界项目、子计划策略篡改均拒绝。

执行前取得现有机器写锁，整批重新扫描和预览；目录清单、政策、安装事实或文件指纹变化均使批准失效。读预览不建锁、不建备份、不写台账、不建项目文件。已有机器锁、坏台账、缺少机器安装或任一新项目预览受阻，整批停止。

## 语义与实现

- `scripts/agm.py`：参数解析、命令路由、统一 JSON 输出及批量封皮校验入口。
- `scripts/agm_core/batch_enable.py`：目录扫描、集中计划、集中确认、锁内复核、顺序执行。使用 enable 既有 `run` 生成预览，持机器锁后复用 `_run_locked`，避免重入同一机器锁；未更改 enable 内核。
- 递归扫描包含目录自身；不进入任何 `.git/` 元数据目录、不跟随目录符号链接。每个带 `.git` 的候选交由既有 `resolve_project` 判定：linked worktree 排除；嵌套独立仓库、分离 Git 元数据目录及子模块形态 Git 文件按同一主 checkout 规则判定。无 `.git` 的普通目录无项目写入。
- 已登记 follow_ck 项目报告 `enabled/noop`，即使入口缺失也不调用 enable 修复。已登记 disabled 项目（remove 与 `--no-memory` 均覆盖）报告 `disabled`，明确“需显式单独重新启用”；批量不会翻转政策。
- 默认透传 `agents=None`：依安装事实启用 AGENTS 骨架与短桥接，已有 AGENTS 全文保留，只补受管块；不预建 CLAUDE.md；已有 CLAUDE.md 也保持原样，预览给出信息性说明。依据决策 §16 实际使用驱动与 B04 修复，主 Agent 本轮已确认此口径取代任务书旧措辞。
- `--agent` 按单项目现行语义透传；显式 claude 可创建或补写引用。WorkBuddy 原生目录缺失则记录 pending，待实际使用后兜底；已有原生目录则按内核补顶部桥接，保留原文字节。不调用 CK 安装器、不初始化记录库。
- 每个项目仍使用 enable 原有事务、指纹与恢复机制。批次不提供跨项目整体回滚：某项目失败后保留已完成项目、停止后续项目；结果行 `result` 为 `completed/failed/not_started/skipped` 等实际状态，顶层 `changes` 仅收集已完成内核返回的实际变更。重新预览后，已完成项目自动跳过。外部不协作写者的竞态限制与既有事务一致。

## 证据

- [preview.json](preview.json)：混合夹具逐行预览，六个 Git 主 checkout，普通非 Git 子目录不入项目清单。
- [approval-synthetic.json](approval-synthetic.json)：一次集中批准的合成测试记录。仅供验收，不可用于真实项目；临时路径已清理。
- [executed.json](executed.json)：三个新项目完成，已启用一个、disabled 两个均跳过。
- [repeated.json](repeated.json)：重复执行无变更。
- [fixture-checks.json](fixture-checks.json)：预览零写、原文字节保留、CLAUDE 默认不触碰、disabled 保留、不创建 WB 原生目录或 CK 库等断言。

定向测试：21 单元 + 5 CLI 子进程通过，分别用时 25.181 秒、5.924 秒。

最终全量回归：**462 单元 + 74 集成 = 536 个全部通过**，相对委派基线 441/69 新增 21/5；[unit.log](unit.log) 记录单元 462/462（进程墙钟 173.60 秒），[integration.log](integration.log) 记录集成 74/74（进程墙钟 187.11 秒）。命令为 `python3 -B -m unittest discover -s tests/unit` 与 `python3 -B -m unittest discover -s tests/integration`。两套并行执行，不把耗时相加当作总墙钟。

一次新增子模块形态夹具因未创建 `.git/modules` 父目录而构造失败，已修正并通过定向重跑；首轮全量单元已读取修正前夹具，且与该修正发生交叠，保留 [unit-initial.log](unit-initial.log) 作为错误记录，不用作最终放行依据。上述 unit.log 来自修正后稳定代码树的完整重跑，不涉及产品实现缺陷。

额外检查：Python AST、验收 JSON 解析、交接相对链接以及 `git diff --check` 均通过。可核验墙钟计时段为 UTC 2026-10-30 15:53:21—16:04:49，共 11 分 28 秒；前段合同细化／实现／首轮定向验证至 15:58:55，5 分 34 秒；其后补充边界夹具、全量回归／稳定树重跑及证据整理，5 分 54 秒。更早的首次规则读取未单独计时，不包含在该计时段中。

只证明合成 HOME/项目下的 CLI 与文件事务行为；未在真实 HOME、真实项目或 Codex/Claude/WorkBuddy 新会话中验收运行时加载。未改 README、INSTALL、SKILL、llms.txt、DESIGN、decisions、上游 CK 或旧管理器。
