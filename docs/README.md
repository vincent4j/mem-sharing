# memSharing 产品文档

所有本轮有效需求、平台状态与项目记录直接放在本目录；旧分阶段目录已按用户要求退出，不自动重新初始化。普通生产入口仍以macOS实证为准；此DELL双端Windows首次预览另有完整限定验收，不泛化为六家/一般Windows通过。

## 产品需求

| 文档 | 范围 |
| --- | --- |
| [安装与原生入口](installation.md) | 六家探测、选装、补装、幂等、交互及CK尾步 |
| [公共用户记忆与融合](sharing.md) | 归属、分组/编号、选择即执行、精确去重、通用触发 |
| [项目规则接入](project-rules.md) | AGENTS/各家桥接、自动接入和项目经历边界 |
| [全机卸载、归还与恢复](uninstall-recovery.md) | 归还正文、来源次数、保全和事务恢复 |
| [Windows双端首次预览](windows-preview.md) | 已实证有限范围、精确14文件、显式新增/退出、未知拒绝 |
| [Windows完整适配目标](windows-support.md) | 一般平台/六家/升级迁移目标与R2剩余门；未完成 |

## 架构、操作与验收

- [架构](architecture.md)、[操作路由](operations.md)、[卸载设计](uninstall-design.md)说明现有组件和操作边界。
- [Windows当前验收与反例](windows-acceptance.md)是有限预览通过与完整路线partial的统一入口；[结构化证据](windows-evidence.json)保存23阶段索引及失败/unknown原内容。
- [既有验收总览](acceptance/index.md)、[Paseo维护入口](plugin-adapters/README.md)保留各自非Windows实证与未验边界。

## 项目状态与历史

- [当前状态/后续](project-state.md)、[有用历史结论](project-history.md)、[经验边界](project-lessons.md)。源码、合成、宿主、客户端新会话与发布分层报告；历史候选不当当前部署。
- 本仓按用户决定不再使用原CK/PRD目录自动布局；不要init/ensure-bridge重建。对其他项目的默认CK功能不变；全局Skill和上游CK不修改。

## 维护与约束

当前没有单独生效的合同文件；四份核心PRD与Windows范围/验收标准共同约束实现。开发先关键词检索本索引再读命中文档，不加载全部历史。UI/客户端完成结论需实际截图/新会话证据；结构检查不替代语义或真实运行。

用户记忆、项目规则、项目经历职责分开。源码提交/推送/main合并、正式发布和真实部署分别按授权执行；本轮仅前三项已授权，不发布。
