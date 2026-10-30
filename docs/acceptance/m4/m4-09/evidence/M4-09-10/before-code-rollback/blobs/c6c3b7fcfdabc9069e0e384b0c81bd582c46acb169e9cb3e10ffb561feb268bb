# 用户规则整理向导：独立模块交接

基线 `0ed6d6e`。开工已有 M4-08/并行文档脏文件，全部保留；本轮只新增 `scripts/agm_core/user_rules_organize.py`、`tests/unit/test_m408_organize.py` 和本证据目录。无既有模块/测试改动，无 commit/push，无真实 HOME 操作，也未接线 install.py 或菜单。

最终稳定写集验证：HEAD `c322693`；**446 单元 + 72 集成 = 518，全绿，两个 discover 退出码均 0**。本轮整理新增 18 条回归已包含在内；`git diff --check` 退出 0。此前并行半编辑导致的失败日志保留为历史证据，已由本次集中审批最终全量覆盖。

本轮采用主 Agent 两项补充裁定：

1. R/memories 是用户内容区，V 完全不动，不登记为 machine/shared 装配对象，不扩路径表，不建 sidecar 账本；逐条归位证据由 transaction manifest 的逐文件 before/after/备份与内容内溯源共同承载。
2. 存量 kind=file/import 的 machine/shared 整文件记录覆盖入口正文时，仍只读分类；涉及编辑则 `ownership_conflict` 整单零写。结果 `blocked_entries` 单列 path/reason/record_types/conversion，不刷新旧指纹、不扩大删除权。用户可把该入口条目的决策全选 keep，再预览其他入口的整理。

最新用户裁定已生效：取消逐项审批，集中审批完整逐条计划。

## 接口与批准

- `plan_organize(request)` / `run_organize(request)` / `run(request)` 均返回 result dict，包含 status/approval_required/next_action/errors/changes/blocked_entries；完整只读草案在 `approval_plan`。无差异返回 completed，不取锁、不建备份。
- request 必需 `home`（显式传入，不默认真实 HOME）、`platform_config`（共享路径表的平台部分）；可选 `agents`（缺省三家扫描）、`topic`（默认 `user-rules.md`，仅简单文件名）、`date`（YYYY-MM-DD）、`decisions`。已有完整安装 V 与 memories 目录是前提；它们不由向导初始化。
- 每条包含稳定 item_id、agent、source、UTF-8 **字节** start/end、原文 text/sha256、分类建议与理由、公共源 comparison（原文/路径/区间/指纹）、suggested_action、action、replacement、target、removes_or_modifies_source。
- `decisions[item_id] = {"action":"keep|move|delete|modify", "replacement":"修改后的文本"}` 后重新预览；modify 必须有具体非空 replacement，其他动作禁止夹带 replacement。独有/归属不明一律 keep，禁止借动作覆写其保护。
- 公共默认提议 move；疑似冗余默认提议 delete，附公共原文对照；这些只是草案，绝无自动执行。可通过 decisions 明确保留冗余或提出修改。
- `execute_organize(plan, approval, request=..., hook=...)` 或 `run(dict(request, approval=...))` 执行。按最新用户裁定，批准为**完整计划** + 真实 confirmed_at/reference，**一次集中确认全部条目**；无 item_confirmations。计划逐条的来源字节区间、原文哈希、处置、目标仍须完整一致；少一项、改任一处置或哈希、未知字段、过期条目均拒绝。旧 item_confirmations 字段也拒绝。
- `next_action` 是上述封皮的 JSON 示例（确认时间/来源保留占位）；由调用方承载真实用户集中确认，示例本身不是授权。

## 扫描与分类边界

按路径表展开三家入口，UTF-8 解码但所有区间/原件均以 bytes 处理；段落和列表项切分，嵌套列表保守留在父项，围栏代码整体保留。跳过 AGM 受管块、V 中登记的 marker 单元、指向公共索引的引用行和 @AGENTS.md 行；重复/残缺/交叉受管 marker 先停。受管块与独有条目字节不变，空白/标题/换行不顺手格式化。

分类是**保守、可审阅的建议**，不调用模型、网络、执行器或工具命令。明确执行器词、工具命令、路径、代码或归属不明内容归独有/保留；通用语言、风格、流程词归公共建议；与公共 Markdown 条目经去列表标记/标点后的高词面相似度作为“疑似语义冗余”线索，附逐字原文对照供用户确认。它不宣称具备任意自然语言的可靠语义判断，也不据此自动删除。公共源与目标中符号链接不解引用，不扫描 references/ 的外部内容，异常编码或目标冲突先停。

## 执行与内容格式

执行先完整重扫比较，再持 `R/var/.agm.lock` 重扫，单个 `Transaction` 用其子锁及 R/backups；allowed_roots 为 HOME 与 R，实际 changes 是计划列出的精确入口/主题/索引文件。入口摘除/修改与公共主题/index 写入在同一个可回滚事务中，逐文件原子替换与读回；**不声称跨文件原子或消除非协作写者的最终窗口**。V/未改公共证据和目录枚举在写入前后继续核验，漂移先停；原子和恢复能力复用既有内核。

主题是普通 Markdown，开头 `## L1 概要` 简列当前有效结论与待办，随后 `## L2 原文与来源`。每个迁入原条目下追加：

```text
> 迁自 ~/.codex/AGENTS.md(2026-10-30, 原段 sha256 <16位前缀>)
```

L0 索引一行提供主题名、一句话当前结论和主题链接；新建索引时注明 L0恒读→需时L1→不足L2，超过200行/25KB拒绝，不自动压缩。既有索引或主题有不兼容文字/格式时停止，不覆盖或猜测。只用既有 .md 类型，不生成摘要 sidecar，也不自动蒸馏原文。再次整理靠来源条目已消失自然成为空计划，不依赖新账本。

成功结果包含 manifest；回滚/恢复失败保留内核 manifest 与 recovery_required；已有 `transaction.recover_manifest` 是明确的恢复 API，本轮不新增自动恢复或偷锁行为。HOME 自身祖先别名（macOS /var→/private/var）规范化为目标绝对路径；HOME 以下受管链路仍拒绝符号链接。

## 证据

- `targeted.log`：18 条新增单元回归。
- `unit-final.log` / `integration-final.log`：稳定写集下最终集中审批版全量原始输出，446 + 72，退出 0。
- `unit.log` / `integration.log`：此前并行 paths.py 半编辑导致的失败现场，保留不覆写；before-central-approval 日志是更早的通过记录，不充当最终证据。
- `commands.txt` / `diff-check-final.log`：执行命令、退出码和 diff 检查。
- `implementation.diff`：仅本轮两个新增源码/测试文件。

覆盖：三家混合分类零写、精确原文字节区间、整份集中批准（绑定全部条目）、冗余保留与具体修改、独有禁止删除/迁入、块/引用行保留、V字节不动、L0/L1/L2与溯源、重复整理零写、预览后 source/public/V/目录变化、写中外部新增保留、嵌套列表/代码、坏marker/编码/符号链接/越界目标、旧整文件记录阻断清单、事务失败恢复原文、HOME祖先别名。

未覆盖真实用户入口与自然语言分类质量的人工验收；不把词面相似建议当语义判定。本轮未接线菜单/安装入口，未提供自动整理或自动删除流程。
