# M4 改名包验收判定(集成者)

日期:2026-10-30 | 判定:**通过**

- 执行者证据:handoff.md + unit.log/integration.log(446 单元 + 72 集成,均 OK,exit 0);
- 集成者独立复跑:integrator-unit.log / integrator-integration.log(446 OK 262s / 72 OK 434s,均 exit 0);
- 抽查吻合:layout.py 新根 `~/.mem-sharing` 与 legacy_root 只读源、enable.py `mem-sharing:*` 标记串、双 URL(OFFICIAL=mem-sharing + LEGACY_OFFICIAL)、`plan_import(source_root, target_root, op)` 双根签名、白名单 after 侧哈希登记(§26 到达时随删除轮整块移除);
- 语义点已知悉:P 台账白名单内存规范化装载(随 §26 删除轮消失)、旧标记块在 T 下按漂移拒绝(符合冻结语义);
- 待办移交:§26 pre-release 机制删除轮(P 四哈希白名单/读侧扩路径/旧投影注销)并入 CK 重构实施轮(upgrade.py 写集重叠)。

结论:改名包达到提交门禁,与文档包分两笔提交。
