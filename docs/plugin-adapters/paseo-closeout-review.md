# Paseo 本轮收尾审核

日期：2026-11-01。审核者：巴克队长。基线 HEAD `d14a3c0d121576cc7dbcab0c55ef4a680985f84e`，分支 `publish-memsharing-paseo-plugin`。

## 结论

**通过，可提交开发候选；不构成正式发行批准。** 本次限定当前未提交的 Paseo/shared 供应、加载绑定与 CI 增量，未发现阻断提交的具体源码缺陷。提交推送由主 Agent 在 CK 收口后执行；本审核未提交、未推送、未操作 HOME/daemon，未启用 PRD Distill，未修改源码或 CK。Orca 不在写集内。

## 检查与证据

- 先读实际 status/scoped diff，再核查安全相关调用链。供应61文件与 payload v3 五文件按新者覆盖形成64个唯一文件，当前逐项 SHA 全匹配；另核对 CI 两文件：check.py `205806d82aa747f48351cbb48724d8a089fd1d579ce1afc5f508d8c8ee469e00`，README `7148b6891a292a9568ec6d1c54dbb462e6322a792fc284a35ad170a6c772155e`。这里的64不是此前10月31日旧64文件清单，不能混用。
- 复用已审已测证据：shared89/89、host27/27（列明的定向宿主集，非声称全部原生UI）、payload v3定向11/11；本轮读回原始TAP计数，未将重叠测试相加。SDK0.13.2 typecheck、实际CJS compiler/evaluator和arm64官方包localHTTP闭环沿用对应冻结交接，不冒称本轮重跑。
- 本轮实际运行生成一致性检查 `node --experimental-strip-types --test plugins/paseo/test/sync.test.ts`：4/4、exit0，包含common逐字转换、无多余模块、开发identity空哨兵和notice副本一致；`git diff --check`通过。没有重复Python或Node全量。
- `HostPayloadBinding`只消费受支持SDK `context.paseo.config.get().config.plugins`；固定包ID memsharing与编译期manifest摘要、完整core文件字节/模式闭合、唯一canonical源共同绑定。每RPC复验，来源/环境漂移闭锁并取消七类flow，原Orchestrator不重建迁移待批计划；SDK异常不暴露原始配置。运行时别名不充当包身份。源码未发现将/Users或/tmp硬编码成生产payload来源。
- 供应资产是包内固定URL/size/hash/tree/link清单，constructor测试缝不由RPC开放。资产准备独立确认；原机器/export批准继续独立，token绑定资产场景，锁内复核与对象身份清理保留。私有Git环境仅对子进程生效，未知/漂移资产保全拒绝。17份notice是披露材料，不声称完整transitive SBOM。Python业务内核本轮没有复制或改写。
- CI只读核对已tracked source/common/notice/identity和原sync测试实际pass数量，再走原release verifier；正式S/R仍需从最终干净提交生成，不得使用本机测试目录作为对外发行源。

## 本机证据的准确含义

本轮只读回以下交接，不重复操作真实机器：

- 固定开发runtime：88文件tree `2a65a9460c69d3a1dd72ae40ef01db174ed92b7bb9cd11cc059f096df0eb1b70`，env.status payload.ready，发行摘要 `8c6acec89d7717badf018a63051b82d0f7164579e661555dcb79ca98c03c475d`。FINAL-HANDOFF SHA `858814c77a700ccae2a5f1f2b24e3c9f806415bdc5c9b255dd3bd653f898ca5b`。这是合成开发安装源，不是正式发行。
- 机器0.1.3→0.1.4：原安装器使用用户核验的本地clean固定d14与精确preserve转换，entry/migration null、16节点保全；handoff SHA `ff04131c94eb05c3aec64a2768f9bba43d9d958d46b5d429cd32c5de47a169d9`。不能说由插件自动升级或远端官方发行安装。
- 主checkout项目接入：真实plugin fresh preview/confirm completed，codex/follow_ck、check registered/errors空；handoff SHA `12f733f153cde678109596d646ca5a61cf69615d684f42a5f107d1f1a70fc09b`。fresh指新预览，不是全新机器首装。
- 新Codex会话读回的汇总见[paseo-current-host-acceptance-20261101.json](paseo-current-host-acceptance-20261101.json)：用户/项目记忆实际读取，resume/check退出0；主checkout与此worktree经历不同，未伪造当前主题命中。此项复用主Agent汇总，不声称审核者重新开启会话。台账runtime_acceptance仍pending，不能手改字段冒充验收。

## 文档收口建议（非源码阻断）

`design.md:3`、`tasks.md:3`、`delivery.md:3,31-34`和`paseo-progress.md`末尾是10月31日阶段快照；其中“未授权实施”“供应未启用”“未宿主安装”等不能再当全局现状。保留历史，不覆盖失败记录。主Agent宜在这些入口加“历史基线，当前见本报告及11月1日证据”的醒目链接。

`plugins/paseo/OVERVIEW.md:5-6`和Setup仍一概写未真实宿主验收，建议改为已验证限定开发runtime/既有机器项目接入，完整fresh-machine/UI验收仍pending。`paseo-supply-evidence-20261101.json`的remaining/boundaries是供应交付时刻的范围，应注明后续宿主证据补充，不能误读成供应执行者操作过真实HOME。上述是低风险现状说明修正，不要求重构或重跑全量；主Agent可在提交前完成。

## 保留的发行/验收门槛

- 全新机器从宿主界面完成缺依赖→供应→机器接入全链路尚未建立；arm64真实原包localHTTP/临时HOME证明不能替代该项。
- x86_64动态执行、远程HTTPS Git传输、CK远端获取/独立激活及其他provider新会话未验。
- 用户确认Command Center可打开，不等于自动CUA完整Modal/拒绝/取消/断连覆盖；CUA失败历史保留。
- 正式干净S/R载荷、固定Git安装源及公开发行尚未进行。开发源码空identity是正确状态。
- 证据JSON内本机绝对路径仅为审计定位，外部机器可能不可访问；不应打包为来源配置或承诺可分发。当前未发现凭据正文或私文正文被加入这些增量证据。

## 可提交文件集

下列为本轮现场读取的非CK增量；另包括本报告。CK两个已有改动由主Agent按授权单独收口、审核后加入，本审核未编辑或对其全文作内容审定。不包括/tmp证据原件、用户HOME备份、任何runtime二进制、node_modules、生成正式payload或Orca。

- `docs/plugin-adapters/paseo-current-host-acceptance-20261101.json`
- `docs/plugin-adapters/paseo-supply-evidence-20261101.json`
- `docs/plugin-adapters/paseo-supply-files-20261101.sha256`
- `plugins/paseo/OVERVIEW.md`
- `plugins/paseo/THIRD_PARTY_NOTICES.md`
- `plugins/paseo/client/flow.tsx`
- `plugins/paseo/index.server.ts`
- `plugins/paseo/notices/dugite-license.txt`
- `plugins/paseo/notices/gcm-LICENSE.txt`
- `plugins/paseo/notices/gcm-NOTICE.txt`
- `plugins/paseo/notices/git-COPYING.txt`
- `plugins/paseo/notices/git-lfs-LICENSE.txt`
- `plugins/paseo/notices/pybs-LICENSE.bzip2.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.cpython.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.expat.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.libedit.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.libffi.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.liblzma.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.libuuid.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.mpdecimal.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.openssl-3.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.sqlite.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.tcl.txt.txt`
- `plugins/paseo/notices/pybs-LICENSE.zstd.txt.txt`
- `plugins/paseo/server/orchestrator.ts`
- `plugins/paseo/server/payload.ts`
- `plugins/paseo/server/shared/common/download.ts`
- `plugins/paseo/server/shared/common/git.ts`
- `plugins/paseo/server/shared/common/production-assets.ts`
- `plugins/paseo/server/shared/common/supply.ts`
- `plugins/paseo/server/shared/common/tar.ts`
- `plugins/paseo/server/shared/common/tool-assets.ts`
- `plugins/paseo/shared/contracts.ts`
- `plugins/paseo/test/dependency.test.ts`
- `plugins/paseo/test/payload-entry.test.ts`
- `plugins/paseo/test/payload.test.ts`
- `plugins/paseo/test/sync.test.ts`
- `plugins/shared/THIRD_PARTY_NOTICES.md`
- `plugins/shared/notices/dugite-license.txt`
- `plugins/shared/notices/gcm-LICENSE.txt`
- `plugins/shared/notices/gcm-NOTICE.txt`
- `plugins/shared/notices/git-COPYING.txt`
- `plugins/shared/notices/git-lfs-LICENSE.txt`
- `plugins/shared/notices/pybs-LICENSE.bzip2.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.cpython.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.expat.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.libedit.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.libffi.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.liblzma.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.libuuid.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.mpdecimal.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.openssl-3.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.sqlite.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.tcl.txt.txt`
- `plugins/shared/notices/pybs-LICENSE.zstd.txt.txt`
- `plugins/shared/src/download.ts`
- `plugins/shared/src/git.ts`
- `plugins/shared/src/production-assets.ts`
- `plugins/shared/src/supply.ts`
- `plugins/shared/src/tar.ts`
- `plugins/shared/src/tool-assets.ts`
- `plugins/shared/sync-to-plugins.mjs`
- `plugins/shared/test/download.test.ts`
- `plugins/shared/test/git.test.ts`
- `plugins/shared/test/tar.test.ts`
- `plugins/shared/test/tool-assets.test.ts`
- `plugins/shared/test/tool-fixture.ts`
- `tools/plugin-release/README.md`
- `tools/plugin-release/check.py`

## 文档收口复核（2026-11-01 追加）

主Agent完成上述非阻断建议后，本审核仅复核以下六文件的文档/证据差异：`design.md`、`tasks.md`、`delivery.md`、`paseo-progress.md`、`paseo-supply-evidence-20261101.json`（均在本目录）及 `plugins/paseo/OVERVIEW.md`。

**通过，文档建议关闭。** 三个历史入口新增醒目时点与当前证据链接，任务书改称历史执行范围；进度仅追加11月1日结论，没有覆盖旧失败。供应证据以snapshot_note/later_evidence区分交付时刻与后续验收，保留旧tests/remaining。OVERVIEW准确限定已验证的本地开发候选、项目接入、新Codex读取，保留完整新机器首装与Intel动态未验，并删除未正式发行源码的安装selector示例。未将自动供应实现等同完整宿主首装通过。

这六文件全部纳入可提交集；其中design/tasks/delivery/progress为本次复核新增文档写集，其余两项已在上方清单。源码审核继续沿用冻结结论，不重审、不重跑测试。PRD未初始化，不据此增加PRD工作。本审核只追加此报告，未修改其他文件或执行提交推送。
