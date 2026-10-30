# 实现架构 v2（M2-01 定稿稿）

基线：DESIGN.md v1.1，53314d7；v2 于 2026-10-29 对照 M1 round3 实际 registry 定稿字段及校验合同。文档版本 v2 不等于 registry schema 升版，后者仍为 1。本文细化实现，不改变 D1–D7；CLI 仍是占位，本文不证明工具或运行时验收完成。政策建议及需用户裁定项见 [decisions-m2.md](decisions-m2.md)，未裁定项不得当作批准实现。M1 macOS、单仓库；M2 工具化。Skills/MCP 管理、用户级全面整理、记忆内容加工均不在本期。

## 0. 文档发现与允许接口

| 来源（本机只读源码） | 已核验接口／可借鉴位置 | 禁止假设 |
|---|---|---|
| ../context-keeper/scripts/install.py:14–33 | BRIDGE_START/END、BRIDGE 语义 | 标记存在不等于指纹无漂移 |
| 同文件:40–66、264–283 | _skill_roots、build_parser 的实际参数 | 不发明 --skill-only；不使用 --all 扩到七执行器 |
| 同文件:168–221 | _ensure_bridge；单个 codex 或 claude；已安装别名决定范围 | --ensure-bridge 不可与 --project/--uninstall 混用；WorkBuddy 停写 |
| 同文件:286–388 | main 安装会一并写 Codex/Claude bridge；预览 approval_required 且 rc=0 | 不能先调用安装器再检查漂移；退出 0 不等于完成 |
| ../context-keeper/SKILL.md、references/save.md | 授权、追加日志、迁移门禁；init --store-dir；record-path/guard | 不从旧摘要推导当前授权；不自己生成 Keeper 记录结构 |
| ~/.agents-group/sync.py:21–100 | group_lock、managed_span、fingerprint、is_owned_link、put、block | fcntl 非跨平台；不直接依赖旧目录代码 |
| ~/.agents-group/project_manage.py:116–207 | project_sync 的快照、现场读回、外置登记、失败恢复 | 不复用其项目 .agents-group/state.json |
| ~/.agents-group/manage.py:15–51 | capture_outputs / restore_outputs 的文件模式、链接及回滚读回 | 不能把恢复尝试等同恢复成功 |

开工时重读这些位置并记录上游提交/文件哈希；行号只是本次定位。模板保留当前 BRIDGE 全部七条语义，另加 WorkBuddy 说明，不形成新的记忆运行时。接口提取与方案撰写分离，旧体系只借鉴机制。

## 1. 模块与调用方向

M1 可由人工严格执行同一顺序，不以先完成整个 M2 CLI 为前提；持久记账、安全写入能力若提前实现，归入 M2 任务并复用，禁止另造一次性安装器。

| 计划文件 | 职责 | 不承担 |
|---|---|---|
| scripts/agm.py | argparse、三命令分派、输出与退出码 | 不承载记忆算法 |
| scripts/agm_core/enable.py | 基座→记忆四态→逐项补缺；接管已有对象 | 不把复用对象改成 created |
| scripts/agm_core/remove.py | 所有权过滤、漂移保护、撤销本工具对象 | 不删记录库、既有规则正文或其他项目所用用户入口 |
| scripts/agm_core/check.py | 登记×执行器矩阵、现场事实、告警 | 不写 registry/锁/备份/入口，不调用会写缓存的 Keeper 探针 |
| scripts/agm_core/project.py | Git 根、主 checkout、worktree 身份与现场 Git 状态 | 不提交、清理或切分支 |
| scripts/agm_core/registry.py | 校验、原子提交、本机所有权账本 | 不存项目事实、会话正文 |
| scripts/agm_core/entries.py | 标记、块指纹、引用与 WorkBuddy 顶部块 | 不重写块外内容 |
| scripts/agm_core/transaction.py | 写命令锁、预检、时间戳备份 manifest、写后读回、回滚 | 不给 check 产生副作用 |
| scripts/agm_core/keeper.py | 固定 provider 的子进程协议、批准/迁移识别 | 无通用 provider 框架、无静默备用来源 |
| scripts/agents.json / templates/workbuddy-bridge.md | 路径数据／暂存桥接模板 | 不持有当前机器事实 |

这些模块是规划，当前仅 agm.py docstring/空函数骨架；不要为模块数强拆任务。依赖方向：命令→共享内核→文件系统/已核验 Keeper CLI。Keeper 不感知 AGM。

## 2. 集中 registry.json 完整字段合同

唯一位置：安装源 scripts/registry.json；运行时生成且 gitignore，不提交示例状态、不在被管项目放 AGM 状态。以下 schema v1 与 round3 实际字段一致；所有字段必填，可空字段显式为 null，没有可省略字段。新登记初始化值见 §2.1，不可用初始化值补齐损坏账本。未知字段/版本/枚举、重复 JSON 键/对象 ID、路径越界均拒绝写入，不宽松补默认授权。

~~~text
Registry = {
  schema_version: 1,
  projects: Map<MainCheckoutAbsolutePath, Project>,
  shared_objects: Map<ObjectId, OwnedObject>
}
Project = {
  main_checkout: AbsolutePath,                 # 必须等于 projects 的键
  memory_authorization: "yes" | "no" | null,  # null 为未知；损坏账本仅内存表示
  authorization_evidence: Evidence | null,
  provider_source: AbsolutePath | null,
  checkouts: Map<CheckoutAbsolutePath, Assembly>
}
Assembly = {
  git_common_dir: AbsolutePath,
  agents: UniqueArray<"codex" | "claude" | "workbuddy">,
  states: {
    source_available: Fact,
    skill_installed: Map<Agent, Fact>,
    bridge_assembled: Map<Agent, Fact>,
    store_authorized_ready: Fact
  },
  store: {
    path: AbsolutePath | null,
    location_approved: boolean,
    approval_evidence: Evidence | null
  },
  objects: Map<ObjectId, OwnedObject>,
  shared_object_ids: UniqueArray<ObjectId>,
  runtime_acceptance: {
    status: "pending" | "passed" | "failed",
    evidence_path: AbsolutePath | null
  }
}
Fact = {
  status: "ready" | "missing" | "blocked" | "unknown",
  observed_at: UTC_ISO8601 | null,
  evidence: string | null
}
Evidence = {
  confirmed_at: UTC_ISO8601,
  reference: string                         # 批准消息/记录定位，不保存对话或隐私
}
OwnedObject = {
  kind: "file" | "block" | "import" | "skill_symlink" | "user_convention",
  path: AbsolutePath,
  scope: "project" | "user",
  agents: UniqueArray<Agent>,
  ownership: "created" | "reused" | "unknown",
  marker: { start: string, end: string } | null,
  fingerprint: { algorithm: "sha256", basis: "file_bytes" | "block_bytes" | "link_target", value: Hex64 } | null,
  original_existed: boolean | null,          # 指该可撤销单元，非必然指承载文件
  link_target: AbsolutePath | null,
  backup_manifest: AbsolutePath | null,
  consumers: UniqueArray<CheckoutAbsolutePath>
}
~~~

约束与生命周期：

- 四态为独立现场事实，不能由一个 ready 位倒推其他三态。某执行器 Skill 缺失时，只降级对应项；全量就绪必须所有目标执行器通过。
- 第四态 ready 必须同时满足本项目 yes、位置获确认、实际库可用、未触发迁移门禁。授权 yes 不代表建库完成；已发现库不代表本次授权。记录库内容不进 registry。
- no 在缺省 enable 与 check 中保留、不反复询问；用户明确 --memory 可改变先前选择并留下批准依据。null 不当作 yes；非交互缺省缺授权时返回待确认。
- 项目主 checkout 为键是 DESIGN 要求；checkouts 是处理同主仓多 worktree 的候选细化，涉及授权作用域的 O1 未决。M1 只用主 checkout；O1 关闭前 M2 不纳管多 worktree，不能把主 checkout 成功冒充 worktree 成功。
- 对象粒度以可撤销单元为准：同一 AGENTS.md 内基座与 Keeper bridge 分别记块；已有 @AGENTS.md 记 reused。文件由本工具新建也不代表将来整文件可删。
- 块指纹取起止标记及其间原始 UTF-8 字节（不含标记外换行）；符号链接记解析后目标路径的 UTF-8 字节哈希并保存目标，不能用上游整个源码哈希替代链接所有权。备份保留整文件原始字节/模式/链接目标。
- 块外新增不误判为块漂移；移除块保留外部字节。只有 created 且整文件仍完全匹配创建后指纹的空用途骨架才可删文件。不存在可信创建账本则 ownership=unknown，禁止删除。
- shared_objects 管用户级一次性约定；consumers 防止 remove 某项目时撤掉其他项目需要的入口。首次遇见已有约定是 reused。具体跨项目释放语义见 O2。
- registry 损坏时 check 只在内存重建可观察事实并输出；不得落盘或恢复授权/所有权。--all 失去项目索引则说明无法枚举全部，不全盘扫描。用户指定 --project 可检查该现场；随后授权 enable 才备份损坏文件并持久重建，未知所有权按保护处理。
- 移动/删除/重 clone 只告警，不凭同名项目继承授权；需要重新 enable。路径必须规范化绝对路径，Git common-dir 身份核对；符号链接输出路径冲突停止。

### 2.1 类型、必填、初始化与交叉校验（冻结）

- `Agent` 仅 `codex/claude/workbuddy`；JSON boolean 不当作 integer。`AbsolutePath` 为本机规范绝对路径，无 `~`、占位、`.`/`..`；checkout/main/common-dir/provider/store 按实际解析路径核对。对象 `path` 保留链接自身的绝对落点，不 resolve 成链接目标；目标独立放 `link_target`。输出落点的父链若出现未批准符号链接或越界即拒绝。
- `ObjectId` 为非空字符串，沿用实际“绝对落点”或“绝对落点#用途后缀”（如 `#base/#keeper/#import/#keeper-exception`）；不解析后缀推导权限。不同单元可同 path，ID 在整个 registry 唯一；同一 path/marker 不可重复登记为两个可撤销对象。
- `UTC_ISO8601` 为合法 UTC 时间，统一写 `YYYY-MM-DDTHH:MM:SS[.小数]Z`。`Hex64` 为 64 位小写十六进制。`Evidence.reference`、非 null 的 `Fact.evidence` 为非空定位字符串；允许 round3 的多个路径/说明串，不假设为单一路径，也不存原始对话。引用存在不等于授权可信，需核对来源与范围。
- 空 registry 的显式初值为 `schema_version=1, projects={}, shared_objects={}`。新 Project 的未知选择为 `memory_authorization=null, authorization_evidence=null, provider_source=null`；main_checkout 必须已解析。新 Assembly 必须已有合法 common-dir 和非空目标 agents，不能凭空登记 Git 身份。新 Fact 为 `unknown/null/null`；观测后才改 missing/blocked/ready。新 store 为 `path=null, location_approved=false, approval_evidence=null`；objects/shared IDs 为空，runtime 为 `pending/null`。这些是构造约定，不是读取时的缺字段默认。
- `yes/no` 均要求非 null 授权证据，null 选择对应 null 证据。`location_approved=true` 要求实际 path 和证据；false 时 approval_evidence 为 null，可有尚未批准的候选 path。provider_source 非 null 只说明已定位，不证明 source ready。
- agents 必须非空、唯一；写出按 codex、claude、workbuddy 排序。`skill_installed` 与 `bridge_assembled` 的键必须恰好等于 Assembly.agents。Codex 两个 Skill 落点都正确才可将 codex 的 Skill Fact 置 ready。新增目标取已登记集合与本次选择的并集；缩小本次 `--agent` 不暗中删除其他目标。
- ready/missing/blocked 必须有非 null observed_at 和 evidence；unknown 可全空，或附本次无法判明的时间与证据。`runtime_acceptance=passed/failed` 要求 evidence_path 非 null 且实际验收证据可定位；pending 可为 null。装配变更、源码身份变化或影响执行器的漂移使既有 passed 失效，下一次写命令登记 pending；check 只报告失效，不改历史登记。
- Assembly.objects 只放 scope=project 且 path 位于该 checkout 的对象；shared_objects 只放 scope=user 且位于已核验路径表允许的用户入口。自定义 store 可以在 checkout 外，但不是可卸载对象。shared_object_ids 必须全部存在，且引用与 shared object.consumers 双向一致；消费者只能是已登记 checkout。项目对象 consumers 恰为所属 checkout；共享 consumers 可空，表示保留的无消费者对象。
- fingerprint 非 null 时必须满足如下 basis 约束：`block` 必须有非空且不同的 start/end marker，fingerprint.basis=block_bytes；`skill_symlink` 必须 marker=null、link_target 非 null、basis=link_target；`file` 必须 marker/link_target=null、basis=file_bytes。`user_convention` 在 v1 只支持有 marker 的 block_bytes 单元。`import` 沿用 round3 的 marker=null、file_bytes、ownership=reused/unknown；v1 不支持自动删除整文件哈希承载的 import，不以整文件指纹声称可安全撤销一行。
- 非链接对象 link_target=null。created 要有 `original_existed=false`、非 null fingerprint 和可核验 backup_manifest；reused 要有 original_existed=true 和 fingerprint；unknown 的这三个证据字段允许 null，绝不因此获删除权。manifest 是必要线索而非单独的可信创建证明。

### 2.2 SHA-256 与所有权（冻结）

算法字段固定 `sha256`，value=`SHA256(输入字节).hexdigest()`；不 trim、不规范化 CRLF/BOM/Unicode、不附加换行。file_bytes 为整文件原始字节；block_bytes 为唯一 start marker 起至唯一 end marker 末尾（含两个 marker），不含块外换行。重复、倒序、嵌套/残缺 marker 均冲突，不按首次命中静默切片。link_target 为链接解析后的规范绝对目标路径 UTF-8 字节，不附换行；须同时确认现场仍是 symlink 且目标相符，普通目录同目标哈希不算链接。源码内容哈希另作预检证据，不替代链接所有权。此规则与 round3 08/11 操作中的 hashlib 实参一致。

`created` 仅来自本工具本次批准操作的“单元原先不存在→实际创建→读回成功→可信账本提交”；反复 enable 不降级为 reused。原来已存在的正确对象为 reused；发现时无法确认创建来源为 unknown。reused/unknown 不因同模板、同 marker、用户再次授权 enable、或重算指纹而升级为 created。unknown 经现场核验为正确既有对象可登记 reused，但仍不可删除；只有该对象已确证不存在、以后在另次批准操作中新建，才形成新的 created 记录，不能覆盖伪造旧历史。

created 漂移后保留原有所有权及期望指纹并报告 blocked，不刷新指纹掩盖漂移。对象丢失只报告 missing；批准后补建可重新记创建证据。卸载成功只从活动账本移除该对象/引用，历史留在 manifest；保留对象及 no/yes 选择不能随意抹掉。remove 不是撤销记忆选择，也不是删除记忆资产。

同文件 `#base` 的 reused 全文件快照与 `#keeper` created 块可以重叠：删除权限只来自块记录。受控块变化会改变全文件哈希，不能据此把 reused 基座升级或删掉整个文件；check 要区分自有块变化与块外变化。新建文件在其内部块移除后可保留空骨架；无可信整文件创建证据时不整文件删除。

### 2.3 四阶段事实与合法迁移（冻结）

“四态”指四个独立装配阶段，每个 Fact 又有 ready/missing/blocked/unknown 四个状态；不是四个顺次互斥的全局状态。源码/Skill/bridge 可以各自 ready，第四阶段仍 unknown/blocked。

| Fact 原状态 | 合法目标及条件 |
|---|---|
| unknown | unknown；只读核实后 ready/missing/blocked，必须附本次证据 |
| missing | missing；补建并读回或发现已存在正确对象后 ready；冲突/授权拒绝/迁移门禁后 blocked；无法继续观测后 unknown |
| ready | 复核后 ready；对象确证消失后 missing；漂移/权限/身份失配/授权失效后 blocked；不能观测时 unknown |
| blocked | 阻断仍在则 blocked；原因已解除且重新验证后 ready；确证不存在后 missing；无法确认原因或现场后 unknown |

状态改变只能基于新证据，不能仅凭子进程 rc=0 或其他阶段 ready。check 将迁移算在输出中，不更新时间戳、不写 registry。写命令只在获批范围内、读回后提交事实；失败报告现场与恢复结果，不先持久化 ready。

第四阶段遇迁移门禁/身份冲突/歧义即 blocked 并停止相关流程；其他情况依次判断：项目选择 null→unknown；no、位置未获批、身份冲突、旧库迁移门禁或歧义→blocked；yes 且位置获批但库确认缺失→missing；yes、位置获批、实际库可用、门禁通过→ready。普通目录存在/源码可用不构成库可用；check 无法通过只读证据判定迁移状态时报告 unknown，不调用会写缓存的探针。Fact 的历史 observed_at 不是永久有效期。

授权选择仅在明确新批准下 `null→yes/no`、`no→yes` 或 `yes→no`；无新批准保持原值。选择 no 不隐式卸载已有对象。ready 的降级不自动抹掉原批准；身份不再相符则原批准对当前 checkout 无效。运行验收仅新会话证据可 `pending→passed/failed`，重验可以改变 passed/failed，装配变动回 pending；不可由四阶段全 ready 推导 passed。

### 2.4 Git 身份、恢复与未裁定边界

Git 主 checkout 从 `git worktree list --porcelain` 与 `git rev-parse --git-common-dir` 的规范路径交叉确定，不按当前分支、仓库 basename 或 remote URL 判为同项目。普通 clone 的 Git 根即主 checkout；linked worktree 的根是 checkout，主键仍为主 checkout。显式 --project 必须是根，省略可从 cwd 子目录向上定位；不把其他 checkout 的入口或库当作本 checkout 已装好。

schema v1 保留 checkouts 容器，但当前批准合同仅覆盖主 checkout；O1 未决前不写 linked worktree、不复制主项目授权。check 可报告 worktree 与主键、未纳管事实。若选择独立授权方案，多 checkout 的 memory_authorization 必须移到 Assembly 或增加 checkout 授权覆盖并升级 schema，不能复用当前 Project 的单个 yes/no 模拟。

路径/common-dir 足以发现不同路径 clone、移动或 common-dir 变化；**无法可靠识别“删掉后在同路径重 clone”或原位替换 .git**。不把 HEAD/remote 内容相同作为实例身份。该限制必须报告，v1 不宣称自动检测所有重 clone；已知更换实例需重新 enable 并取得当前授权。若要求自动识别此情形，先另定外置实例证据及 schema 升版，不在项目创建 UUID/AGM 状态。

registry 丢失/损坏时不恢复 created 或 yes/no；check --all 无索引即报告范围不完整，不扫描整机。check --project 只构造内存观察，未知所有权仍保护。O7 关于写重建后 unknown/reused 的取舍、O2 最后消费者释放政策未裁定前，保持不删除未知或用户共享对象的边界；具体候选及输入/预期矩阵见 decisions-m2.md。

## 3. agents.json 路径表合同

当前骨架在 scripts/agents.json，只定义 darwin。顶层 schema_version=1，platforms 为 OS→Agent→配置映射；Agent 限定上述三家。每项包含：

| 字段 | 类型与语义 |
|---|---|
| user_entry | 字符串，用户级原生规则文件 |
| project_rule_entry | 字符串，项目规则的入口；WorkBuddy 通过用户约定读此路径 |
| project_bridge_entry | 字符串，自动记忆入口写入落点 |
| project_skill_roots | 非空唯一字符串数组，安装器对应的原生 Skill 根 |
| installation_signals | 非空数组，每项 kind=directory_exists、path=字符串、strength=hint |
| rule_mode | native / import_agents / user_convention |
| bridge_owner | context-keeper / agent-group-memory |
| runtime_status | upstream_verified_local_pending / pending；本机通过写 registry，不改静态表 |

路径表所有表列字段必填、无读取缺省；路径/模式/枚举为非空字符串，schema_version 为整数 1，未知版本/字段/重复 JSON 键拒绝。platforms 至少一个 OS，每个平台应完整列出三家（不完整平台不能冒充已支持）；静态 runtime_status 不接受 passed。数组项不重复；installation_signals 仅接受表列三个必填字段及固定 kind/strength，不将其扩展为命令执行器。未来平台条目先取得实证，不按操作系统名称猜路径。

仅允许 {home}、{project} 占位，分别由 Path.home()、校验后的 checkout 根展开；未知 OS/占位停止，不硬套 macOS。目录存在只表示安装线索，可能为残留；目录不存在也不能证明未安装。显式 --agent 与用户确认决定目标，目录线索不授权写入，也不证明 CLI/应用可运行。后续若加入应用 bundle/命令信号，先实证再扩 schema，不猜 WorkBuddy 应用包名。

## 4. CLI 参数与输出约定

~~~text
python3 scripts/agm.py enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...] [--memory|--no-memory]
python3 scripts/agm.py remove-memory [--project <Git根>]
python3 scripts/agm.py check-memory [--project <Git根>|--all]
~~~

--project 缺省从 cwd 定位 Git 根，显式路径要求是 Git 根；--agent 一次接受多个唯一值，未知值拒绝。--memory 与 --no-memory 互斥；--all 仅 check 可用。`enable-memory` 未指定 --agent 时目标固定为 codex、claude、workbuddy 三家（本次任务指定），不按残留目录缩减；显式 --agent 非空且一次使用，重复值拒绝，不能影响未选执行器。M1 历史操作仍以其显式参数为证。不新增公开 --force/--repair 或第四子命令。骨架未接 argparse，不应运行它验收 CLI。

enable 总是准备规则基座；--no-memory 不装记忆且记录 no；缺省未就绪推荐说明后取得同意，已就绪且有授权直接补装，曾拒绝不重复问。provider 已就绪但项目授权未知，不能据此默认同意。交互确认须展示范围与记录路径；非交互需要用户决定的步骤停止并返回结构化待确认信息，不自行批准。

参数只适用于示例中列明的命令；remove 不接受 --agent/--memory，按当前 checkout 登记目标撤销；check 不接受任何写入批准参数。省略 --all 的 check 仅当前目标，--all 不与 --project 同用。未知参数、重复单值参数、空 --agent 与互斥组合必须在写入前拒绝。--memory 表达启用选择，不等于批准任意用户级文件或任意记录库位置；--no-memory 仍需合法基座写范围。TTY 只影响能否提问，不扩大权限；非 TTY 不从 stdin 猜测 yes，不因 CI/环境变量自动批准。

非交互批准承载**尚未批准公开参数**。D-M2-04 建议新增 `--approval-file <JSON>`（只限两写命令），由宿主将用户已确认的具体计划绑定到命令、主键/checkout/common-dir、目标 agents、记忆选择、实际库位置、源码身份、对象变更和预期前指纹；字段方案与备选见 decisions-m2.md。在裁定前，非交互遇缺批准只能返回待确认，不能擅加 --yes/--approved/--store-dir 等 AGM 参数。上游自己的 --approved 仅在 AGM 已验证同范围批准后传入，不成为用户批准的替代来源。

输出合同：stdout 单个 JSON 对象，stderr 人读诊断/交互提示；JSON 含 schema_version=1、command、status、projects[]、changes[]、warnings[]、errors[]、approval_required、next_action。projects[] 每项含主键、checkout、四态、目标 agents 与 evidence；changes[] 每项含 path、operation、ownership、before/after 指纹、applied 布尔；errors[] 含 code、path（可 null）、message、recovery。check 的 changes 永远为空，候选修复放 next_action。status 固定 completed/gaps/approval_required/migration_required/failed/recovery_required；approval_required 为 boolean，projects/changes/warnings/errors 为数组；next_action 为字符串或 null。解析失败仍尽量输出同一 JSON envelope（command 可 null），帮助文本不属于执行结果。项目项字段为 main_checkout、checkout、states、agents、evidence、runtime_acceptance（沿用登记结构，现场判失效时输出 pending 并告警）；evidence 为定位字符串数组。change.operation 为 create/update/remove，applied 仅表示最终保留的本次变更，回滚成功置 false；指纹可 null，失败的中间写入在 errors/recovery 中报告。before/after 字段名固定为 before_fingerprint/after_fingerprint。不得输出凭据或私有记忆正文。

| 退出码（建议，需用户裁定 D-M2-05） | 含义 |
|---|---|
| 0 | 请求完成；check 仅说明静态检查结果，不代表新会话验收 |
| 1 | check 发现缺口/漂移，需用户 enable 或人工核对 |
| 2 | 参数、路径、schema、冲突或执行失败（具体 errors.code 区分） |
| 3 | Keeper 迁移门禁，停止相关读写 |
| 5 | 需授权/确认，未完成请求 |

建议表获批准后：安装器 rc=0 + approval_required 映射 AGM 5；probe init 的 5 同样处理；init 的 2 不伪装成 3。未知子进程失败一律不提升就绪。运行时验收 pending 与装配 ready 分开呈现。建议多结果退出优先级：执行/参数/schema/恢复失败 2 > 迁移 3 > 待确认 5 > 检查缺口 1 > 完成 0；即使返回 2 也保留 migration_required 错误，绝不继续迁移相关读写。第四阶段因显式 no 被阻断时，enable --no-memory 的已批准基座完成可返回 0；check 则以 gaps 说明记忆未启用。运行验收 pending 本身不将静态 check 判为失败；请求的静态条件缺口才返回 1。

## 5. 写命令的执行与恢复

顺序：解析目标→只读 Git 状态与所有对象现状→取得必要授权→写锁→锁内重新核对指纹/Git 身份→时间戳备份和 manifest→执行最小变更→逐项读回→原子提交 registry→提示新会话验收。备份只含本次受影响配置，不采集私有记忆库；记录库本体不进入 AGM 回滚集。未关联本次修改的 dirty 文件保留；目标文件 dirty 或权限/链接歧义时展示冲突，不覆盖。

manifest 位于安装源 scripts/backups/<UTC时间-操作ID>/，含 operation、路径、原先存在与否、文件模式、链接目标、前/后指纹、恢复结果。不纳入 Git；90 天只提示清理，不自动删除。多文件操作不能声称文件系统原子事务：registry 最后提交，部分失败按备份恢复且读回；恢复失败保留现场与 manifest，报告 recovery_required。Keeper init 已创建的库不回删；它是项目资产，未完成装配可重新核对后续做。

remove：逐对象验证 created、指纹与消费者→只撤销当前对象→保留 reused/unknown→保留全部记录库及私有自动记忆→读回更新账本。不能直接整包调用上游 --uninstall：它会同时删 Skill 与 bridge，且共享 .agents/skills 可能要求 --all（范围过宽）。精确卸载策略由 M2-06 验证；借鉴 _check_remove_target，不能绕过所有权。

check：不 mkdir、不创建锁、不更新时间戳登记、不修桥接、不 init。只读现场元数据、入口与登记；模拟只读文件系统验证。检测 AGENTS.override.md、引用缺失、规则双写增长、桥接丢失/漂移、库授权未知、项目失配与旧 WorkBuddy 约定冲突，报告人工处理/enable 路径。

## 6. context-keeper 调用边界

所有调用采用 subprocess 参数数组、sys.executable、UTF-8；不 shell 拼接、不 curl/安装 pip、不为安装失败复制 Skill 目录。只调用已核验源码，不导入其内部函数作为稳定 API。Python ≥3.9 是 AGM 约束，上游解释器最低兼容性另见 O8。

1. 先确认源码实际路径与身份；源码缺失时的获取来源/版本未定（O5），不暗中下载。检查当前全部 Skill 目标、Codex/Claude 入口块及 registry 指纹。已有正确对象记 reused；手改块停止。
2. 预览普通安装（占位变量由宿主填入已核验绝对路径）：
   ~~~text
   <python> <source>/scripts/install.py --project <root> --codex --claude --workbuddy
   ~~~
   它可能写两个 bridge，必须在调用前已检查二者。取得此次具体写范围授权后才在同参数末尾加 --approved；不能认为总任务授权已批准任意建库位置。
3. 分别调用已安装项目别名，确保不是用户级范围：
   ~~~text
   <python> <source>/scripts/install.py --ensure-bridge --skill-dir <root>/.agents/skills/context-keeper --root <root> --codex
   <python> <source>/scripts/install.py --ensure-bridge --skill-dir <root>/.claude/skills/context-keeper --root <root> --claude
   ~~~
   如普通安装已经写好，通常返回 unchanged；只有已批准同一范围且预检未变才可加 --approved。结果必须 scope=project、bridge=预期文件，否则停止。绝不向 WorkBuddy 传 --ensure-bridge。
4. AGM 将 templates/workbuddy-bridge.md 置于项目 MEMORY.md 顶部，单一完整标记，保留原生正文与每日日志；用户级 MEMORY.md 保留公共源与 AGENTS.md 约定，只追加“项目记忆用 context-keeper 记录库，由项目桥接块驱动”。实际部署是后续获批 M1 操作，本轮不写家目录。
5. 授权记录库：
   ~~~text
   <python> <source>/scripts/context_keeper_probe.py init --root <root>
   <python> <source>/scripts/context_keeper_probe.py init --root <root> --store-dir <confirmed-path> --approved
   ~~~
   默认位置批准可省 --store-dir；rc=5 先展示位置，rc=0 后读回实际位置并保存授权依据。已存在库仍需核对项目授权。自定义路径可能由 Keeper 产生 context-keeper.json，这是 provider 配置而非 AGM 状态；O4 要澄清措辞。
6. Keeper 任一命令 rc=3 立即停止相关读写，只转告用户按其 migrate 预览/审批流程处理。不得手读旧库来“恢复事实”、改结构或自动加 --approved。普通安装不探测所有旧库，不能以安装成功证明迁移门禁通过。
7. 后续记忆写入全部走 Keeper Skill 的实际路径、record-path/guard、session-id、save-report；AGM 不包办内容生成和蒸馏。M3 回传模板及证据后验证旧块接管再删除本地模板。

## 7. 错误到恢复的映射

| 现场 | 当前动作 | 恢复 |
|---|---|---|
| 源码缺失/目标复制目录/异源链接 | 停记忆档，基座可独立报告 | 用户核对来源后重新 enable，禁止覆盖副本 |
| 标记重复/残缺/块指纹漂移 | 安装器调用前停止 | 展示差异、人工裁定；无 force 覆盖 |
| preview approval_required 或 init rc=5 | 不记完成，不置第四态 | 取得对应范围/位置确认后继续 |
| registry 缺失/损坏 | check 内存报告；授权与所有权未知 | enable 获授权重建，已有对象只复用 |
| WorkBuddy 重置丢块 | check 报缺失 | 用户 enable 补齐，再开新会话验证 |
| 锁冲突/写失败/读回不符 | 不继续后续阶段 | 恢复本次配置，校验；失败保留证据 |
| 迁移 rc=3 | 停止相关读写 | Keeper 迁移门禁，不绕行 |
| 记录库位置歧义/冲突 | 不猜实际库，不创建第二库 | 用户明确定位并遵守上游限制 |
| 删除/移动/重 clone 或 worktree 未决 | 不继承旧装配成功 | 用户重新 enable，O1 决定 worktree 记账 |
