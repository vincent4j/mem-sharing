状态：文档版本 1.0；基线 ae0775a；2026-10-31。

# memSharing 操作手册

本手册供使用者与执行 Agent 使用，机制说明见 [系统架构](architecture.md)。
命令已核对 `scripts/agm.py --help`、各子命令帮助及 `scripts/install.py --help`。
示例中的绝对路径、完整 SHA 和版本号必须替换为实际核验值。

## 1. 环境与操作入口

当前实证平台为 macOS；Windows/Linux 不列为已验收平台。
需要 Python ≥3.9 和 Git，Python 无额外 pip 依赖。
缺失或版本不足时，执行 Agent 在安装汇总确认后用可用系统包管理器准备依赖。
Python CLI 本身只诊断，不负责自动安装 Python/Git。
包管理器缺失、权限受阻或依赖安装失败时停止，说明实际阻塞。

用户可直接说“安装 memSharing”，安装后可用 `/mem-sharing` 菜单或自然语言。
六个菜单入口为：给项目启用记忆、添加新的 Agent、健康检查、停用记忆、整理用户规则、批量启用记忆。
菜单由用户级规则文本承载，不要求安装 memSharing Skill。
下文项目示例从源码根运行；已安装后可改用 C 中的脚本绝对路径。
C 为 `~/.local/share/mem-sharing`，R 为 `~/.mem-sharing`。

为什么这样设计：使用者表达意图，Agent 翻译为受控命令，不要求用户维护执行器差异。

## 2. 安装：五拍剧本与命令

1. 接收安装请求，说明先检查运行环境和本机 Agent。
2. 汇总 Python、Git、验证为已安装的 Agent 与待准备依赖，一次确认，回车开始。
3. 确认后静默获取、核验和安装；完成只报用户记忆中枢与实际接入名单。
4. 紧接着正向询问是否安装用户级 keeper，回车同意，n 跳过。
5. keeper 安装后提醒在所需项目使用 `/context-keeper`，首次按 keeper 流程激活。

unknown 或仅有残留目录不列为已安装。
成功简报不罗列内部路径，不添加未安装 Agent 或新会话自检提示。

先使用核验过的干净本地 Git checkout 预览：

```bash
python3 scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
```

也可用 `--source-manifest /absolute/path/source.json` 提供固定来源对象。
它包含 `root/url/commit/version/files`，不要与 source/commit/version 混用。
不得 reset/pull 用户的 dirty checkout 来满足干净要求。
安装器只读判别全新、确认的 v0 内容复制、有效产品升级或异常停止。
v0 仅复制获准的 memories/references，旧目录 `~/.agents-group` 原地保留。

无批准时返回 `approval_plan`，不会安装。
Agent 展示完整计划并绑定真实确认，将计划连同 `confirmed_at/reference` 写入批准 JSON。
批准必须对应当前计划，不填写虚构确认，不将一次确认扩大成任意修改授权。

```bash
python3 scripts/install.py --approval-file /absolute/path/install-approval.json
```

安装可重复 `--agent codex --agent claude` 限定目标，仍须通过安装事实核验。
`--project` 只用于报告后续项目命令，不表示安装时顺便启用项目。

为什么这样设计：先固定来源与现场再写入，安装请求能落实到可核对的精确变更。

## 3. 给单个项目启用记忆

进入未登记的 Git 主 checkout 时，用户级规则驱动默认启用。
这不是后台监听；非 Git 目录与 linked worktree 不触发。

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project
```

新项目建立 `AGENTS.md` 骨架；已有规则正文保留，只补所需协议。
默认启用完全不触碰 `CLAUDE.md`，包括已有文件。
Claude 实际使用时由其用户级规则补 `@AGENTS.md`，Codex 原生读取无需兜底。
有意接入 Claude 时可显式执行 `enable-memory --project ... --agent claude`。
WorkBuddy 只在 `.workbuddy/memory/` 原生目录存在时补规则指针，不预建目录。
原生目录缺失表示待实际使用；静态桥接不等于运行时加载通过。

启用不调用 keeper 安装器、不安装项目级 Skill、不创建 keeper 记录库。
没有 keeper 仍可使用用户记忆与项目规则，只是没有项目经历能力。
若需精确非交互批准，先查看预览，再加 `--approval-file /absolute/enable-approval.json`。
`--agent codex claude` 可一次选择多个唯一值；未显式选择时按已安装事实处理。
写前发现受管单元漂移则停止，批准文件不能强制覆盖漂移保护。

为什么这样设计：规则接入与项目经历激活分开，默认流程不为未使用的执行器创建文件。

## 4. 批量启用项目

在菜单选“批量启用记忆”，提供需要扫描的目录：

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects
```

递归扫描包含目录自身，不进入 `.git`，不跟随目录符号链接。
仅 Git 主 checkout 可入选，linked worktree 排除。
汇总预览每项目一行，集中批准全部新项目的精确计划，不逐项目重复询问。
已启用项目跳过；disabled 项目保持停用，必须单独显式恢复。

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/batch-approval.json
```

批准绑定扫描目录、完整清单、台账哈希和各项目计划，执行前锁内重新核对。
某项目执行失败即停止后续，已完成项目保留，未开始项目不会假报成功。

为什么这样设计：集中确认降低重复操作，同时保留每个项目的事务与故障边界。

## 5. 停用、禁止自动记录与重新启用

菜单“停用记忆”对应撤销项目接入：

```bash
python3 scripts/agm.py remove-memory --project /absolute/path/project
```

只撤销有创建证据且允许撤销的入口与桥接，复用内容不获得删除权。
项目记为 disabled，默认启用条款不再自动触发。
规则正文、全部项目经历数据、用户级接入、机器产品及 keeper 安装保留。
非交互执行须使用该计划的 `--approval-file`，不要把 stdin 的 yes 当作批准。

如果只想保留规则接入、禁止自动项目经历记录与初始化，使用进阶操作：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --no-memory
```

此政策优先于残留 keeper 自动规则，但不是 keeper 脚本硬拒写接口。
手动 keeper 操作仍按用户明确请求与 keeper 自身流程进行。
缺省 enable 不会翻转 disabled；重新启用必须显式解除并批准精确计划：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --memory
```

为什么这样设计：撤销入口、阻止默认复开和暂停自动记录分别有明确结果，数据不随停用丢失。

## 6. 添加新的 Agent 与健康检查

先核验新 Agent 的安装事实，再通过机器安装入口的 `--agent` 接入用户规则。
使用第 2 节安装预览流程限定目标；不是编辑 agents.json 来伪造安装事实。
已有项目需要该执行器时，可显式接入：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent claude
python3 scripts/agm.py check-memory --project /absolute/path/project
python3 scripts/agm.py check-memory --all
```

`--all` 读取已登记项目，不扫描整个磁盘寻找新项目。
check 只报告登记与现场缺口，不写锁、不备份、不修复、不触发安装。
入口字节、安装事实和执行器新会话加载应分别判定。
运行时验收仍需实际使用证据；WorkBuddy 无证据时保持 pending。

为什么这样设计：巡检可以安全重复，修复必须落实到另一次明确的写入计划。

## 7. 用户规则整理与 keeper 激活

“整理用户规则”由 Agent 调用 `user_rules_organize.py` 的预览与执行 API。
当前 `agm.py` 没有整理子命令，不使用虚构的 organize CLI。
向导把公共候选、重复规则、执行器独有内容和归属不明内容分开展示。
分类只是建议，独有与归属不明内容锁定保留，不能并入公共源或删除。
一次确认完整逐条计划，原文指纹逐项绑定；批准前候选可改判保留。
公共内容与入口编辑使用可恢复事务，整理不修改活动台账 V。

为什么这样设计：公共规则需要人工语义判断，不能用自动分类扩大共享范围。

keeper 是独立可选引擎，主安装完成后才产生独立批准封皮。
独立路由示例：

```bash
python3 scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper
python3 scripts/install.py --context-keeper --approval-file /absolute/ck-approval.json
```

源码须为持久、干净且符合固定 pin 的 checkout，目前不自动下载。
只有真实交互回车表示同意，空格、EOF 或非交互输入不算。
同意后为全部实际接入执行器安装用户级 keeper，落位由 keeper 自有安装器负责。
keeper 缺源、失败或结果不明分别报告，主产品成功保留，结果不明不自动重放。
在需要的项目首次运行 `/context-keeper`，按其流程确认并初始化项目经历库。
后续保存、续接、查找与迁移门禁全部遵守 keeper；需要迁移时先停止相关读写。

为什么这样设计：可选引擎独立授权，安装成功不冒充项目记录库已激活。

## 8. 常见问题与恢复入口

**锁冲突：** 保留锁与 journal，核对是否仍有写者，不自动删锁或抢锁。
**入口漂移：** 保留当前字节，检查报告路径与受管单元，重新评估计划；不要手改台账绕过保护。
**台账缺失或损坏：** 停止写入，不能凭入口文件猜测原授权或静默重建为全新。
**旧开发版或旧标记：** 保全后重装；schema=3 首发基线不承诺开发版迁移，不提供逆 schema 转换。
**升级中断：** 用报告所指固定恢复工具，避免运行混版 C 中的安装器。
机器恢复先预览，确认后执行同一计划：

```bash
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue --approval-file /absolute/recovery-approval.json
```

需要回滚时用 `--action rollback` 重新预览与批准；V 已提交且输出全为 after 时只收尾。
项目事务失败则按报告中的 manifest 与 recovery 指引处理，不套用机器 journal。
第三种字节、缺失材料或工具漂移一律停止，不覆盖未知修改。
为什么这样设计：恢复只能依据完整证据执行，重试不能把不确定结果放大。
