# M1-06 UTC 时间线

| UTC（2026-10-29） | 现场事件 | 证据 |
|---|---|---|
| 11:19:10.947697 | 固定 P0 快照、唯一事实和未开始待办，HEAD 3fc2696；证据暂存库外 | run.json、before.json、before/ |
| 11:19:10.971597 | 启动独立 codex exec | codex-process.json、codex-command.txt |
| 11:19:56（日志为 +08:00） | Codex 新增日志与当前主题，待办未开始 | after-codex/、codex.stdout.jsonl 第 31 行 |
| 11:20:17.122967 | Codex 退出 0 | codex-result.json |
| 11:20:20 前 | 只读复制 P1 库快照并生成 P0→P1 diff | after-codex.json、codex-store.diff |
| 11:20:20.820226 | 启动独立 claude -p；消息无标记与路径 | claude-process.json、claude-command.txt |
| 11:21:00（追加段时间为 +08:00） | Claude 在旧 Codex 日志追加续接段，当前待办推进到进行中 | after-claude/、claude.stdout.jsonl 第 170–175 行 |
| 11:21:09.748640 | Claude 退出 0 | claude-result.json |
| 11:21:22（快照时间） | 只读复制 P2 库、生成差异和入口元数据；之后复制证据到仓库 | after-claude.json、claude-store.diff、total-store.diff、protected-after.json |

P1/P2 模型会话各启动一次，没有重跑；Codex 会话内部保存检查再调用一次，详见 evidence.md。WorkBuddy/P4 均未运行。没有为配合结果修改计划验收表或既有记录库。
