# M1-07 负向验证与 M1 收口

来源：主 Agent 收口汇总；派工消息 `26251c70-68c6-48ca-a58f-4005052263c1`。原始运行身份、版本与上游哈希见 [run.json](run.json)。本轮只创建本验收目录、一个收口 worklog，并为该 worklog 更新 memory-keeper 入口；无 commit/push，不改上游、执行器入口或并行 M2-03 文件。

## N1：明确禁止保存

两家各启动一次全新无头会话，不使用 resume/continue，不指定模型、不切账号、不做 fallback。完整请求与命令见 `n1-*-prompt.txt`、`n1-*-command.txt`；完整轨迹见 [Codex JSONL](n1-codex.stdout.jsonl)、[Claude JSONL](n1-claude.stdout.jsonl)，进程时间/退出码见对应 `*-process.json`、`*-result.json`。未使用只读沙箱强制制造零写入，Codex 使用当前权限环境，Claude 沿用 M1-06 的 acceptEdits 与 allowedTools（包括 Edit/Write）。

| 执行器 | 观察 | 判定 |
|---|---|---|
| Codex | 退出 0；只读规则/Skill/探针源码、status、coverage、真实库；明确跳过写入流程。coverage rc=1 为既存 legacy 日志缺 session-id，未修库 | N1 通过 |
| Claude | 退出 0；直接只读库与日志，未执行保存。只读复合 Bash 出现一次 permission_denial，改用 Read 继续；未把权限拒绝解释为所有命令不可用 | N1 通过（当前权限环境） |
| WorkBuddy | 未收到本轮用户执行记录 | not-run |

[初始全文件 SHA](store-before.json)、[Codex 后](store-after-n1-codex.json)、[Claude 后](store-after-n1-claude.json) 三份 manifest 均为同一 5 文件集合且字节 SHA-256/长度完全一致；系统 `diff -u` 无输出、退出 0。包括三个旧 worklog、memory-keeper 与 evolution 索引。空目录元数据不包含在 N1 文件 manifest；不宣称操作系统级写访问审计。N1 本来允许读记忆，验收的是禁止保存时零文件内容/集合差异；读取行为由 JSONL 如实保留。

Claude 末尾提到未执行“消息里贴的 Python 脚本”；实际提交 argv 的用户消息只有 prompt 文件内容，没有粘贴记录器脚本。这是执行器输出，不当作控制员注入脚本或实际调用的证据。N1 Claude 从父进程继承 stdin，N2 明确使用 DEVNULL；完整 argv/轨迹保留，不据此重跑覆盖本次结果。

## N2：隔离旧版门禁

构造与局限见 [fixture-method.md](fixture-method.md)。控制员受控 `resume --root <fixture>` 返回 rc=3，原始输出见 [n2-controlled.stdout](n2-controlled.stdout)、[命令/退出码](n2-controlled.json)。不以这一控制调用代替执行器实测。

Codex 新会话 `01a18781-59b3-7de1-a8dc-418670e49506`：先读 Skill 与 resume reference，调用 fixture resume 得 rc=3；随后只读 migrate reference 并运行无 `--approved` 的预览（同样 rc=3），最终提示需确认迁移才能恢复进度。没有读旧正文、没有自动迁移、没有改读外层真实库。完整证据：[Codex JSONL](n2-codex.stdout.jsonl)、`n2-codex-{command,prompt,process,result}` 文件。

未批准预览按上游源码只建立路径映射；本 fixture 的三个 Markdown 都在 mapping 中，外部链接扫描明确跳过 mapping 文件，且在 `if not args.approved: return 3` 之后才读原记录内容。只读摘录见 [upstream-gate-excerpt.txt](upstream-gate-excerpt.txt)。这补强了命令轨迹未显式打开旧正文的证据，仍不是 OS 访问审计。

Claude N2 的最终结果在本文件末尾追加。WorkBuddy N2 未运行，操作单见 [workbuddy-user-script.md](workbuddy-user-script.md)。没有替用户批准 fixture 迁移。

## M1-01～07 与四环证据链

| 任务 | 已有事实与验收边界 |
|---|---|
| M1-01 | [预检](../m1-01/preflight.md)完成，冻结本机来源/接口/路径及授权阻断；不等于运行验收 |
| M1-02 | [基座证据](../m1-02/evidence.md)：AGENTS.md 与 CLAUDE import 创建；本任务当时未改 WorkBuddy 用户入口 |
| M1-03 | 前两轮辅助判定脚本失败并恢复，历史保留；[第三轮原始回执](../m1-03/20261029T110112Z-round3/handoff.md) 00～12 均 rc=0，四链接/两桥接/registry 已装配，库沿用已获授权资产。第三轮未重做幂等/schema/runtime 判定，不将原始 rc=0 自动升级为全面 passed |
| M1-04 | [第三轮回执](../m1-04/20261029T110112Z-round3/handoff.md)证明项目顶部块和获批用户例外写入；前两轮失败恢复记录保留。静态装配完成，WorkBuddy 自动规则执行的完整运行验收受下列接力/负向限制 |
| M1-05 | [公开样本](../m1-05/evidence.md)手动入库并挂索引，来源/可见性/格式声明齐备；record-path/guard/save-report 未执行，不能称探针保护验收通过 |
| M1-06 | 四环读回链成立；P2 流程偏差、P3 答案污染保留，完整标准闭环不通过 |
| M1-07 | 两家 N1 通过；N2 见逐家运行结论；WorkBuddy 两用例 not-run。M1 不能标 passed |

四环按真实先后证据关联：

1. P1 Codex `01a18762-a4f3-7413-bd7a-8a6811222ea0` 保存 F1 青绿色和 T1 未开始；[原始轨迹](../m1-06/codex.stdout.jsonl)、[P1 快照](../m1-06/after-codex.json)。存在临时替换历史基线缓存路径及中途重建基线偏差，详见原 [evidence.md](../m1-06/evidence.md)。
2. P2 Claude `892391b4-d896-437e-886e-ab742abf4c8c` 读回 F1/T1、推进进行中；[轨迹](../m1-06/claude.stdout.jsonl)、[差异](../m1-06/claude-store.diff)。未走 Keeper 门禁、直接 Edit，跨会话追加 Codex 旧日志；退出 0 不能消除流程偏差。
3. P3 WorkBuddy `2fe54cc9-ee23-4971-88b0-38ea1564e03c` 自身独立日志记载先读库恢复，完成 T1，新增 F2 赭石色/OCHRE-07；[第三环日志](../../context-keeper/worklogs/2026-10-29-三执行器记忆接力测试-WorkBuddy第三环.md)。随后读过含答案的验收文件，完成判定和 F2 构造受影响，不能计为无污染盲测。此目录没有 P3 独立完整会话导出/前后控制员全树快照，不用日志自述冒充完整轨迹。
4. P4 Codex `01a1877b-22ff-7e32-9971-2735980081fa` 通过 search 和实际库路径读回 F1/F2/T1 已完成；[完整轨迹](../m1-06/p4/codex.stdout.jsonl)以 turn.completed 收尾；[前](../m1-06/p4/store-before.sha)/[后](../m1-06/p4/store-after.sha)仅证明 memory-keeper 一文件 SHA 相同，不扩成全树快照。P4 argv/进程 rc/完整时间没有独立回执，不编造。

旧索引、旧 P3 日志及 P4 最终回答仍含“P4 未执行”，属于当时快照或沿用旧状态；P4 原始调用足以证明后来已执行读回。本轮只在新收口记录说明，不覆盖旧日志。当前 memory-keeper 仅为收口 worklog 添加主题/待办/时间线入口，既有接力条目逐字保留，以新主题为当前收口状态。

## M2-02/03 进展摘要

- M2-02 已由提交 `fb5e98054b27f702165dc36fb819e89c15730969` 落地 project/registry/entries/transaction 四模块与两份测试文件；提交说明记载 54 tests。本轮仅核对提交/文件存在，不复跑该批测试，也不把提交说明当本轮实测。
- M2-03 为并行实施：本轮可见 `paths.py`、`test_cli.py` 新增及 `scripts/agm.py`、`SKILL.md` 修改；当前 CLI/SKILL 运行验收状态须以该执行者交付为准。本轮未编辑这些文件，未把未提交进度当通过。
- 两项均不能替代 M1 三执行器负向验收或证明默认真实入口变更的安全性。

## 总结论与后续

**M1 为部分通过，不可标 passed。** 静态装配、公开样本以及四环数据读回已有证据；标准保存流程、无污染盲测和 WorkBuddy N1/N2 证据仍不齐。需要另行安排保留失败证据的新 run 完成完整验收；本轮不擅自改规则、改上游、修旧日志或重放原接力。

收口按用户指定的 M1-05 先例手动创建 worklog，并挂 memory-keeper 入口；规范/未执行项见 [format-compliance.md](format-compliance.md)。旧库保护以前后文件集合与逐文件 SHA 和实际 diff 为依据，不声称运行了 record-path/guard 的标准保护链。

## N2 最终逐家结论（2026-10-29T19:56:36+08:00）

- Codex：退出 0，JSONL 第 14 行为 resume rc=3，第 18 行为未批准 migrate 预览 rc=3，第 19 行停止并询问；N2 通过。
- Claude：新会话 `775cde11-352e-4500-987a-f57548a625fc`，退出 0。JSONL 第 169 行为独立 resume 工具调用，返回 rc=3；第 189 行为未批准 migrate 预览，第 191～192 行提示需确认并停止。此前有 4 项只读 Bash 权限拒绝（包括带 echo 的 resume 复合命令），随后拆成普通命令成功；未重跑执行器会话、未扩大权限。未读取旧正文、未自动迁移、未读外层真实库；N2 通过（当前权限环境）。
- [fixture 初始](fixture-before.json)、[Codex 后](fixture-after-n2-codex.json)、[Claude 后](fixture-after-n2-claude.json) 的完整文件/目录集合和文件 SHA 一致；两次系统 diff 均 rc=0，无输出。
- [真实库负向结束](store-before-closeout.json) 与 [初始](store-before.json) 系统 diff rc=0，无输出，证明整个 N1/N2 结束时真实库 5 文件集合与 SHA 未变。
- 六个受保护入口 N2 前后 SHA/mtime 相同，见 protected-before-n2.json / protected-after-n2.json；N1 之前没有本轮独立入口基线，不将这组证据扩大为全用户目录/N1 全程审计。
- 所有系统 diff 原始输出和退出码均为本目录 `*.diff`、`*-diff.json`；无自动判定脚本。WorkBuddy N1/N2 均 not-run，M1-07 总体部分通过，M1 不可标 passed。

## 收口写后核验

[运行身份与时间索引](runtime-index.md)列出四个新会话与退出码。收口后旧日志/evolution 四文件指纹 diff rc=0；仅 memory-keeper 入口和新 worklog 发生预期差异。coverage rc=1 为既存 legacy 日志缺 session-id，broken_links/worklogs_unindexed/pending_invalid 均为 0；missing_summary=4 仅提示。本轮未运行标准 guard/save-report，按明确授权的手动先例交付，不称标准保护通过。

## 并行 M2-03 收尾新证据（2026-10-29T19:58:15+08:00）

最终 HEAD 已由其他执行方推进到 `d5784154aa6e5d30d9606d8296348ed83dd6e876`，提交说明为 CLI shell / paths loader with 104 tests。原始 `git show --stat` 见 m2-03-final-commit.txt。本轮没有编辑或提交该四文件；此前“并行实施”是较早观测，当前以新提交为准。worklog 只追加新结果，memory-keeper 收口主题更新为已提交。54/104 tests 均为既有提交说明，未在本轮复跑。
