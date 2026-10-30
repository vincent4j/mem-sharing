# M1-03 执行失败与恢复证据

状态：**failed / 已回滚**。M1-03 未全绿，M1-04 未开始。执行者：呱唧；日期：2026-10-29 UTC。无 commit/push。

## 授权与现场

本轮授权来自 Paseo 派工消息 `7b6244d9-426f-4681-9d22-b94566ae21f1`：本仓库记忆档=yes，位置=`docs/context-keeper/`，M1-02 基线追认、固定本机 Keeper 来源、WorkBuddy 指定追加例外。本授权与执行结果分开：授权仍为 yes，安装现场已恢复，库未创建。

已读取共享 MEMORY.md、DESIGN v1.1 相关段、tasks/architecture/preflight、M1-02 evidence、Keeper Skill 与 install/save references。当前操作仅项目安装，不更新用户 Codex/Claude 入口。未读取旧库正文、未迁移。

安装前通过：Git root/common-dir；上游 clean、commit `a8e584159b3853b11f96b0ec89036d04ce29dce2`；SKILL/install/probe 三哈希与预检一致；override 缺失；两基座整文件哈希等于 M1-02 批准值；四项目链接与实际库/配置均缺失。详见 [baseline.json](baseline.json)。

## 实际命令与结果

完整 argv、UTC 时间、rc/stdout/stderr 见各 JSON；顺序如下。

1. `install.py --project R --codex --claude --workbuddy`：rc=0，approval_required=true；仅预览，不算完成。见 [install-preview.json](install-preview.json)。
2. 同参数加 `--approved`：rc=0，四个链接全部解析到冻结来源，AGENTS/CLAUDE 两 bridge 追加并读回；基座原始字节作为前缀全部保留。上游追加一个分隔换行，其字节变化已计入预期后指纹及 diff。用户三入口指纹未变。见 [install-applied.json](install-applied.json)、[AGENTS diff](AGENTS.md.attempted.diff)、[CLAUDE diff](CLAUDE.md.attempted.diff)。
3. Codex `--ensure-bridge --skill-dir R/.agents/skills/context-keeper --root R --codex`、Claude 对应 `.claude`：各 rc=0，均 scope=project、action=unchanged，无 approval_required。见 [ensure-codex.json](ensure-codex.json)、[ensure-claude.json](ensure-claude.json)。
4. **失败点**：验收辅助脚本比较现场快照与 manifest 的 before 字典时，将只存在于备份元数据中的 `backup_file` 字段也直接比较，触发 AssertionError。独立只读核对剔除该字段后，ensure 前后文件字节/模式/mtime/块/块外指纹全部相等。此为本轮校验代码缺陷，不是上游 ensure 失败；仍遵守“任一步失败即停并回滚”，不当作任务通过、不继续重跑。
5. 调度中在读取该失败结果前多执行了一次只读 `probe init --root R`：rc=5，建议默认位置；**没有执行 init --approved**。这是停止顺序的偏差，保留 [init-preview.json](init-preview.json) 与 [failure.json](failure.json)，不隐去。
6. 停止安装后续步骤，按本次后指纹核对无并发变化，再恢复原两基座整文件字节/模式，移除本次四个链接及新建空父目录。三用户入口、源码均未变；库/config/registry 仍缺失。见 [rollback.json](rollback.json)。恢复导致基座 mtime 改变，未伪称时间戳恢复。

## 所有权与改动清单

| 对象 | 本轮操作及归属 | 最终现场 |
|---|---|---|
| AGENTS.md / CLAUDE.md 基座 | M1-02 created，本轮 reused；只追加 Keeper block | 已恢复原始字节/模式，mtime 因回滚改变 |
| 两个项目 Keeper block | 本轮 created | 已撤销 |
| `.agents/skills/context-keeper` | 本轮 created symlink | 已移除 |
| `.codex/skills/context-keeper` | 本轮 created symlink | 已移除 |
| `.claude/skills/context-keeper` | 本轮 created symlink | 已移除 |
| `.workbuddy/skills/context-keeper` | 本轮 created symlink | 已移除 |
| 上述新建空父目录 | 本轮 created | 已移除；无既有目录被删 |
| 三用户级 Skill | 原有 reused，仅核对来源 | 未写入 |
| 用户 Codex/Claude/WorkBuddy 入口 | 原有保护对象，仅核对指纹 | 未写入，字节/mtime 均未变 |
| Keeper 库 / context-keeper.json | 未创建 | 缺失，未删除或覆盖任何库 |
| scripts/registry.json | 原先缺失，未创建 | 以本目录 state-ledger.json 作集中草表，不冒充 CLI 持久登记成功 |
| docs/acceptance/m1-03、m1-04 证据 | 本轮 created | 保留 |
| scripts/backups 本轮备份 | 本轮 created，本机 gitignore | 保留 |

原有 dirty 文件（含 docs/plan/m1-acceptance.md、M1-01/02 产物）未编辑。未修改上游或旧管理器源码、人格文件、任何用户入口。

## 备份与恢复

- 安装 manifest：`scripts/backups/20261029T105159Z-m1-03-install/manifest.json`
- ensure manifest：`scripts/backups/20261029T105159Z-m1-03-ensure/manifest.json`

manifest 含存在性、类型、文件模式/整文件哈希、受控块及块外哈希（适用时）、链接原始与解析目标（写后）、授权依据、预期后指纹、读回与恢复状态。安装前原文件整字节保存在同目录 .bin。备份目录权限 0700。未备份用户私密正文。

真实恢复已执行：只恢复仍匹配本次写后指纹的对象；四链接目标核对后移除；新建父目录仅 rmdir 空目录。未使用上游 uninstall、未删库。恢复检查 passed，不能扩大为所有故障分支恢复能力通过。

## 四态与未验证项

集中草表：[state-ledger.json](state-ledger.json)。最终 source_available=ready；三家项目 skill_installed=missing；三家 bridge_assembled=missing；store_authorized_ready=blocked（授权 yes、位置 approved，实际库缺失）。运行时始终 pending。

幂等复跑：**not-run**；两 ensure 的 unchanged 只证明当时入口匹配，不是完整安装/init 幂等验收。建库、status 实际路径读回、registry ready、M1-04、三家新会话、负向迁移、样本、其他平台均 not-run。

辅助 paseo-progress 的 show/help 均因缺少 zod 返回 rc=1；未更改插件依赖或扩大修复范围。它不导致安装回滚；实际停止原因是上述验收脚本断言失败。

下一步：本任务已按硬边界停止。后续重新执行前需修复备份快照比较方式，保留本次失败证据，重新核对现场与授权范围；不得沿用曾短暂安装成功作为当前 ready。

## 收尾发现：并发 Git 状态

起始 HEAD 为 a43e31c，基座未跟踪；收尾 HEAD 已由其他执行方推进为 `a422ec8`，其中 AGENTS.md/CLAUDE.md 含本轮短暂追加的 Keeper bridge。当前文件已按本任务硬边界恢复到 M1-02 批准的原始字节，所以 Git 相对该新 HEAD 显示删除两个块。这不是干净工作区，不修改索引、不 reset、不改写他人提交。此前文件级恢复检查只证明现场文件未被并发改写，未覆盖 Git 提交级并发；后续需主 Agent 对账。见 [concurrent-git-state.json](concurrent-git-state.json)。


## 重试失败与恢复（本轮追加）

状态：**failed / 已恢复入口，已初始化的库保留**。授权仍有效。本轮未 commit/push。

- 独立证据目录：`20261029T105740Z-retry`；辅助脚本：`retry.py`。
- 修正了现场比较白名单，`backup_file` 不参与比较；对应回归检查通过。安装前 source commit/三哈希、基座和用户入口漂移检查通过。
- M1-03 安装、四链接读回、基座原字节保留、两家 ensure unchanged、`init --approved --store-dir docs/context-keeper`、status 实际位置及安装/init 幂等（字节/模式/mtime）均通过；见目录内 `m1-03-passed.json` 与各命令回执。
- M1-04 模板七条语义比对、项目顶部块、用户级原字节前缀保留、两文件幂等检查通过。随后写 registry，快照函数将 JSON 中多次出现的 marker 字符串引用误当为入口标记重复，触发 AssertionError；自动恢复又触发同一错误。此为验收辅助代码第二处缺陷，不能记全绿。
- 失败后未执行任何后续业务命令或只读 probe；只记录失败并运行专用恢复。恢复仅比较基础现场字段；对中断的本次新建 registry 核对项目与本轮证据路径后保留本地副本并移除；其余对象按已记录写后指纹和备份恢复。
- 两基座及三用户入口恢复原始字节/模式/mtime；四链接、WorkBuddy 项目块和新建空父目录移除；registry 缺失。Keeper 库已实际创建，按架构 §5 项目资产保留，未删除、未搬运样本、未写项目历史。
- 集中 registry 没有最终提交成功；当前 source ready，三家 skill/bridge missing；第四态保留本次授权与已建库事实，不把整体装配称为 ready；runtime pending。最终恢复逐对象校验见 `rollback.json`，完整备份位于 `scripts/backups/20261029T105740Z-retry-*/manifest.json`。
- 本轮立即停止，不自行第三次重试。后续需将入口 marker 校验限制在实际入口文件，registry JSON 只做结构和整文件快照校验，取得后续派工后再做安装重试。


## 第三轮追加：原始操作回执（不作验收判定）

操作 ID `20261029T110112Z-round3`；协议依据派工消息 `4c4c4df3-3f6c-4ed5-ba98-fbb213cbbac1`。本轮所有操作命令 rc=0；未运行验收判定脚本，未回滚，未 commit/push，已建库不改不重新 init。完整命令、原始输出、前后指纹、所有权及备份 manifest 索引见 [20261029T110112Z-round3/handoff.md](20261029T110112Z-round3/handoff.md)。三家 runtime pending；验收结论由主 Agent 独立给出。
