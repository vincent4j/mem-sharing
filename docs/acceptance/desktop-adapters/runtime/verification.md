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

## 当前边界

本文件为阶段证据。真实升级、DSH/ZCode 接入、原生新会话和共享 Skill 实际加载待后续追加实际结果。不能用源码/合成测试代替桌面运行验收。
