# M4-04 主 Agent 验收判定

日期:2026-10-30。判定人:主 Agent(独立复核)。

## 结论:通过

## 独立验证记录

1. 定向:单元 17 项 + 进程集成 2 项(discover 口径)全部 OK;全量 360 单测 + 59 集成通过(注:仓库平铺导入惯例下,须用 discover 调用,以模块路径直调会因 `from test_m403_migrate import ...` 报 ImportError——非缺陷);
2. 七类现场路由:empty/fresh、v0/legacy_copy(confirmed_v0 封皮)、valid_old 与 same/upgrade(拒绝首装覆盖,归 M4-03/07)、future/stop、bad_registry/stop、interrupted/stop,外加"无 V 但有 C/marker 等痕迹→abnormal/stop 不猜 v0";旧产品账本与 v0 内容同在→upgrade+独立 content_candidate,不择一抹掉;
3. 首装:R 标准结构齐备;C=layout.code(H/.local/share/agent-group-memory,新裁定)落位并以 .agm-code-manifest 全树核验;bootstrap 目录/journal/固定工具包(不依赖正在落位的 C);V 最后提交;~/.agents/skills 未搬未接管;
4. v0 一次复制:快照先在 bootstrap 封存再移入 backups/v0-<op>/source;legacy-v0-<op>/ 阅读包镜像三目录,旧 MEMORY.md 原字节双保留,根 MEMORY 换短索引并链接;manifest 五态状态机,终态仅在 V 读回后;同 op 重试/回滚,不换 op 不重复复制;冲突与漂移全停;
5. 授权接口扩展合规:verified_product_source 仅 ContextVar 安装器上下文有效,普通请求拒绝(回归在 test_installer_only_preview_extension_binds_source_and_execution_C,含预览绑定 SKILL SHA256、执行要求 C 存在且指纹相符、普通请求拒绝三断言)——两条绑定条件均落实;
6. 写集合规:tracked 仅 user_entries.py(授权内最小扩展),其余皆新增。

## 未验收范围(留后续)

升级执行(M4-07,含 C 版本切换/回退布局)、独立安装 CLI(M4-08)、真实机器首装/v0 迁移(M4-09/10)、新会话加载、非 macOS。
