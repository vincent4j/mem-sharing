# CK 集成重构验收判定(集成者)

日期:2026-10-30 | 判定:**通过**(经一轮修复)

- 执行者证据:HANDOFF.md + unit.log/integration.log(441 单元/69 集成 OK),测试期间源码指纹不变,pre-b04 证据如实留档;
- 集成者第一轮独立复跑:单元 441 OK;**集成 69 中 1 失败**(integrator-*-round1.log)——CK 路由测试在本机(真实装有 WorkBuddy.app)断言 connected=['codex'] 实得 ['codex','workbuddy'];
- 根因:测试密闭性缺陷,CLI 层此前无探测输入注入口,detect 回落系统 /Applications 泄露宿主机真实执行器;非产品 bug;
- 修复(主 Agent,原执行者会话已关闭):INPUT_KEYS 纳入 search_paths/app_directories/user_candidates(--request-file 注入并随封皮回放);该测试传 app_directories=[];详情见 HANDOFF「验收轮修复」;
- 修后本机全量:integrator-unit.log / integrator-integration.log(441 OK + 69 OK,均 exit 0);
- 抽查吻合:schema=3 严格合同(registry.py:484)、--context-keeper 独立路由与 install-context-keeper 封皮及互斥(install.py:315-349)、B04 修复(claude_active 仅显式 --agent claude,enable.py:399)、§26 白名单 upgrade.py 零残留、mem-sharing:project-experience 标记落位(check.py/enable.py);
- 测试计数变动核对:test-counts.json 逐文件映射 coherent——CK 尾步 +29、provider/四态/旧迁移退役(enable -10/check -16/migrate -15/迁移集成 -3/P 链 -2),升级回归 19→23 保留并扩充;
- 真机项如实 pending:真实 HOME、三家新会话、四会话接力、正式发行身份、CK 上游真实调用链。

结论:达到提交门禁,整包提交。
