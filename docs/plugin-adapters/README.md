# Paseo 插件维护手册

本目录维护现行适配合同和[验收记录](acceptance.md)。产品本体的合同、事务和使用方法分别见[设计](../../DESIGN.md)、[系统架构](../architecture.md)、[操作手册](../operations.md)。面向插件用户的说明保留在[OVERVIEW](../../plugins/paseo/OVERVIEW.md)。Orca 未实现，不属于当前交付范围。

## 单仓与发行来源

Python 业务只维护 `scripts/agm_core`，项目与机器入口分别为 `scripts/agm.py`、`scripts/install.py`。Node 公共代码只维护 `plugins/shared/src`，通过 `sync-to-plugins.mjs` 生成到 `plugins/paseo/server/shared/common`；许可披露同步进入插件目录。宿主子目录不依赖安装后的父仓库文件。

源码提交 S 必须干净且固定完整 SHA。生成器从 S 的八份受管文档与 scripts 集合生成 `payload/core`、`payload/release.json`、根 `release/core-release.json` 和 `server/shared/release-identity.ts`。R 仅包含允许的生成变化，S/R 的受管字节和模式必须相同。内核身份记录 S，获取来源记录 R；摘要校验只证明完整性，不自证官方来源。开发 identity 保持空哨兵，不能手填摘要使开发目录冒充发行。

生成、重生成和 CI 的准确步骤统一在[发行工具说明](../../tools/plugin-release/README.md)。普通 Git 安装与插件使用相同源身份和版本库存。版本来自获批发行输入，不从插件版本推断；同版异内容、未知前身、缺精确 conversion 或未来版本继续由原内核拒绝，不提供降级/同版覆盖捷径。修改受管文档也改变产品树，后续发行须重新生成与核验，不能继续使用旧 S/R。

## 宿主适配

最低 SDK/manifest 为 Paseo 0.13.2，当前只有 Command Center、一次性计划界面和 typed RPC，无常驻管理页、无自动 hooks。workspace 命令提供项目路径，执行器由用户选择；Paseo 是宿主，不是新增 Python Agent 类型。linked worktree、非 Git 项目及 disabled 政策沿用内核，插件不能默默改写主 checkout 或恢复自动记忆。

宿主用受支持的 `context.paseo.config.get().config.plugins` 定位自身包；只消费 plugins，不记录其他配置。固定包 ID `memsharing` 与编译期 manifest 摘要、完整载荷字节/模式、唯一 canonical 来源共同绑定。CLI runtime 别名不等于包身份。每次 RPC 复验；来源/环境漂移闭锁并取消七类 flow，要求重载后重新预览，不重建 Orchestrator 来继承旧批准。

## 接入与批准

用户目标是仅安装插件、在宿主内确认即可接入，不先普通安装、不另开终端。当前实现为命令驱动，不能承诺安装即自动发起向导。

1. 检查现有 Python≥3.9、Git、发行载荷与机器状态；缺工具时单独展示固定官方资产及目标路径，用户确认后准备私有依赖。
2. 从当前包调用原 `--release-request` 解析器；必要时独立批准持久 export，然后用返回的 `--source-manifest` 形成机器计划。历史 export 仅可作为恢复候选，不能绕过当前包验证。
3. 展示原内核精确计划、完整 JSON 和政策转换，确认后执行。相同计划的 digest 可相同；一次性 confirmationToken 另绑定 nonce、host/HOME、argv、内核树及资产场景，旧预览/跨 worker token 不可复用。
4. 项目接入复用原内核预览和批准。历史 disabled 仅作规则接入 tombstone，不表示 CK 停用；不把已退役 `remove-memory/--memory/--no-memory` 当作可用新请求。原生入口按当前 Agent 实际使用补齐。

拒绝计划不执行其业务写入；宿主可保留私有 request/operation 证据，不承诺整个文件系统绝对零写。机器状态只由原 R/C/V、库存、锁和 journal 管理，宿主辅助状态不是第二套台账。

## Python/Git 供应

固定来源真源是 `plugins/shared/src/production-assets.ts`；RPC 和用户环境不能覆盖 URL/hash。当前资产为 CPython 3.13.18（python-build-standalone 20261026）和 Git 2.56.0（dugite-native v2.56.0-2），含 arm64/x86_64 的 size、SHA256、解包树摘要、入口与精确链接表。目标最低 macOS 为 arm64 11、Intel 10.15；目标存在不等于全部动态平台已验。

依赖存放于 HOME 内 `mem-sharing-runtimes`，不改系统 Python、全局 PATH 或 Git 配置。下载、容量、解包链接和完整树检查通过后还要实际 probe 才写 verified；漂移、未知所有权或冲突保全拒绝。取消仅处理自身 inode 匹配的 lease/暂存；保留可审核的中断材料，重试要新计划。许可与对应源码见[运行时披露](../../plugins/shared/THIRD_PARTY_NOTICES.md)，17份 sidecar 不代表完整 transitive SBOM。

## 所有权、取消与恢复

R=`~/.mem-sharing`、C=`~/.local/share/mem-sharing`、V=`~/.mem-sharing/var/registry.json` 是唯一活动产品。载荷获批后导出至 `~/.local/share/mem-sharing-sources/<version>/<tree>/`；恢复不能依赖会被移除的插件目录。

运行取消终止本操作进程组，但不能承诺即时回滚；结果未知时保留原 journal。恢复仅选择与原 journal source/tools hash 匹配的 CLI/toolkit，再走原继续/回滚批准。V 提交后的收尾与成功安装后的主动降级不是同一操作，不自动抢锁或回放旧计划。插件卸载不删除产品、公共记忆、用户入口、持久源、已用运行时或 CK。

## Context Keeper

CK 是独立可选 Skill，固定 pin 为 `695074ee4b6ddb9999be858093f833d6377bd641`。来源获取先独立批准，持久 clean checkout 验证后再调用原上游安装器，安装批准单独进行。拒绝/失败不回滚 memSharing，不自动建项目记录库。

当前上游安装支持 Codex、Claude Code、WorkBuddy，DSH/ZCode/OpenCode 按不支持跳过。宿主 enabled、Skill 链接存在、原生新会话实际读取和首次命令/保存是不同证据。无项目聊天、disabled、linked worktree 和首次 `/context-keeper` 规则继续生效，不用插件 hook 模拟自动保存。更新/卸载插件不升级或接管 CK。

## 维护验证与历史

只针对改动执行所需检查：common/notice 修改运行 sync 一致性测试，宿主修改运行相应 Node 测试与 SDK typecheck；内核改动按项目 Python 测试规定验证。发行前执行 source/release CI，不以合成通过代替真实宿主批准或新会话。

旧设计、任务拆分、v1-v5/r1-r2日志与hash清单不再作为当前输入；完整历史保存在 Git `0906d7acea8f0f1dc02ddef734f90322a8180579`。例如 `git show 0906d7a:docs/plugin-adapters/design.md`。CK 历史中的旧相对链接按同一提交和原路径追溯，不能把已删过程文件当作证据从未存在。
