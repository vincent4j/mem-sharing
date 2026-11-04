# 安装后六家原生用户文件核对与 Codex 安装链代表验证

日期：2026-11-04。执行者：突突兔（zcode GLM-5.3/high/yolo）。授权依据：用户原话「安装测试一个agent就可以了，你要的是核对安装后每个agent自己用户记忆文件改的对不对」及「当前用户测试」「继续干到底别老确认」；范围由主 2026-11-04 01:39:58 UTC 派工限定。本任务不跑六家模型、不排桌面/ACP；写集仅本文档。

## 1. 当前安装版本与待测代码关系

- 台账 V（`~/.mem-sharing/var/registry.json`，schema=3）：product_code_version **0.1.7**，source commit `8f3c43e30674dc2769559c6aab3010fb6df62dbd`，tree_sha256 `99f96abd…59b2f`（清单摘要，非 git tree 对象哈希），installation_status=complete，六家 installation=installed（2026-11-03T10:40:32Z 探测证据）。
- 活动 C（`~/.local/share/mem-sharing`）：46/46 文件与 `.agm-code-manifest.json` 逐字节一致；`agents.json`、`user_entries.py`、`install.py`、`agm.py`、`public_layout.py` 五份合同文件与 commit `8f3c43e3` 的 git 内容逐字节相同。C 即该 commit 的忠实安装。
- 本 worktree HEAD `4e8c2d53` 且 dirty（主与旧执行者改动在）：**已装 0.1.7 不含本 worktree 未提交修复**；本报告全部结论针对已装版本，不冒充 worktree 代码已安装。
- R（`~/.mem-sharing`）：memories/var/backups 结构在位；公共索引 9 行、2 主题行，与 MEMORY.md 治理合同（≤200 行）一致。

## 2. Codex 安装链代表验证（显式限定 + 幂等 no-op）

从已核验活动 C 执行 `python3 -B ~/.local/share/mem-sharing/scripts/install.py --agent codex`（无来源参数，按合同由 C/V 自证推导）：

- 结果 rc=0，`status=completed`、`approval_required=false`、`approval_plan=null`、`changes=[]`——满足 INSTALL「真 no-op 只读返回」全条件，构成**当前已装版本安装链验证**（再接入路径、来源推导、入口核对全部走通）。
- `--agent codex` 限定生效：connected=[codex]，其余五家列 unselected，未被触碰。
- 零写实证：六用户文件 + V + 公共 MEMORY.md/user-rules.md 共 9 目标前后 sha256 全等；未新建 bootstrap 目录。

过程披露（如实）：首次预览 rc=2 `install_conflict: Managed code dirty/extra/missing`，根因是**我**此前用 `python3 -I` 从 C 导入模板函数，在 `C/scripts/agm_core/__pycache__` 生成了 11 个 pyc（时间戳全部为 2026-11-04T01:46:10–11Z，无 11-03 残留）。我删除该目录后复验 C 46/46 完整，预览即通过。该事故同时实证了 C 的 extra 检测门禁有效；对 C 的净改动为零（恢复原状）。

## 3. 六家原生用户文件检查表

核对方法：不凭 marker 存在即通过——用**已装 C 自身**的模板函数（`native_public_source_block` / workbuddy convention 组装 / claude `@import`+fallback）与真实文件受管区间逐字节比较；公共索引引用计数限定恰 1；标记配对、尾换行、无私文行丢失。

| 家 | 文件（均普通文件非链接） | 受管结构 | 模板逐字节 | 公共索引引用 | 重复/截断/悬垂 | 私文行数 | 结论 |
|---|---|---|---|---|---|---|---|
| codex | `~/.codex/AGENTS.md` 644 | BASE_MARKER 块 ×1 | 一致 | 1 | 无 | 25 | PASS |
| claude | `~/.claude/CLAUDE.md` 644 | `@<公共MEMORY>` 单行 + claude-fallback 独立块 ×1 | 一致 | 1 | 无 | 32 | PASS |
| workbuddy | `~/.workbuddy/MEMORY.md` 644 | convention 块（指针+约定+fallback）×1 | 一致 | 1 | 无 | 66 | PASS |
| dsh | `~/.dsh/AGENTS.md` 600 | BASE_MARKER 块 ×1 | 一致 | 1 | 无 | 19 | PASS |
| zcode | `~/.zcode/AGENTS.md` 600 | BASE_MARKER 块 ×1 | 一致 | 1 | 无 | 17 | PASS |
| opencode | `~/.config/opencode/AGENTS.md` 600 | BASE_MARKER 块 ×1 | 一致 | 1 | 无 | 17 | PASS |

六家入口路径与 C `agents.json` 六条 `user_entry` 全部吻合；claude 为一行 @导入加独立 fallback 块，符合派工单描述。V 的 `machine.agents.<家>.static/runtime_acceptance` 仍为 unknown/pending——连接事实由本次实测与预览 live 核对承载，非台账存量字段。

## 4. 原文保全证据（本机真实基线，按下述比较口径）

三段链，全部事务 committed 且备份字节与台账指纹逐一相符：

1. **装前原文**：安装事务 entry-backups（`~/.mem-sharing-install-20261103T104014Z-…/entry-backups/20261103T104032Z-…`，0–5.before 对应六文件）——六文件装前均存在且字节与 manifest before 指纹全等。
2. **安装步**：装前→装后私文行集合六家均完全一致（0 增 0 删），安装只添加/更新受管块。
3. **融合步**（2026-11-03T10:41:10Z organize-user-rules）：每家恰删 6 行、0 新增，全部 36 行被删片段逐行见于公共 `user-rules.md`/`MEMORY.md`（用户已批迁移项）；当前六文件哈希与该事务 after 指纹逐一吻合。

比较口径为去受管块后非空行集合（行级），未做字节 span 级对账；在此口径下无任何未解释丢失或新增。历史基线可用，在上述行级口径内未发现未解释丢失；不据此宣称空白字节与原始span完全不变。

## 5. 实际改动 / 未改 / 阻塞

- **仓库写**：仅新增本文档。未改源码、版本、SKILL、既有文档；未 commit/push；未动 CK 与 dirty 改动。
- **真实 HOME**：全程零写（预览 no-op + 快照全等）；唯一例外为 §2 披露的 C `__pycache__` 自染自清，净零。
- **Codex 实测**：一次只读新会话（rc=0，1 次模型调用，16,342 tokens），经原生入口 `~/.codex/AGENTS.md` 实读并确认受管块指向，实读公共索引（9 行/2 主题行，与真实文件一致），仅回路径与行数证据，无私文输出。
- **未验/待后续**：其余五家新会话原生加载（本轮明令不跑）；worktree 未提交修复的安装发行（无授权）；台账 static/runtime_acceptance 存量字段仍 pending，属登记滞后非文件错误。
- **阻塞**：无。

临时脚本与证据：`/tmp/msf-verify/`（compare_six.py、preserve_chain.py、check_integrity.py、codex-preview2.json、codex-entry-run.log 等）。

## 6. 主负责人复核 2026-11-04 01:54:35 UTC

- 用python3 -B重新核六家模板，6/6 PASS；活动C清单46/46哈希一致。
- 安装与融合manifest均committed；逐家核安装before备份、融合before备份及当前after哈希，18项均一致。补查非空私文行序列（含重复次数），安装前后六家均完全一致。融合删除用Counter计数每家6行、新增0行，删除的完整行均存在于公共文件，不再依赖集合/子串命中。仍不将此扩为全字节span或空白完全保全。
- 已读Codex安装预览实际JSON：completed/approval_required=false/approval_plan=null/changes=[]；已读新会话输出确认其主动读取原生入口及公共索引，不把主动read称为自动注入。
- 用户收窄后的验收目标通过：当前已装版本一次Codex再接入幂等验证，加六家用户文件正确性核对。不是全新重装，也不代表当前worktree未提交修复已安装。五家模型/UI读取不再作为本任务门槛。
