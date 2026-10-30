# R2/R3 修复 主 Agent 验收判定

日期:2026-10-30。判定人:主 Agent(独立复核)。

## 结论:通过

- R2:分型后受控重建(项目数据损坏/证据不可达可重建;未知 schema/不可解析/机器与迁移信息损坏即停);`rebuild` 批准字段含旧账 SHA256、字节数、将移除的项目与共享登记清单及影响范围,须另提供 `rebuild_confirmation={registry_sha256, confirmed_at, reference}`;缺独立批准→approval_required 零写入;预览后账本变化使两重批准均失效。
- R3:写前窗口(hook 后、紧邻替换前)二次核对;外部编辑不再被静默覆盖——主 Agent 以 review E3 最小复现独立验证:同场景现在抛 `recovery_required`(message 指明"output changed immediately before mutation"),文件最终字节保留 external edit;正向/回滚/显式恢复路径同步收紧;协作锁边界如实声明(不声称消灭非协作写者竞态)。
- 回归:新增 8 项定向全绿;全量 343 单测 + 57 集成通过;M4-03 迁移合同与 tombstone 保护未破坏。
- 范围:R1(yes→no 残留指令)不在本次,已并入 M4-06。
