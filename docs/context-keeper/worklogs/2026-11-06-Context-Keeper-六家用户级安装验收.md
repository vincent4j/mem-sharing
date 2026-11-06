<!-- context-keeper: session-id=01a1ab89-6dfd-74e0-b0c9-920aab77b502 -->
# Context-Keeper-六家用户级安装验收


## 追加记录 2026-11-06T16:22:14+08:00

- **目标与授权：** 用户在独立列明六家执行器和项目经历用途后回复“安装”；本次不把 memSharing 的共享授权当作 Context Keeper 授权。
- **实际操作：** 从干净且官方 origin 的唯一源码目录 `/Users/vincent4j/Tools/Source/context-keeper` 实时 fetch 官方 main，经 memSharing 0.1.10 的独立 `--context-keeper` 入口预览并执行。固定当次提交 `66d7e9191d2c8f0693d1d17112b9fc672f9aab3f`，精确安装计划 `5c1918ece66519ba3e0123b7ac098f9f750a08ffb0a891fccf0980cc2f19257d`；未修改上游源码。
- **观察结果：** rc0、status=configured；Codex、Claude Code、WorkBuddy、ZCode、DSH、OpenCode 全部受当前上游支持，无跳过。7 个原生 Skill 链接均解析到同一源码，6 个用户级入口块读回通过，块外字节保全。公共记忆及 memSharing 台账 bytes/mode/inode/mtime 未变。安装阶段未改项目规则或既有项目记录、未初始化或迁移记录库；随后仅本日志与现有主题摘要作为收口记录。
- **边界：** configured 只证明文件配置成功。六家 Context Keeper 新会话实际发现/读取/触发尚未验证；此前 ZCode 新会话因 quota1310 失败，未改用其他付费模型重试。真实 Paseo UI 仍因 native pipe 不可用待验。
- **当前使用：** 新会话通过 `/context-keeper` 保存、继续或查找；沿现有项目记录库，不重新建库。
- **证据：** [独立预览](/Users/vincent4j/Tools/Source/memsharing-019-evidence-20261106T022519Z/context-keeper-install-current-main/preview.json)、[执行结果](/Users/vincent4j/Tools/Source/memsharing-019-evidence-20261106T022519Z/context-keeper-install-current-main/execute.json)、[安装读回](/Users/vincent4j/Tools/Source/memsharing-019-evidence-20261106T022519Z/context-keeper-install-current-main/readback.json)。


## 追加记录 2026-11-06T16:23:11+08:00

- **保存校验：** save-report 返回2，索引内既有 three references 指向已不存在的 six-native-skill-distribution.md（两处）与 desktop-agent-contracts.md（一处）；已对比 HEAD 与本次工作树，同名旧引用未被改动。coverage 显示本日志已索引，4个未索引日志、2个缺会话标识和55个失效链接均属于旧记录，不在本次安装中批量修复。安装本身 configured/读回通过；项目记录保存检查未完整通过，二者分开报告。


## 追加记录 2026-11-06T16:50:36+08:00

- **用户新决定：** CK通用触发规则在已接入memSharing环境中应共享一份，各家仅留必要入口；项目经历仍留项目。
- **范围纠正与事实：** 原先认为只改memSharing集成即可；核对当前CK安装器固定原生rule_files、无共享目标参数，直接移动会被其独立安装/更新写回。可靠最小方案需要CK增加可选共享入口模式、默认独立安装不变，memSharing仅传参与校验。项目明文不修改上游CK源码，因此实现尚未开始，等待用户是否批准本次跨仓库例外。未修改CK源码、未创建新worktree/版本、未迁移真实规则。
- **证据：** 外置context-keeper-install-current-main/shared-trigger-design-gate.json；CK scripts/install.py参数定义；memSharing scripts/agm_core/ck_install.py上游scope校验。


## 追加记录 2026-11-06T17:36:07+08:00

- **范围纠正：** 用户拒绝修改上游 Context Keeper；随后批准仅在 memSharing 实现通用触发共享、更新后复用和归还/卸载恢复。上段所述“必须改 CK”判断已撤回；上游和真实用户文件均未修改。
- **源码交付：** 独立 worktree `/Users/vincent4j/Tools/Source/memsharing-ck-common-trigger` 在第二段截止 09:34:25 UTC 前冻结；作者报告新增15项及相关97项通过，另两套非绿回归在干净HEAD复现同样失败。本主审未重复整批测试，不将作者测试计为独立验收。
- **独立审查与判定：** 嵌套保护/围栏候选、伪必读协议、拆组重复公共正文三项经原反例回放关闭，审计写入尝试0。但 `_consumed_index` 仍接受CK来源替代环 A→B→A，将两条来源标为consumed；归还侧过滤后存在遗漏原文风险。P1阻断未关闭，源码不予验收或部署。正常链测试通过不能覆盖该反例。
- **暂停与续接：** 两名执行者已按原截止停止，不自动换人或续期。后续先修替代关系的真实producer证明和环拒绝，回放原反例并验证正式归还/卸载，再决定发行及精确迁移。当前真实CK配置保持原状，未提交、发布或启用本功能。
- **证据：** 外置 `ck-common-trigger-dev/handoff-second.md`、`frozen.patch`、`frozen-sha256.json`；独立报告 `ck-common-trigger-dev/review/quality-boundary-review.md`（均位于本轮 memsharing-019-evidence-20261106T022519Z 根下）。


## 追加记录 2026-11-06T19:05:44+08:00

- **用户指定接管：** 用户明确要求巴克队长亲自完成；已按现场Profile codex/gpt-6-astra/full-access/medium创建90580c72-4190-4680-8ac5-c38af152a0a9，不再委派。历史耗时保留，接手首个落盘10:56:19UTC、结束11:04:37UTC，未进入第二段。
- **交付与定点核验：** 巴克补齐替代环拒绝、旧manifest指纹承诺和事务before/after/公共producer证明，并修复单家更新卸载假环及Claude受控写回。主Agent读回handoff、原probe修后输出，确认环被ShareError拒绝、写尝试0；现场12个交付文件sha256全部匹配。未重复整批测试。
- **验证边界：** 作者最终CK17、普通共享16、native卸载22、卸载生成3，共58通过；包含多轮写回、单家及最后归还、正式卸载和独立恢复。原4fail/1error与基线相同，未隐藏。此前P1状态由本次修复和原反例拒绝更新为源码/隔离范围关闭；不扩大为真实宿主验收。
- **当前状态：** 源码交付验收通过，未集成主区、提交、发布或迁移真实CK规则；UI及新会话待验。证据为ck-common-trigger-dev/buck/handoff.md、final-sha256.json、after-probe.log及相关最终测试日志。


## 追加记录 2026-11-06T19:08:43+08:00

- 用户明确要求“推送代码”。主Agent已将巴克最终12文件按冻结sha256精确整合到main，整合前main与fresh origin/main均为065eb962；无冲突、无功能再修改。源码自测沿用同字节58项证据。PRD提交前check为initialized/errors0/warnings0、两个inbox均空、diff --check通过；未命中生效合同。
- 本次提交范围为12个源码/测试/PRD文件与本轮已授权项目记录2文件，推送main；不生成payload、不改版本、不部署。实际提交及远端结果以Git和用户最终回执为准。记录save-report既有失效链接未扩修。

- 提交门禁补充：未跟踪测试stage后发现一处行尾空白（此前普通diff未覆盖未跟踪文件）；已仅去除该空白，功能字节无变化，最终以cached diff检查为准。
