# WorkBuddy 接入缺口诊断与修复建议

> 历史阶段材料，保留原始观察及计划；其中状态仅指当时。当前有效判定统一见 [verdict.md](verdict.md)。

2026-10-31；只读现场与代码诊断，测试仅使用合成临时 HOME。未修改产品代码、用户规则或真实台账。源码基线仍为 51ecf55；此前验收文档改动保留。

## 确认的问题

### 1. 既有私人正文分支没有接入公共规则

`user_entries._plan` 对 WorkBuddy 传 `append_to_unblocked=False`；`_Planner.marker_block` 遇到已有无受管块文件就直接返回，既不追加约定也不登记对象。测试 `test_workbuddy_existing_entry_without_block_is_preserved` 明确锁定此旧语义。这是现有实现选择，不是本轮偶发写入失败。

真实现场只提取结构：WorkBuddy 用户文件存在，无公共目录指针、无 mem-sharing:rules 块；机器安装事实 installed，static=unknown，runtime_acceptance=pending；关联机器对象 0 个。未输出私人正文。安装态 installed 只证明应用存在。

### 2. 空文件首装模板本身也缺公共读取指针

`WORKBUDDY_CONVENTION_TEXT` 只有“项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。” `_plan` 拼接治理/兜底/菜单，但没有 Codex 分支的 `planner.memory_index` 读取语句。治理条款里的 R/memories 不等于让执行器读取具体索引。

因此仅改“已有文件也追加”仍不够：新追加的内容也必须明确要求读取运行态公共索引。

### 3. 完成报告与 Keeper 前置条件不一致

`scripts/install.py::_report` 在 completed 时直接用 `plan['effective_agents']` 填 agents.connected；effective_agents 来自应用探测 installed，而非入口装配核验。与此同时 `ck_install._scene` 要求每个 installed 执行器至少有登记对象，否则 ck_main_incomplete。

所以当前组合可出现“主安装完成/报告已接入”但实际无入口对象，随后 Keeper 尾步拒绝。Keeper 拒绝反映了入口缺失；不建议只删除此检查来掩盖问题。

真实已安装 C 中 user_entries.py、ck_install.py 与源码同名字节一致，排除这两个文件的源码/安装版本漂移。

## 合成复现与验证

复用现有 UserEntryFixture，不改测试代码，不接触真实 HOME：

| 场景 | 执行结果 | 有公共索引路径 | WB 机器对象数 | 私人原文 |
|---|---|---|---|---|
| 用户入口缺失 | completed | 否 | 1 | 不适用 |
| 已有合成私人正文、无受管块 | completed | 否 | 0 | 原字节保留 |

相关现有三个单元测试通过：existing_entry_without_block_is_preserved、machine_convention_carries_governance_and_menu、convention_uses_enable_template_text（UserEntryFixture）。它们验证旧约定，不证明公共共享工作正常；未跑全量测试，因为本轮没有改实现。

## 项目标记的边界

合成项目原生 `.workbuddy/memory` 目录及其 MEMORY.md 均不存在；产品契约不允许本执行器预建来冒充 WorkBuddy 实际使用。手动任务的可见答案自述读 AGENTS，排序和张数正确，但没有 PROJECT/PUBLIC 字面值；独立工具日志不可见，再次 UI 复核受窗口错误阻断。

公共入口缺失已有代码/现场/夹具证据。项目标记遗漏可能涉及规则遵循或可见输出提取，尚无证据确定根因，不能统一说成“WorkBuddy 不读项目规则”。本轮不重复要求用户做同样测试。

## 建议修复范围（尚未实施）

1. 统一 WorkBuddy 用户级入口合同：在其受管约定中加入实际公共索引绝对路径的读取要求，保留项目 AGENTS 约定；已有私人正文完整保留，在精确批准计划中追加最小受管块，不将私人内容并入公共，不取得私人正文所有权。
2. 已登记旧约定块需显式计划更新：绑定旧块指纹、新块字节与批准；受管内容漂移仍停止。不能仅改变模板而放任旧块被原样采用，也不能无批准覆盖既有块。现有“无块文件整文件不动”合同、测试与文档须同步改为“私人字节不动，批准后追加入口”。
3. 修正报告：探测 installed 与入口静态接入分开。只有满足本执行器入口语义与对象登记的目标才能列入 connected；无法接入如实报告 pending/partial。对象存在本身仍不能代表实际运行通过。
4. 保留 Keeper 的完成主操作/登记对象/指纹校验，在正确入口装配后覆盖“既有私人正文 + WB 接入 + Keeper 尾步”的组合回归；不要用跳过安全检查作为修复。
5. 本地通过后另行给出真机精确计划：仅 WorkBuddy 受管入口、必要台账与受管代码，备份私人正文并验证字节保留；不改上游 Keeper。获准部署后再做一个无答案泄漏的新会话，分别验公共实读与项目标记。CK 首次激活和跨执行器接力仍独立判定。

验收至少覆盖：缺失文件、已有私人正文、既有正确块/旧块/漂移块、重复执行、撤销只移除受管内容、installed 但未接入报告、Keeper 组合成功及缺失/漂移继续阻断。实现后运行单元与集成全量回归，随后才讨论真机修复。

以上是建议变更，不视为用户已批准修改旧合同、用户文件或部署。本轮的“同意”用于继续定位。
