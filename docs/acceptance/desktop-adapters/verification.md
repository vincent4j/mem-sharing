> 最新状态：2026-10-31审核问题已修复，源码收尾复核通过；以下保留修前记录。见[修后复核](review-fix/verification.md)。

# 双桌面端适配验收

日期：2026-10-31。基线：`e6603730304de7352f4c6caef1615adb2ad74e97`。

## 当前结论

DeepSeek Harness（`dsh`）和 ZCode（`zcode`）源码适配完成，已整合主工作区，未提交或推送，版本仍为 0.1.3。真实安装、桌面原生新会话及 Skill 实际加载均为 pending。

两家用户入口为 `~/.dsh/AGENTS.md`、`~/.zcode/AGENTS.md`，项目均原生读 `AGENTS.md`；共用公共索引，保留私文。完整路径与本机静态取证见[原生合同](../desktop-agent-contracts.md)。默认目标保持旧三家，新两家显式选择。

## 证据

| 验证层 | 结果 | 依据 |
| --- | --- | --- |
| 本机应用身份与静态签名 | 通过 | 两款应用的现有检测器返回 verified；未启动应用 |
| 全量单元测试 | 578/578 通过，278.024s | [原始日志](unit.log)，`python3 -m unittest discover -s tests/unit` |
| 全量集成测试 | 74/74 通过，113.740s | [原始日志](integration.log)，`python3 -m unittest discover -s tests/integration` |
| 独立限定审查 | 通过 | 原审查者复核四项问题关闭，未重复跑测试 |
| 主工作区整合 | 通过 | 19个代码/测试文件逐字节一致，7份产品文档同步；目标合同哈希、旧前身常量及 Python 3.9 语法静态核对通过 |
| 真实安装与桌面运行 | pending | 本轮未执行，不用合成 HOME 或 ACP 结果代替 |

测试总数为652，不叠加已包含在全量中的定向测试。新增18个发现用例覆盖安装身份、私文保全、幂等、拒绝零写、根路径、check/remove/disabled、CK混合与不支持组合，以及迁移读者与原生块幂等。

独立审查与整合所用组合 SHA-256：`79607142d8f2d9fba0c9673375abc86dc014fbb07fbdc252c512c380216ba890`；算法为脚本/测试的 binary diff + NUL + 新测试相对路径 + NUL + 新测试字节。该值不包括文档，也不是发行负载身份。

## 修正与边界

- 已关闭：环境变量原值进入错误、空白/tilde/相对默认根误拒、Codex预算误套新增客户端、安装简报漏名。DSH非默认根拒绝默认入口接入，不回传原值；自定义preset/显式配置不承诺。
- CK固定上游不支持两款新执行器的安装flags。仅新两家时 `status=skipped`、`reason=upstream_unsupported`；混合时结果分别列出受支持的 `agents` 和 `skipped_upstream_agents`，不影响主产品接入，不改上游。
- 首轮全量560项曾5F/63E；原日志保留于 `/tmp/guaji-desktop-unit.log`。运行中重冻结与旧WB夹具错用五家表等问题修正后，在固定文件下重新跑完最终全量。旧before/predecessor常量未修改。
- 突突兔（GLM）完成核心初版、首轮修正及部分旧测试；随后两任务因1310周/月额度耗尽中断，按既定顺序由呱唧接续新增测试、回归和文档，巴克队长整合验收。未从头重做。
