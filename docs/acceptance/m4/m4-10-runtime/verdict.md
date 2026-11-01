# M4 暂停验收与续审位置

更新：2026-11-01。这里保留尚未完成的人工验收状态；当前机器已更新至0.1.4，不再以历史0.1.1部署当作当前版本。**WorkBuddy新会话、CK首次激活、自动入口与四会话接力仍按用户暂停处理**，整理文档不恢复其执行授权。产品/Paseo后续证据见[验收总览](../../index.md)。

## 已有证据与边界

- 本机0.1.0安装及v0导入为历史本机路线，不是独立用户/VM首装。
- WorkBuddy 0.1.1修复已真实部署：公共指针/登记入口与私人5788字节前缀、CK块保全，固定27文件与台账读回成立。旧整文件保留造成的入口/keeper前置冲突已修；CK实际安装尾步与修复后公共实读仍未复验，不能称缺陷全闭合。
- Codex CLI0.162.0 session `01a18f59-3aec-7c40-94a2-a5bf2fbe841a`：公共索引/主题工具读取及随机答案匹配，已有项目规则行为和字节保全。Claude CLI2.1.295 session `85bdc56b-8380-4425-a1ca-d150ebeccd0e`：主题实际Read、索引原生导入与项目标记行为；没有独立AGENTS工具读取事件。两者均exit0，未证明缺失入口自动生成或CK建库。
- 用户曾提供首轮 `e4198600674e` 截图，不能称从未执行；但主题当时已不存在且答案提到manifest，不能排除来源污染。
- 手动任务 `纸卡核验-62c1da664d93` 已于2026-10-31取回。WorkBuddy5.9.3，会话标题“纸卡核验规则文件整理”，项目空间workbuddy，用户确认项目 `/tmp/mem-sharing-m4-runtime-20261031/workbuddy`（实际回答用 `/private/tmp/...`）。可见结果未出现PUBLIC/PROJECT字面标记，读取路径只有回答自述，session-id与独立工具事件不可见；不把不可见推断为根因已知。完整原提示/转录在Git历史，不用旧答案污染新测试。
- 修复部署后的自动续测在窗口 `cgWindowNotFound` / 旧Raise元素失效时停止，没有发新提示，未新增临时规则。2026-11-01的Paseo新Codex读回不能替代WorkBuddy或四会话接力。

## 现场与恢复状态

人工项目曾保留在 `/tmp/mem-sharing-m4-runtime-20261031/workbuddy`；此处只提供续审定位，本轮未检查、重建、启动或删除该目录。后续先核对它是否仍存在以及是否有新用户修改，不盲跑旧命令。

旧续测 `纸卡核验-6ab436d62882` 未发送。公共索引在2026-10-31T00:35:56Z恢复，临时主题撤除。手动62c任务结果取回后，于01:16:31Z恢复索引并撤主题；before/restored SHA均为 `b86fbc67104aedec142c66c8d421204e2c5190ea7f19524377a5b777303d135b`。不存在仍需等旧回答而保留临时公共规则的待办。测试标记已失效，不复用于盲测。

原私人备份、机器journal/库存位于仓库外受限目录；本文不是恢复脚本，也不授权自动删除、抢锁、重放计划或已提交版本降级。

## 恢复验收时的最小步骤

仅在新的明确指令下执行[运行验收规格](../m4-10-prep/release-checklist.md)：重新核对当前产品版本、项目与新会话身份；通过章教授inspect→action→verify取得可读窗口后才发送一次新合成任务。不可读就blocked，不换CLI冒充桌面。公共临时规则结束/阻断后按before恢复；来源不明或提交结果未知不重发。

需要独立验证：WorkBuddy用户公共读取及项目约定、CK独立安装尾步/首次激活、默认缺失入口生成、禁止保存/迁移门禁/disabled、Codex→Claude→WorkBuddy→Codex四会话接力。日志必须区分工具事件、原生注入与回答自述；已存在规则的只读证明不等于自动写行为。

## 历史原件

以下均可用 `git show 0906d7a:<路径>` 取回：

- `docs/acceptance/m4/m4-10-runtime/workbuddy-manual-result.md`：人工转录与定点复核。
- 同目录 `manual-fixture.json`、`manual-cleanup.json`、`workbuddy-continuation.md`、`workbuddy-continuation-cleanup.json`：原任务与恢复回执。
- 同目录 `workbuddy-live-deployment.md`、`workbuddy-live-readback.json`、`codex.json`、`claude.json`：部署及规则读取证据。

完整失败、诊断和修复沿革由Git及只追加CK日志保存，不在工作树维持失效的hash清单或临时测试正文。
