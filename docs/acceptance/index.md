# memSharing 验收门禁总览

当前产品能力、运行限制与发布准备分层记录。**M4 整体未关闭，不可宣传三家完整接力或全部运行验收通过。** 当前结论与删留质检见[发布前收尾报告](release-review.md)，运行证据唯一汇总见[M4-10 判定](m4/m4-10-runtime/verdict.md)。

| 里程碑 | 已证范围 | 当前证据边界 |
|---|---|---|
| M1 | 静态装配、数据读回、Codex/Claude N1/N2 | **部分通过**；标准闭环有流程偏差/答案污染，WorkBuddy 负向未验。原始判定 `f06db31:docs/acceptance/m1-07/evidence.md` |
| M2 | 本地实现、macOS 安装/卸载/恢复、两项目装配与 Codex/Claude 读回 | **运行验收部分通过**；WorkBuddy 两项目新会话未做、Claude 未显式走 Skill/resume，Windows/Linux 未验。原始 `f06db31:docs/acceptance/m2-08/README.md` 的 second-run；[M2-09 日志](../context-keeper/worklogs/2026-10-29-M2-09平台矩阵与发布前文档.md) |
| M3 | 旧管理器现场处置 | 沿用前轮结论，本次不重跑、不扩成 M4 接力证据 |
| M4-02～08 | 布局、台账、安装、入口、生命周期、升级、改名及治理 | 沿用各子项实现/合成验收；历史 `f06db31:docs/acceptance/m4/` 下对应 verdict，不替代真实客户端验证 |
| M4-09 | 62 案证据矩阵 | **限定合成范围通过**：43 executed 通过、15 blocked 原因合理、4 not_in_scope 归 M4-10；另发现1项菜单缺陷已在后续修复。不是63案或62案全部运行通过 |
| M4-10 | 本机安装/v0 导入、0.1.1 WorkBuddy 修复部署、部分新会话 | **部分通过、未关闭**；部署与静态读回成立，WorkBuddy 修复后新会话/CK 实际尾步及其他门禁未验，用户已暂停相关运行活动。详见[当前判定](m4/m4-10-runtime/verdict.md) |

历史判定与原始材料在 Git `f06db31` 中按路径读取，例如：

```sh
git show f06db31:docs/acceptance/m1-07/evidence.md
git show f06db31:docs/acceptance/m2-08/README.md
git show f06db31:docs/acceptance/m4/m4-09/evidence/JUDGEMENT.md
```

本次核对了上述三份原始判定，纠正前版总览对 M1/M2 的无条件“通过”。未重新验证整个历史大证据集的字节完整性，不以历史目录数量/体积冒充全面核验。当前未提交的 M4-10 材料另有仓库外备份，不能称其已在 Git 历史中。

发布条件与未来恢复运行验收的规格集中在[发布清单](m4/m4-10-prep/release-checklist.md)。执行记录、静态检查、真实运行和发布批准分别判断；暂停与合理 blocked 均不转为 pass。
