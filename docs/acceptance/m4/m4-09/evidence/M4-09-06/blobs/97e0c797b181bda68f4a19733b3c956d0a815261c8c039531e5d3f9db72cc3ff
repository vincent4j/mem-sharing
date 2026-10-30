# M2 身份与 schema 决策单

日期：2026-10-29；任务 M2-01；设计基线 DESIGN.md v1.1。配套合同：[architecture.md v2](architecture.md)。本文是可评审的定稿建议，不表示用户已接受政策选项，也不是 CLI/卸载/运行时通过证明。本轮只更新这两份文档；不写判定脚本、不修改 registry、真实入口或记录库，不 commit/push。

## 1. 证据与冻结范围

| 来源 | 本轮采用的证据 |
|---|---|
| [任务书 M2-01](tasks.md) | 字段校验、身份、授权作用域、损坏恢复；未决项交用户裁定 |
| [M1-01 预检](../acceptance/m1-01/preflight.md) §5 | O4 为 AGM 状态边界；O5 来源冻结但通用获取待定；O8 兼容性边界；O9 歧义/部分写入停写 |
| [08-create-registry.json](../acceptance/m1-03/20261029T110112Z-round3/08-create-registry.json) | schema=1；基座/引用 reused、四链接与两块 created；WorkBuddy 当时 missing、runtime pending；argv 内保留实际构造及哈希算法 |
| [11-update-registry.json](../acceptance/m1-03/20261029T110112Z-round3/11-update-registry.json) | 加入 WorkBuddy 项目块、用户例外块及共享 reused 基座；WorkBuddy ready、runtime 仍 pending |
| 本机 `scripts/registry.json`（只读、不提交） | SHA-256 `ba54cd4ad8303d2cd703ccf643ffeb5d8781885e0fe5609dcd129bd802f58a7c`，与 11 的 after 快照一致；1 个主项目/checkout、10 个项目对象、2 个共享对象 |
| 本机 `scripts/agents.json` / `scripts/agm.py` | 路径表仅 darwin；CLI 只有占位函数，不能据文档声称已实现 |

已冻结的技术合同：沿用 schema_version=1 和现有字段，无缺字段默认；null 必须显式写入；新增字段需另行版本化。SHA-256 按原始文件字节、含 marker 块字节、解析后的链接目标 UTF-8 字节计算。四装配阶段分别保留四值 Fact 及证据，合法迁移见 architecture §2.3。created/reused/unknown 的删除边界不放宽。

CLI 固定三命令；本次派工明确 `--agent` 缺省为三家，不再作为待裁定项。目录存在仅是 hint，不改变目标，也不构成安装成功；只选 --agent codex 不授权写 Claude/WorkBuddy 入口。若上游普通安装会触及未选执行器的缺失 bridge，必须在调用前报告范围冲突并停止，不能扩大 argv 的有效写范围。

下列 D-M2-01 至 05 是完整的用户拍板清单；“建议”尚未生效。不因其他文档任务验收提到返回 5，就把 O6 的完整数值表视为用户已批准。

## 2. 需用户拍板清单

### D-M2-01 / O1：worktree 授权作用域

**需用户裁定。建议 A：每个 checkout 独立批准记忆选择及位置，主 checkout 的 yes/no 均不自动继承。** 同一 common-dir 只用于归组；每个 worktree 仍按 D3 重新 enable、现场核验入口/实际库并单独新会话验收。优点是一个分支的授权不外溢到另一分支或外置库，代价是增加一次首次确认。若采用 A，当前 Project.memory_authorization 不足以表达多个选择，需先定 schema v2，将授权与证据移至 Assembly（主 checkout 旧记录只迁入对应 Assembly），不能把旧 yes 复制给全部 worktree。

备选 B：记忆选择按主项目共享，但每 checkout 的库位置和装配仍单独批准；可沿用 schema v1，但必须明确 no 如何影响已有 worktree、外置库能否共用。备选 C：M2 只支持主 checkout，worktree 明确报告未支持，待后续再定。**未裁定期间按 C 的保护边界，不把 C 当作最终产品决策。** 不论选哪项，新 clone 不继承旧实例授权。

### D-M2-02 / O2：最后一个消费者 remove 后共享入口怎么办

**需用户裁定。建议 A：保留用户级一次性接入约定。** 项目 remove 仅释放该 checkout 的 shared_object_ids/consumers；消费者归零也保留共享对象、ownership、指纹和原创建依据，后续项目复用。不撤掉用户原有公共源或 AGENTS.md 约定，不把用户级接入变成单项目生命周期。优点是符合一次性接入定位、避免卸载项目改变其他用户工作流，代价是保留无消费者的受控块。

备选 B：最后一个消费者移除后，允许撤销本工具 created、唯一 marker、无漂移且批准范围包含该用户文件的共享块；reused/unknown、块外正文和记录库始终保留。消费者不为空、索引不一致或 registry 不可信时不得删除。若选 B，同一次 remove 的批准必须展示该用户块，不能将“卸载项目”默认为删全部用户约定。**未裁定时只保留，不执行用户共享块删除。**

### D-M2-03 / O7：丢失 registry 后 unknown 与 reused 如何落账

**需用户裁定。不可从现场恢复 created、原 yes/no 或 --all 项目列表，这条保护边界固定。建议 A：内存观察与重建账本分开。** check --project 里所有创建来源不明对象为 unknown；用户重新确认该项目选择/位置后，enable 将已完整核验的既有正确对象登记 reused（保留此次核验定位），无法核验来源或范围的对象仍 unknown；本次实际补建且有证据的单元可 created。重建前备份损坏原文件，不扫描整机，不擅自把其他旧项目补成空登记。

备选 B：重新批准 enable 后所有旧对象继续 unknown，直到用户逐项确认接管为 reused。B 更显式，但两者均不可删除旧对象，日常确认负担较大。**未裁定前 check 仅内存 unknown，写重建流程不落地。** 用户“批准启用”不能追认“过去由本工具创建”；备份 manifest 或 marker 单独存在也不自动恢复删除权。

### D-M2-04 / O6：非交互批准怎样传入 CLI

**需用户裁定。建议 A：增加写命令专用 `--approval-file <JSON>`，以明确、可核对的计划承载已获用户确认的范围。** 宿主先展示计划并取得确认，再生成批准文件；文件不是密码、签名或新的授权来源，任意 JSON 不能自证用户已批准。建议 envelope 必填 `schema_version=1`、`command`、`main_checkout`、`checkout`、`git_common_dir`、`agents`、`memory_authorization`（remove 时为 null，表示不改选择）、`store_path`（无库操作为 null）、`provider_source`、`provider_fingerprints`（路径/sha256 数组）、`changes`（path、operation、before_fingerprint、after_fingerprint）、`confirmed_at`、`reference`。agents 使用规范唯一顺序；所有 nullable 字段显式 null，changes 精确列出实际写集。CLI 核对命令/目标/库位置/源码/前指纹与锁内现场完全一致才写；范围扩大或现场变化则重新预览和确认。批准材料由调用者放在项目外，不扩成第二份纳管状态。

备选 B：新增 `--approved` 与明确库位置参数，由外层宿主保存批准证据并保证范围；界面更短，但批准范围约束弱，需要额外规定引用来源和重核机制。备选 C：本期只允许交互完成首次批准，非交互遇缺批准返回待确认，可执行已有有效范围内的幂等补装。**裁定前不实现任何新增公开参数，非交互缺批准即停；--memory 只表明选择，不能代替位置或用户级写入批准。** A 的字段方案也需与参数选择一并认可，非“已批准 schema”。

### D-M2-05 / O6：公开退出码和合并优先级

**需用户裁定。建议采用 architecture §4 的表：0 完成、1 check 缺口、2 参数/schema/冲突/执行或恢复失败、3 Keeper 迁移门禁、5 待授权。** 详细差异用 errors.code，不新增大量数值。安装器 rc=0 + approval_required 映射待授权；init rc=2 原样归执行失败，不能冒充迁移；未知子进程非零归失败并保留原码。多项目结果建议优先级 2 > 3 > 5 > 1 > 0，JSON 完整保留所有错误，迁移相关读写仍立即停止。

备选：将参数错误与执行/恢复失败拆分为不同数值（例如 2 与另行选定的值），提高 shell 自动化分辨率，代价是更大兼容面。若希望迁移总压过执行失败，也需明确调整优先级；不能靠最后一个子进程的 rc 决定总退出码。数值和优先级未裁定前仅作为实现建议；Keeper 自身 rc=3 的停写语义已经固定，不受本表待批影响。

## 3. 与实际 registry 的差异及迁移说明

| 项目 | round3 实际 | v2 合同/建议 | 迁移与本轮动作 |
|---|---|---|---|
| schema/字段/层级 | schema=1，字段与原草案一致 | 保持 schema=1；本文 v2 是文档版本 | 无结构迁移；本轮未改 registry |
| 缺省/必填 | 构造时显式写全部字段、null | 明确全必填，不为损坏记录补默认 | 现有单主 checkout 无新增字段；后续实现读取校验 |
| original_existed | bridge=false，承载 AGENTS/CLAUDE 文件可已存在 | 定义为“可撤销单元原先存在”，非承载文件 | 保留值；恢复整文件必须用 manifest 的文件存在信息 |
| SHA-256 | 原始字节块/文件、resolved target UTF-8 | 同算法；新增拒绝重复/残缺 marker 的校验 | 不重算/覆盖基线指纹，不把验旧算法当现场验收 |
| import | reused、marker=null，整文件 fingerprint | v1 限于只读复用/保护；不可据此删除引用行 | 无迁移；未来要撤销新建 import 先扩单元定位合同并版本化 |
| reused base + created block | 同文件双记录，base 为含块的完整快照 | 拆分所有权粒度；块变化与块外变化分别判断 | 不因 base 整文件变化升级所有权或删除文件 |
| 工作树授权 | Project 单个 yes、1 个主 checkout | 单 checkout 可表达；O1-A 需 checkout 级授权 | 若 A 获批另制 schema v2 迁移；只迁已知主 checkout，不填新 worktree 授权 |
| shared consumers | 两个共享对象均有当前主 checkout 消费者 | 双向一致；归零保留/删除待 O2 | 当前无差异；remove 实现前选政策 |
| 运行验收 | pending、evidence_path=null | 原样允许，与静态四阶段全 ready 独立 | 不把 ready 升为 passed；本轮不作运行验收 |
| evidence | 字符串可含多个路径、说明 | 保留字符串定位，不强转结构数组 | 无迁移，不回写旧证据 |
| Git 实例身份 | 仅路径与 common-dir 路径 | 明确同路径重 clone 不可可靠检测 | 无迁移，不伪造检测能力；若要求增强另定字段/版本 |
| 所有权恢复 | 现账本记录 created/reused，来源为 08/11 | 丢失后不由同内容反推 created | 当前账本不降级、不重建；仅定义未来 O7 流程 |

schema v1 的收紧属于实现前合同细化，不声称已有脚本验证全部交叉条件。后续若校验发现历史记录不符合，应先报告字段/证据差异，再做获批迁移；不能为通过校验自动补批准或修改原始证据。

## 4. 输入与预期案例（后续测试设计，不是已跑用例）

| 输入/现场 | 预期 |
|---|---|
| 主 checkout 已登记 yes、位置批准、全部现场通过；默认 enable | 目标三家，保留 created/reused；只补批准范围的缺口，不重复询问原选择 |
| 主 checkout 先前 no；无 --memory | 保留 no，准备基座，不重复询问记忆；不以源码 ready 覆盖选择 |
| cwd 为主 checkout 子目录；省略 --project | 定位 Git 根；显式 --project 指子目录则参数错误 |
| 同一 common-dir 的新 linked worktree | 按 O1 待裁定保护边界只报告，不继承 yes 或装配；A 获批后需独立授权 |
| 新 clone 在不同绝对路径、同 remote/同 HEAD | 新实例，不能继承旧授权/created；入口既存按 reused/unknown 保护 |
| 删除后同路径重 clone | 仅 v1 字段无法保证识别；不得宣称检测通过，已知替换必须重新确认 |
| 项目移到另一目录，旧路径失效 | check 报旧登记失配；新路径需重新 enable，不按 basename 搬授权 |
| A/B 共用一个 created 用户块，remove A | 仅释放 A；B 消费仍在，禁止删除共享块 |
| B 为最后消费者；块无漂移 | O2 未裁定保留；A 方案保留且 consumers=[]；B 方案须同次批准后精确撤块 |
| shared IDs 与 consumers 不一致/用户块漂移 | 报冲突，不靠“最后一个消费者”删除或重算哈希 |
| registry 丢失，check --all | 无法枚举全部，报告索引缺失/范围不完整，无全盘扫描，无落盘 |
| registry 损坏，check --project R | 在内存报告现场、未知授权/所有权；不写备份、锁或 registry |
| 重新批准 enable、已有同模板块 | 依 O7 选择 reused/unknown，绝不变 created；批准不是历史来源证明 |
| --agent codex，但上游将新增 Claude bridge | 停止范围冲突；不借上游组合副作用触碰未选执行器 |
| 非交互 --memory、位置尚未确认 | 待确认，不 init；D-M2-04 未批前无绕行批准参数 |
| 重复字段/未知枚举/created 缺证据/schema 不认识 | 拒绝写入，不默认修复或跳过坏字段 |
| Keeper rc=3 或 init 双候选 rc=2 | 前者立即停相关读写；后者报告歧义失败，不改上游、不删库消歧 |

## 5. 后续开工门槛

M2-02 可据已冻结单 checkout 字段、指纹与证据合同设计内核；worktree 写入、共享归零删除、丢失账本重建和新增公开批准参数必须先等对应裁定。M2-03 的返回码及非交互承载按 D-M2-04/05 拍板后落地，不以本文建议替代授权。O5 通用源码获取仍属 M2-04 前另裁定项，本文不默许下载或换来源。

## 5. 用户裁定(2026-10-29,当场生效)

| 编号 | 裁定 | 说明 |
|---|---|---|
| D-M2-01 / O1 | **选 C:本期只支持主 checkout** | worktree 明确报告未支持,待后续版本再定;新 clone 不继承授权(维持) |
| D-M2-02 / O2 | 按建议 | 最后消费者退出后**保留**用户级约定 |
| D-M2-03 / O7 | 按建议 | 已核验对象登记 reused,无法核验保留 unknown;均不恢复 created |
| D-M2-04 / O6 | 按建议 A | 新增 `--approval-file`,绑定具体执行计划的批准 |
| D-M2-05 / O6 | 按建议 | 退出码 0/1/2/3/5;多项目优先级 2 > 3 > 5 > 1 > 0 |

以上裁定依据用户 2026-10-29 会话指令;§2 各节的"建议"表述自此视为已生效的产品决策。WorkBuddy 接力第三环结果待回贴,不影响本节效力。
