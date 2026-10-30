# M4-09 冻结案例清单（预备，未执行）

依据：[任务书修订 2](../../../plan/tasks-m4.md)、[机器合同](../../../plan/decisions-m4.md)、[DESIGN v1.9](../../../../DESIGN.md)。本清单冻结覆盖范围，不是通过报告；当前所有案例均为 **未执行**。执行者只采集原始证据、标执行/未执行，主 Agent 独立判定，不编写综合判定脚本。未冻结调用点以 TODO 保留，执行前由主 Agent 对照代码填定，不擅造参数。

## 隔离与命令约定

每案及每个故障子窗口使用独立临时 HOME、合成 R/C/V、Git 主 checkout 项目 P、隔离执行器信号与已核验源 S；不使用真实 `~/.agents-group`、真实共享 Skills 或真实凭据。证据写在被测 HOME 之外的独立 raw 目录。预先记录绝对路径、平台、Python/Git 版本、源码 commit/清单、环境隔离范围与未隔离面。仅改 HOME 不证明全部执行器发现已隔离。

下列 I/A/R 是命令展开记号，不是新增 CLI、shell 函数或可直接粘贴的整段脚本：

- `I`：`python3 -B "$S/scripts/install.py" --source "$S" --commit "$COMMIT" --version "$VERSION"`；manifest 分支改用 `--source-manifest "$SOURCE_JSON"`，不混用。恢复/获取命令不带 I 的普通安装参数，help 可只调用脚本 `--help`。
- `A`：`python3 -B "$C/scripts/agm.py"`；未安装/冷启动用已核验 S 下的 agm.py，证据注明来源。
- `R`：`python3 -B <已核验完整安装器或固定恢复入口> --recover "$MANIFEST" --action continue|rollback`；MANIFEST 为实际 journal 绝对路径；安装器与固定 recover.py 的实际接口分别记录，选择具体 action，不原样传竖线。
- `AP/RP/PP`：机器安装、独立恢复、项目计划的绝对路径批准文件，分别绑定本次真实确认，不凭空填确认来源。
- 分号和“获批后”表示独立采集步骤；每个实际 argv 单独留存，预览并不授权后续操作。

每案必须采集的原始证据（下表 E0）：实际 argv、cwd 与隔离环境、起止 UTC、退出码、原始 stdout/stderr；前后路径树（包括隐藏项、节点类型、权限、链接文本）、文件长度/SHA-256/mtime；逐文件字节 diff、批准与计划、op/manifest/恢复位置。外部合成哨兵也留前后指纹。失败保存现场，不修饰成成功；每个子场景/窗口单独编号。目录清单与证据索引仅供核对，不能生成自动 passed 判定。不得保存真实隐私原文。

<!-- TODO(与代码侧核对): 隔离 HOME/platform_config/安装信号注入方法、import/探测调用点、支持源发行清单与 P/T 冻结产物的实际路径；不引入生产 --home 等未冻结参数。 -->
恢复预览：安装器 `--recover <journal> --action continue|rollback`，无批准输出 `approval_plan`；获批后加 `--approval-file`。批准是完整计划加 `confirmed_at/reference`。主动版本回退不经本 CLI 的 `--request-file`（该文件仅承载 `conversions/legacy_registries/legacy_source_commits/evidence_files/legacy_identity`），由升级内核按版本库存另立新计划。独立获取为 `--acquire --staging <目录> --commit <SHA> --version <SemVer>`，先预览再批准执行。
<!-- TODO(与代码侧核对): 固定工具包在首装/迁账的入口、故障注入/并发旧写者精确 argv；沿用已有受控接口，不写新测试或判定脚本。 -->

## 案例矩阵

| 编号 | 案例与前置现场 | 操作命令／步骤 | 采集的原始证据 | 预期核对要点（主 Agent 判定） |
|---|---|---|---|---|
| M4-09-01 | **冷启动只读**：空隔离 HOME；源码只读；无产品、v0、Keeper 或执行器目录。 | I --help；A --help；A check-memory --project "$P"；I；模块 import 与探测（见接口 TODO）。 | E0；本案全部子场景逐项留存。 | R/C/V、锁、缓存、备份、执行器目录均无新增；check 不修复。 |
| M4-09-02 | **全新安装**：空隔离 HOME，只有 Codex 的可验证 installed 信号。 | I；获批后 I --approval-file "$AP"；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 结构、库存、代码、台账及接入读回；报告来源与三版本；新会话仍 pending。 |
| M4-09-03 | **同版零写**：02 完成的同版同来源现场。 | I；按实际 noop 合同调用；重复 I。 | E0；本案全部子场景逐项留存。 | 不刷新内容、mtime、op、锁、备份或库存；无重复入口。 |
| M4-09-04 | **v0 身份未确认**：非空无产品痕迹合成 R。 | I；分别未答、否认、确认曾安装、无法确认。 | E0；本案全部子场景逐项留存。 | 零写；不能仅因无账本导入；确认来源缺失不能自证授权。 |
| M4-09-05 | **v0 一次复制**：确认合成 v0；三内容目录、旧脚本、状态、mcp；源索引有相对链接。 | I；明确 confirmed_v0 后 I --approval-file "$AP"；再次 I。 | E0；本案全部子场景逐项留存。 | 快照、legacy 包与原件字节保真；原索引 basename 保留，活动索引链接它；旧脚本/状态/mcp 原地；第二次不重复导入。 |
| M4-09-06 | **实际前驱升级**：冻结可运行 P/T 源和精确转换白名单；由 P 自身安装完成。 | 用 P 的 I 安装并运行 P 的 A；用 T 的 I 预览、获批执行；运行安装后 A。 | E0；本案全部子场景逐项留存。 | 真实不同 commit/代码清单；先库存后代码、最后 V；用户内容不变，非仅改版本字符串。 |
| M4-09-07 | **未来与未知版本**：分别为高 schema/structure/code、未知前驱、不可验证来源。 | 每个子现场 I；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 拒绝且零写；无降级、首装或空账重建。 |
| M4-09-08 | **坏台账**：分别为坏 JSON、重复键、缺字段、类型错误、身份矛盾、缺 created 证据。 | 每个子现场 I；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 零写，保留坏账原字节，不以诊断为由创建备份或重建。 |
| M4-09-09 | **中断普通入口**：未完成 manifest、锁、暂存或 V 已提交但收尾未闭合，分别构造。 | I；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 保留现场，不清锁、不识别为 v0；给独立恢复路径。 |
| M4-09-10 | **六阶段故障恢复**：prepare/archive/inventory/code/verify/commit 各前后窗口独立夹具。 | I --approval-file "$AP"（受控注入）；I；R --approval-file "$RP"（继续/回滚分别）。 | E0；本案全部子场景逐项留存。 | 每窗口独立原始证据；V before 仅允许匹配现场继续/逆序回滚，V after 全 after 只收尾。 |
| M4-09-11 | **rename 与提交窗口**：库存 rename、每个代码 replace、V commit 前后分别中断；C 混版且来源不可访问。 | 受控故障 I --approval-file "$AP"；用固定工具包恢复入口（见 TODO）。 | E0；本案全部子场景逐项留存。 | 恢复工具不依赖 C；逐窗口记录，不拿一次阶段故障替代所有窗口。 |
| M4-09-12 | **恢复拒绝与锁**：第三态字节、坏备份、工具漂移、活跃 PID、无法证明退出的锁；V after 混合。 | I；R --approval-file "$RP"；另做缺批准 R。 | E0；本案全部子场景逐项留存。 | 停止并保留；不能偷锁、覆盖第三态或将未知结果报完成；锁接管须精确证据与批准。 |
| M4-09-13 | **已安装版本主动回退**：P→T 后新增项目授权；完整可信 P 库存及历史收据。 | 按 §12 回退计划接口预览并获批执行（见 TODO）；运行回退后 A。 | E0；本案全部子场景逐项留存。 | 只换代码/产品版本信息，保留当前项目、授权和用户数据；缺库存、坏库存、未知逆迁移拒绝。 |
| M4-09-14 | **同名索引与链接**：v0 MEMORY.md 引用 ./主题.md 和 ../references/手册.md，含原有失效链接。 | I；I --approval-file "$AP"。 | E0；本案全部子场景逐项留存。 | 旧索引快照及 legacy 逐字节保真；可用链接不新增失效；原有失效如实报告。 |
| M4-09-15 | **同字节与异字节冲突**：分别构造目标同类型同字节、异字节、类型冲突、legacy/快照占位。 | 各现场 I；仅合法同字节复用分支获批执行。 | E0；本案全部子场景逐项留存。 | 同字节复用不获得删除权；冲突全计划停，不按 mtime 选、不加后缀绕过。 |
| M4-09-16 | **预览后源漂移**：预览后分别修改、增加、删除源条目；另含本次合法索引置换。 | I；外部受控修改；I --approval-file "$AP"。 | E0；本案全部子场景逐项留存。 | 锁内/写前/提交前复核阻断真实漂移；合法精确写项不误判；不覆盖新增用户字节。 |
| M4-09-17 | **目录外链接**：外部/绝对/悬空 Skill 链接、内部相对链接、escape 后重入；外部目标放合成哨兵。 | 各现场 I；只对允许分支批准执行。 | E0；本案全部子场景逐项留存。 | 不解引用外部目标；排除项记录链接文本，legacy 不激活外链；有效原链接因排除失效则停。 |
| M4-09-18 | **特殊路径与源码占位**：循环链接、特殊节点、大小写/Unicode 碰撞、穿越；独立/dirty/异源产品源码占位。 | 每个子现场 I。 | E0；本案全部子场景逐项留存。 | 规划失败零写，不能跳过后宣称完整；不接管独立 checkout；真实内容不用于夹具。 |
| M4-09-19 | **M2/M3 迁账保真**：严格合法 schema=1 与原始 manifest、备份、created/reused、授权、消费者。 | I；迁移计划获批后 I --approval-file "$AP"；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 逐字段比对权利与项目选择；旧账原始字节及证据映射可达，唯一活动 V；不扩大删除权。 |
| M4-09-20 | **双账冲突**：旧源码账与 V 不同，或半迁移字段/映射矛盾。 | I；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 不按时间选账、不归零、不双写；保留两账及原始指纹。 |
| M4-09-21 | **旧源漂移与并发写者**：迁移批准后改旧源；独立子现场启动真实旧代码写者与新写者。 | I --approval-file "$AP"；旧版本 A 的真实写命令（见 TODO），记录并发时间线。 | E0；本案全部子场景逐项留存。 | 源漂移拒绝；旧代码遇 tombstone 实际停止；两写者不能同时成功，按冻结锁序执行。 |
| M4-09-22 | **迁移中断恢复**：迁账各切换/提交窗口中断，旧材料仍存在。 | 故障 I --approval-file "$AP"；I；R --approval-file "$RP"。 | E0；本案全部子场景逐项留存。 | 恢复后单一活动状态源；旧恢复材料不随代码替换失效；未闭合不能首装。 |
| M4-09-23 | **后装另一家**：仅 Codex 完成；随后增加真实可验证 Claude installed 夹具信号。 | 先运行 A check-memory --project "$P"；用户主动选 /agent-group → 添加新的 Agent → 输入 claude，再 I --agent claude，获批执行后重复同一请求。 | E0；本案全部子场景逐项留存。 | check 不自动发现或提示新装执行器；用户主动接入才核验安装事实并另列计划；原正文保留，第二次接入零字节/mtime 变化。 |
| M4-09-24 | **absent unknown 与显式选择**：残留 hint、unknown 信号、absent；另有 installed 未选者。 | I --agent claude；I --agent codex；分别预览/批准合法计划。 | E0；本案全部子场景逐项留存。 | 显式选择不豁免 installed；absent/unknown 不创建入口；报告未选与 unknown 分列。 |
| M4-09-25 | **AGENTS 生命周期**：项目已装配；分别编辑标题/非 bridge 正文、bridge、重复/丢失 bridge。 | A check-memory --project "$P"；预览并获批 A remove-memory --project "$P" --approval-file "$PP"。 | E0；本案全部子场景逐项留存。 | 非桥接区自由编辑，撤销后 AGENTS 永存；受管单元漂移停写。 |
| M4-09-26 | **CLAUDE 生命周期**：分别为新建纯入口、新建后加正文、旧 reused import、旧 created 但缺引用创建证据。 | 各现场预览并获批 A remove-memory --project "$P" --approval-file "$PP"。 | E0；本案全部子场景逐项留存。 | 仅证据完备纯 created 文件可删；用户正文原字节保留；旧 reused/缺证据不追认删除权。 |
| M4-09-27 | **WorkBuddy 原生目录**：installed 但原生目录不存在；另有已建目录与原文、纯新建 MEMORY；模拟重置。 | A enable-memory --project "$P"；合法计划获批执行；check/remove/重置后 check，再获批 enable。 | E0；本案全部子场景逐项留存。 | 不预建原生目录；缺目录 partial/blocked；正文保留，remove 不删目录；check 不修复。 |
| M4-09-28 | **最后消费者与授权状态**：最后项目消费者；机器对象独立；含记忆 yes→no 场景及源码假 ready 现场。 | A enable-memory --project "$P" --no-memory（预览、获批）；A remove-memory --project "$P"（预览、获批）；A check-memory --project "$P"。 | E0；本案全部子场景逐项留存。 | 机器指针/Skill/共享零消费者对象与记录库保留；no 不残留生效指令，源码存在不冒充 ready。 |
| M4-09-29 | **缺 Git 受控环境**：无 Git 的独立受控 macOS 环境，Python 可用，已核验源或待获取源。 | git --version；python3 --version；I；记录获取层诊断。 | E0；本案全部子场景逐项留存。 | 只给手动步骤或已核验本地源路径，不自动装 Git；未满足必要依赖不报完成。PATH 模拟仅证明分支。 |
| M4-09-30 | **缺 Python 受控环境**：独立受控环境无可用 Python；不借真实机器工具补齐。 | python3 --version；记录 Agent/用户的启动诊断和引导，不声称运行 I。 | E0；本案全部子场景逐项留存。 | 解释器不能启动由外层诊断；只给安装步骤，无自动安装；非真实受控环境则 not-run。 |
| M4-09-31 | **LLM 文档地图**：冻结文档集与仓库根 llms.txt。 | 只读列出 llms.txt；逐条读取相对链接对应文件。 | E0；本案全部子场景逐项留存。 | 安装/使用/设计/验收/决策分组；一行一文档且链接存在；验收快照不当当前指南。 |
| M4-09-32 | **L0/L1/L2 模板**：新首装合成索引/主题，以及三家入口、AGENTS 和 SKILL 模板。 | I；获批安装；读取生成文件与相关模板，保存逐字节 diff。 | E0；本案全部子场景逐项留存。 | L0 主题名+一句当前结论+链接且 ≤200行/25KB；L1 开头有效结论与待办；L0恒读→需时L1→不足L2；无新文件类型/自动摘要/配置旋钮。 |
| M4-09-33 | **partial 与完整报告**：下载/clone 完成但接入失败；无 installed；成功静态安装三个独立现场。 | 获取层记录；I；合法批准后 I --approval-file "$AP"。 | E0；本案全部子场景逐项留存。 | 逐项核对 §4 报告；失败报 partial，不把源码取得说成安装完成；无 installed 报接入待办，runtime pending。 |
| M4-09-34 | **批准绑定及未安装三命令**：无产品；另有错 op/来源/现场/选择/changes/确认缺失批准。 | A enable-memory --project "$P"；A remove-memory --project "$P"；A check-memory --project "$P"；I --approval-file "$AP"。 | E0；本案全部子场景逐项留存。 | 三命令仅指引安装，不隐式装/升；不匹配批准停写，不复用项目批准作机器批准。 |

本清单纳入最新用户裁定：后装 Agent 无自动发现、无自动提示，只有 `/agent-group` 菜单主动添加；与旧任务书 §M4-05/09 的自动提示措辞冲突时，以此新裁定为准。

## 覆盖与交接边界

任务书七类对应：冷启动 01/34；安装七现场 02–13；内容冲突/漂移/链接 14–18；迁账 19–22；执行器接入 23–24；生命周期 25–28；运行时缺失 29–30。修订 2 追加 31–32，报告及批准边界补充 33–34。Windows/Linux 生产支持、真实执行器新会话、三家接力与真实 v0 属 M4-10，本清单不替代其验收。

执行后另建 raw 材料与执行索引，不覆盖本清单，不在此提前填写 passed。主 Agent 需核定 TODO 与具体夹具来源后安排执行；本次仅交付预备清单。
