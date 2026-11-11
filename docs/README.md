# memSharing 文档

只维护现行产品需求、实现边界和操作说明，不存放历史日志、阶段报告、证据流水或过期计划。

## 产品需求

| 文档 | 内容 |
| --- | --- |
| [安装与原生入口](product/installation.md) | 检测、选装/补装、幂等、安装交互和可选Context Keeper |
| [公共记忆与融合](product/sharing.md) | 归属、原文提案、选择即执行、共享与去重 |
| [项目规则](product/project-rules.md) | 自动接入、原生入口、保护和项目经历边界 |
| [卸载、归还与恢复](product/uninstall-recovery.md) | 全机范围、正文归还、所有权与独立恢复 |

## 架构与操作

- [系统架构](architecture.md)：组件、来源、数据与事务、验收和恢复边界。
- [操作路由](operations.md)：常用命令、批准、故障和兼容入口。
- [卸载技术合同](uninstall-design.md)：精确归还、producer链、宿主义务和恢复条件。
- [Paseo维护](integrations/paseo.md)：薄宿主适配、固定来源、依赖供应、批准、取消及发行。

前三份路径是发行文档闭包的一部分，保持兼容位置；其他文档按产品、平台和集成分类。

## 平台与已验证范围

| 范围 | 当前边界 |
| --- | --- |
| macOS普通产品入口 | 已有真实安装/共享/退出实证；源码、文件适配、各原生客户端会话与发布仍分别验收，不承诺所有客户端/版本都同等通过 |
| [Windows双端首次预览](platforms/windows-preview.md) | 固定DELL Win11 x64本地NTFS、ZCode3.17.2.9661/WorkBuddy5.9.3.0的首次安装、双向新增/新会话读取、退出保全已验证；非一般Windows生产入口 |
| [Windows完整适配目标](platforms/windows-support.md) | 已补 Codex、Claude Code、DeepSeek Harness、OpenCode 的官方 Windows 目录及 Mac 对照；各家运行验收、升级迁移与恢复分别记录，普通生产平台保护不变 |
| [Windows Paseo 双端预览](integrations/paseo.md#windows-预览接线与候选准备) | 固定 DELL 已验安装、状态/新增与双客户端新会话读取，ZCode 新增→WorkBuddy 读取已验；反向写入跳过，实际退出/重装待验，未发布 |
| [Windows 可选 Context Keeper](integrations/paseo.md#windows-可选-context-keeper) | 固定 DELL 已验安装、技能加载和 WorkBuddy 原生客户端保存→独立新会话续接；收尾修复已审核并部署，Paseo WorkBuddy 运行入口仍需登录，其余边界见安装说明 |
| Linux/WSL与其他架构 | 未准入，不从其他平台或文件测试推定支持 |

## 维护规则

开发先检索本索引并只读命中文档。当前无独立生效合同文件；以模块PRD与明确支持边界为准。界面/模型读取结论要有对应客户端证据，状态字段或测试通过不替代真实运行。

本仓不自动初始化PRD/Context Keeper旧目录或记录库；技能可用于语义整理，但不要init/ensure-bridge重建过程文档。其他项目的产品默认 Context Keeper 行为不变。正式发行、真实安装部署与Git提交合并分别按授权执行。
