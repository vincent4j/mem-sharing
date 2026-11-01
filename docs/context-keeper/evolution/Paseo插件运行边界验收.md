# Paseo 插件的真实运行边界验收

- **编号：** CK-PASEO-001
- **状态：** 已验证
- **触发条件：** Paseo 插件源码测试或 loader 显示 running，准备判断载荷、项目接入或记忆读取可用。
- **已知事实：** 本轮两次不同边界的真实操作纠正了测试结论：实际 CJS loader 丢失源码位置，running 时 payload 仍 missing；修复来源绑定后，活动旧版 memSharing CLI 又拒绝 --preview。分别经真实 env.status 与项目 enable.preview 发现，并在来源绑定修复、获授权更新机器版本后关闭。不能用合成环境或 loader ready 替代这些检查。
- **证据位置：** [完整过程](../worklogs/2026-10-31-Paseo插件单仓双入口调研.md)、[当前 Host 分层验收](../../plugin-adapters/paseo-current-host-acceptance-20261101.json)、[独立收尾审核](../../plugin-adapters/paseo-closeout-review.md)。原始 loader、升级及项目 RPC 路径由这些记录定位。
- **建议动作：** 先在实际宿主只读检查 payload 的持久路径及编译期摘要，再经实际插件生成项目预览，确认所调用活动程序支持批准合同；有旧版兼容问题按精确升级计划处理，不去掉预览或绕过来源门禁。经批准接入后另启新会话实际读取用户与项目记忆；运行证据和台账字段分开，不手改 runtime_acceptance 冒充实测。
- **适用范围：** 本机 macOS / Paseo 0.13.2 开发候选和本轮 memSharing 0.1.4 既有机器接入。尚未证明全新机器缺依赖宿主全链、其他平台、所有 provider 或未来 Paseo loader 版本。
