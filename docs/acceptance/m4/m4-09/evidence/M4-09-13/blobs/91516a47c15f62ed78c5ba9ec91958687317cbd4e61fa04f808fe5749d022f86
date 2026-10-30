# CK 上游接口只读核验（2026-10-30）

## 结论与核验边界

按执行器进行 CK 用户级安装的接口可直接使用，省略 `--project`，只传实际已接入执行器对应的开关；不需要 `--all`。安装会同时配置 Skill 链接和用户级规则块，不能只批准 Skill 目录。安装器预览返回 0 并带 `approval_required=true`，不是安装成功。

§24 的实现假设有三处需明确修正：

1. 首次 `/context-keeper` 是菜单和自动入口检查，不是自动建库。首次保存才进入记录库位置确认，随后由 CK 初始化。
2. CK 不读取 memSharing 的 `disabled` 政策，也没有对应的脚本级拒写接口。停用保护由项目规则约束 Agent；不能宣称 CK 命令本身强制执行该政策。
3. CK 不识别 `mem-sharing:project-experience`。新协议与 CK 自有块可以共存，但新块不会替代 CK 自有块；如果 CK 解析到项目级 Skill，后续 ensure 仍可能在项目规则中新增 CK 块。只换标记不足以保证项目始终只有三行短协议。

本轮仅静态阅读文件、查询本地 Git 身份与工作树状态；未运行 CK 安装器、probe、初始化、ensure、迁移或测试，未对宿主入口、CK 源码、记录库做写入。结论是接口与控制流核验，不是安装或三家运行时验收。本仓仅新增本文件，不更新日志，不提交或推送。

### 证据定位约定

下文 `CK/` 指真实源码根 `/Users/vincent4j/Tools/Source/context-keeper/`，所有 `文件:行号` 都相对于此根，除非明确写为本仓文件。行号绑定本轮核验提交：

```text
695074ee4b6ddb9999be858093f833d6377bd641
```

本轮 `git status --porcelain` 无输出。建议将该完整 commit 作为集成参考 pin，不用浮动 `main`，也不把 `SKILL.md` 的 `version: 1.0.0` 当作代码唯一身份。未联网核验远程最新版本，不声称这是上游最新发行。

入口追溯：用户指定的 `~/.agents/skills/context-keeper` 是指向上述根目录的符号链接，`git rev-parse --show-toplevel` 与其一致。`references/install.md:3` 声明单一真实副本，`:16-18` 给出官方 Git 来源和核对 HEAD 的方式，但没有声明本机绝对路径；本机路径由安装别名解析和 Git 根查询确认，不能从文档猜测。`SKILL.md:17` 同样要求从唯一源码加载。

本仓读取到的 HEAD 为 `a36c24442b2e217a9f63f9f62f063a705f87dc1d`，有并行改名及文档工作，不作为未来动笔基线。决策采用本仓 `docs/plan/decisions-m4.md:388-419`：§26 覆盖 §24 的 pre-release 转换链；本报告不恢复已取消的 P→v2→v3 承诺。

## 1. 用户级按执行器安装

### 参数与落点

真实参数定义在 `CK/scripts/install.py:287-305`：

| 参数 | 实际含义 |
|---|---|
| `--codex`、`--claude`、`--workbuddy` | 可同时选择；安装到指定执行器 |
| 无 `--project` | 用户级；`main` 将 project 设为 None |
| `--approved` | 从预览转为执行，不接受 memSharing 的批准文件 |
| `--all` | 选择上游全部七家，超出 memSharing 当前三家范围；不用 |
| `--bridge-only` | 仅入口，不满足本任务安装 Skill 的目标；不用 |
| `--ensure-bridge` | 首次使用时的单执行器补入口，与多执行器安装是不同分支；尾步不用 |
| `--codex-dir`、`--claude-dir` | 自定义根；正常用户级集成不需要 |

`main` 要求显式目标，不按目录或命令猜测宿主（`CK/scripts/install.py:314-322`）；用户级范围判定与桥接目标构造见 `:327-337`。

| 执行器 | 用户级 Skill 链接 | 同时写入的用户规则文件 |
|---|---|---|
| Codex | `~/.agents/skills/context-keeper`、`~/.codex/skills/context-keeper` | `~/.codex/AGENTS.md` |
| Claude Code | `~/.claude/skills/context-keeper` | `~/.claude/CLAUDE.md` |
| WorkBuddy | `~/.workbuddy/skills/context-keeper` | `~/.workbuddy/MEMORY.md` |

证据：`CK/scripts/install.py:47-73` 的 HOME/roots、`:154-158` 的规则文件。多执行器共享同一解析根时去重（`:340-347`）。源码没有按宿主“是否已安装”筛选的逻辑，实际已接入名单必须由 memSharing 传入。

### 幂等、现有目录和冲突

- `skills` 父目录已经存在是正常情况；目标是其下名为 `context-keeper` 的子项。目标缺失时创建父目录与源码链接；目标已链接到同一源码则复用（`CK/scripts/install.py:102-124`）。
- 同名目标指向其他来源时拒绝；包括其他来源符号链接，不自动替换。真实复制目录即使含 `name: context-keeper` 也拒绝，避免删除局部修改；无法确认归属的目录同样拒绝（`:102-112`）。
- 同源链接复用不等于内容固定：链接仍指向可变源码目录；memSharing 的 pin 和执行前内容核对不可省略。上游 Git 源验证分支只看 `.git` 是否存在，不验证 clean HEAD/commit；无 Git 时另有安装包 manifest 校验（`:76-99`）。
- 原规则块与当前模板字节一致时 `unchanged`；WB 还要求块位于顶部。不同则更新；缺失则追加，WB 为前置（`:161-186`）。块外 CRLF 与尾部字节通过直接解码/编码保留（`:168-185`）。
- CK 只检查自己的标记数目与顺序，不检查 memSharing 的已登记指纹。完整标记中的正文即使被用户编辑，也会被批准安装更新，不能据此声称“上游自动阻止所有漂移”（`:189-206`、`:172-180`）。memSharing 独立封皮仍需绑定实际前指纹，遇自身受管单元漂移停止。
- 全部 Skill 目标与选中规则块在写入前检查（`:357-362`）；执行中的 RuntimeError/OSError 尝试恢复原桥接字节并移除本次新建链接（`:383-410`），不保证清理所有新建父目录，不把异常结果当无残留。

### 退出码与结果协议

| 情况 | 结果 | 证据 |
|---|---|---|
| 普通安装未带 `--approved` | rc=0，JSON 含 `approval_required=true`、`skill_entries`、`rule_files` | `CK/scripts/install.py:364-373` |
| 已执行完成 | rc=0，JSON 含 scope/project/installed/bridges/configured_agents | `:411-419` |
| ensure 已是当前版本 | rc=0，JSON action=unchanged | `:245-248` |
| ensure 需要确认 | rc=0，JSON approval_required=true | `:249-252` |
| 配置冲突或系统读写错误 | 外层捕获 RuntimeError/OSError，打印失败文本，退出 2 | `:422-427` |
| 参数解析错误 | argparse 默认错误路径，退出 2；非上述成功 JSON | `:287-288`、`:309-310` |

安装器没有 init 的 rc=5 或旧记录迁移的 rc=3 分支；这些属于 probe 协议，不能混在同一成功判据里。异常类别未被外层捕获时也不能假设固定 rc=2。封皮消费者应对非零、非 JSON、结果缺字段、范围不符、超时和结果不明分别拒绝报 configured。

## 2. 首次命令、记录库与停用

### 实际流程

1. 调用 Skill 时先按 `SKILL.md:23-31` 进行当前执行器的 ensure 预览/确认；其作用仅为入口，不建库（`references/install.md:21-37`）。用户级别名会映射到用户级规则，`--root <repo>` 不强制将 ensure 写到项目。
2. 只输入 `/context-keeper` 而未指定动作时展示保存/继续/查找菜单；已给出动作则直接路由（`SKILL.md:66-78`）。不是 slash 一出现就调用 init。
3. 首次保存由 `references/save.md:5-19` 引导；先确认项目和用户保存意图，再预览 init，取得位置确认后执行。无授权库时普通工作结果不自动建库或询问（`SKILL.md:84-95`）。

因此“项目级不默认开启”与现有上游一致，装机时无记录库创建；“首次命令激活”应解释为“首次命令进入 CK 流程，按所选动作确认并初始化”，不能写成“首次命令保证建库”。

### 路径与创建条件

- 默认 `docs/context-keeper/`；自动发现 `docs/context-keeper/` 与根下 `context-keeper/`，候选歧义即拒绝（`CK/scripts/context_keeper_probe.py:24-25`、`:73-107`）。
- 优先显式 `--store-dir`；无显式参数时先发现候选，再读 `context-keeper.json`，最后默认值。不是配置文件无条件覆盖已发现候选（`:73-84`）。
- 已发现目标库且位置一致时 init 直接 rc=0，不再要求批准（`:782-795`）。这里“像记录库”的检查只需命中任一标记，不等于全面校验记录库健康（`:91-107`）；memSharing 不能把该返回值升格为第四态授权/健康。
- 新库缺 `--approved` 返回 rc=5 且不创建目录；有批准后才建 plans/worklogs/evolution、memory-keeper.md 和 evolution/index.md（`:850-878`）。默认候选路径会移除旧配置；候选之外、显式路径才写配置（`:864-867`，写配置内容见 `:117-121`）。
- 改记录位置需显式 `init --store-dir ... --migrate --approved`，拒绝目标非空、互相包含或证据链接将变向的迁移（`:802-831`）。这不是旧版目录结构的 migrate 子命令。

### 退出码 3 的真实门禁

probe 的 `main` 在调用具体子命令前查旧结构；除 migrate 外发现旧记录即返回 `_migration_warning`，后者 rc=3（`CK/scripts/context_keeper_probe.py:124-151`、`:1990-1999`）。所以 init 自身“库已存在即 rc=0”不能绕过 main 的旧结构门禁。`references/save.md:19` 的 init 返回值列表未列全局前置 rc=3，集成应按源码与 `SKILL.md:45` 的门禁处理。

memSharing 尾步不调用 probe；未来实际 CK 操作遇 rc=3，Agent 停止并遵循 CK migrate 预览与批准，不通过 memSharing 自动迁移，也不以根目录下已有新库为由继续读旧目录。

### disabled 与首次调用不是 CK 的机器状态

本轮在 CK `scripts/`、`SKILL.md`、`references/` 定点检索 `disabled`、`mem-sharing`、`memory-denied` 无命中；结合 init 的完整控制流，可确认没有读取 memSharing 政策的接口。CK 也不记录“本项目第一次 slash 已激活”的专门状态；已有获授权库可以自然触发保存（`SKILL.md:84-95`）。

§24 的 disabled 必须由 memSharing 保存并渲染为明确项目禁止自动记录/初始化的规则；默认启用不得删掉它，只有显式恢复批准才解除。该规则与 CK“用户禁止保存/改文件则跳过”的指令兼容（`SKILL.md:84`、`:93`；安装模板 `scripts/install.py:20`、`:39`），但这是 Agent 指令约束，不是直接执行 `probe init --approved` 时的硬门禁。人工显式保存/初始化请求与停用政策冲突时应先明确恢复/授权范围，不因普通 slash、菜单访问或 CK ensure 偷偷翻转政策。

## 3. 独立封皮的最小上游调用

以下仅是待实施时的调用示例，本轮没有执行：

```text
python3 -B <pinned-ck-source>/scripts/install.py --codex --claude --workbuddy
python3 -B <pinned-ck-source>/scripts/install.py --codex --claude --workbuddy --approved
```

最少一个实际目标开关即可；执行比预览只多 `--approved`。上游没有 `--approval-file`、`--context-keeper` 或 command=install-context-keeper 参数，独立封皮由 memSharing 自己校验，不能原样传给 CK。不传 `--project`、`--all`、`--root`、`--skill-dir`、`--ensure-bridge`、`--bridge-only`，也不调用 probe。

运行环境固定批准用户 HOME、持久源码目录与 Python 解释器；cwd 固定到已核验 CK 源。来源推荐 pin `695074ee4b6ddb9999be858093f833d6377bd641`，执行前验证其工作树/受执行内容和已批准来源一致；未来要用另一版本先重做接口核验。CK 安装的是源码链接，不能把源码放在会被清理的临时目录，或 memSharing 的可替换发行目录中。

封皮最小绑定：主产品安装身份、scope=user、实际目标名单、上述完整来源身份、预览 skill_entries/rule_files、前指纹、精确 argv、confirmed_at/reference。CK 自身只收 `--approved`，不核验外部封皮；精确比较与失效重预览归 memSharing，安装后仅验证本次配置范围，不恢复项目 provider 探针。

执行成功需 rc=0 且不是 approval_required，scope=user/project=null，配置的目标名单和落点匹配。`configured_agents` 使用显示名而非内部 ID（`CK/scripts/install.py:417`），消费者需明确映射。主产品成功与 CK 子步骤失败分别报告；上游普通安装没有逐规则文件独立读回步骤，memSharing 可对本次批准落点做配置读回，但不据此宣称 CK 行为验收通过。`references/install.md:37` 已说明配置与运行时的区别。

## 4. 标记兼容和双写风险

### CK 实际写入的标记

- Codex/Claude：`<!-- context-keeper:start -->` / `<!-- context-keeper:end -->`（`CK/scripts/install.py:12-14`）。
- WorkBuddy：`<!-- context-keeper:workbuddy:start -->` / `<!-- context-keeper:workbuddy:end -->`（`:29-43`）。
- ensure 根据当前宿主选择上述模板（`:148-158`），不认识 memSharing 新标记。

如果目标文件只有 `mem-sharing:project-experience`：CK 不会把它认作损坏旧块，也不会删除它；CK 自有标记缺失时预览要求确认，批准后 Codex/Claude 追加 CK 块，WB 前置 CK 块（`:161-196`、`:245-259`）。它不是“同标记重复”，但会形成两种协议/行为块共存。

如果把 memSharing 三行文本放入 `context-keeper:*` 旧标记内，CK 会判定其不是当前模板并在批准后恢复自己的全文（`:199-206`、`:253`）。因此不能保留 CK 标记、只改其内文而期望上游长期不回写。CK 自有重复/损坏标记会拒绝；memSharing 指纹漂移没有被 CK 接管。

### ensure 的范围选择风险

`--skill-dir` 若是明确用户级安装别名，就按该别名推导用户级入口（`CK/scripts/install.py:220-230`）。若宿主只给解析后的源码路径，则从当前项目及祖先找同源别名，再找用户位置，先命中者决定范围（`:231-244`）。所以只新增用户级安装，并不能自动消除旧项目级同源别名的影响。

建议切换策略：

1. memSharing 完全退出 CK 项目 install/ensure；项目新协议与 CK 自有用户块分别归两方。用户级 CK 规则块保留，由 CK 管理，不复制到项目。
2. CK 实际首次使用时优先传递明确的用户级安装别名，避免解析源码后被遗留项目别名抢先命中。该建议须靠宿主真实传参验收；memSharing 无权保证所有宿主一定保留别名。
3. 对旧项目别名只做显式清点与用户确认后的独立清理/重装；不因本次 provider 退役自动删除，不通过 CK `--uninstall` 顺带删项目规则。旧 CK 项目块按 §24 的明确批准/所有权处理；旧产品标记按 §26 漂移停止并指引重装。
4. 若仍存在 CK 项目别名或宿主只提供源码路径，则报告“CK 可能恢复项目块”的已知边界，不声称纯三行形态稳定。不要自动调用 ensure，再由 memSharing 删除 CK 块，造成双方反复写同一位置。
5. 如果产品要求“即使遗留项目别名存在，任何首次 CK 调用都不得再写项目 CK 块”，当前 pin 不提供此开关。这需要单独讨论上游接口/宿主装载策略；本轮不改 CK，不以静默修改其模板解决。

## 5. 与 §24 假设的差异及实施顺序修正

| 原假设/容易误读处 | 本轮核验 | 对实施的修正 |
|---|---|---|
| 首次 slash 就建库 | 不成立：先 ensure/菜单；首次保存另确认位置 | 文案改为“进入 CK，按需确认初始化”；测试 slash 菜单不得建库 |
| disabled 是 CK 自带开关 | 不成立：CK 未读该政策 | 先落 memSharing 政策与禁止自动记录规则；单测缺省不翻转，真机验 Agent 遵从；不夸大脚本门禁 |
| 新短块会被 CK 识别为已有 bridge | 不成立：标记空间独立 | 先约束 ensure 使用用户别名，再验证旧项目别名存在/缺失两条路径 |
| CK 安装仅写 Skill 目录 | 不成立：还写用户规则块 | 封皮同时披露并绑定 rule_files、块外字节与 memSharing 自己受管块 |
| rc=0 代表已装好 | 不成立：预览也为 0 | 按 JSON 字段和实际配置读回区分 preview/configured |
| CK 自己能阻止完整标记内的所有漂移 | 不成立：批准后可直接更新正文 | 外层独立封皮继续做精确前指纹验证，不把上游当所有权保护器 |
| P→改名 v2→v3 必须转换 | 已由 §26 撤销，不是 CK 接口要求 | schema=3 首个正式基线；旧账只读诊断/保全，不引入开发版升级白名单 |

收到“动笔”后建议按以下顺序执行：

1. 重新核验改名验收后的 SHA、写集、§24/§26 与 CK pin，先把上述差异纳入实施验收口径。
2. 合同退役先落 schema=3、显式 disabled 和实际使用驱动的规则入口，删除 CK 项目安装/模板提取/四态探针；不依赖 CK 修改。
3. 落独立尾步封皮，先核对 CK 预览影响再执行用户级安装，成功/跳过/失败与主产品分层报告。覆盖同源复用、异源冲突、预览 rc0、非法范围与结果不明。
4. 项目短协议与已批准旧块处置最后做；此前先在测试设计中列明用户级别名、遗留项目级别名、解析后源码路径的 ensure 落点，避免“迁完即被 CK 恢复”。不能解决的严格纯三行保证单列待裁定，而非绕过归属保护。
5. 未来用隔离 HOME 和固定 CK 源做安装配置测试，再分别做三家新会话的菜单、首次保存、disabled、已有库/旧结构门禁验收；本轮全部未执行。当前文档不代表重构已开始。
