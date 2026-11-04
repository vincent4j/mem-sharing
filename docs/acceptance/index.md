# 当前验收状态

基线：[固定源码 `4fb22c09`](https://github.com/vincent4j/mem-sharing/tree/4fb22c0988426c06183d9f4faa71b7b00747a546)，2026-11-04。需求以[模块 PRD](../prd/README.md)为准；此页只记录证据和缺口，不重述操作流程。

| 层次 | 当前结论 | 边界 |
| --- | --- | --- |
| 最新受影响合成回归 | 同一冻结快照 80 个唯一测试通过，112 个源码/测试/目标文档指纹前后一致 | 不是完整 unit/integration，也不累加此前 80、136 等重叠轮次 |
| 历史退出链 | 固定 `1b995587aeb1e55eed6f8a79e116c40541ff9103` 全部受管代码生成临时 C，真实旧 CLI 产融合/归还，再正式卸载及恢复通过 | 覆盖旧融合入口、Claude 引用退休、错引用/备份篡改/私文漂移零写拒绝；70KB 私文另测，重复 test ID 不另计 |
| 新安装链 | 临时 HOME 安装→CLI 融合/空标题及重复入口清理→重复安装零写→正式卸载→恢复通过 | 新链通过不能替代真实旧安装验收 |
| 六家 Skill 分发 | 文件适配与合成选择/补装/冲突/漂移/恢复有证据 | 各客户端原生发现、命令形式与模型读取分开验证；未证明六家真实会话全部通过 |
| 真实当前用户 | 本轮未操作真实 HOME、已安装核心、备份、账号或上游 CK | 历史安装、用户自行卸载与本轮修复不能拼作当前真机全链通过 |
| Paseo | [独立验收入口](../plugin-adapters/acceptance.md) | 插件加载、宿主卸载义务和产品内核分别判定 |
| 平台与发行 | 当前实证以 macOS 为主 | Windows/Linux、全新机器缺依赖首装、当前源码生成的新发行物及其运行验收保持待验 |

## 后续验收

1. 固定待验源码与完整来源，先核实际安装身份、私文和备份；新代码不得热改旧 C 或伪造 receipt。
2. 验证真实安装对话、融合选择即执行、查看零写、CK 最后且单独询问；实际名单与结果一致。
3. 对真实旧融合/归还现场验证正式整机卸载与恢复；未知或漂移先保全，不用手工清理冒充卸载通过。
4. 分别记录六家原生 Skill 发现与新会话实际读取，以及当前所需完整 unit/integration、发行与宿主结果。

## 固定历史证据

- [本次合成结果、原失败与源码指纹记录](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/retrospectives/2026-11-03-module-disposition-review.md#2026-11-04-历史融合退出续修)。记录中本机临时日志路径仅作当时辅助定位，长期结论以此固定提交为依据。
- [历史安装/手工清理/重装验收](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/skill-first-real-reinstall.md)、[六家入口分发与原生发现边界](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/six-native-skill-distribution.md)。两者是各自当时的结果，不表示本轮已部署。
- [其余阶段材料的固定目录](https://github.com/vincent4j/mem-sharing/tree/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance)、[复盘原件](https://github.com/vincent4j/mem-sharing/tree/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/retrospectives)。中间文档不再留在工作树；Git 保留完整原件与失败事实。

`docs/context-keeper/` 由 Context Keeper 独立管理，本次保留全部文件，不改其正文与元数据。旧日志指向已删过程文件的历史相对链接保留，可按固定提交和原路径追溯。真实外置材料不在此次文档整理范围。
