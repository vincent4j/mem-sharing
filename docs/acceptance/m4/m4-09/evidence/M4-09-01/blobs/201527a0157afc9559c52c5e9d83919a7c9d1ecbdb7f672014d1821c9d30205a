# M1-05 格式符合性说明(对照 Keeper save.md 规范)

对照文件:`.agents/skills/context-keeper/references/save.md`(Skill v1.0.0,源码 commit a8e5841)。逐项说明,判定由主 Agent 独立给出。

## worklog 文件

| 规范点(save.md 出处) | 实际情况 |
|---|---|
| 文件名 `worklogs/YYYY-MM-DD-中文主题.md`(§3/§4 示例) | `worklogs/2026-10-29-仓库创建与设计演进.md` |
| 记录目标、实际操作、观察、后续与证据(§3) | 以六节事实结构覆盖:建仓/各版本/评审/M1 执行/时点状态,每条带提交哈希或证据路径 |
| 只追加,不覆盖旧记录(§3) | worklogs 原为空目录,本文件为首条,无旧正文可覆盖 |
| 标注 legacy 来源(任务书 M1-05:"记忆原文用 Keeper 规范记录来源/日期") | 头部元数据列明类型=legacy worklog、事实区间、来源(git 区间+文档+派工转述)、搬运时间、可见性、记录原则 |
| 历史事实只来自记录、区分原文/转述/推断 | 引号处为逐字摘录;两条派工转述事实单独标注"未在 git 历史中独立核验";§6 状态注明"搬运时点" |
| 只记事实不评价(派工要求) | 全文陈述式;对两轮验收中断仅转录 evidence.md 已记录的缺陷定位事实("均为验收辅助代码,非上游失败"为 m1-03 evidence.md 原结论的引述) |

## memory-keeper.md 入口

| 规范点(save.md §4) | 实际情况 |
|---|---|
| 主题摘要放 `## 主题摘要(按类型)` 下,一行简短内容+来源链接 | 新增一行:`- **仓库演进(legacy):** …;来源:[日志](worklogs/…)` |
| 时间线条目 `## YYYY-MM-DD - 中文主题 \`类型\``,含任务与详见链接,最新在前,只链接实际存在文件 | 新增 `## 2026-10-29 - 仓库创建与设计演进(legacy) \`legacy\``;无"关键经验"行(规范允许省略);链接指向实际新建文件 |
| 先找同主题再更新,只改发生变化的部分 | 原有空模板结构、未完成事项、进化经验入口逐字保留;纯追加六行,无既有行修改 |
| 不把普通进度写成编号经验(§5) | 未创建 evolution 条目,evolution/index.md 未动 |

## 未执行项与理由(如实声明,不作通过声明)

- **record-path / record-guard / save-report 未运行**(任务书 M1-05 验收清单含"日志通过 record-path/guard 与 save-report"):
  - probe.py:894 显示 record-path/record-guard 会写 `~/.cache/context-keeper/*.json`(用户级);派工边界明确"不动 …用户级任何文件",且第三轮协议同样不调用 store 探针(round3 handoff:"no store/probe/init commands")。
  - 因此本任务按记录库 worklog 规范手动写入,原始前后指纹见 before.json/after.json;探针路径的验收(含会话指纹基线)留给主 Agent 在获准用户级缓存写入后执行。
- **coverage / compact 未运行:** 同上理由;库内仅一条 worklog 与一个主题,未达 compact 阈值条件。
- 本文件与同目录证据均为原始记录,不含比较断言脚本(第三轮协议)。
