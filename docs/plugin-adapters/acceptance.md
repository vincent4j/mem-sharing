# Paseo 验收记录

更新：2026-11-01。**0.1.5 固定发行候选 R 已生成并通过当前 Host 的真实加载与只读状态验收；尚未完成目录上架、截图和全新机器缺依赖的宿主首装全链路。** 该 R 固定于 S=`e1a7c391…`（2026-11-01），不含其后合入维护 HEAD 的六家选择器与卸载三模块；最终新 S/R 尚未生成，现行整体待验范围见[上线前清单](../acceptance/release-readiness.md)。当前实现与维护边界见[维护手册](README.md)。下表区分不同冻结时点，不把重叠用例数相加。

| 层次 | 已取得证据 | 范围与未验项 |
| --- | --- | --- |
| Python 最终整合快照 | unit606/606、integration75/75，exit0 | 11月1日当前 Python 内核；临时 Git/HOME，不是原生UI |
| Node 供应增量 | shared89/89、宿主定向27/27、SDK0.13.2 typecheck | 官方 arm64 原包经localHTTP→独立资产确认→export→机器安装的临时HOME闭环；非真实宿主缺依赖首装 |
| payload v3 | 定向11/11、SDK检查、安装包CJS compiler/evaluator通过 | 包ID与runtime别名分离、配置/载荷漂移拒绝、取消七flow；旧v1/v2失败不作为最终通过 |
| 生成与CI | common/notice/空哨兵4项通过，S/R只读检查已审 | 供应61与payload覆盖形成64项增量、另CI2项曾匹配冻结；不是10月31日原64项清单 |
| 历史开发runtime | payload.ready，持久来源加载、编译期摘要匹配 | `memsharing-synthetic-dev`，包ID memsharing；非正式发布 |
| 本机产品升级 | 原安装器0.1.3→0.1.4 completed，精确preserve转换，16记忆/入口节点保全 | 用户核验的clean本地d14来源；不能称插件自动升级或官方远端发行 |
| 插件项目接入 | 主checkout新preview→confirm completed，codex/follow_ck，registered且errors空 | 新preview不是全新机器；AGENTS原正文及16节点保全 |
| 新Codex会话 | 用户MEMORY与项目memory-keeper实际读回，CK resume/check退出0，无写入 | 主checkout与worktree记忆不同，没有当前Paseo主题命中；不代表其他provider或CK远端激活通过 |
| UI | 用户确认⌘K可打开 | 用户已将 Paseo 主窗口前置，CUA 新鲜复核仍超时；未保存真实截图，也未取得完整Modal/拒绝/取消/断连自动UI验收 |

## 0.1.5 固定发行候选与当前 Host 验收

本节记录固定发行提交，不把后续维护文档提交或分支未来 HEAD 当作新 R。S=`e1a7c3911dcae93f99f32d2b294074f3369b34f0`；R=`6ab3129c992656c5b8ab99ab913eba87d484df00`，唯一父提交为 S。产品候选版本 `0.1.5` 经用户批准；来源 URL 为 `https://github.com/vincent4j/mem-sharing`。本地 clean checkout 取得 R 后设置官方 origin，核验本身不是远端获取或正式上架的证明。

| 证据层 | 本次结果 | 范围 |
| --- | --- | --- |
| clean S source gate | exit0，4/4、0 skipped，12 common 模块 | common、notice 同步与开发 identity 空哨兵 |
| 双次外部生成 | 35 文件字节与模式完全一致，S 保持 clean | 仅根 manifest、Paseo payload、生成 identity 三类路径 |
| clean R release gate | exit0，3/3、0 skipped；checkout_delivery 通过 | 固定 clean/pin、S/R 祖先及受管集合/字节/模式、闭合载荷与编译期摘要 |
| 巴克独立只读审核 | 主 Agent 收到限定通过回执，未发现具体阻断 | 直接读 Git S/R blob，核 35 生成变化、32 受管文件、manifest/identity 和包内依赖闭包；不含宿主安装、新机器或截图 |
| 子目录归档 | 88 文件，解包后全部文件字节/模式及目录模式与 clean R 一致 | 仅 `plugins/paseo` 内容，含 icon、OVERVIEW、17 份 notice 与闭合 payload，无 node_modules 或父仓库源码 |
| 当前 Host 真实 R | plugin running、loader `Plugin ready`，真实 `env.status` 的 payload/identity 均 ready | 仅替换既有 runtime alias 的来源；活动产品仍 0.1.4，不是 fresh-machine 或 0.1.5 产品安装验收 |

巴克审核的原始来源是主 Agent 收到的会话回执：Agent `41150194-36bd-4dca-8659-ee59f9b14aee`，消息 `5d52a8bc-fcfa-4d34-bfae-109a18b1e7d5`，完成回执 `e13d04ad-6942-4546-96be-e665493de7dc`。

- manifest / 编译期摘要：`d5eb5f65f9c0f0e08ae08b272be5872cd11f2f6a2538ee515ad80d725a8270fe`；内核树：`6d7012b771942936517a7c2fc43e61a7c410492196e34ce2aedf2270886deafa`。
- 原始 source/release gate、生成 argv/exit/stdout/stderr 与清单：`/private/tmp/paseo-stage-a-20261101-c3l6le66/candidate-015-evidence/`、同根 `R-6ab3129-evidence/`。
- 归档：`/private/tmp/paseo-stage-a-20261101-c3l6le66/memsharing-paseo-0.1.5-6ab3129.tar.gz`，685767 bytes，SHA256 `32d309c83edcd85426da27df69ca7e3bb430d804f44ba0464eebddc8df176edd`。逐文件 SHA/mode 见 `R-6ab3129-evidence/archive-files.json`；这是可分发候选，不表示目录上架完成。
- 当前 Host：`localhost:6767` / `srv_snTWUoI0EgfS`，runtime alias 仍为 `memsharing-synthetic-dev`，包 manifest.id 保持 `memsharing`。新持久来源为 `~/.paseo/local-plugins/memsharing-0.1.5-candidate/6ab3129c992656c5b8ab99ab913eba87d484df00`。真实 `installerPath` 精确落在该根的 `payload/core/scripts/install.py`，返回 manifestSha256 与上述实际 manifest / 编译期摘要相同。
- 当前 Host 原始证据：同阶段根 `native-R-host/FINAL-NATIVE-R-HANDOFF.json`，SHA256 `0a050727718e36cefb4fd053f43d47bfdb15b5eac43efd0e86c2a5f6cc94a4ab`；同目录保留命令退出码、loader、只读 RPC、前后 metadata 与回退来源。
- 本轮仅执行 `memsharing.env.status`，未调用 bootstrap/dependency/machine/enable/CK/recover 或任何预览。产品 registry 整文件 SHA 与关键节点 metadata 前后一致，活动产品仍是下节记录的 0.1.4 / d14 来源，其他插件来源和启用配置未变。安装插件正常写入 `~/.paseo` 的该插件配置、候选目录及 loader 状态，不能称整个 HOME 零写；未重启 daemon。旧 `2a65…` 持久开发候选及更早回退材料保留。

OpenCode 已纳入 Python 核心，但本轮 Paseo 选择器/RPC 仍限定 codex、claude、workbuddy、dsh、zcode 五项；不称六家插件接入闭环。新一轮有界核查未找到已核实的缺 Python/Git macOS 测试目标或独立 provider 测试身份；新 HOME 与最小 PATH 不能屏蔽探测器的固定系统候选。尚无免登录可用推理路径证据，不复制真实 provider 凭据，也不以假 runner、localHTTP 或现有 0.1.4 Host 替代首次宿主全链路验收。

2026-11-02 补记：上段“五项”是本节 R 验收时点状态，不删改。其后维护 HEAD 的 `client/flow.tsx` 与 `shared/contracts.ts` agents 枚举已加入 opencode 成六项，`scripts/agm_core/` 合入 `uninstall.py`、`uninstall_recovery.py`、`policy_migration.py` 与自然语言入口（`daee8d6`）。这些仅是源码状态：最终新 S/R 未生成，本节旧 R 不能用于验收六家插件接入或整机卸载；最终回归、发行包与逐组真实验收缺口按[上线前清单](../acceptance/release-readiness.md)执行。

## 历史本机交接定位与保留材料

这些是特定验收现场的审计指针，不是插件默认来源、安装配置或可分发payload。外部机器不保证存在；本次文档清理未触碰它们。

- 旧开发来源（已被上节 R 替换，保留回退）：Host `localhost:6767` / `srv_snTWUoI0EgfS`；开发runtime `memsharing-synthetic-dev`。88文件树 `2a65a9460c69d3a1dd72ae40ef01db174ed92b7bb9cd11cc059f096df0eb1b70`，manifest `8c6acec89d7717badf018a63051b82d0f7164579e661555dcb79ca98c03c475d`。
- 载荷交接：`/private/tmp/paseo-payload-fixed-dev-20261101-dhpbxotd/FINAL-HANDOFF.json`，SHA256 `858814c77a700ccae2a5f1f2b24e3c9f806415bdc5c9b255dd3bd653f898ca5b`。
- 机器升级：`~/.paseo/memsharing-upgrade-evidence/0.1.4-20261101-b282e379/FINAL-UPGRADE-HANDOFF.json`，SHA256 `ff04131c94eb05c3aec64a2768f9bba43d9d958d46b5d429cd32c5de47a169d9`。来源 `d14a3c0d121576cc7dbcab0c55ef4a680985f84e`，产品树 `5f65647a0b496bed48feadae67107a968fc086173e9766db74dc5b01fe80dfca`；入口和迁移计划均null。
- 项目接入：`~/.paseo/memsharing-project-acceptance/20261101-83679ac2/FINAL-PROJECT-HANDOFF.json`，SHA256 `12f733f153cde678109596d646ca5a61cf69615d684f42a5f107d1f1a70fc09b`；项目 `/Users/vincent4j/Tools/Source/mem-sharing`，不是linked worktree。
- 新会话：`18ac05cf-08ee-4fd4-8874-2b977d2d0db8`，workspace `wks_6712fc2176016436`。实际台账runtime_acceptance保留pending，没有用手改台账替代读取证据。
- 受限C/V备份：`~/.memsharing-native-acceptance-backups/20261101T014015Z-62d47aaab60d`。33文件/685444B、权限0700/0600、sandbox恢复/幂等/第三态拒绝通过；仅代码与台账，不覆盖历史私文、库存或用户入口。该阶段真实撤下数为 0，未执行真实恢复；只有沙箱重建与核验通过，不能用它替代后续升级/项目备份。原始范围说明见同目录 `recovery-verification.json`。

## 仍需验收或发布的事项

1. 全新机器在真实宿主内完成缺依赖→资产批准→export→机器接入，并验证拒绝、取消、断线及恢复；不能用Python直调或假runner替代宿主RPC。
2. x86_64动态、远程HTTPS Git传输；资产固定URL/hash/链接/树已取得，17notice仅披露所列范围，不声称完整transitive SBOM。
3. CK官方网络获取、独立安装/首次激活及其他provider新会话；安装成功与实际加载分别判定。
4. 固定 0.1.5 S/R 的生成与完整性 gate 已按上节通过；仍需两入口的实际安装、全新机器宿主批准链路，以及截图/目录上架验收。S 的开发 identity 空哨兵与 R 的生成摘要分别核验，不以未来维护 HEAD 或旧开发来源替代固定 R。

## 历史证据取回

阶段原始日志、清单和审核结论统一留在 Git `0906d7acea8f0f1dc02ddef734f90322a8180579`，不在工作树重复维护。需要复核某次结论时按原路径读取，例如：

```sh
git show 0906d7a:docs/plugin-adapters/paseo-closeout-review.md
git show 0906d7a:docs/plugin-adapters/paseo-supply-evidence-20261101.json
git show 0906d7a:docs/plugin-adapters/paseo-current-host-acceptance-20261101.json
```

606/75 的原始汇总位于 `/tmp/paseo-final-regression-20261101-x54rx1cr/python/run-ztrxgg8z/summary.json`，同目录 `unit.result.json`、`integration.result.json` 记录退出码与计数；最终整合原始分离日志位于 `/tmp/paseo-final-regression-20261101-x54rx1cr`。供应与payload原始日志分别在 `/tmp/paseo-supply-validation-20261101`、`/tmp/paseo-payload-fix-20261101`。这些仅为原现场定位，不承诺临时目录永久可用；已提交的摘要与对应测试源码可从上述Git取回。本记录不重写历史失败，不把早期pending误报为当前全部未实现。
