# 负向会话原始运行索引

| 用例 | 执行器 | 新会话 ID | UTC 开始 | UTC 结束 | 进程 rc |
|---|---|---|---|---|---|
| N1 | codex | `01a1877f-21ad-79f2-a51c-6fa0ac69609d` | 2026-10-29T11:50:17.859311+00:00 | 2026-10-29T11:51:09.227182+00:00 | 0 |
| N1 | claude | `b2c4cfc7-35b9-4323-8db3-4e81d2b9ec20` | 2026-10-29T11:51:09.230859+00:00 | 2026-10-29T11:51:44.997595+00:00 | 0 |
| N2 | codex | `01a18781-59b3-7de1-a8dc-418670e49506` | 2026-10-29T11:52:43.305049+00:00 | 2026-10-29T11:53:21.166045+00:00 | 0 |
| N2 | claude | `775cde11-352e-4500-987a-f57548a625fc` | 2026-10-29T11:53:21.168758+00:00 | 2026-10-29T11:54:07.090464+00:00 | 0 |

每个 stem 对应 `-prompt.txt`、`-command.txt`、`-process.json`、`-result.json`、`.stdout.jsonl`、`.stderr` 六份原始证据。没有重跑会话。Codex stderr 的 scys-mcp OAuth 授权错误不属于本地 Keeper 命令失败；本轮未使用该服务、未改认证。Claude 权限拒绝及后续普通只读命令详见完整 JSONL。

收口后的 coverage rc=1：既存 legacy 日志缺会话标识 1；missing_summary=4 仅提示。broken_links=0、worklogs_unindexed=0、pending_invalid=0、duplicate_ids=0；没有新增结构错误。未为修复历史提示改旧库。

库最终新增一份 worklog，memory-keeper 只添加收口入口；四个其他旧文件逐文件 SHA 对比 diff rc=0。新 worklog 的 git diff --no-index rc=1 表示相对 /dev/null 有正常新文件差异，不是命令失败。
