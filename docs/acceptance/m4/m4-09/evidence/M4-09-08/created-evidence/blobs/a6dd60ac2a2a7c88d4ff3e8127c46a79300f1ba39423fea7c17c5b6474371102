# 实现任务拆分

> **状态(2026-10-30 修订,原横幅夸大)**:16 项任务的**实现与本批报告已交付**(M1 七项、M2 九项,另加 M3 WorkBuddy 桥接回传上游);**运行时验收为部分通过**——WorkBuddy 负向 N1/N2 与新会话接力 not-run(见 [../acceptance/m1-07/evidence.md](../acceptance/m1-07/evidence.md)),M2-08 第二轮 WorkBuddy 未运行、Claude 未显式走 Skill/resume(见 [../acceptance/m2-08/README.md](../acceptance/m2-08/README.md)),WorkBuddy 真机新会话验收后经用户裁定列为可选。本文件保留为原始任务书,仅供追溯,不再是待办清单;补证触发条件与负责人见各 evidence 文件。

依据 DESIGN.md v1.1(53314d7);本文件是未执行任务书。共 16 项:M1 7 项、M2 9 项。角色为本次派工建议,常规编码由突突兔负责,高风险与核心不确定性由呱唧负责;规划交付者不写实现。每项交接需带实际 diff、命令/退出码、证据位置与未验收范围。不得以静态测试替代新会话接力。

## Phase 0：开工条件与文档发现

已完成只读接口发现，见 architecture.md §0、§6；未做运行时验证。开工 Agent 必须先读 DESIGN §2/4/5/6/8、本任务相关上游引用，确认接口未漂移。确认工作区现有规划文件的归属，不覆盖并行 Agent 改动。源码、用户入口、测试库、操作授权应逐项明确；本轮授权仅规划/骨架，不含后续实际安装或用户配置写入。

所有任务共同反模式：不修改旧管理器或 Keeper 源码；不发明上游参数；不写项目 .agents-group；不 commit/push；不做 Skills/MCP 管理；不借测试绕过迁移/记录库授权；未知状态不是成功。

## M1：dogfood（人工编排可先行，macOS 单主 checkout）

### M1-01 接口冻结与 dogfood 操作预检（呱唧）

- 目标：形成可执行、可恢复的单仓库操作计划。
- 范围：核对三执行器、Keeper 源码/解释器、Git 状态、入口与已有库、记录库授权、备份范围；收敛 O4/O5/O8/O9。不改入口或记录库。
- 涉及文件：docs/plan/m1-acceptance.md、后续 docs/acceptance/<run>/preflight.md；只读上游 install.py/probe.py、实际入口。
- 依赖：无；采用 architecture §0/6 的实际 API。
- 验收：列出实际路径、版本/哈希、已有/缺失/冲突、授权待办和恢复方案；未知项明确阻断对应步骤；不存在把 rc=0 预览算完成。
- 风险：源不可用、解释器不兼容、已有库未获授权；不得擅自安装依赖或读取旧版库正文。

### M1-02 规则基座装配（突突兔）

- 目标：建立 D1 唯一规则源与三家可达性。
- 范围：批准后补根 AGENTS.md 骨架、CLAUDE.md 的 @AGENTS.md；核对 WorkBuddy 公共源/项目规则约定；基座无需 Keeper。
- 涉及文件：目标仓库 AGENTS.md、CLAUDE.md；审批后可能涉及 ~/.workbuddy/MEMORY.md；操作证据与所有权清单。
- 依赖：M1-01；读 DESIGN §4.1/4.3、sync.py 的 block/put 模式。
- 验收：块外字节保留；新建/复用逐项登记；重复操作无新 diff；无记忆内容塞规则；若 AGENTS.override.md 存在先报告冲突。
- 风险：已有规则混杂不能自动清空；子目录规则仅根摘要，WorkBuddy 子目录盲区保留。

### M1-03 记忆档四态与授权（呱唧）

- 目标：源码、Skill、bridge、记录库授权分别有证据。
- 范围：批准范围内调用真实安装器；事前漂移检查；Codex/Claude 单独 ensure-bridge；init 位置确认与实际路径读回；为 M1-04 留 WorkBuddy bridge 缺口。
- 涉及文件：三家项目 Skill 链接、AGENTS.md/CLAUDE.md、批准的 Keeper 库/配置；集中记账草表或已实现 registry。
- 依赖：M1-02；读 install.py:169–221/286–388、probe.py:765–888/1973–1982。
- 验收：同意/拒绝/未知均有明确状态；approval_required、init rc=5 不置 ready；未经第四态不写库；自定义路径不被硬编码默认值覆盖；先 Keeper 后 Group 的对象标为 reused；迁移 rc=3 停止。
- 风险：普通 install 同时写 bridge，不能按“只装 Skill”处理；init 失败可能部分写入，保留现场不删除库。

### M1-04 WorkBuddy bridge 与用户级追加（呱唧）

- 目标：补上唯一未验收执行器的触发入口。
- 范围：模板置项目 MEMORY.md 顶部；保留原生日志；用户级仅追加记忆条款，保留已有公共源和 AGENTS.md 约定；记录待运行时验收。
- 涉及文件：templates/workbuddy-bridge.md；批准后目标 .workbuddy/memory/MEMORY.md、~/.workbuddy/MEMORY.md；操作证据。
- 依赖：M1-03；读 DESIGN §5、上游 BRIDGE 七条语义。
- 验收：唯一配对 marker、顶部位置、前后指纹、重复操作无 diff、用户规则原文保留；第四态与三执行器 bridge 均读回；不向上游传 --ensure-bridge --workbuddy。
- 风险：WorkBuddy 不加载/重置入口，静态存在不得判通过；M3 回传前不可声称原生已支持。

### M1-05 单份可公开存量样本（突突兔）

- 目标：验证“只搬运不加工”的最小路径。
- 范围：只一份用户批准且可公开的样本；分类预览展示来源、目标、Git 可见性变化；规则冲突保留原文待裁定；记忆原文用 Keeper 规范记录来源/日期。
- 涉及文件：用户指定样本、实际库 worklogs 中新 legacy 记录、迁移报告；若涉及子目录 CLAUDE.md 留 @AGENTS.md 薄入口。
- 依赖：M1-04、记录库第四态；读 DESIGN §4.2/4.3、Keeper references/save.md。
- 验收：逐项批准证据；原文对照无蒸馏/改写；目标是实际库；个人偏好与专属指令原地保留；日志通过 record-path/guard 与 save-report。
- 风险：未批准样本不得找真实私有内容充数；没有样本则报告 M1 此项未完成，不扩大全面整理。

### M1-06 三执行器正向接力（呱唧）

- 目标：证明换执行器后事实/待办连续，完成 DESIGN §6 正向闭环。
- 范围：严格四个新会话，Codex→Claude→WorkBuddy→Codex；普通续接不给入口提示。
- 涉及文件：获授权测试库、docs/acceptance/<run>/ 正向证据；执行 [m1-acceptance.md](m1-acceptance.md) P0–P4。
- 依赖：M1-04；与 M1-05 不同时写同库。
- 验收：唯一事实、待办三轮变化、WorkBuddy 追加事实最终均恢复；每轮有 session-id、实际来源、库 diff、输出；无编造恢复。
- 风险：宿主上下文泄漏答案、旧会话复用、Agent 看本验收答案；任何一种不能计普通续接成功。应用交互需依环境委派边界交给章教授。

### M1-07 负向验证与 M1 收口（呱唧）

- 目标：验证禁止保存与迁移门禁，区分静态与运行时结论。
- 范围：三执行器分别做两个负向用例；汇总一份公开样本与正向闭环；不修改真实库成旧版。
- 涉及文件：隔离获授权旧版 fixture、docs/acceptance/<run>/ 汇总；执行 N1/N2。
- 依赖：M1-05、M1-06；迁移夹具准备可与 M1-02–04 并行。
- 验收：禁止保存时库树无内容/文件集合差异；rc=3 后三家停止读写并提示；不读取旧正文、不触发自动迁移；全部证据齐备才标 M1 passed。
- 风险：无写入差异不能单独证明“未读”；须保留工具调用轨迹；无新会话或缺执行器只能报告部分通过。

## M2：工具化（macOS 优先）

### M2-01 身份与 schema 定稿（呱唧）

- 目标：关闭主 checkout/worktree、所有权及默认行为核心缺口。
- 范围：architecture §2/3 schema、O1/O2/O6/O7；明确字段校验、授权作用域、损坏恢复。
- 涉及文件：docs/plan/architecture.md、scripts/agents.json；后续 tests/unit 中 schema 用例设计。
- 依赖：M1-01；可在 M1 运行验证期间推进文档。
- 验收：主 checkout、clone、worktree、共享用户入口均有输入/预期案例；无项目新增 AGM 状态；未决设计明确提交用户裁定，不自作结论。
- 风险：继承错误授权、共享入口误删。

### M2-02 共享安全内核（呱唧）

- 目标：可恢复的最小配置变更。
- 范围：project/registry/entries/transaction 模块；块指纹、并发锁、备份 manifest、读回、恢复失败报告。
- 涉及文件：scripts/agm_core/{project,registry,entries,transaction}.py，tests/unit/、tests/integration/。
- 依赖：M2-01；读旧 sync.py:21–100、manage.py:15–51、project_manage.py:116–207。
- 验收：漂移先拒绝、块外保留、同内容不重写、链接冲突拒绝；故障注入覆盖写失败/读回失败/恢复失败/registry 最后提交；锁不会被 check 创建；保留失败现场。
- 风险：崩溃中断不是普通异常回滚，manifest 恢复范围须实际测试；不直接复制 fcntl 做跨平台承诺。

### M2-03 路径加载与 CLI 外壳（突突兔）

- 目标：三个命令的严格解析和稳定输出。
- 范围：agents.json 读取验证、路径展开、目标选择、错误序列化、SKILL 操作路由。
- 涉及文件：scripts/agm.py、scripts/agm_core/paths.py、scripts/agents.json、SKILL.md、tests/unit/test_cli.py。
- 依赖：M2-01；可与 M2-02 并行，先锁定公共类型避免共改文件。
- 验收：参数互斥/非法 Agent/未知 OS 拒绝；目录信号仅 hint；非交互待确认返回 5；无第四修复命令；SKILL 不能暗示已验收。
- 风险：残留目录误报安装；默认 agent 未决前只测显式目标。

### M2-04 enable 与 Keeper 适配（呱唧）

- 目标：把 M1 顺序实现为幂等写命令。
- 范围：零依赖基座、四态、安装预览语义、用户授权、WorkBuddy 顶部块、双安装顺序。
- 涉及文件：scripts/agm_core/{enable,keeper}.py、相关集成测试。
- 依赖：M1-04、M2-02、M2-03。
- 验收：调用安装器前全部相关块通过漂移检查；不带 --all；ensure-bridge 返回项目范围；yes/no/unknown、默认推荐/拒绝保持/已就绪补装完整；init 3/5/2/部分写入均保守报告；不借 check 补装。
- 风险：上游变化与批准间竞态；批准后重新预检；不做来源 fallback 或复制目录安装。

### M2-05 只读 check 与巡检矩阵（突突兔）

- 目标：只读检测，不制造修复副作用。
- 范围：--project/--all、四态与缺口、损坏登记内存重建、移动/重 clone 告警、入口预算/覆盖风险。
- 涉及文件：scripts/agm_core/check.py、tests/integration/test_check_readonly.py。
- 依赖：M2-02、M2-03；可与 M2-04/06 并行，各自独立文件。
- 验收：前后文件集合/字节/mtime 及写调用拦截证明无锁/缓存/registry 写入；可只读目录执行；--all 不扫描未知项目；检测 AGENTS.override、缺引用、WorkBuddy 重置、双写与漂移。
- 风险：Keeper status/probe 可能有缓存写入，check 不调用；registry 丢失不能宣称已巡检全部。

### M2-06 所有权卸载（呱唧）

- 目标：撤销只触及本工具对象。
- 范围：created/reused/unknown、部分文件块、共享链接/用户入口消费者、移除后的登记与恢复。
- 涉及文件：scripts/agm_core/remove.py、tests/integration/test_remove.py。
- 依赖：M2-02、M2-03；先读 install.py 卸载的共享目录保护。
- 验收：预先已有 Skill/bridge/引用不删除；created 漂移不删除；块外新增保留；记录库与 context-keeper.json 不删；共享消费者仍在则不移用户入口；二次 remove 无变更。
- 风险：上游 --uninstall 会组合删除且建议 --all，禁止为绕过共享保护扩大范围。

### M2-07 幂等与故障矩阵（突突兔）

- 目标：证明 CLI 的装/补/查/拆可重复。
- 范围：集成回归、临时 HOME/仓库隔离、双安装顺序、登记损坏、部分失败、共享对象。
- 涉及文件：tests/unit/、tests/integration/、docs/acceptance/m2-matrix.md。
- 依赖：M2-04、M2-05、M2-06。
- 验收：首次 enable→二次 enable 无字节/mtime变化；check 发现清空桥接但不修→enable 修复；先 Keeper/先 Group、拒绝记忆、位置自定义、复制目录冲突、损坏 registry 都有断言；read-only/rollback 不以 mock 成功替代真实文件证据。
- 风险：只写镜像实现的测试没有价值，优先验证破坏性边界与故障结果；无实际变更不反复全量测试。

### M2-08 两项目复制与新会话验收（呱唧）

- 目标：在 knowwind、poster-fit 验证可复用而不污染既有工作。
- 范围：每项目先只读 Git/库/入口盘点，再批准装配；复用真实安装器和新会话；不为测试擅自改生产内容。
- 涉及文件：两项目明确允许的入口、授权库、集中 registry；本仓库 docs/acceptance/ 证据。
- 依赖：M1-07、M2-07。
- 验收：每项目幂等重装无 diff；三执行器普通续接与证据；保留既有 dirty work、私有记忆、未授权文件；用户未授权项目操作则明确未执行。
- 风险：项目名字不等于路径/授权；必须实时核对，不能把 M1 成功当两个项目成功。

### M2-09 平台矩阵与发布前文档（突突兔，异常平台由呱唧评估）

- 目标：明确支持范围及恢复说明。
- 范围：macOS 安装/重装/卸载/失败恢复证据；Windows/Linux 有环境且上游策略可用才扩展；README/SKILL 补实际命令与限制。
- 涉及文件：README.md、SKILL.md、docs/acceptance/m2-platforms.md、agents.json 的实证扩展。
- 依赖：M2-08。
- 验收：每平台四项各自 passed/failed/not-run 与证据；未测平台不得写“支持”；无第二套复制降级；文档声明 runtime 验收边界。
- 风险：AGM Python ≥3.9 不保证上游相同；本任务不含提交、发布、定时器安装。M3 另案上游接管旧 WorkBuddy 块。

## 顺序与可并行项

~~~text
M1-01 → M1-02 → M1-03 → M1-04 ┬→ M1-05 ─┐
                             └→ M1-06 ─┴→ M1-07
M1-01 → M2-01 ┬→ M2-02 ─┐
             └→ M2-03 ─┴→ [M2-04 | M2-05 | M2-06] → M2-07
M1-04 ───────────────────→ M2-04
[M1-07 + M2-07] → M2-08 → M2-09
~~~

M1-05/06 图示是逻辑独立，不许同时写同一库；先样本后闭环更容易固定基线。M2-02/03 可并行，04/05/06 在内核接口冻结后按文件隔离并行。同一 registry 写操作串行；M1 与 M2 不并行修改真实入口。验收由主 Agent 根据实际证据收口，不重复执行已通过且未改动的低风险检查。

## 风险／开放问题（不自行改 DESIGN）

| 编号 | 缺口与已有证据 | 决策/验证时点 |
|---|---|---|
| O1 | DESIGN 主 checkout 为键，但新 worktree 要重装；授权是主项目共享还是每 checkout 单独确认未定义。architecture 的 checkouts 是候选细化。 | M2-01 用户裁定前只支持 M1 主 checkout，不推定授权继承 |
| O2 | 用户级入口被多项目共用；最后一个项目 remove 是否撤销一次性接入约定未明确。 | M2-01 明确消费者及撤销政策；未决时保留用户级入口 |
| O3 | DESIGN §8 仍写 memory-state + registry，§4.4/4.7 已定单一 registry。 | 按更明确 D7/§4.4 仅 registry，实现前确认文案遗留，不另建状态文件 |
| O4 | “项目内零新增状态文件”与 Keeper 自定义库生成 context-keeper.json 的范围可能误读。 | M1-01 明确零新增指 AGM 状态；provider 配置按上游保留，不删不另造 |
| O5 | 源码未就绪时从何来源、版本获得 Keeper 未指定；不能默默下载默认分支。 | M1-01 使用用户确认已有 checkout；通用获取策略 M2-04 前裁定 |
| O6 | 未给 --agent 时目标集、无交互时批准承载方式与字段/退出码未写定。 | M2-01 收敛，M1 显式三家；只建议待确认返回5，不加未批准公开参数 |
| O7 | registry 丢失可重建事实，不能重建所有权；--all 同时失去项目列表。 | M2-01 接受保守 unknown/reused 与指定项目检查，不扫描整机或猜 created |
| O8 | AGM ≥3.9、仅标准库；上游运行时兼容性、symlink 能力须实际验证。旧 fcntl/ExceptionGroup 不能原样搬成跨平台承诺。 | M1-01 验证当前解释器；M2-09 平台矩阵 |
| O9 | 上游 init 双候选歧义在处理 --store-dir 前拒绝（probe.py:768–771），与 save.md:19 描述有差异；新建异常可能残留（862–878）。 | M1-01/ M2-04 如实报告，不改上游/删库/绕门禁；失败按现场读回标 partial |

M1 不包含用户级全面整理或索引升级（M1.5）；M3 模板回传与旧块接管另立任务；本期不扩 Skills/MCP。
