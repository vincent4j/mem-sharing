状态：文档版本 1.2；2026-10-31 公共记忆分层修订；源码机制、本轮目标与实际验收分层。

# memSharing 系统架构

memSharing 为多个执行器提供同一份用户规则和项目规则入口。
它使用 Python 标准库、Markdown 文件和 JSON 台账，不运行常驻服务。
本文描述当前机制与已批准的公共记忆分层目标，依据 [DESIGN](../DESIGN.md) 与 `scripts/` 实现；分层目标的运行结论以验收为准。
裁定存在替代关系时采用当前有效条款，不把撤销的实现承诺列为能力。

## 1. 三层记忆与职责

### 用户记忆

用户记忆保存跨项目的工作习惯、偏好与通用约束。
公共源位于 `~/.mem-sharing/memories/`，入口为 `MEMORY.md`。
`MEMORY.md` 只保留短读取契约、200 行/25KB 预算、公共治理要点、按需指南指针与真实主题索引；六项菜单与详细 L0/L1/L2 维护规则集中在 `topics/使用约定.md`，不在索引重复全文。
各执行器的原生用户入口只写公共指针与自身规则；Claude 的项目兜底规则在它自己的用户文件，不放公共索引。
触发 `/mem-sharing` 及同义操作或默认项目接入前，先按指针读公共指南；索引中的相对链接以 `MEMORY.md` 所在目录解析，指南内链接以指南所在目录解析；指南缺失时停止相关操作；索引只指向指南，不回圈复制菜单。
索引指向主题文件，参考资料放在 `references/`。
公共内容的整理和写入由 Agent 按规则执行，不经过模型服务或向量检索。
该分层为本轮实现目标，运行验证以验收总览为准。

为什么这样设计：个人工作方式跟着人走，避免在每个项目重复维护。

### 项目记忆

项目根 `AGENTS.md` 是项目规则唯一真源。
它是共享基座，任何实际使用的已接入执行者都可按政策默认建立，不依赖安装 Codex。
它包含项目约束、必要骨架和项目经历协议，不承载工作日志。
规则随 Git 走，本机启用事实则记录在仓库外的台账中。
子目录要求可留在子目录规则文件，WorkBuddy 的子目录可见性有边界。
对 WorkBuddy 必须可见的重要要求，应在项目根规则中保留摘要。

为什么这样设计：同一项目只维护一份公共规则，执行器入口只负责到达它。

### 项目经历

项目经历保存进度、决策、工作日志与经验，由 Context Keeper 管理。
默认记录库为 `docs/context-keeper/`，实际位置和授权按 Context Keeper 自身流程确定。
用户级 Context Keeper 安装不等于项目记录库已经初始化。
项目首次 `/context-keeper` 命令按 Context Keeper 流程激活记录库。
memSharing 不定义日志格式、不蒸馏内容，也不接管 Context Keeper 的保存与查找逻辑。

为什么这样设计：规则和经历分开维护，编排层不复制记忆引擎的职责。

## 2. R、C、V 与版本库存

R 为用户记忆中枢：`~/.mem-sharing`。
C 为当前活动代码目录：`~/.local/share/mem-sharing`。
V 为唯一活动台账：`~/.mem-sharing/var/registry.json`。
版本库存为 `~/.local/share/mem-sharing-versions`，不是第二份活动台账。

```text
~/.mem-sharing/
  memories/MEMORY.md
  memories/topics/使用约定.md
  references/
  backups/
  var/
    registry.json
    .agm.lock/
~/.local/share/mem-sharing/                 当前活动代码
~/.local/share/mem-sharing-versions/
  <代码版本>/<源码树哈希>/                   完整发行库存
~/.mem-sharing-install-<op>/                独立装机与恢复材料
```

`layout.py` 只解析路径，不因查询创建目录。
运行时受管路径链检查符号链接和文件类型，拒绝越界或异常目标。
项目里不新建产品状态目录，项目主 checkout 的规范绝对路径作为登记键。
项目身份还绑定 Git common-dir，路径复用不能静默继承旧授权。
linked worktree 不作为可启用项目，移动或重新 clone 后须重新核对身份。

库存包含发行描述、文件哈希、代码和完整性标记。
库存就绪只证明版本可用，不授权激活；最终生效状态以 V 为准。
操作备份负责恢复具体现场，库存负责保留完整版本，两者不能互相替代。
用户内容与活动代码分离，代码更新不覆盖用户记忆。

为什么这样设计：内容、代码、活动状态各有唯一职责，恢复时有明确判断依据。

## 3. 入口与模块分工

`scripts/agm.py` 提供四个项目命令：

- `enable-memory`：启用规则入口和项目经历协议。
- `enable-memory-batch`：扫描目录并集中批准批量启用。
- `uninstall-machine`：精确归还公共记忆并清理机器资产；`recover-uninstall` 提供外置恢复；`migrate-policy` 退役历史产品控制。
- `check-memory`：只读核查登记和现场。

`scripts/install.py` 是独立机器安装入口，负责安装、获取、升级及恢复路由。
它另提供 `--context-keeper`，执行与主安装分开的 Context Keeper 用户级安装。
项目命令不隐式完成机器安装或机器升级。

`paths.py` 和 `agents.json` 定义执行器与平台路径白名单。
`project.py` 解析 Git 身份，`layout.py` 解析机器布局。
`detect.py` 收集执行器安装事实，`entries.py` 处理入口字节与标记边界。
`registry.py` 严格校验台账，`transaction.py` 执行原子写入与恢复。
`enable.py`、`remove.py`、`check.py`、`batch_enable.py` 编排项目操作。
`user_entries.py` 管理机器用户入口，`user_rules_organize.py` 提供整理向导 API。
`legacy_import.py`、`user_install.py`、`migrate.py` 处理安装及存量证据。
`versions.py`、`upgrade.py` 管理发行库存、版本切换和升级恢复。
`ck_install.py` 编排 Context Keeper 自有安装器，不在项目 enable 中调用它。

为什么这样设计：命令外壳与文件操作内核分离，项目操作不会顺手扩大到装机。

## 4. 六家执行器接入

### 用户级入口

Codex 使用 `~/.codex/AGENTS.md`。
Claude Code 使用 `~/.claude/CLAUDE.md`。
WorkBuddy 使用 `~/.workbuddy/MEMORY.md`。
DeepSeek Harness（`dsh`）使用 `~/.dsh/AGENTS.md`，ZCode（`zcode`）使用 `~/.zcode/AGENTS.md`。
OpenCode v2（`opencode`）使用 `~/.config/opencode/AGENTS.md`。机器安装、再次安装与升级默认发现全部支持对象，只为核验为 installed 的 Agent 装配用户入口；显式重复 `--agent` 限定新接入范围。项目命令缺省仍为 `codex/claude/workbuddy`，其他执行者实际使用时显式选择；项目启用一次多值，例如 `--agent dsh zcode opencode`。各家共用公共索引，保留独有私文。

历史公共布局迁移先在内存重算 V2 入口快照与台账，再预览新增入口计划；两个子计划都进入外层 `plan_sha256`。预测上下文不能从请求恢复，也不能携批准进入执行。迁移后回到真实现场重算并严格比较原批准，拒绝漂移。显式范围只限定新增装配，既有公共读取依赖仍完整迁移。历史前身身份与合同冻结不变，同版不同来源不能靠重冻目标合同绕过升级门禁。
安装为验证为 installed 的目标写入用户级公共指针与自身规则；菜单与详细使用约定在公共指南，不整段驻留用户文件。缺失的执行器用户目录不预建。
既有专属内容保留，用户规则整理是另一个显式流程。
产品不建立公共 Skills/MCP 目录，也不投影 memSharing Skill。
`/mem-sharing` 是公共指南承载的约定菜单，自然语言也可触发；触发时先读指南，指南缺失停止相关操作。

### 安装事实与运行事实

检测结果为 `installed`、`absent`、`unknown`。
残留目录只算弱提示，不能据此判定 installed。
有效 App 元数据与可读可执行入口、支持的 CLI 包或原生结构、显式哈希收据作为安装证据，不能由空配置目录替代。自动与显式接入均不调用 `codesign`；签名失败、签名标识不同或后端缺失不再是接入拒绝条件。坏链接、不可读、产品元数据不符及来源歧义仍为 unknown，全部可检查且无候选、无 hint 才为 absent。同一 Agent 恰好一个受支持的 CLI 候选加一个 App 候选、且没有任何本地失败证据时可判 installed；两 CLI、两 App、更多候选或坏候选仍为 unknown，仅证明本地安装面，不证明模型登录、发布者可信或运行加载。
此项简化不证明发布者可信，也不放宽产品固定 S/R 来源完整性、合法原生路径、原文备份、精确批准、漂移与恢复门禁。CLI 不变，新策略尚未进入已生成的 0.1.7 载荷。
检测不启动应用，不读取登录态，也不执行模型请求。
安装事实、入口静态状态、新会话运行验收分别记录。
WorkBuddy 桥接已配置也不能直接宣布运行时加载成功。

### 项目级实际使用驱动

`AGENTS.md` 是共享项目规则基座，不依赖安装 Codex；Codex、DeepSeek Harness、ZCode 与 OpenCode 均原生读取，无需额外引用文件或隐藏项目桥接。
只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立。
默认接入由当前实际执行者按指南以 `--agent <当前执行者>` 执行；不带 agent 参数按已安装事实处理，可能顺带补齐其他执行器已存在的原生目录，仅用于用户显式要求全体或批量接入，不改 CLI 语义。
机器探测到执行器安装或原生目录存在，不等于当前执行者实际使用。
不带 `--agent` 的通用 `enable-memory` 不触碰 `CLAUDE.md`，包括已有文件。
Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `@AGENTS.md` 引用；该兜底规则位于 Claude 自身用户文件，不放公共索引。
其它执行者默认流程不预建 `CLAUDE.md`。
显式 `enable-memory --agent claude` 是另一条有意接入路径。
该路径按精确计划添加引用，不把机器上已安装 Claude 当作预建条件。
WorkBuddy 仅在 `.workbuddy/memory/` 原生目录已存在时补规则指针。
原生目录缺失时报告待实际使用，不提前创建目录。

DeepSeek Harness 本次合同限默认 coding `cordis` preset 与默认根；非默认 `DSH_HOME` 拒绝默认入口接入，`DSH_AGENTS_HOME` 影响共享根，检查不回传变量值，自定义配置未验证。`ZCODE_HOME` 不是 ZCode 规则根。两家静态支持 `~/.agents/skills` 及各自用户 Skill 根，不创建投影，不代表实际加载。详见[操作手册](operations.md#桌面端默认根与验证边界)。

OpenCode 检测分别报告 CLI 与桌面 App 安装面。桌面核对 `OpenCode.app` 的产品名、`ai.opencode.desktop` 标识、可读可执行的 `OpenCode` 入口与非空且一致的 bundle 版本，不要求 Apple 证书链、团队或签名标识核验。CLI-only 不表示桌面已安装；恰好一个支持的 CLI 候选与一个支持的桌面 App 均满足静态证据、且无失败候选时允许并装，额外来源仍为 unknown。CLI 没有静态版本证据时保持版本 unknown；本地安装证据不代表发布者身份可信或新会话运行成功。

OpenCode 原生入口根据受支持的命令名 `opencode`、可读可执行文件与 Mach-O 结构记录安装事实，父级无 name 的 package.json 不阻断识别；不要求应用签名。非 Mach-O 包装入口仍核对 `@opencode/cli` 包名与实际入口，文件名或目录 hint 本身不构成 installed。版本没有静态证据时保持 unknown。规则根仅支持默认绝对路径；`XDG_CONFIG_HOME`、`OPENCODE_CONFIG_DIR` 的相对值、字面 `~` 或非默认值及非空 `OPENCODE_CONFIG` 均拒绝，不回显原值。

为什么这样设计：机器安装清单不代表每个项目都使用每个执行器。

## 5. schema=3 与所有权记账

活动台账 schema 为 3，顶层包含：
`projects`、`shared_objects`、`product`、`machine`、`migration`、`legacy_import`。
产品代码版本、产品结构版本和台账 schema 分别记账，不能混为一个版本号。
`product` 绑定产品身份、安装身份、来源 commit、树哈希和最近操作。
`machine` 保存执行器安装事实、静态入口状态、运行验收与机器受管对象。
项目记录包含 checkout 身份、执行器清单、入口对象和记忆政策。
项目政策仅为 `follow_ck` 或 `disabled`。
台账不再保存 Context Keeper provider、四态就绪探针或记录库授权字段。
记录库授权由 Context Keeper 自行管理，不从残留文件推断。

受管对象记录路径、种类、作用域、执行器、标记、指纹与备份证据。
所有权为 `created`、`reused` 或 `unknown`。
复用已有内容不产生删除权，未知所有权也不能猜测成工具创建。
共享对象的消费者索引用于避免某项目停用时影响其他项目。
新受管单元可带生命周期证据，描述实际创建的块或引用及其容器边界。
整文件存在不表示整文件都归产品所有，后加的用户正文必须保留。
`AGENTS.md` 中自由编辑的项目规则与受管协议单元分别处理。
指纹用于识别漂移；用户批准不能覆盖 created 对象的漂移保护。
台账最后提交，登记的所有权必须能由事务材料证明。

为什么这样设计：停用权来自具体创建证据，不能从“文件现在存在”推导。

## 6. 事务与六阶段恢复

项目写入先取得机器协作锁，再使用事务锁保护具体写集。
`check-memory` 不获取写锁，不创建备份、不修复文件。
事务捕获 before 快照、记录 manifest，再逐项写入并读回核验。
文件替换使用原子写入；台账是事务最后一项变更。
失败时按已记录证据恢复，不能覆盖 before/after 之外的第三种字节。
锁冲突不会自动抢锁，恢复材料缺损也不会退回“全新现场”。

升级采用六个固定阶段：

1. `prepare`：固定恢复工具包与目标暂存。
2. `archive`：归档 before 现场与当前版本库存。
3. `inventory`：目标库存落位，建立升级中标记。
4. `code`：按受管清单逐文件切换 C。
5. `verify`：核验必要入口及输出，记录 `outputs_verified`。
6. `commit`：原子提交最终 V，完成 journal、标记与锁收尾。

每阶段及细粒度写入窗口都有故障定位和恢复证据。
升级中标记存在时，普通项目命令停止，转向明确恢复入口。
恢复先预览，再批准 continue 或 rollback，绑定当时的现场指纹。
提交前按 journal 和 before/after 状态决定继续或回滚。
V 已提交且输出均为 after 时只允许收尾，不重新执行提交前回滚。
恢复工具使用操作固定版本，避免依赖正在混版的 C。
主动选择旧发行是新的版本计划，不等于中断事务的 rollback。

为什么这样设计：提交点把“尚未生效”与“已生效待收尾”分开，防止重复执行。

## 7. 安装与独立批准

机器安装先只读判别四通道：全新、确认的 v0 内容复制、有效产品升级、异常停止。
同版一致场景保持幂等，不把损坏、未来版本或中断现场当作全新。
v0 源为 `~/.agents-group`，只复制获准的 memories/references。
旧脚本、Skills、MCP 和旧状态不运行、不接管，旧目录原地保留。
复制保留原文、源快照、清单与一次导入证据，冲突不静默覆盖。

安装来源须为核验过的 clean checkout 或固定来源 manifest。
计划绑定完整 commit、文件清单、布局、版本、执行器事实和精确变更。
批准封皮由完整计划加真实 `confirmed_at`、`reference` 构成。
执行前在锁内重新核对，现场变化要求重新预览，批准不授权计划外修改。
获取是单独的 `--acquire` 计划，获取完成不代表产品已经安装。

五拍对话由执行 Agent 编排：请求、检查确认、静默安装结论、Context Keeper 询问、用法提醒。
Python/Git 缺失时，系统包管理器准备属于外层 Agent 职责。
当前 Python CLI 不自行安装运行时依赖。
主安装完成后才生成 `install-context-keeper` 独立封皮。
对 Context Keeper 的安装同意仅以真实交互回车为准，EOF、非交互或空格不算。
Context Keeper 封皮仍绑定固定源码与全部实际接入执行器；其固定 pin 安装器只支持 Codex、Claude Code、WorkBuddy 的 flags，由其负责用户级 Skill。`dsh`、`zcode`、`opencode` 明确跳过（`reason=upstream_unsupported`），混合时旧三家仍可安装，不影响它们的 memSharing 接入。
Context Keeper 失败不回滚主产品，也不合报为全部成功；结果不明不自动重放。

为什么这样设计：主产品与可选引擎有独立授权、失败边界和交付证据。

## 8. 项目接入、历史迁移与整机卸载

未登记 Git 主 checkout 的默认启用由用户级规则与公共指南驱动，当前实际执行者以 `--agent <当前执行者>` 执行，并非后台监听。
启用保留已有规则正文，补缺失骨架与项目经历短协议。
协议只说明位置、命令入口和职责，不初始化记录库、不安装项目 Skill。
已登记 disabled 项目不被默认条款重新启用。
旧 Context Keeper 桥接替换须有显式计划：created 退役重建，reused 展示确认，漂移停止。

批量扫描含给定目录自身，不进入 `.git`，不跟随目录符号链接。
只对新的 Git 主 checkout 形成计划，已启用和 disabled 项目跳过。
集中批准绑定目录、完整清单、V 指纹及每个项目计划。
锁内重新扫描核对后逐项目执行，失败即停止后续，已完成项目保留。
批量不是跨项目全有或全无事务，不提供整批回滚。

旧 `remove-memory`、`--memory`、`--no-memory` 已退役，新请求零写拒绝。历史 disabled 只作规则接入 tombstone，默认跳过、不重建；它不否决 Context Keeper 的自动规则，不表示 CK 已停用或入口已删除。使用 `migrate-policy [--project ABS]` 精确预览并批准后，仅退役产品自有且指纹匹配的旧控制与已知旧模板，保留私文、CK 设置和历史数据，不替用户启用 CK。

整机卸载使用 `python3 -B scripts/agm.py uninstall-machine --backup-dir <全新外置目录>` 先预览，再以 `--approval-file` 精确批准。归还当前完整公共记忆给每个实际接入者的自身用户目录，再核验、清依赖、最后删除产品；不是恢复安装前。外置 manifest/recover.py 与独立解释器支持删除代码后的精确恢复。未知/漂移阻断，项目 AGENTS、有效 Claude/WB 桥接及 CK 默认保留。完整数据与门槛见[整机卸载方案](uninstall-design.md)。

CLI 的 `scope=standalone_declared`、`host_plugin=not_applicable` 仅声明调用范围；Paseo 为 `machine_and_paseo`，机器 completed 但插件仍在时 overall=partial。必须在插件移除前经外置入口独立绑定真实安装 ID/来源/CLI/daemon/live serverId，再用户 remove、同目标 full-list check 证实缺席，最后才可另选卸载 CK。disabled、查询错误、能力/版本错误均不算 removed；默认保留 CK，尾步另行精确批准。正式 payload 待干净提交与版本授权后生成，本轮源码/合成验证不等于实际宿主卸载或六家新会话加载验收。

为什么这样设计：公共共享与规则接入归 memSharing，经历行为归 Context Keeper；退役项目 remove 和经历开关可避免跨产品否决，卸载按数据归还与所有权证据清理，用户规则和历史数据保留。

## 9. 升级承诺与证据边界

关键裁定 §26 规定：开发版不承诺升级，schema=3 是首个正式发行基线。
旧 v1/v2 仅严格只读诊断与保全，不承担开发版转换链。
未知或旧开发版明确拒绝，开发机须保全现场后重装。
旧产品标记按漂移停止，不建立改名迁移框架。
正式发行起，升级承诺覆盖冻结的首发 T0 到后续发行。
不提供逆 schema 迁移；库存和通用故障恢复内核保留。
用户路径白名单、所有权、字节保全、批准和真实 v0 双目录导入继续有效。

为什么这样设计：把兼容承诺放在稳定发行边界，避免为未发行状态维护永久转换链。

静态入口正确、夹具测试通过、真实 HOME 安装和新会话加载是不同证据。
本文描述机制，不将配置成功解释为所有执行器运行时验收完成。
实际操作见 [操作手册](operations.md)，具体命令以当前 `--help` 为准。
