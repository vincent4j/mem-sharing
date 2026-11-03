# Skill 优先两家共享链验收

状态：两家源码与临时 HOME 合成链通过；完整产品未验收。日期：2026-11-03。

## 范围与分工

分支 `refactor/skill-first-memory-sharing`，基线 `50001cf259be8ea6a7c29201dfa0e5a82d67758b`，改动未提交。突突兔（GLM）完成主体；ZCode 1302 限流后，按实际 Profile 顺序由呱唧（GPT）串行递补修复。巴克队长核查冻结哈希、关键归还逻辑与文档入口，未重复执行同批测试。

## 已有证据

执行者报告的实际命令与结果：

| 命令 | 不同用例 | 退出码 |
| --- | --- | --- |
| `python3 -B -m unittest tests.unit.test_memory_share tests.integration.test_m202_transactions` | 37（共享16、事务21） | 0 |
| `python3 -B -m unittest tests.unit.test_fusion_phases tests.unit.test_fusion_recovery` | 11 | 0 |

随后只加强两个既有断言，单独运行 `test_hook_failure_rolls_back_everything` 和 `test_share_manifest_persists_metadata_before_writes`，2项通过。合计48个不同用例、50次执行，不将重跑算新用例。

覆盖普通CLI预览/批准共享/预览/批准归还（退出码5/0/5/0）；第二次共享；同文件重复标题、不同上下文、原有重复次数、格式变体和独有/CK保全；公共改写/新增与原生漂移后的明确归还；无关Claude引用保留与错误目标检查；部分归还保留另一来源依赖，最后归还再删公共；未处理新增正文禁止移除读取入口。hook在实际删源阶段失败后精确回滚；独立测试子进程os._exit(70)后按原manifest恢复，陈旧锁先拒绝，由测试模拟操作员核查清理后回滚。无真实原生Agent运行证据。

主负责人实测13:41:44 UTC后核对六文件SHA256全部与冻结报告一致，关键归还代码及测试断言抽查、`git diff --check`通过；未重跑上述测试。实现与验收证据层分开。

## 具体修复

原失败：公共空白/变体顺序期望不清、测试死代码触发StopIteration、批准CLI混用参数导致在crash注入前退出。已明确逐原文保留并补一个分隔空行、修正测试来源、分别运行普通CLI和独立crash fixture。

另修复默认选择错误全选、归还公共写集遗漏/重复删除、原位偏移与同位插入顺序、keep_public误消费、未闭合事务、任意@引用误删/错误入口假连接、部分归还丢公共依赖。原生入口先全部建立并核验，再删来源，仍使用既有Transaction分阶段写入和恢复；来源关系在首次manifest持久时保存，旧manifest不改删，无独立share-records目录。

## 审核与计时

此前首段审核结论为方向可继续但样例不足：补同文件重复作用域与次数、完整多来源关系、未迁移内容不归还、当前正文/新增明确目标；不是无条件通过。原GLM按修正实现但留失败，用户再明确授权续行，GPT因限流递补修复。

本次用户授权续行窗口13:29:25–13:40:09 UTC，共10分44秒（含限流及交接），呱唧实际接管13:31:43后8分26秒。它不是全部重做累计耗时，也不替代旧验收17:17:31历史。此前第二段结束时间与工具时钟矛盾的纠正保留在[工作日志](../context-keeper/worklogs/2026-11-03-新空间Skill简化重做.md)，不伪造闭合数字。本次未触发到时审核。

## 冻结文件

| 文件 | SHA256 |
| --- | --- |
| `SKILL.md` | `020e3e149156790a2275a98bb83a339d9097ee1d1daa580fd3ecc6d534c994f3` |
| `scripts/agm_core/memory_share.py` | `9c43e3f6a15fcd8cd880905602e0b69927e05303c15665812d1bcf10759414b3` |
| `scripts/agm_core/transaction.py` | `ebf9f1e37c2ded57740bcb354997e098a343f59aa27d279a7f404e3dcb5eacfa` |
| `scripts/memory_share.py` | `1983fdf4f88de47570ec0eb728482768ac246d12bd339268c004024fdb4f473c` |
| `tests/unit/test_memory_share.py` | `dc26729996641cf7ad95cd8a0a8dfb12fead791eeb5148d9043c5ac0898df227` |
| `tests/unit/memory_share_crash_fixture.py` | `52ae349b3285e53faa6d66d055b4366cc4f4ccc0b357812fd4348f87c2265783` |

## 未完成范围

真实Skill对话及原生新会话加载、其余四家新主线、项目新主线、旧安装向新主线的真实兼容、整体产品验收均待做。旧兼容代码保留，未生成发行物；未提交推送、未安装、未改真实HOME。批准模块去向方案没有被本次两家成功等同为全部完成。
