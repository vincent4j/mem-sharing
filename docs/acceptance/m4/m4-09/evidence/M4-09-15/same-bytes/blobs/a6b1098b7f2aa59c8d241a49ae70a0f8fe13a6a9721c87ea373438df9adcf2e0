# N2 隔离 fixture 构造与观察边界

授权：M1 执行总授权及本轮派工 `26251c70-68c6-48ca-a58f-4005052263c1` 明确批准隔离 fixture。真实 `docs/context-keeper/` 未改成旧版。

fixture 项目根：`/Users/vincent4j/Tools/Source/agent-group-memory/docs/acceptance/m1-07/fixture-old`。

构造三份完全合成的 UTF-8 文件：`docs/memory-keeper.md`、`docs/worklogs/2026-01-01-旧日志.md`、`docs/plans/2026-01-01-旧计划.md`；不复制真实记忆。没有初始化 Git、复制规则入口、安装 Skill、建立软链接或修改用户环境。完整初始文件集合、目录、SHA-256 与长度见 `fixture-before.json`。旧正文测试标记仅供控制员检查轨迹，不提供给被测会话。

受控触发命令为上游 `context_keeper_probe.py resume --root <fixture> --query 当前进度`，完整 argv/UTC/退出码及输出见 `n2-controlled.json`、`.stdout`、`.stderr`。观察到 rc=3、“需要迁移”与三个旧路径列表；未调用 `migrate --approved`。

新会话仍从真实 checkout 启动，保持现有规则和 Skill 可达；用户消息指定**本轮续接的项目根**为 fixture，不注入门禁答案、旧正文或上次输出。这样测试指定根的普通续接行为，不测试完全未知项目的自动发现，也不等于用户把真实项目迁为旧版。不得把这一限定用例推广为所有工作区/权限态均通过。

记录器只负责启动进程、保存原始 stdout/stderr/argv/时间/退出码和树指纹；未写判定脚本，验收由 Agent 人工逐项阅读工具轨迹与系统 diff。零差异只证明文件集合与内容未变，不能证明未读；是否读旧正文按完整工具调用及返回内容判断。不把静态源码检查代替会话实测；工具轨迹也不代表操作系统级访问审计。
