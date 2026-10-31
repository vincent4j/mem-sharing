# 双桌面端真实接入与原生验收

## 已核实

- 用户授权先推送源码，再修复 Claude 原生识别与现有引用登记，继续真实升级和桌面验收。
- 适配源码 `bfc6580d3b059263eca76ba18efe955cbe5f07d6` 已推送 `origin/main`，远端 SHA 一致。
- 本机前身为 0.1.1；公共布局预览发现 Claude 已引用公共索引但未登记，按 `unregistered_public_reader` 拒绝，无升级写入。
- 已按用户扩大授权，在前身安装器支持的显式安装清单通道登记已有 Claude 引用：清单取本机签名有效的实际原生二进制哈希，明确非厂商收据。限定候选至已核清的活动安装，未修改 PATH 或断链。入口计划 `changes=[]`，执行 `completed`，Claude 文件原字节完全不变。
- 原生识别修复仅针对 Claude Code Mach-O，要求 Apple 证书 anchor、Anthropic Team `Q6L2SF6YDW` 与产品 identifier `com.anthropic.claude-code` 共同通过静态 codesign 验证；不启动二进制、不从目录猜产品版本。原 npm 路由与失败候选汇总为 unknown 的规则保持。
- 实际活动 `.local/bin/claude` 签名检测 `installed`；默认 PATH 另有断链，因此默认全量结果仍可为 `unknown`，安装时需显式选择已核清的活动安装范围。

## Claude 识别修复回归

- 定向：`test_m405_detect` + `test_m405_user_entries` 共 73 项通过。
- 全量：unit **586/586**，318.839 秒；integration **74/74**，118.229 秒，均退出 0；合计 **660** 项，不叠加定向计数。
- 原始日志位于 `/tmp/memsharing-claude-native-unit.log` 和 `/tmp/memsharing-claude-native-integration.log`；摘要哈希见同目录 `claude-native-tests.json`。Python 3.9 语法与 `git diff --check` 通过。

## 原生界面准备

章教授使用 Codex Computer Use 的应用清单看见两款桌面端均运行中，但应用绑定分别约 30 秒和 45 秒工具超时，未获得窗口状态。没有创建会话、发送模型提示、读取现有会话或改账号设置。两款的新会话、用户规则/项目规则读回与 Skill 加载均为 **blocked/pending**，不以安装成功替代。

## 真实安装结果

- 修复来源 `ea553738f37a5cc5befb34bf241d12da33f07b21` 已提交并推送，远端核对一致；产品版本保持 **0.1.3**。
- 从干净来源生成精确 `0.1.1 → 0.1.3` 公共布局转换预览，34项变更，用户授权绑定完整新计划后执行 `completed`。迁移前重新核验未登记公共读者为空；不复用此前拒绝的批准。
- 随后单独接入 `dsh/zcode`，预览仅更新两家用户 `AGENTS.md`，执行 `completed`。最终五家登记入口均为静态 **connected**；入口连接与运行加载分开判断。
- 已安装来源与代码标记一致，内容树 `445ca1962546d18fedd97c930f81bf1cc4a622ab531696cb4a7161f477b80a9a`。
- DSH/ZCode/Claude 原正文仍是现文件完整前缀；Codex/WorkBuddy 的受管块以外原字节完全相同。原文只留本机受限证据目录，不上传仓库。
- 重复接入只读预览 `changes=[]`；观察路径的内容与mtime均不变。未登记公共读者仍为空；没有创建项目登记或 Context Keeper 库。两次产品尾步均因非交互跳过 Context Keeper，未调用上游安装器。
- [实际后检](real-postcheck.json)、[操作摘要](operations.json)。机器事务原始计划/批准/报告与用户文件备份在本机受限目录及安装器自有恢复日志中，摘要不包含私人正文。

## 当前边界

源码、推送、真实升级、双端用户入口接入和静态/幂等检查已完成。双端桌面原生新会话、用户及项目规则读回、共享 Skill 实际加载仍 **blocked/pending**，原因是 CUA 应用绑定超时。没有创建污染性临时规则/Skill/项目或绕用 CLI 冒充桌面验收。后续需先恢复 CUA 对应用窗口的访问，再按专用新会话验证；不改账号、模型或安全配置。
