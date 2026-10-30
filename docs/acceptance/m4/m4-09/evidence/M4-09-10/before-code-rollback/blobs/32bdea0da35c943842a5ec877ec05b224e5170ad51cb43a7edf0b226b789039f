# poster-fit M2-08 second-run

状态：**部分通过**。装配、幂等、CLI 检查及 Codex/Claude 普通新会话读回通过；WorkBuddy 未执行，整体不记通过。证据时间 2026-10-29T13:56:06.517117Z。旧 ../report.md 等阻断证据完整保留。

## 真实装配与边界

- 基线 CLI 提交 0919ec9。项目身份见 identity.json；Git 比较仅针对本地 origin/main，未 fetch。增量盘点见 tree-before.json、entries-before.json、git-status-before.txt；延续上次目录盘点，没有读取旧管理器配置/凭据。
- preview-initial → source-proposal → preview-exact → approval.json；批准依据见 approval-basis.md。预览返回 5；正式 enable 返回 0。精确写集为项目四个 Skill 链接、WorkBuddy 项目桥接、AGENTS.md 和 CLAUDE.md。计划中没有 ~/.workbuddy/MEMORY.md；该用户文件前后 SHA/mtime 相同。
- registry 只由真实 CLI 正常写入；没有手改登记、绕过漂移、手工 init 或改上游源码。真实上游 install/init 由 enable 驱动。check.json 返回 0；源码、Skill 与桥接为 ready，记录库为 unknown（只读 check 不调用可能写缓存的探针）。真实 enable 已成功调用上游，Codex 新会话 resume 也实际读回；这些证据分别保留，不将 check=0 等同四态全绿或新会话验收。
- 既有业务代码与记录库全部保持 SHA/mtime。装配前后既有文件变化仅入口：AGENTS.md；新增输出逐项见 assembly-fingerprints.diff 与 managed-output/。未 commit/push，未执行真实业务或生图。

## 幂等与新会话

正式装配后再次运行 `python3 scripts/agm.py enable-memory --project /Users/vincent4j/Tools/Source/poster-fit --memory`，退出 0、changes=[]。tree-after-enable.json / tree-after-idempotent.json 相等，idempotent.diff 为空；按 m2-matrix §6，registry 时间戳及事务备份属于允许的记账写入。快照覆盖全部 Git 跟踪/非忽略未跟踪文件以及本轮受管输出，非全机器快照。

Codex `01a187ef-d070-72a0-ac31-a0e5f56131c4` 与 Claude `24806297-4a27-4577-b332-7783b4c2ca98` 均为全新无头会话，prompt 不含记忆路径。均退出 0，实际读到本项目记录，恢复进度及待办并给出处；详见 session-evidence.md 和原始轨迹。CLI 启动目录为本项目，保留正常原生配置发现；Codex read-only，Claude plan/禁止交互权限请求/禁用 hooks，工具限读和续接。会话前后快照一致，sessions-files.diff 为空。Claude 未显式运行 Skill/resume 的程序合规范围保留，不能扩大为三执行器全流程通过。

WorkBuddy：**未验收**；操作单见 workbuddy-user-script.md，不以操作单或装配静态检查算通过。

## dirty 保留

正式澄清消息 654e071a-980e-45e3-b834-98b56cf21c81 允许追加桥接块。旧 AGENTS.md 的完整 12,889 字节与新文件前缀逐字节相等，新文件 15,191 字节，仅追加 2,302 字节。旧/新 SHA 分别为 `67223927eeb4916e9c00e42a8f2247f7a8743d59a9dd9bbb03b57ae6e91596a7` / `09067905d39f89392e373af0861b9e9b225aee547dfa3cd678fb636b4273fea6`。其他 dirty 文件内容和 mtime 均相等。见 dirty-preservation.json、dirty-before/after.json、dirty-byte-snapshot/、dirty-diff-before/after-enable.patch 与 dirty-diff-delta.patch。人工读回 delta：原有 AGENTS 修改与两份计划的 diff 保留，仅新增桥接段（Git blob index 随之变化）。

## 异常与未验证

- 进度插件因缺 zod 无法启动，未修插件；以本地证据记录进度。
- dirty AGENTS 追加语义曾暂停确认，收到正式澄清后执行，未覆盖原有字节。
- 无 created 外部漂移，无迁移门禁，无用户级 WorkBuddy 写项。
- 未验证 WorkBuddy 运行、所有执行器严格 Skill 路由、业务待办真实性与端到端生产结果；未将本轮扩展为项目修复或生产验收。
