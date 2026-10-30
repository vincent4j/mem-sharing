# Poster Fit 项目规则（精简版）

> **2026-10-18 当前生效修订（五节点默认，优先于下方10/15、10/9、10/13历史表述）：** 新SKU默认按[五节点](./docs/workflows/服装商品图综合生产工作流.md#默认操作五节点完成本次新款请求)：①资料与全特征校准——三块一次反馈（输入够不够；全部可见特征逐项＋独特之处单列＋逐项经验状态；模特方向并询问搭配参考），等用户指令才写prompt；②白底搭配筛选与确认——专门选择子阶段，不称S1、不构成黄金批准，身份/搭配选择不等于商品结构通过；有参考每种1～2张精确数量本次定，无参考选中方案每风格2张；③大场景筛选与确认——先问参考，无则4～6文字方案、仅选定场景1～2张候选，不恢复旧S2～S5目录菜单；④分镜分批生成与自审——已知硬错不交用户代审；⑤交付与归档。全部可见特征未列出不算已识别，未观察类别诚实UNKNOWN，NOT_APPLICABLE须附依据。每轮报告当前i/5与后续节点；执行中最长10分钟一次真实反馈。规范见[五节点需求验收](./docs/prd/五节点需求验收.md)。10/15候选/批准/交付/C60边界并入五节点继续生效，旧六步锚点保留历史兼容。

> **2026-10-15 历史修订（默认步骤由10/18五节点取代，交付/批准边界继续生效）：** 原六步默认见[用户视角六步](./docs/workflows/服装商品图综合生产工作流.md#默认操作六步完成本次新款请求)：资料够不够 → 完整组合建议 → 真实候选选组合并一次定整组 → 生成审核 → 一次必要修正 → 原图/总览/指定文件夹交齐并登记。已有合法基准可跳过候选波；本次已确认真实候选，每批数量明确。候选不是自动批准，但完整质量PASS、实拍测量、原生整图、canonical结算、新协议审核与精确整图人审且无后到拒绝齐备时，可独立正式批准并合法复用；原candidate stage/history不改，选脸或UNKNOWN不提升。existing_approved_visual_target原七项证据不变。完整/compact均ready→实际host展示→立即同包finalize登记，终态复盘另行收尾；C60跨原request全部候选/正式批，不重置scope/t0，终点=max(全范围必要真实已审展示及约定副本/总览交付完成观察，canonical登记完成)。复制/上传/总览/登记算系统，缺真实边界或必要副本为UNVERIFIED；离线通过不证明live60。质量、HUMAN_ACCEPTED与UNKNOWN共存及E12～E16冻结边界继续生效，不授权实际生图。技术入口另见[request C60协议](./docs/workflows/request-C60计时协议.md)。

> 2026-10-09 历史路线（默认步骤由10/15修订，以下质量边界保留）：用户已接受[结构保真与人景交互路线](./docs/reviews/2026-10-09-结构保真与人景交互工作流评审.md)：实拍事实与测量 → 搭配、一个场景与交互一批锁定 → 直接完整交互首图 → 商品和交互双验收 → 最多一次相关修正 → 获批后同一大场景扩图。数字母片/S1仅为可选诊断，不恢复S2～S5菜单；扣数、扣位、门襟横条与主要图案等明显结构错误一票否决；旧母片不是实拍真值；E14现有批准不变，不授权自动重开商品或生图。

> 2026-10-13 历史增量（人工认可等边界继续生效，默认节奏按10/15）：[四图HUMAN_ACCEPTED与复用配方](./knowledge/application/E14书店批量生活照复用配方.md)。先明确每张目的，整组身份搭配/同大场景/镜头/实际参考/模型原生规格/明确次数一次确认；已有完整批准基准后合法batch可并行，返回即审，整组review_ready一次交图，当时登记收尾后置；10/15起真实展示后立即同包登记，终态复盘另行收尾。自然遮挡/书高度/浏览视线按现实可解释性及商品主要信息可用性判断；镜头职责偏差不自动判融合失败。HUMAN_ACCEPTED与局部UNKNOWN可并存，保留冻结机器历史，无证实硬错误不无限阻止已满意原图交付或强制返修2K。无固定20cap，仍按当次明确调用范围，不将“图便宜”当价格证据或无限授权；新SKU填法见配方，E14专用payload不得直接改SKU。

用户当前明确指令优先。默认使用简体中文。完整项目规则正文（原AGENTS全文搬移，唯一完整源）：[docs/project-rules-full.md](./docs/project-rules-full.md)。先在下方路由匹配任务，再**读取所列文件的相关章节/合同原文**后执行；不要每会话预读完整规则或整个知识库，无关任务不加载生产细则。

## 0. 每轮硬边界（任何任务生效）

- **执行反馈节奏（2026-10-18用户强行约定）**：任务执行中向用户同步进展最长每10分钟一次真实反馈（有结果立即报），如实报告当前卡点；反馈须有真实发送证据，不以计划或定时器设定冒充已发送。每轮同时报告当前节点（i/5）、节点名、已完成、待确认、后续各节点名与下一步。用户暂停或任务结束后停止主动催报，恢复后不冒充持续有进展。会话卡死时自身计时不可靠，卡住通知须依赖宿主独立机制；未证实宿主能力前按未实现处理，不以轮询冒充可靠通知，不自动重发可能收费的请求。
- **用户规则与委派**：开工先读 `~/.agents-group/memories/MEMORY.md`（委派分工与安全）；网页研究遵守章教授委派规则，匿名走 agent_reach，确需登录态才用 Computer Use。
- **授权与费用安全**：任何付费生图/编辑前必须有 `experiment_id`、开工清单与用户本次请求的明确图片数/任务范围；派发严格以任务范围封顶（`budget.scope_dispatch_calls`），实际已发加在途/未知预占不得超出，范围未声明或超范围一律阻断，不得超范围自动追加重试/返修/扩图；价格、estimated_cost、结算金额与 charge_status 不作为派发前置条件，不自动预留返修次数。ClawPower Key 按 `~/.agents-group/memories/MEMORY.md` 明确授权边界执行。
- **仅通用Git/仓库零写入**：GitHub 只保存可跨商品复用的 workflow/template/rule/knowledge/code/tests；普通单品生产的事实、输入、锁定、生成、审核、批准、计时、台账、日志、交付索引与知识候选一律外置 `/Users/vincent4j/同步空间/poster-fit-assets/<product_id>/<experiment_id>/`；普通生成仓库磁盘零写入、Git 零变化，不自动保存仓库 Git Context Keeper，改写外部 production summary；旧 `products/`、`experiments/` 只读兼容；显式 publish 才写共享知识。 原文单品路径仅按 archive 历史只读解析，旧 repo 图片入口不是今后默认；外置链接映射待迁移owner闭合，现存47张知识图片保留。
- **冻结边界**：E12～E16 成图冻结，未经用户确认不重开；当前仅解冻阶段3一次新正式商品迁移验证；开放式模型比较、E09相似迭代、UI/数据库/批量SKU/M2/M3 建设继续冻结。
- **状态语义不可混用**：`gate_status=PENDING/PASS/FAIL`；`attempt_status=CANDIDATE/SELF_REWORK/REJECTED`；`cycle_status=IN_PROGRESS/PASS/BLOCKED/NEEDS_ASSET/BLOCKED_VARIANT/NEEDS_HUMAN/ABANDONED`；对用户展示英文状态附中文；未知/失败不转 PASS。

- **通用经验落库（2026-10-14用户长期指令）**：用户明确确认并授权发布的跨商品通用经验，必须进入项目生效知识并按授权提交、推送GitHub；外置只保存单品资料/证据和待审候选，不能以外置候选宣称知识沉淀完成。已有明确授权的本次及以后任务直接完成授权范围内的落库与提交推送，不重复确认；未确认的新候选仍为pending_human，不自动发布。注册表变化仍须按发布合同绑定真实授权及candidate/hash；知识正文可按明确授权维护。

## 1. 任务路由（匹配后读取对应章节/合同原文，非仅记链接）

| 任务 | 必读 |
|---|---|
| 服装生成/图生图返修/原生2K重生成 | `docs/project-rules-full.md` §1/§2/§5；`docs/workflows/服装商品图综合生产工作流.md`（唯一默认生产入口，五节点默认）；`docs/prd/五节点需求验收.md`（五节点定义、全特征与Checklist状态语义）；`docs/workflows/生图输入分级与缺项检查.md`；`docs/templates/生图准备检查卡-中文模板.md`；`docs/contracts/淘宝头图商品保真与单色选择合同.md`（同款同色正面＋材质表面实拍必需并实传，缺项标 `NEEDS_ASSET`；单色单变体锁定）；固定事实复核/局部编辑加读 `knowledge/application/固定商品事实拓扑验收规则.md` |
| 场景/交互/批量镜头生产 | `docs/project-rules-full.md` §1/§5；`docs/prd/服装动作与场景联动.md`（整组一次确认、合法batch、自然遮挡、双验收四项PENDING、`scene_interaction` 一次修正）；`knowledge/application/E14书店批量生活照复用配方.md`（新SKU `original_at_golden`/`existing_approved_visual_target` 与 reuse_evidence 七项） |
| 单次完整成图/黄金样片/扩图 | `docs/workflows/单次完整成图.md`；`docs/templates/完整视觉目标.yaml`；`docs/project-rules-full.md` §5（三道门禁、唯一 `attempt_id`、无 `approved` 不得扩图；最多三个主差异→一次相关修正→接受或停止） |
| 实验开工/计费/收尾/交付复盘 | `docs/prd/contracts/experiment-learning.md`（preflight、预算授权 fail-closed、六项复盘正文、外置资产） |
| 评分/硬失败/一票否决 | `docs/prd/contracts/m1-head-images.md`；人物图加读 `docs/contracts/淘宝头图相机实拍感验收合同.md`、`docs/contracts/淘宝头图光源与投影合理性合同.md`、`knowledge/application/服装左胸标定位与验收规则.md` |
| 单张返回提速/120秒时延 | `docs/workflows/单张生产提速操作.md` |
| Eagle/参考图/模特方向/参考原创 | `docs/project-rules-full.md` §3/§4；`knowledge/application/服装参考图可学习性评估标准.md`；`knowledge/model-cards/`（scene-cards 仅历史）；Eagle 默认只读 |
| 知识发布/终态close/capture/完结复盘 | `docs/contracts/商品知识发布触发合同.md`；`knowledge/README.md`；`docs/project-rules-full.md` §3（真正终态才 close，新规则 `pending_human`，不 Agent 自批） |
| 生成后反馈格式 | `docs/project-rules-full.md` §5（按原文固定顺序＋“生图锁定”列本次实际输入参考图及职责；未过硬门禁写明“没有最终交付图”） |
| 开发/修 bug/陌生业务词 | 按下方 PRD/合同约束检索 `docs/prd/README.md` |

任务命中多行时，合并各行要求并按文件和完整章节去重，不因命中一行跳过其余匹配行。本文的“读取”“必读”均按以下策略执行：

- 首次需要的规则、合同和资料必须读原文。同一会话中，已读过、内容未变化且当前上下文足以准确使用的部分直接复用，不因再次命中路由或引用而重复读取。
- 文件变化、版本不明、上下文压缩后丢失关键条款，或任务新增未读章节时，只补读本次需要的完整章节及适用修订；不能只读关键词命中行，也不能用旧摘要替代合同原文。
- 利用当前上下文和已有变更信息判断是否需补读，不为去重另建台账或逐次执行全量检查、哈希校验。此策略只去除资料重读，不免除首次必读、当前授权与生产状态核验，也不改变安全和验收要求。

详细方法：[总体方案](./服装生图-总体方案.md)；[MVP 工作流](./服装生图-MVP头图工作流.md)。

<!-- prd-distill:start -->
## PRD / 合同约束

开发、修 bug、改行为或遇到陌生业务词时：

1. 先检索 `docs/prd/README.md`，只读命中的 PRD/合同片段；核心流程或命中不足时才扩大读取，回归/高风险时再查 `docs/context-keeper/memory-keeper.md`。
2. 编码前有命中则列最多 5 条“受影响合同：ID、原因、证据”；无命中说明“未命中生效合同”。
3. 实现后只验证受影响合同；视觉/UI 需截图、DOM 或页面证据。最终只报告 `通过/部分通过/未验证/不适用`。
4. 提交前若修改 plans/worklogs/memory/PRD/合同，执行 PRD Distill 收尾。
<!-- prd-distill:end -->


<!-- prompt-gap:start -->
## PromptGap 留档
2026-10-14 用户指示：本项目停止使用 PromptGap。项目状态已置 `disabled`，不再新建任务/需求/begin 留档，生产清单不要求 `prompt_gap` 绑定，入口按关闭状态直接跳过；历史留档保留只读，不删除、不改写。未获用户新的明确指示不重新 enable。
<!-- prompt-gap:end -->
