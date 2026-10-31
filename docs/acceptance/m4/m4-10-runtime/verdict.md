# M4-10 当前判定与证据索引

更新：2026-10-31。**M4-10 部分通过，M4 整体不关闭。** 已部署基线为 `04c32e24b9ab9504514908f2368cddca4356e478` / 0.1.1；后续仓库收尾不等于再次部署或发布。

## 当前状态

| 验证层 | 判定 | 证据与限制 |
|---|---|---|
| 本机 0.1.0 主装与 v0 导入 | 已有记录 | [前轮日志](../../../context-keeper/worklogs/2026-10-31-M4-10真机安装与仓库整理.md)；用户选择本机路线，不能称独立用户/VM 隔离首装 |
| WorkBuddy 0.1.1 源码修复与窄合同升级 | 本地回归及历史真机部署通过 | [部署报告](workbuddy-live-deployment.md)、[读回](workbuddy-live-readback.json)；474 单元/74 集成是该冻结版本的历史结果 |
| WorkBuddy 入口及私人字节保全 | 静态通过 | 27 产品文件 hash、原私人 5788 字节前缀及 CK 块、保护入口/公共索引、台账/收据读回；不含新会话证明 |
| Codex CLI 0.162.0 公共规则/已有项目规则 | 限定范围通过 | [Codex](codex.json)；公共索引/主题工具读取与随机答案匹配，已有 AGENTS 行为与字节保全 |
| Claude CLI 2.1.295 公共规则/已有项目规则 | 限定范围通过 | [Claude](claude.json)；主题实际 Read，索引原生导入；项目标记行为成立，没有独立 AGENTS 工具读取事件 |
| WorkBuddy 修复前手动新会话 | 未达到验收条件 | [可见回答](workbuddy-manual-result.md)无 PUBLIC/PROJECT 字面标记，读取仅回答自述；不能推断不可见工具链不存在或根因已知 |
| WorkBuddy 部署后新会话 | blocked，用户暂停 | Computer Use `cgWindowNotFound` / 旧 Raise 元素失效后停止；未发送新提示，未新增临时规则 |
| keeper 安装尾步 | 实际尾步未复验 | 独立 keeper 安装已有记录；0.1.1 `_scene` 只读通过，未再次调用安装，不等同真实尾步成功 |
| CK 首次激活/自动入口/四会话接力 | pending，用户暂停 | 本轮不重启；已有规则只读验收不能证明缺失入口自动生成或新库写入 |
| Windows/Linux、缺依赖自动安装、隔离首装 | 未验 | 不以本地 Python 回归替代 |

## 缺陷状态

- **D-M4-CK-WB：** 旧版整文件保留导致没有 WorkBuddy 登记入口，与 keeper 尾步前置条件冲突。源码及合成组合已修、正式 0.1.1 已部署、只读前置已过；剩余关闭条件为实际尾步验证。不能再称“尚无修复/未部署”，也不能称全缺陷已关闭。
- **R-M4-WB：** 旧版缺少公共索引指针，现有入口与静态接入已修并读回；公共实读仍待独立新会话证据。
- **项目标记缺失：** 修复前可见回答未呈现项目标记；尚不确定是规则执行、输出或界面提取问题，不能用安装器修复推断已解决。
- **发行转换阻断：** dirty source 与旧 `entries=preserve` 合同限制曾阻止升级；固定来源、窄转换处理器与正式升级已解除这两个历史阻断。成功升级后不承诺自动降回旧版。

## 历史过程与来源

下列材料是当时的原始操作或诊断记录；其中“当前”“未部署”“待批准”仅指该阶段，不替代上表。

1. 初轮只读夹具与公共主题：[checks](checks.json)、[fixture](fixture.json)、[prompt](prompt.txt)、[public-topic](public-topic.txt)。Codex session `01a18f59-3aec-7c40-94a2-a5bf2fbe841a`、Claude session `85bdc56b-8380-4425-a1ca-d150ebeccd0e`，均 exit 0。未创建 CK 库、CLAUDE 或 WB 原生目录；权限只读，不能证明自动写行为。公共索引随后[原字节恢复](cleanup.json)。
2. WorkBuddy 两次自动化未发送：[初轮](workbuddy.md)、[续测](workbuddy-continuation.md)、[续测恢复](workbuddy-continuation-cleanup.json)。用户随后提供首轮 e4198600674e 截图，项目标记行为匹配，但公共主题已不存在且提到 manifest，来源污染不能排除；不是“用户从未执行”。
3. 用户手动新会话 `62c1da664d93` 已执行并取证：[可见转录](workbuddy-manual-result.md)、[合成夹具](manual-fixture.json)、[临时主题](manual-public-topic.txt)、[恢复](manual-cleanup.json)。主题保持有效直至对应回答取回；不能归因于提前撤规则。没有重发提示。
4. [诊断](workbuddy-diagnosis.md) → [源码修复/冻结回归](workbuddy-fix-verification.md) → [升级准备与当时阻断](workbuddy-live-plan.md) → [正式部署/静态读回](workbuddy-live-deployment.md)。部署中首次 UTC `+00:00` 格式拒绝发生于写入前，旧操作未重放；新唯一操作 `wb-public-index-011b` 使用 Z 时间成功。
5. 本轮收尾另见[仓库质量报告](../../release-review.md)。它只验证本地源码与静态材料，不扩大上述运行证据。

## 证据保全与适用范围

CLI 事件按合成任务白名单保留，完整筛选前流只留关联 hash，不能称完整原流仍可复查；不保存账号元数据、思考内容、无关私人正文或供应商诊断载荷。历史自动记忆注入未整体关闭，因此不宣称全环境无历史上下文。临时公共源每轮按原字节恢复，测试标记已失效，不用于后续盲测。

原始私人备份仍在仓库外受限目录；仓库只保留脱敏摘要、hash、合成数据。历史 CK 日志保持原文，仅当前主题更新。本轮已按用户指令暂停 WorkBuddy 新会话、CK 真实激活、自动入口及跨客户端接力；恢复这些活动须新的明确指令。
