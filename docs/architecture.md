状态：文档版本 1.0；基线 ae0775a；2026-10-31。

# memSharing 系统架构

memSharing 为多个执行器提供同一份用户规则和项目规则入口。
它使用 Python 标准库、Markdown 文件和 JSON 台账，不运行常驻服务。
本文描述当前机制，依据 [DESIGN](../DESIGN.md)、[DESIGN](../DESIGN.md) 与 `scripts/` 实现。
裁定存在替代关系时采用当前有效条款，不把撤销的实现承诺列为能力。

## 1. 三层记忆与职责

### 用户记忆

用户记忆保存跨项目的工作习惯、偏好与通用约束。
公共源位于 `~/.mem-sharing/memories/`，入口为 `MEMORY.md`。
索引指向主题文件，参考资料放在 `references/`。
各执行器的原生用户入口通过受管约定读取公共源。
公共内容的整理和写入由 Agent 按规则执行，不经过模型服务或向量检索。

为什么这样设计：个人工作方式跟着人走，避免在每个项目重复维护。

### 项目记忆

项目根 `AGENTS.md` 是项目规则唯一真源。
它包含项目约束、必要骨架和项目经历协议，不承载工作日志。
规则随 Git 走，本机启用事实则记录在仓库外的台账中。
子目录要求可留在子目录规则文件，WorkBuddy 的子目录可见性有边界。
对 WorkBuddy 必须可见的重要要求，应在项目根规则中保留摘要。

为什么这样设计：同一项目只维护一份公共规则，执行器入口只负责到达它。

### 项目经历

项目经历保存进度、决策、工作日志与经验，由 Context Keeper（keeper）管理。
默认记录库为 `docs/context-keeper/`，实际位置和授权按 keeper 自身流程确定。
用户级 keeper 安装不等于项目记录库已经初始化。
项目首次 `/context-keeper` 命令按 keeper 流程激活记录库。
memSharing 不定义日志格式、不蒸馏内容，也不接管 keeper 的保存与查找逻辑。

为什么这样设计：规则和经历分开维护，编排层不复制记忆引擎的职责。

## 2. R、C、V 与版本库存

R 为用户记忆中枢：`~/.mem-sharing`。
C 为当前活动代码目录：`~/.local/share/mem-sharing`。
V 为唯一活动台账：`~/.mem-sharing/var/registry.json`。
版本库存为 `~/.local/share/mem-sharing-versions`，不是第二份活动台账。

```text
~/.mem-sharing/
  memories/MEMORY.md
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
- `remove-memory`：撤销允许撤销的项目受管对象。
- `check-memory`：只读核查登记和现场。

`scripts/install.py` 是独立机器安装入口，负责安装、获取、升级及恢复路由。
它另提供 `--context-keeper`，执行与主安装分开的 keeper 用户级安装。
项目命令不隐式完成机器安装或机器升级。

`paths.py` 和 `agents.json` 定义执行器与平台路径白名单。
`project.py` 解析 Git 身份，`layout.py` 解析机器布局。
`detect.py` 收集执行器安装事实，`entries.py` 处理入口字节与标记边界。
`registry.py` 严格校验台账，`transaction.py` 执行原子写入与恢复。
`enable.py`、`remove.py`、`check.py`、`batch_enable.py` 编排项目操作。
`user_entries.py` 管理机器用户入口，`user_rules_organize.py` 提供整理向导 API。
`legacy_import.py`、`user_install.py`、`migrate.py` 处理安装及存量证据。
`versions.py`、`upgrade.py` 管理发行库存、版本切换和升级恢复。
`ck_install.py` 编排 keeper 自有安装器，不在项目 enable 中调用它。

为什么这样设计：命令外壳与文件操作内核分离，项目操作不会顺手扩大到装机。

## 4. 三家执行器接入

### 用户级入口

Codex 使用 `~/.codex/AGENTS.md`。
Claude Code 使用 `~/.claude/CLAUDE.md`。
WorkBuddy 使用 `~/.workbuddy/MEMORY.md`。
安装为验证为 installed 的目标写入用户级公共源指针与项目接入约定。
既有专属内容保留，用户规则整理是另一个显式流程。
产品不建立公共 Skills/MCP 目录，也不投影 memSharing Skill。
`/mem-sharing` 是规则文本承载的约定菜单，自然语言也可触发。

### 安装事实与运行事实

检测结果为 `installed`、`absent`、`unknown`。
残留目录只算弱提示，不能据此判定 installed。
CLI 包身份、应用包身份等强信号必须完成静态核验。
检测不启动应用，不读取登录态，也不执行模型请求。
安装事实、入口静态状态、新会话运行验收分别记录。
WorkBuddy 桥接已配置也不能直接宣布运行时加载成功。

### 项目级实际使用驱动

Codex 原生读取 `AGENTS.md`，无需额外引用文件。
默认 `enable-memory` 完全不触碰 `CLAUDE.md`，包括已有文件。
Claude 在该项目实际使用时，由其用户级兜底规则补 `@AGENTS.md`。
显式 `enable-memory --agent claude` 是另一条有意接入路径。
该路径按精确计划添加引用，不把机器上已安装 Claude 当作预建条件。
WorkBuddy 仅在 `.workbuddy/memory/` 原生目录已存在时补规则指针。
原生目录缺失时报告待实际使用，不提前创建目录。

为什么这样设计：机器安装清单不代表每个项目都使用每个执行器。

## 5. schema=3 与所有权记账

活动台账 schema 为 3，顶层包含：
`projects`、`shared_objects`、`product`、`machine`、`migration`、`legacy_import`。
产品代码版本、产品结构版本和台账 schema 分别记账，不能混为一个版本号。
`product` 绑定产品身份、安装身份、来源 commit、树哈希和最近操作。
`machine` 保存执行器安装事实、静态入口状态、运行验收与机器受管对象。
项目记录包含 checkout 身份、执行器清单、入口对象和记忆政策。
项目政策仅为 `follow_ck` 或 `disabled`。
台账不再保存 keeper provider、四态就绪探针或记录库授权字段。
记录库授权由 keeper 自行管理，不从残留文件推断。

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

五拍对话由执行 Agent 编排：请求、检查确认、静默安装结论、keeper 询问、用法提醒。
Python/Git 缺失时，系统包管理器准备属于外层 Agent 职责。
当前 Python CLI 不自行安装运行时依赖。
主安装完成后才生成 `install-context-keeper` 独立封皮。
keeper 仅真实交互回车算同意，EOF、非交互或空格不算。
keeper 固定源码与全部实际接入执行器绑定，由 keeper 安装器负责用户级 Skill。
keeper 失败不回滚主产品，也不合报为全部成功；结果不明不自动重放。

为什么这样设计：主产品与可选引擎有独立授权、失败边界和交付证据。

## 8. 项目启用、批量与停用

未登记 Git 主 checkout 的默认启用由用户级规则驱动，并非后台监听。
启用保留已有规则正文，补缺失骨架与项目经历短协议。
协议只说明位置、命令入口和职责，不初始化记录库、不安装项目 Skill。
已登记 disabled 项目不被默认条款重新启用。
旧 keeper 桥接替换须有显式计划：created 退役重建，reused 展示确认，漂移停止。

批量扫描含给定目录自身，不进入 `.git`，不跟随目录符号链接。
只对新的 Git 主 checkout 形成计划，已启用和 disabled 项目跳过。
集中批准绑定目录、完整清单、V 指纹及每个项目计划。
锁内重新扫描核对后逐项目执行，失败即停止后续，已完成项目保留。
批量不是跨项目全有或全无事务，不提供整批回滚。

停用分三层语义：

- 菜单“停用记忆”调用 `remove-memory`，撤销允许撤销的入口与桥接，保留数据。
- remove 后登记 disabled，默认启用不再触发；恢复须显式 `enable-memory --memory`。
- `enable-memory --no-memory` 保留规则接入，禁止自动项目经历记录及初始化。

停用防护优先于残留 keeper 自动规则，但不是 keeper 脚本硬拒写接口。
手动 keeper 操作仍遵循用户明确请求与 keeper 自身流程。
机器安装、用户记忆、keeper 安装和项目经历数据不因项目停用被删除。

为什么这样设计：撤销接入和暂停自动记录是不同需求，数据始终作为用户资产保留。

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
本文描述机制，不将配置成功解释为三家运行时验收完成。
实际操作见 [操作手册](operations.md)，具体命令以当前 `--help` 为准。
