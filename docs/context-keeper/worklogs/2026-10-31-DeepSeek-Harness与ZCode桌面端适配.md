<!-- context-keeper: session-id=01a19147-5499-7052-9fb2-7827f709582e -->
# DeepSeek-Harness与ZCode桌面端适配

## 追加记录 2026-10-31T17:28:03+08:00

- 用户明确要求直接实现 DeepSeek Harness、ZCode 桌面端适配，允许并行，由巴克队长统筹派发；不再等待方案确认。
- 主工作区 main，基线 e660373，开始时 clean。创建独立 guaji/desktop-native-contracts 与 tututu/desktop-agent-adapters worktree。
- 呱唧负责本机原生加载合同取证及后续聚焦审查；突突兔（ZCode/GLM-5.3）负责代码、文档、测试；主 Agent 整合验收，不提交推送，不升级版本，不修改上游 Context Keeper。
- Paseo create_agent 首次因 provider 需 provider/model 被拒，按工具返回纠正后两者运行，名称与实际配置已读回核对。进度面板缺 zod，未扩大修复。
- 本机产品台账只读核验：0.1.1，已登记 codex/workbuddy；本次代码适配不代表真实安装或新会话验收通过。
- 采用 OpenViking 执行器入口按需生成经验：不因本机安装就预建项目专属入口，保留 disabled 政策与私有内容。

## 追加记录 2026-10-31T17:32:20+08:00

- 呱唧完成两款本机应用包静态读取链核实；原生用户入口 .dsh/AGENTS.md、.zcode/AGENTS.md，项目均原生读 AGENTS.md。已整合[原生合同](../../acceptance/desktop-agent-contracts.md)。
- 主 Agent 使用现有 detect._check_app_bundle 及真实 codesign --verify，要求版本非空、签名identifier匹配；两者verified。没有启动桌面端或模型请求。
- DSH_HOME可覆盖用户入口根，DSH_AGENTS_HOME影响共享根；新适配只承诺默认根，非默认DSH_HOME在接入规划前拒绝，DSH自定义preset不承诺。
- 枚举分为五家支持列表与原三家缺省目标；已明确台账白名单、显式检测、迁移读者扫描必须覆盖新增Agent。pinned CK不支持新flag，明确跳过而不冒充安装。
- GLM多次收到steer后重复合同分析且尚无写入；主Agent一次中断并给出冻结实施裁定，要求直接落最小闭环、不再重复全盘分析。PUBLIC_LAYOUT_TARGET_CONTRACT允许按本候选改动重算目标哈希，不改旧SOURCE合同、不升级版本。
- 初次save-report通过；coverage所报12条断链与2条缺会话标识均为历史日志，未批量改写。新日志缺历史快照摘要只是提示项。

## 追加记录 2026-10-31T17:43:27+08:00

- GLM已落核心12文件；呱唧对2026-10-31T09:41:06Z脚本diff快照做独立聚焦审查（diff SHA256 b6c4ec471b5b777638b7ef20b7544bd209591bd1cc109baaacbf97bf4b0ddccf）。
- 审查退回4项：DSH_HOME原值进入错误信息（P1）；空白、~/.dsh误判（P2）；Codex32KiB阈值误套新增Agent（P2）；CK尾步主产品简报漏列新增Agent（P2）。主Agent已集中交GLM修正并补回归，不能将待修状态写为通过。
- 同快照支持列表/缺省列表分离、检测与台账白名单、迁移读者全量扫描、TARGET冻结hash一致；旧before与前身合同保持未变。该结论只是限定审查，不等于全量测试或桌面runtime。

## 追加记录 2026-10-31T17:50:10+08:00

- 为并行收口，将尚未开始的产品文档拆给第二位突突兔独立worktree；两个GLM任务随后均报1310周/月额度耗尽，提示2026-11-06重置。未反复重试或等待额度。
- 按当前Profile顺序突突兔的前一位呱唧接管：新建guaji/desktop-adapters-recovery与guaji/desktop-docs-recovery，从原GLM工作树按文件SHA-256逐项复制15个代码/测试文件与README。源工作树保留，不做重写/重置/提交。
- 接管任务已按真实呱唧Profile配置启动并读回名称；代码与文档写集仍独立。GLM实际承担核心适配初版、第一轮审查修正和部分旧测试更新，GPT接续未完成的新测试/回归/文档，升级原因为真实额度耗尽。

## 追加记录 2026-10-31T17:57:58+08:00

- 文档续接7文件已完成：README/SKILL/INSTALL/DESIGN/architecture/operations/llms；47个本地链接与锚点核验、diff --check通过。按主验收反馈移除README交付过程句、operations个人环境/候选版本句，精确对齐skipped/upstream_unsupported输出。已按交付hash整合主树。
- 独立呱唧限定复核通过：前4项问题关闭；只读源/测试审查，无改文件、无重复全量测试。恢复树scripts/tests diff SHA256=987296cab66451991e8b89c122c9fd5014aaae09711fafe7340f8b677019ca5a；新增test_desktop_adapters.py SHA256=3ebe1035e5b8c2268e8e009772fe492ab336101bf8fc98834c883e776b745b48。
- 接续执行者报告定向双端9/9、CK31/31、迁移68/68、WB9/9通过；最终integration74/74 OK（113.740s，/tmp/guaji-desktop-integration.log），unit仍在运行，不提前标全量通过。
- 首轮unit曾560项5F/63E；执行者定位运行中重冻结造成已加载常量与新文件不一致及一项恢复内核漂移，另旧WB夹具错用新增五家表；夹具改读历史0f690ef三家表，生产旧before/predecessor四组常量未改。保留失败原日志，终态待全量。

## 追加记录 2026-10-31T18:02:11+08:00

- 最终固定工作树：unit578/578 OK（278.024s）、integration74/74 OK（113.740s），合计652项，不叠加定向用例；最终日志已归档至[验收记录](../../acceptance/desktop-adapters/verification.md)同目录。
- 独立审查组合快照79607142d8f2d9fba0c9673375abc86dc014fbb07fbdc252c512c380216ba890与交付树一致；主Agent整合19个代码/测试文件逐字节核对、7份产品文档按交付哈希整合，未覆盖非本轮dirty。
- 主树静态复验：五家表/旧三家缺省、三目标合同哈希、旧before/predecessor四组AST常量不变、Python3.9语法与INSTALL/PROMPT一致、git diff --check全部通过。未重复执行已通过全量。
- 源码适配完成，版本仍0.1.3，未commit/push、未真实安装、未改上游CK。真实桌面新会话/用户与项目规则读回/Skill实际加载pending；不冒充已生效。
- 本轮采用既有入口按需生成边界并通过缺省负向测试验证新增双端未被默认预建；这是对既有方法在本适配中的核验，不新增编号经验。
