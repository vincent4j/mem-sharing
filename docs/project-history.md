# 项目历史与文档归并记录

本页为有用阶段结论的历史摘要，不是当前全部通过清单。当前结果看[项目现状](project-state.md)与[Windows验收](windows-acceptance.md)；有效产品要求看四份核心PRD及Windows PRD。失败/未验按当时结论保留，不把旧候选身份当当前部署。

## 关键演进

- 早期M1验证了部分跨执行器读回链路，但WorkBuddy负向与P2/P3偏差未齐；M2复制/幂等及原文前缀保全有实证，部分真实新会话仍待验。测试数量/提交说明不自动成为模型行为通过。
- 2026-10-31形成公共与专属记忆分层、普通薄Skill和独立执行器接入；移除Codex依赖。项目规则归memSharing，项目经历归Context Keeper；两者不混存。
- 全机卸载先精确归还/保全用户记忆，再处理已声明资产；未知来源、foreign改动和不完整producer链保场。自然语言卸载仍走同一预览/批准流程。
- Paseo经历过loader running而payload missing、活动旧CLI不支持preview的真实反例，后经来源绑定/精确升级修复；running和合成测试不能代替业务接入或模型读取。
- 发行保持干净固定S、精确R、闭包与hash一致；无同版异源替换，不用动态候选冒充正式载荷。真实安装、源码推送和registry发布分别验收。
- CK通用触发只保留一份公共正文，六家native文件仅去相同正文、其他字节/入口保留；初次错误选择、相邻保护块及归还修复保留为失败与修复链。核心PRD已承接当前合同。
- Windows最初原生共享/rename反例、ACL/CF失败保留；转有限产品目标后完成DELL两家真实预览闭环。一般R2仍partial，不以文档/官方资料代替真机。详见[分层验收](windows-acceptance.md)。

## 原时间线的有用摘要

以下保留原计划的任务范围与当时结果；没有新的宿主复验，不恢复为当前待办。

### 2026-11-09 - Windows-DELL敏感目录往返与真实别名 `acceptance`
- **任务：** 连续完成R2；敏感目录闭环/短名已限定主审通过，临时映射已恢复；权限/CF/SDK仍待验。
### 2026-11-09 - Windows原生句柄只读底座与反例 `implementation`
- **任务：** Win32只读身份/NTFS/reparse与权限快照已实现；原生r2为13/14 exit1，未开放生产。
### 2026-11-08 - Windows平台安全切片 `implementation`
- **任务：** 已批准实施；只读平台诊断、Windows路径语法及节点保守分类、隔离测试/CI准备；生产Windows仍待验，目标存在、连接以后提供。
### 2026-11-08 - Context Keeper通用触发真实共享准备 `memory`
- **任务：** 核对真实未迁移、修相邻保护块误判并生成六家共享零写方案；待选择，不冒称迁移完成。
### 2026-11-07 - Paseo页面体验改进与真实界面验收 `ui`
- **任务：** 状态与共享流程三客户端文件改版、统一检查/独立审查和原生只读页面验证。
### 2026-11-07 - Paseo插件文案同步与发行前核验 `review`
- **任务：** 文案同步、固定源码审核导出与统一检查、原生UI只读核验；正式载荷仍待新S及版本。
### 2026-11-07 - Paseo插件剩余工作核对 `review`
- **任务：** 核对主线与载荷六文件差异、融合文案和真实验收待办；未操作宿主。
### 2026-11-03 - Paseo插件展示名与README前部更新 `docs`
- **任务：** 插件展示名改 Memory Sharing & Fusion（id/指令/协议不变）；README 前部补六家支持与 Paseo 插件一句话；删除 README/OVERVIEW 平台实证与未验提示（中英）。
### 2026-11-03 - Paseo 0.1.6 原生界面只读验收 `acceptance`
- **任务：** 按步骤验收新安装的 0.1.6 Paseo 插件；Paseo 运行中但 CUA 无可绑定原生窗口，本轮界面/读链 blocked，未改变现场。
### 2026-11-02 - 0.1.5最终候选pin完整并发回归与S指定 `test`
- **任务：** S 542f248 回归 859 通过、R 417e1637 门禁全过后，用户两次确认真实机器升级 0.1.5 一次 exit 0（21.46s，25 变更/162 新增/1 删全归因，私文与 CK 保全，证据 x1cb3x23）；后续 migrate-policy preview exit 2 uninstall_conflict 与 Claude 入口 baseline drift 只读调查中，六家/Paseo/真实卸载恢复 pending，R 未 push/发布。
### 2026-11-01 - 整机卸载与自然语言入口实现 `implementation`
- **任务：** 实现独立归还、外置恢复、宿主义务与自然语言卸载预览，记录分层验证及真实运行边界。
### 2026-11-01 - 旧共享目录退役 `maintenance`
- **任务：** 迁移6处旧入口引用，保全后移除 `~/.agents-group` 原路径并验证。
### 2026-10-31 - Paseo插件单仓双入口调研 `research`
- **任务：** 核查官方插件开发与发布要求，明确同仓双入口诉求与候选方案。
### 2026-10-31 - 双桌面端源码固化与真实接入 `deployment`
- **任务：** 用户批准源码固化、真实接入与桌面验证，按精确安装门禁执行。
### 2026-10-31 - 收尾审核问题修复 `fix`
- **任务：** 修复审核1项P1与2项P3，补回归并复核，不安装或提交。
- 2026-10-31 `review` 双桌面端收尾审核（含调度纠正）：用户要求巴克队长审核；原8人解读已撤回，已结束3份报告作为参考，后续由主Agent收尾。；详见 [日志](project-history.md)
- 2026-10-31 `implementation` DeepSeek Harness 与 ZCode 桌面端适配：核实原生读取合同并并行实现两款桌面端的 memSharing 适配。；详见 [日志](project-history.md)
- 2026-10-31 `implementation` 公共记忆分层与独立执行器接入：精简公共索引、专属规则归位、支持不安装 Codex 的组合并验证精确迁移。；详见 [日志](project-history.md)
- 2026-10-31 `review` 发布前收尾质检：本地源码/安装文档/证据审查，保全后删合材料并修复发布质量问题；真实验收保持暂停。；详见 [日志](project-history.md)、[质量报告](https://github.com/vincent4j/mem-sharing/blob/0906d7acea8f0f1dc02ddef734f90322a8180579/docs/acceptance/release-review.md)
- 2026-10-31 `milestone` M4-10真机安装与仓库整理；详见 [日志](project-history.md)
- 2026-10-30 `implementation` M4-02 统一运行态与产品台账：路径解耦、schema=2 兼容模型及三命令接线；隔离回归单元 250 / 集成 53。；详见 [日志](project-history.md)
- 2026-10-29 `milestone` M2-09 平台矩阵与发布前文档：M2 收官——平台矩阵、本仓库真实卸载/重装/失败恢复演练、README/SKILL 发布文档、281 项测试全绿。；详见 [日志](project-history.md)
- 2026-10-29 `test` M2-08 重跑装配与新会话验收：两项目真实装配、幂等、dirty保留及新会话读回；整体部分通过，待WorkBuddy。；详见 [日志](project-history.md)
- 2026-10-29 `test` M1 负向验证与收口：汇总 M1-01～07、四环证据、负向验收与 M2-02/03 进展；来源为主 Agent 收口汇总。；详见 [日志](project-history.md)
- 2026-10-29 `test` 三执行器记忆接力测试（WorkBuddy 第三环）：恢复 F1/T1，完成接力验证待办，新增唯一事实 F2 并落库。；详见 [日志](project-history.md)
- 2026-10-29 `test` 三执行器记忆接力测试：保存本次测试标识、纸鹤颜色和未开始的验证待办。；详见 [日志](project-history.md)
- 2026-10-29 `legacy` 仓库创建与设计演进（legacy）：M1-05 单份可公开存量样本搬运——本仓库建仓至 M1-04 的演进事实自公开 git 历史入库。；详见 [日志](project-history.md)

## 2026-11-10 扁平归并与Git授权

用户要求删除三目录、把全部有用文档直接归并docs根。先将106份当前文件（含untracked/旧日志/原JSON）完整快照并机器回读；原始内容、SHA与dirty归属清单在：

`/tmp/memsharing-docs-flatten-94cd7dce-a55f-4811-a986-f81a8b561252`

核心产品要求完整迁入安装/共享/项目规则/卸载四PRD；Windows有效要求与完整路线分开；23原证据JSON保留全部结构化内容到windows-evidence.json，带原始size/SHA；私有截图/原始SD及测试值不进仓库。未在仓库另建archive。代码冻结不随文档改动，冻payload不回填。

巴克负责最后独立验收及一次feature提交、推feature、main快进合并和推main。用户已授权；在Git实际完成前本页不写虚构结果。无发布、无真实环境变更。此处记录是用户明确退出旧CK目录后的扁平项目记录，不调用旧初始化流程。

归并收尾检查：106份输入均有根文档归属；23份证据JSON内容/原始size与SHA均保留；31个本轮scripts/tests冻结未变；24份维护Markdown的131个本地链接无断链，三个目录均不存在。PRD工具返回not_initialized是用户退出后的预期，不当作结构通过；不运行CK初始化/旧save-report重建目录。Git提交推送及主分支合并由巴克接手实际执行。
