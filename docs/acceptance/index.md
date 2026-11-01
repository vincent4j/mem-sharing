# 验收总览

更新：2026-11-01。源码、合成测试、真实安装、原生新会话与正式发布分别判定。**M4整体和全新机器Paseo首装仍未全部关闭**，不宣传五家完整互通或全部平台通过。

| 范围 | 已证结论 | 未完成边界 |
| --- | --- | --- |
| M1 | 静态装配与Codex/Claude部分读回 | 标准闭环有流程偏差/答案污染，WorkBuddy负向未验 |
| M2 | macOS安装/卸载/恢复、两项目装配与Codex/Claude读回 | WorkBuddy两项目新会话、Claude显式Skill/resume、Windows/Linux未验 |
| M3 | 旧管理器现场处置沿用历史记录 | 不扩成M4接力证据 |
| M4实现 | schema3、R/C/V、精确批准/漂移/恢复、公共布局、五家入口实现与合成回归 | 实现不等于所有客户端实际加载 |
| M4-09 | 62案矩阵：43 executed通过、15合理blocked、4 not_in_scope | 另发现的菜单缺陷后续已修；不是62案全运行通过 |
| 旧WorkBuddy/M4人工验收 | 0.1.1修复部署与静态读回；Codex/Claude有限规则读取 | 用户暂停，见[续审位置与门槛](m4/m4-10-runtime/verdict.md)；不得自动重启 |
| 桌面适配与0.1.3 | Claude原生签名检测、公共布局升级、DSH/ZCode用户接入及幂等/私人字节保全 | 桌面新会话与Skill加载仍pending，见[入口合同](desktop-agent-contracts.md) |
| Paseo与0.1.4 | 供应/加载实现、开发runtime、本地原安装器升级、插件项目接入、新Codex记忆读取 | 具体分层证据和未验项见[Paseo验收](../plugin-adapters/acceptance.md) |

## 维护入口

- [发布与运行验收清单](m4/m4-10-prep/release-checklist.md)：固定身份、保全、逐层验证与暂停边界。
- [Paseo维护手册](../plugin-adapters/README.md)：单仓来源、批准、依赖、取消恢复和CK职责。
- [产品设计](../../DESIGN.md)、[系统架构](../architecture.md)、[操作手册](../operations.md)：现行行为合同，不在验收文件重抄实现方案。

## 历史定位

M1/M2/M4-09原始材料在 Git `f06db31`：`docs/acceptance/m1-07/evidence.md`、`docs/acceptance/m2-08/README.md`（second-run）、`docs/acceptance/m4/m4-09/evidence/JUDGEMENT.md`。这些记录本来就是部分通过，不能从目录数量推断全面验收。

截至清理前的阶段日志/hash清单、桌面审核修复、运行摘要与旧版本发布准备全部在 Git `0906d7acea8f0f1dc02ddef734f90322a8180579`。例：`git show 0906d7a:docs/acceptance/desktop-adapters/runtime/verification.md`。旧0.1.2/0.1.3过程报告不再是当前安装状态或可执行升级输入；需要考古时按完整原路径取回。

CK工作日志保持原文，其中指向已删过程文件的链接可按上述提交追溯；链接不在工作树不等于原证据不存在。当前主题由CK维护者更新，不为清零断链改写历史日志。仓库外真实备份、journal与安装库存不在文档清理范围内。
