# Paseo 验收记录

更新：2026-11-01。**开发候选限定通过，不是正式发行，也未完成全新机器缺依赖的宿主首装全链路。** 当前实现与维护边界见[维护手册](README.md)。下表区分不同冻结时点，不把重叠用例数相加。

| 层次 | 已取得证据 | 范围与未验项 |
| --- | --- | --- |
| Python 最终整合快照 | unit606/606、integration75/75，exit0 | 11月1日当前 Python 内核；临时 Git/HOME，不是原生UI |
| Node 供应增量 | shared89/89、宿主定向27/27、SDK0.13.2 typecheck | 官方 arm64 原包经localHTTP→独立资产确认→export→机器安装的临时HOME闭环；非真实宿主缺依赖首装 |
| payload v3 | 定向11/11、SDK检查、安装包CJS compiler/evaluator通过 | 包ID与runtime别名分离、配置/载荷漂移拒绝、取消七flow；旧v1/v2失败不作为最终通过 |
| 生成与CI | common/notice/空哨兵4项通过，S/R只读检查已审 | 供应61与payload覆盖形成64项增量、另CI2项曾匹配冻结；不是10月31日原64项清单 |
| 本机开发runtime | payload.ready，持久来源加载、编译期摘要匹配 | `memsharing-synthetic-dev`，包ID memsharing；非正式发布 |
| 本机产品升级 | 原安装器0.1.3→0.1.4 completed，精确preserve转换，16记忆/入口节点保全 | 用户核验的clean本地d14来源；不能称插件自动升级或官方远端发行 |
| 插件项目接入 | 主checkout新preview→confirm completed，codex/follow_ck，registered且errors空 | 新preview不是全新机器；AGENTS原正文及16节点保全 |
| 新Codex会话 | 用户MEMORY与项目memory-keeper实际读回，CK resume/check退出0，无写入 | 主checkout与worktree记忆不同，没有当前Paseo主题命中；不代表其他provider或CK远端激活通过 |
| UI | 用户确认⌘K可打开 | CUA未完成自动界面核验；未取得完整Modal/拒绝/取消/断连自动UI验收 |

## 当前本机交接定位

这些是特定验收现场的审计指针，不是插件默认来源、安装配置或可分发payload。外部机器不保证存在；本次文档清理未触碰它们。

- Host：`localhost:6767` / `srv_snTWUoI0EgfS`；开发runtime `memsharing-synthetic-dev`。88文件树 `2a65a9460c69d3a1dd72ae40ef01db174ed92b7bb9cd11cc059f096df0eb1b70`，manifest `8c6acec89d7717badf018a63051b82d0f7164579e661555dcb79ca98c03c475d`。
- 载荷交接：`/private/tmp/paseo-payload-fixed-dev-20261101-dhpbxotd/FINAL-HANDOFF.json`，SHA256 `858814c77a700ccae2a5f1f2b24e3c9f806415bdc5c9b255dd3bd653f898ca5b`。
- 机器升级：`~/.paseo/memsharing-upgrade-evidence/0.1.4-20261101-b282e379/FINAL-UPGRADE-HANDOFF.json`，SHA256 `ff04131c94eb05c3aec64a2768f9bba43d9d958d46b5d429cd32c5de47a169d9`。来源 `d14a3c0d121576cc7dbcab0c55ef4a680985f84e`，产品树 `5f65647a0b496bed48feadae67107a968fc086173e9766db74dc5b01fe80dfca`；入口和迁移计划均null。
- 项目接入：`~/.paseo/memsharing-project-acceptance/20261101-83679ac2/FINAL-PROJECT-HANDOFF.json`，SHA256 `12f733f153cde678109596d646ca5a61cf69615d684f42a5f107d1f1a70fc09b`；项目 `/Users/vincent4j/Tools/Source/mem-sharing`，不是linked worktree。
- 新会话：`18ac05cf-08ee-4fd4-8874-2b977d2d0db8`，workspace `wks_6712fc2176016436`。实际台账runtime_acceptance保留pending，没有用手改台账替代读取证据。
- 受限C/V备份：`~/.memsharing-native-acceptance-backups/20261101T014015Z-62d47aaab60d`。33文件/685444B、权限0700/0600、sandbox恢复/幂等/第三态拒绝通过；仅代码与台账，不覆盖历史私文、库存或用户入口。该阶段真实撤下数为 0，未执行真实恢复；只有沙箱重建与核验通过，不能用它替代后续升级/项目备份。原始范围说明见同目录 `recovery-verification.json`。

## 仍需验收或发布的事项

1. 全新机器在真实宿主内完成缺依赖→资产批准→export→机器接入，并验证拒绝、取消、断线及恢复；不能用Python直调或假runner替代宿主RPC。
2. x86_64动态、远程HTTPS Git传输；资产固定URL/hash/链接/树已取得，17notice仅披露所列范围，不声称完整transitive SBOM。
3. CK官方网络获取、独立安装/首次激活及其他provider新会话；安装成功与实际加载分别判定。
4. 从新的干净S生成正式R，核验两入口、固定来源和完整载荷，再按明确授权发布。当前源码identity空哨兵正确，不将本机开发runtime或临时路径作为公开发行。

## 历史证据取回

阶段原始日志、清单和审核结论统一留在 Git `0906d7acea8f0f1dc02ddef734f90322a8180579`，不在工作树重复维护。需要复核某次结论时按原路径读取，例如：

```sh
git show 0906d7a:docs/plugin-adapters/paseo-closeout-review.md
git show 0906d7a:docs/plugin-adapters/paseo-supply-evidence-20261101.json
git show 0906d7a:docs/plugin-adapters/paseo-current-host-acceptance-20261101.json
```

606/75 的原始汇总位于 `/tmp/paseo-final-regression-20261101-x54rx1cr/python/run-ztrxgg8z/summary.json`，同目录 `unit.result.json`、`integration.result.json` 记录退出码与计数；最终整合原始分离日志位于 `/tmp/paseo-final-regression-20261101-x54rx1cr`。供应与payload原始日志分别在 `/tmp/paseo-supply-validation-20261101`、`/tmp/paseo-payload-fix-20261101`。这些仅为原现场定位，不承诺临时目录永久可用；已提交的摘要与对应测试源码可从上述Git取回。本记录不重写历史失败，不把早期pending误报为当前全部未实现。
