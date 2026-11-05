<!-- context-keeper: session-id=01a1ab52-60ab-7aa0-824d-db2cbd103842 -->
# Context-Keeper-实时获取-main-与全称

## 2026-11-05T19:06:22.836764+08:00

- 用户要求：安装 Context Keeper 时实时获取其官方 main，不绑定固定版本，不将上游源码内置于 memSharing；面向用户一律使用全称。
- 用户另行澄清：要把 mem-sharing 自身 main 更新合并到当前分支。实际 fetch 后本地 main 与 origin/main 均为 aacfd1d9，当前 verify/skill-first-runtime 已快进到该提交。主 checkout 的四个未提交文件未触碰，本轮修改以 stash 85203a41 保全后恢复，三处冲突按最新要求解决。
- 实现：Python 与 Paseo 获取当前 main；当次提交只绑定本次计划，保留来源、漂移、私文与失败保护。六家参数、共享目录去重、卸载历史审计兼容同时保留。Context Keeper 源码保存在独立目录，不写入本仓库。
- 验证：实际重新获取上游 main 86af1507，在隔离 HOME 用真实上游安装器六家配置成功（7 Skill 入口/6规则）。真实上游两项隔离归还/恢复测试通过；六家实际 producer 的卸载审计验证通过。Python 首轮两项旧夹具期望失败已纠正；首次真实验证使用 /tmp 未解析 canonical 路径被拒，改用 resolve 后成功；合并后曾出现 Agent 顺序期望不一致，已按上游顺序修正。Paseo 22项定向测试通过，类型检查通过；当前最终 Python 合并后回归正在收尾。
- 边界：未安装或修改真实 HOME 的 Context Keeper；未改其上游源码。未提交、推送或部署本轮改动。证据在 /tmp/msf-context-keeper-*，真实上游 isolated 输出为 live-main-isolated-second.log、live-main-exit.log。

### 最终回归
- 合并后50项发现：48通过、2项可选真实producer测试跳过；先前真实上游两项另轮已通过，不拼成全量。Paseo 22项通过，最终类型检查、PRD检查和diff检查通过。
- save-report 返回2，原因是项目记忆原有链接失效（six-native-skill-distribution.md、desktop-agent-contracts.md）。本轮新日志与主题链接已写入，未为校验通过改写历史记录，不宣称保存校验通过。
