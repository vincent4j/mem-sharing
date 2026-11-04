# 当前用户真实运行验收：CLI 新会话与合成对话（第二段）

状态：合成对话提案与预览已生成（用户尚未选择或确认，交互链未完成）；Codex/Claude 新会话只读验证通过；OpenCode 入口受阻（免费额度，pending）。日期：2026-11-03。用户裁定：不创建测试用户，当前用户直接测试；当前用户不作沙箱看待。第二段 16:47:30–（实际执行 16:48:22–16:52 UTC，硬截止 17:02:30）；首段 16:22:36 起耗尽、16:46:37 超限等待另记（主审核口径）。

边界遵守：未登录新账号、未取/拷/输出凭据、未自动安装升级、未打开旧对话、未修改真实公共/原生记忆、未执行任何共享批准、无 HOME 覆盖伪称隔离、无图形 App、无网页。临时输出仅 /tmp 与系统临时目录。单命令 ≤60s；每家最多 1 次实际模型请求（OpenCode 0 次）。

## 一、CLI 真实新会话只读验证

任务 prompt（三家同文）：实际读取本 worktree `SKILL.md` 绝对路径、报告所用工具与路径、概括「用户记忆：四步入口」每步要点（仅文件内容）、如能原生列举可用 Skill 则只列名称；禁止读取/输出其他记忆、历史、账号、凭据。

| 家 | 实际命令 | rc/耗时 | 模型调用 | 显式读取源码 Skill | 原生 Skill 列举层 |
| --- | --- | --- | --- | --- | --- |
| codex 0.166.0 | `codex exec --skip-git-repo-check -s read-only -o /tmp/codex-last.txt <prompt>`（cwd=/tmp，stdin 关闭） | 0 / 40.0s | 1 次 | ✓ 经 exec(`cat`) 读取 `/Users/vincent4j/.paseo/worktrees/0p9qz2xa/skill-first-runtime/SKILL.md`，四步概括准确 | ✓ 可原生列举约 68 个名称（含 context-keeper、paseo 系等）；**清单中无 mem-sharing** |
| claude 2.1.295 | `claude -p <prompt> --allowedTools Read`（cwd=/tmp） | 0 / 12.4s | 1 次 | ✓ 经 `Read` 工具读取同一路径，四步概括准确 | ✗ -p 模式会话无可用 Skill 列表，如实报告无法列举 |
| opencode 2.2.5 CLI | `opencode run <prompt>`（cwd=/tmp） | 1 / 2.7s | 0 次（预检拒绝） | pending | pending |

过程记录：codex 首跑 rc=1 于 0.2s 预检失败（"Not inside a trusted directory and --skip-git-repo-check was not specified"，错误信息原文即给出旗标名），按证据加旗标单次重试成功；两次合计仅第二次发生模型调用。opencode 失败原文："Free usage limit reached. Connect a provider or subscribe to OpenCode Go to keep going, or switch models."——属账号/订阅层，不重试、不擅自连接 provider 或切换模型，记 pending 待用户裁定。

分层结论：
- **显式读取源码 Skill**：codex、claude 均在实际新会话中按绝对路径读取了本 worktree SKILL.md 并给出非私密准确概括（证据：/tmp/codex-run.log、/tmp/codex-last.txt、/tmp/claude-run.log）。
- **自动发现已安装 Skill**：codex 原生列举层可用，但清单中无 mem-sharing——仅证明本次会话所列清单未包含 mem-sharing，不能推出当前用户全局未安装；该Skill自动发现成功未获证据；claude 本次返回无法列举，不推广为-p模式固有能力限制，该层 pending；opencode pending。
- **原生公共记忆加载**：本轮任务明确禁止读取记忆正文，三家均未验证公共记忆自动加载，全部 pending（需后续专门任务）。

## 二、合成对话链（完整交付，未执行）

1. 布置：`stage-synthetic-home.sh`（无参数 mktemp）→ `/var/folders/.../T/memshare-dialogue.gNqAnI`，三文件 sha256 记录。
2. 预览：`share-user-memory --agent codex --agent claude --agent workbuddy --home <H>` rc=0，participants 全文 + 12 segments + basis。我完整阅读三份原文（材料即本人所写 fixtures，participants 返回全文复核一致）。
3. 提案（手工 A/B/D）：`/tmp/memshare-proposal.json`——A 三家同文"提交信息使用中文"（true）；B 两家"修改后运行相关测试"（true）；D 同名"缓存策略"标题下 codex 构建缓存 vs claude 会话缓存（**false**，不得去重）。
4. 带提案预览 rc=5：两块稳定编号 **默认共享=1（A）；由你选择是否共享=2（B）、3（D）**；D 因 same_content=false 进待选、默认不共享——符合修订后 expected-flow 合同。
5. 查看零写：`--selection '查看 3'` rc=0，前后三文件 sha256 完全一致（ZERO-WRITE OK），返回 D 组两处完整原文与来源。
6. 候选确认清单（执行者为覆盖场景模拟"共享 2、3"→选定 1、2、3；不是用户已选择）rc=5：`final_list` 逐处原文、来源字节区间、公共对应段、三家读取入口新增、恢复安排；`changes` 解码后公共 `user-rules.md`/`MEMORY.md` 与三家删源后全文可读；D 两份原文各自独立入公共（未合并）；`plan_sha256=346b8ad0…56c`。**未写 confirmed_at、未执行批准**。
7. 可审阅汇总：`/tmp/memshare-reviewable-summary.json`（含完整解码清单）；预览 `/tmp/memshare-final-preview.json`、查看 `/tmp/memshare-view3.json`、初预览 `/tmp/memshare-preview.json`。主可直接向用户展示实际编号与清单。

## 三、未完成/pending

- OpenCode CLI 入口（免费额度；连接 provider/订阅/切模型均需用户单独授权）。
- claude Skill 自动发现层（本次未提供列举证据；CLI交互不等于图形App）。
- 三家原生公共记忆自动加载验证（本轮明确禁读，未验）。
- WorkBuddy/DSH/ZCode：本执行者未执行图形App线，仍属六家总任务待验；PATH未找到CLI不代表无CLI入口。
- 真实用户批准与共享执行：等待用户按可审阅清单实际确认。

本段写集仅本文档；fixtures 未需修改；未 commit/push；未触碰 CK 与其他现有文件。

## 主审核 16:53 UTC

已核候选解码清单：五个目标全部位于合成临时目录，D两原文分别保留。编号1默认、2/3待选；用户尚未进行实际编号选择，三项全选清单仅候选，不得作为用户确认依据。下一步先向用户展示两块选择，再按实际选择刷新完整清单。CLI结果按执行者运行报告收录；未将清单未列出推为全局缺失，也未将App未执行推为不适用。

## 执行闭环 2026-11-03 23:13:29 UTC

用户实际选择按默认方案并确认完整清单后，执行仅编号1的合成事务。首次命令漏传--home，被approval_mismatch在执行前拒绝（changes=[]）；按CLI现行合同补传已批准的合成HOME后rc=0，status=completed。五个目标逐字节与批准after_hex一致，编号2/3原文保留。manifest为合成HOME/.mem-sharing/backups/20261103T231318Z-0a7bf877c7404cc5813ef2db942582df/manifest.json，status=committed。未修改真实用户记忆。默认对话的真实选择→清单确认→合成执行验证闭环通过；原生自动加载及App线仍pending。
