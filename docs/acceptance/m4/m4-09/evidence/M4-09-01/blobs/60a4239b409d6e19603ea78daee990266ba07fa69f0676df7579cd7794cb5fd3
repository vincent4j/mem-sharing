# M2-08 两项目复制验收

采集时间：2026-10-29T13:34:25.106460+00:00。执行者：呱唧。任务来源：Paseo 消息 ba2d7261-b5d6-44db-a455-e067307afb3f；依据 docs/plan/tasks.md M2-08。

**总体：阻断，M2-08 未通过。两个项目均未装配，三执行器新会话与幂等验收均未执行。**

| 项目 | 只读盘点 | 装配 | 阻断 |
| --- | --- | --- | --- |
| knowwind | 完成 | 未执行写入阶段 | 用户级 WorkBuddy 已登记模板 drift |
| poster-fit | 完成 | 按规则停止 | AGENTS.md 与记录库计划 dirty |

逐项目证据：[knowwind](knowwind/report.md)、[poster-fit](poster-fit/report.md)。两项目分别有原始 Git 读回、入口/库路径和 SHA-256/mtime 清单、前后空 diff、带前置条件的 WorkBuddy 用户操作单。没有写判定脚本，没有业务代码修改，没有 commit/push，没有从旧项目复制私有记忆正文。

knowwind 真实调用顺序：

```text
python3 scripts/agm.py enable-memory --project /Users/vincent4j/Tools/Source/knowwind --memory
# rc=5，预览缺少源码定位
python3 scripts/agm.py enable-memory --project /Users/vincent4j/Tools/Source/knowwind --memory --approval-file docs/acceptance/m2-08/knowwind/source-selection-proposal.json
# rc=2，前检查发现 drift，未进入装配
```

初次终端预览随后为证据落盘原样重跑一次（仍 rc=5）。提案仅补源码/默认位置与授权来源，因缺完整现场计划没有当作最终精确批准。未伪造最终批准文件；两项目都没有执行 init，因此未遇到 init 交互/迁移，也没有登记新项目。集中 registry 继续由真实 CLI 管理，未手工修改。

其他异常：paseo-progress show 与 --help 均因 ERR_MODULE_NOT_FOUND（缺 zod）无法启动；未为本验收安装依赖或修改进度插件。验收前置以当前只读现场为准；用户消息中的 M1/M2 前置结论未被替代为本轮端到端证据。

下一步：由负责人审查用户级 WorkBuddy drift；用户处理 poster-fit 相关 dirty。之后各项目重新盘点并按精确计划继续。WorkBuddy 操作单只适用于装配和幂等完成后的全新会话，当前不可计为部分通过。

## Second-run 2026-10-29（旧阻断证据保留）

依据修复 0919ec9 和新授权，两项目真实装配、幂等重装均返回 0，输出快照零幂等 diff；Codex/Claude 共四个全新无头会话实际读回记录，WorkBuddy 尚未运行，整体部分通过。poster-fit 原 AGENTS.md 全部字节保留为前缀，其余 dirty SHA/mtime 不变。

- [knowwind second-run 报告](knowwind/second-run/report.md)
- [poster-fit second-run 报告](poster-fit/second-run/report.md)
- 两项目各 second-run/ 下包含批准依据、精确计划、批准文件、装配/幂等/只读检查输出、前后快照与 diff、会话原始轨迹及 WorkBuddy 操作单。
- 限定：Claude 读回成立但未显式走 Skill/resume；check 的库状态为 unknown，不用退出码替代运行证据。进度插件缺 zod；无用户级 WorkBuddy 变更或 created 漂移。未 commit/push。
