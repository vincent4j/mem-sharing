# Windows 完整适配目标

## 1. 支持边界

普通安装器与升级器仍保持macOS平台保护，Windows仅提供[双端首次预览](windows-preview.md)的有限入口。该预览在DELL Win11 x64本地NTFS、ZCode3.17.2.9661/WorkBuddy5.9.3.0完成安装、双向新增/全新会话读取和退出保全；不能推定一般六家、更多版本、旧安装升级或迁移可用。

本文定义完整Windows适配的长期目标，不是已实现能力清单，也不是预览版的追加前置。无证据的能力保持未验证；文档、SDK声明和单项观察都不能替代目标环境实测。

## 2. 完整适配的支持边界与关键取舍

以下均为推荐设计，不是对 Windows 或第三方产品当前支持状态的事实断言；第三方最低系统、架构和原生入口须由 W00 核实官方材料及固定版本。

| 维度 | 首批建议 | 理由与扩展门槛 |
|---|---|---|
| 操作系统 | Windows 11，明确记录通过验收的版本/build | 聚焦可获得真实环境；Windows 10、Server 暂不承诺，不能只靠版本号检测放行 |
| 架构 | x64 原生 Python/客户端 | ARM64 与模拟运行分别待验，不套用 x64 结论 |
| 权限 | 普通用户、当前用户范围；不要求管理员、开发者模式或 WSL | 避免通过提权掩盖入口和文件权限问题 |
| 文件系统 | 本地 NTFS 普通目录；用户目录与代码默认同卷 | 首批只承诺可完成权限、锁与恢复核验的边界 |
| 存储排除 | UNC、映射网络盘、可移除盘、同步盘/云占位文件、未知 reparse、大小写敏感目录暂拒绝写入 | 实施前明确识别方法；不能判断则未知并停止，不凭路径含某字符串判定 |
| Shell | PowerShell 原生流程为首要验收；cmd 单独做调用/引用烟测 | Git Bash、MSYS、Cygwin、WSL 不作为成功替代；不要求用户执行 bash 脚本 |
| 客户端 | 六家逐家准入，可先发布经验证子集 | 发布名为“Windows 支持：具体名单”，其余明确待验，不能笼统“六家支持” |
| 依赖 | 复用可执行且兼容的 Python≥3.9、Git | 不因用户已有版本较新就要求重装；版本政策改变需独立 review |

推荐维持同一仓库、同一 Python 标准库内核、平台适配边界。替代方案比较：

- 仅删除 darwin 检查：改动少，但路径、权限、恢复尚未保证，拒绝。
- 要求 WSL：可绕开部分原生差异，但不满足原生 Windows 客户端接入目标，不作为本次方案。
- Windows 独立内核：初期易局部实现，长期形成融合与归还双套语义，拒绝。
- 打包 exe/内置 Python+Git：可降低依赖门槛，但增加供应链和更新负担，首批不做；依赖安装困难有实际证据时再独立评审。

## 3. 六家能力矩阵与准入

按客户端分别记录路径依据、实现接线和宿主运行结果。Codex、Claude Code、DeepSeek Harness、OpenCode 的官方默认目录已核对，详见下方路径表；官方目录确认不等于本项目已安装或客户端已加载。Windows 的 HOME/配置目录覆盖、App 与 CLI 差异及实际规则加载仍须按目标版本核验。不将 `.app`、POSIX 可执行位或目录存在用于 Windows 强安装判据。

| 客户端 | 当前线索 | Windows 必须关闭的独有验证门 | 当前状态 |
|---|---|---|---|
| Codex | `.codex/AGENTS.md`，项目 AGENTS；`.agents/skills` 与专属 roots | CLI/App 分别识别；自定义配置根；用户规则与 Skill 在新会话可发现并读取 | 官方默认目录已核对；本项目 Windows 安装与新会话加载未执行 |
| Claude Code | `.claude/CLAUDE.md`，`@AGENTS.md` | 原生 Windows 执行形态、导入路径含空格/中文、已有 CLAUDE 正文和引用幂等 | 官方默认目录已核对；本项目 Windows 安装与新会话加载未执行 |
| WorkBuddy | `.workbuddy/MEMORY.md`，项目 `.workbuddy/memory/MEMORY.md` | 桌面实际安装证据；用户约定入口和项目桥接实际加载；不能以目录残留认定安装 | 仅DELL首次预览已验；完整安装/升级/迁移与其他配置待验 |
| DeepSeek Harness | `.dsh/AGENTS.md`、项目 AGENTS | 官方 Windows 桌面发行已确认；自定义配置根、Skill 查找及原生规则实际加载 | 官方默认目录已核对；本项目 Windows 安装与新会话加载未执行 |
| ZCode | `.zcode/AGENTS.md`、项目 AGENTS | 目标发行版本、配置根/覆盖与 Skill 查找；与其他共用 AGENTS 不重复消费 | 仅DELL首次预览已验；完整安装/升级/迁移与其他配置待验 |
| OpenCode v2 | `.config/opencode/AGENTS.md`、项目 AGENTS | 默认配置根与 Skill 根已有官方依据；自定义环境、CLI/Desktop 差异及 v2 入口实际加载 | 官方默认目录已核对；本项目 Windows 安装与新会话加载未执行 |

每家分别记录：官方资料/版本、强安装信号、文件接入、原生发现、模型实际读取、共享往返、卸载恢复。只有前两项不能判定支持；没有第三方 Windows 发行证据时维持不准入。未登录可报告文件层完成，但不得冒称模型读取通过。

平台表建议保留六家结构，另增加显式准入能力/原因；校验器不得接受“待验路径”供写入使用。默认名单=强证据已安装且该版本已准入的交集；目录只作为提示。用户显式选择未准入客户端时展示原因并停止该项，不静默绕过。App/CLI 指向同一原生文件时只算一个真实来源。

### 3.1 官方默认规则与 Skill 目录

核对日期：2026-11-11。这里只读官方资料和官方仓库，没有安装或启动下列客户端。`H` 表示原生 Windows 用户主目录，默认写作 `%USERPROFILE%`；Mac 对应 `~`。表内 Windows 路径按官方的 home 相对目录展开；配置覆盖、WSL 的 Linux HOME 和远程 Host 必须另行解析，不能机械替换为当前应用电脑的目录。

| Agent | Mac 默认用户级入口 | Windows 默认用户级入口 | 对照结论 |
| --- | --- | --- | --- |
| Codex | 规则 `~/.codex/AGENTS.md`；Skill `~/.agents/skills/<name>/SKILL.md` | 规则 `H\.codex\AGENTS.md`；Skill `H\.agents\skills\<name>\SKILL.md` | 默认相对结构一致。`CODEX_HOME` 可改变 Codex 配置/规则根；规则还存在 `AGENTS.override.md` 优先级。当前官方 Skill 文档列 `.agents/skills`，不能把它与 `.codex` 配置根混为一谈 |
| Claude Code | 规则 `~/.claude/CLAUDE.md`；Skill `~/.claude/skills/<name>/SKILL.md` | 规则 `H\.claude\CLAUDE.md`；Skill `H\.claude\skills\<name>\SKILL.md` | 默认相对结构一致。官方明确 Windows 的 `~/.claude` 为 `%USERPROFILE%\.claude`，另有 `CLAUDE_CONFIG_DIR` 覆盖 |
| DeepSeek Harness | 规则 `~/.dsh/AGENTS.md`；Skill `~/.dsh/skills/<name>/SKILL.md` | 规则 `H\.dsh\AGENTS.md`；Skill `H\.dsh\skills\<name>\SKILL.md` | 默认相对结构一致。官方实现按 OS HOME 解析；`DSH_HOME` 可覆盖，另读取共享 `.agents/AGENTS.md` 与 `.agents/skills`，共享根由 `DSH_AGENTS_HOME` 控制 |
| OpenCode v2 | 规则 `~/.config/opencode/AGENTS.md`；Skill `~/.config/opencode/skills/<name>/SKILL.md` | 规则 `H\.config\opencode\AGENTS.md`；Skill `H\.config\opencode\skills\<name>\SKILL.md` | 官网默认结构一致，不把用户根改写为 AppData。官方另列 `.claude/skills`、`.agents/skills` 兼容搜索根。机器级目录不同：Mac 为 `/Library/Application Support/opencode`，Windows 为 `%ProgramData%\opencode` |

官方依据：

- Codex：[Windows 用户根](https://learn.chatgpt.com/docs/app/windows#share-config-auth-and-sessions-with-wsl)、[AGENTS.md 与 CODEX_HOME](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[Skill 搜索根](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。
- Claude Code：[Windows 配置目录](https://code.claude.com/docs/en/settings#find-or-create-your-settings-files)、[用户规则](https://code.claude.com/docs/en/memory#choose-where-to-put-claudemd-files)、[个人 Skill](https://code.claude.com/docs/en/skills)。
- DeepSeek Harness：[官方开发文档入口](https://www.deepseek.com/en/harness/)、[Skill 搜索顺序](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills#local-discovery-priority)、[配置根定义](https://deepseek-harness.github.io/deepseek-harness/en/reference/config-catalog)、[官方 HOME 解析实现](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/util/home-paths/src/index.ts)、[官方用户规则发现实现](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/context/agent-instructions/src/files.ts)。
- OpenCode v2：[配置目录](https://opencode.ai/docs/config/#locations)、[规则目录](https://opencode.ai/docs/instructions/#scope)、[Skill 搜索根](https://opencode.ai/docs/skills/#discovery)。本表使用 v2 文档，不混用 `/v1/` 规则页。

本项目当前 `scripts/agm_core/paths.py` 的 Codex 薄 Skill 入口仍为 `.codex/skills`，与本次官网列出的 `.agents/skills` 存在差异；后续接线须核对目标版本的发现规则和已有安装归属，不在路径核查时迁移、覆盖或补装。Claude Code、DeepSeek Harness 与 OpenCode 的现有默认薄入口目录分别与上表一致。`scripts/agents.json` 当前仍只声明 darwin，不因文档路径确认自动放开 Windows 写入。

### 3.2 程序安装位置与接入目录的区别

规则/Skill 目录不是应用程序目录。应用本体不能沿用 Mac `.app` 路径作为 Windows 探测依据，也不能从下列程序位置推断规则已经加载：

| Agent | 官方明确的 Windows 程序安装位置或规则 |
| --- | --- |
| Codex | 独立 CLI 安装器的默认命令目录为 `%LOCALAPPDATA%\Programs\OpenAI\Codex\bin`；npm 安装取实际全局包位置，桌面应用采用 MSIX 部署。不能对这些安装方式写死同一个 EXE 目录。见[官方 Windows 部署](https://learn.chatgpt.com/docs/enterprise/windows-deployment#set-the-installation-context) |
| Claude Code | 原生安装命令为 `%USERPROFILE%\.local\bin\claude.exe`，版本文件在 `%USERPROFILE%\.local\share\claude`；Mac 原生启动入口为 `~/.local/bin/claude`，指向 `~/.local/share/claude/versions/`。WinGet/npm 等安装形态分别识别。见[官方安装与卸载](https://code.claude.com/docs/en/setup#uninstall-a-native-installation) |
| DeepSeek Harness | 官方确认 Windows 桌面版，安装器为当前用户安装且目录可编辑；本次所读官方说明未给出可跨版本写死的默认应用绝对目录，不能由 `.dsh` 反推 EXE 位置。桌面附带命令为安装目录中的 `resources/runtime/cli/bin/dsh.cmd`；Mac 对应脚本，命令管理入口可创建 `/usr/local/bin/dsh`。见[官方 Desktop 说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/desktop/README.md#windows-installer-interface) |
| OpenCode v2 | 官网提供 Windows CLI 独立二进制及桌面下载，并明确 Windows 不支持页面列出的包管理器安装；独立二进制的存放目录由用户选择，不能编造固定目录。规则/Skill 根仍按上表处理。见[官方安装入口](https://opencode.ai/docs/#cli)，实际路径可由[只读 paths 命令](https://opencode.ai/docs/cli/#paths)查询，但本轮未执行 |

对外逐家说明“官方目录已确认”“当前实现是否一致”“实际宿主运行是否验收”，不以总数替代具体结论，也不把官网路径核对写成实际安装成功。

## 4. 用户全旅程

交互继承 [安装 PRD](../product/installation.md)、[共享 PRD](../product/sharing.md)、[项目 PRD](../product/project-rules.md)、[卸载恢复 PRD](../product/uninstall-recovery.md)，下列为 Windows 增量，不替换既有规则。

| 场景 | 预期行为与完成条件 | 失败/退出边界 |
|---|---|---|
| 环境检查与预览 | 输出系统、实际可用依赖、已安装且准入名单、待验项；展示真实安装范围后一次开始确认 | help/check/预览零写，不下载、不建缓存；无可准入对象则不报安装成功 |
| 依赖准备 | 已有兼容版本直接复用；缺失时先给可信来源、版本、权限与变更范围 | 缺依赖不能声称 Python 安装器运行；依赖失败停止并保留明确信息 |
| 首次安装 | 固定来源→精确计划→真实用户批准→锁内复核→持久核心和所选薄入口→核验 | EOF/非交互空输入不批准；批准后不再 TTY 二次询问；漂移重新预览 |
| 首次共享 | 完整读原文与语境；两块连续编号，展示全部合格待选；查看原文零写；选择即执行 | 专属/未知保留，空/缺失与读失败分开；公共和入口核验后才删精确源片段 |
| 再次安装/补装 | 同版同范围幂等零写；仅补本次选定的新客户端 | 新检测结果不得追溯扩大旧批准；不覆盖陌生同名目录 |
| 增量共享 | 保留公共前缀、源次数、私文与合法公共后续编辑；等价提案仍绑定整文件基线 | CRLF/LF 或编码差异不当作字节相等；不修改公共字节来“适配 Windows” |
| 项目接入 | Git 主工作目录首次接入；保留 AGENTS/CLAUDE 全文，仅补当前执行者入口 | disabled、非 Git、linked worktree 跳过；路径别名不重复登记；Context Keeper 不自动初始化 |
| 升级/回滚 | 固定版本及代码清单；保留数据、来源链、入口；验证后提交台账 | 不动 dirty checkout；不做逆 schema；失败保留恢复材料，不降级洗台账 |
| 独立归还 | 公共完整正文直接还回各处原生来源，次数与上下文可核对 | 不只写备份链接；来源漂移或 producer 链不足时停止 |
| 全机卸载 | 精确预览和授权覆盖所有已登记客户端；先归还核验，再删已知产品资产 | 未知资产保留；不删 Context Keeper、客户端、账号及无关插件；备份留待明确清理 |
| 崩溃/占用后恢复 | 外置清单+备份+恢复入口能在核心已删除后工作；明确待恢复状态 | 不偷锁、不按超时自动强解，不以重装绕过未完成事务 |
| Context Keeper 尾步 | 公共整理完成/明确跳过后单独询问；按上游现场能力列实际支持名单 | 不借 memSharing Windows 支持承诺 Context Keeper Windows 支持；上游不支持时可跳过并说明 |

## 5. 平台适配方案

### 5.1 职责边界与已有接口

语义层继续负责分组、用户选择及等价理由；通用内核继续负责精确计划、来源、事务、台账、归还恢复。平台层集中提供路径身份与允许范围、安装信号、文件节点分类、权限快照/恢复、替换与错误分类、依赖解析。禁止在融合规则中分散硬编码 Windows 分支。

Phase 0 可复用的真实接口为：`paths.select_platform(table, platform)`、`paths.load_agents_table(path=None)`、`transaction.read_snapshot(path)`、`transaction.write_lock(path)`、`Transaction.run(...)`、`user_install.plan_install(request)`、升级 `_plan(request, *, allow_marker=False)`。这些是当前内部接口，不是已承诺 Windows 行为；实施者先读实现及对应测试再复用。新的平台抽象名称/签名由实施任务确定，不在本文虚构现成 API。

### 5.2 路径、文件身份与目录布局

建议 Windows 保持用户可辨认的相对布局：公共根 `<用户根>/.mem-sharing`、活动核心 `<用户根>/.local/share/mem-sharing`、版本库存相邻、台账在公共根 `var/registry.json`。这是产品路径设计，不是 Windows 推荐目录的外部事实；W00 验证客户端可读取该布局后才定稿。不能把 `~`、`$HOME` 当作 Windows 命令里必然展开的路径。

- 当前用户根须由可核验的 Windows 用户环境解析；HOME、USERPROFILE 与客户端自定义根冲突时明确显示解析结果，禁止静默选另一个用户目录。测试根必须显式隔离。
- 展示路径保留原拼写；内部授权用规范绝对路径、卷身份及真实节点身份校验。大小写、分隔符、短文件名/别名、硬链接与不同盘符映射不能造成重复来源、越界或目标源重叠。
- 拒绝盘符相对路径、保留设备名、ADS、尾随点/空格歧义、设备路径与未经允许的扩展路径；中文、空格、非 ASCII 用户名为必测正例。长路径先做只读可用性检查；超出已验能力时明确拒绝，不能默认修改系统策略。
- 所有祖先及叶节点都检查 symlink/junction/reparse；首批对用户可变写入链中的未知链接拒绝。系统管理的用户根解析例外须在 W00 有明确证据后逐项批准，不能放开整个 reparse 类别。
- 产品原生 Skill 使用普通薄入口文件，指向唯一持久核心；不要求管理员创建 symlink/junction，不复制第二份可编辑内核。历史链接资产按原类型保全和诊断，不盲目转换。
- 跨卷公共/项目操作不宣称全局原子：每个目标同目录替换，统一 journal 记录阶段；不把跨卷 rename 当成提交。外置备份失败时不得开始破坏性阶段。

### 5.3 字节、编码、来源和权限

用户正文以原始 bytes 建快照、哈希、范围与恢复证据；解析文本只是视图。保留 CRLF/LF、BOM、首尾空白和原始编码，不使用默认文本换行转换重写整文件。候选解析首批建议支持 UTF-8（含 BOM），其他编码保全但不自动共享，给出可读错误；不得静默转码。

新建产品文件采用统一确定的 UTF-8/LF；对既有文件的追加策略必须在计划中列出确切字节，只修改受管区，不能顺带全文件规范化。来源内容不同换行即不同原文，只有明确等价提案且精确绑定各自 bytes 才允许复用公共条目。

Git 来源固定 commit、tree 与逐文件哈希；Git for Windows 的 autocrlf/eol/filter/可执行位差异是供应验证门。推荐在产品拥有的独立干净源目录以局部配置获取已批准 commit，并从 Git 对象确定发布清单，验证安装字节与该清单一致；不得修改用户全局 Git 配置或对用户 checkout 强制 reset。必须明确现有 `tree_sha256` 的生成语义；若需改清单格式，要有版本化及旧清单兼容读者，不把 CRLF 后的工作树哈希直接与旧发布值混用。

权限不能靠 chmod 0600/0700 宣称 Windows 隐私保证。W02 须验证所有者、DACL、继承及备份/临时文件可见性；优先使用标准库可达的受审 Windows 系统接口，若无法满足最小权限与精确恢复则提出依赖取舍复审，不悄悄引入包。替换前后保留目标访问语义，禁止扩大其他用户权限；不复制来源不必要的权限到公共根。日志不得带原文、凭据或整份用户目录。

### 5.4 事务、并发、文件占用与恢复

沿用先备份、精确基线复核、分阶段落盘、台账最后提交。单文件替换不等于多文件原子，也不直接承诺断电持久性。

- Windows 实测 mkdir 排他、节点身份、句柄释放及同目录 replace；普通用户并发安装/共享/卸载只能一个写者，其他返回忙且零写。
- 客户端编辑器、杀毒软件和同步服务占用造成的共享冲突分类报告。可对明确瞬态占用做有界退避（建议最多 3 次、总计不超过 2 秒）；每次重试仍检查基线，不重跑用户选择，不无限等待。
- 替换失败前未改正文则零改动退出；已部分修改时按 journal 回滚并核验。回滚再失败必须报告“需要恢复”，列已完成/未完成步骤及备份，不报整体失败后假装现场未变。
- 对正常终止、强杀进程、重启分别注入故障；权限、bytes、来源次数与恢复后的台账都要验证。stale 锁由显式恢复流程核实，不仅凭 PID/时间判断。
- 非合作写者在最后复核后仍可能竞态；不得宣称现有锁消除了全部外部竞争。验收要覆盖窗口内编辑，无法安全判断则保留现场和恢复材料。
- 外置恢复包含固定版本恢复程序、完整 bytes/元数据与清单；不得依赖被卸载的 C 目录。验证离线恢复、路径被替换、备份篡改、ACL 无法恢复等拒绝路径。

### 5.5 历史兼容与 Paseo

历史 schema、producer、来源替代和 Context Keeper 通用触发沿既有规则，不为 Windows 放宽环检测、整文件基线或来源证明。schema v1/v2 只读诊断；v0 只复制已授权内容且旧源原地保留。macOS 备份复制到 Windows 不自动成为可恢复本机安装：平台、路径、权限表示和来源身份不匹配时拒绝自动恢复，单独迁移方案另审。

Paseo 不列首批阻断依赖：Python 原生入口可以独立交付。插件后续需单独核实 Windows 宿主发行、插件加载、Node 进程路径与引号、Python/Git 获取、运行时资产许可与 hash、UI 调用及卸载义务；[插件验收](../README.md)沿用分层口径。未完成前插件展示“不支持此平台”，不能隐藏错误后继续或复用 macOS 下载资产。

## 6. 错误、隐私与诊断

建议错误分类为候选实现要求，不是现有 CLI 已有错误码清单。输出包括原因、是否写入、保留位置与下一步，不泄露正文。

| 场景 | 用户文案示例 | 必须可观察的结果 |
|---|---|---|
| 平台/客户端未准入 | “当前版本尚未验证此 Windows 环境／客户端，未开始安装。” | 无产品写入；列可支持组合 |
| 依赖不可执行 | “找到 Python，但运行检查未通过。请修复所列路径后重试。” | 不将商店别名/空壳命令当可用解释器 |
| 权限/路径不安全 | “此目录的权限或链接状态无法安全确认，未修改文件。” | 不自动提权、改 ACL 或关闭防护 |
| 文件占用 | “目标文件正在使用。请关闭占用程序后重试；本次状态：未修改／需要恢复。” | 展示真实阶段，不统一报零写 |
| 基线漂移 | “文件在预览后发生变化，请重新生成方案。” | 旧批准失效；当前正文不被覆盖 |
| 恢复未完成 | “恢复尚未完成，备份保留在〈位置〉。请先恢复，再继续安装。” | 后续写操作阻断，诊断可只读运行 |

默认诊断只含版本、能力、脱敏路径、阶段和错误类型；详细路径仅本地面向用户。不得自动上传日志或原文。依赖安装不用远程脚本管道，不绕过执行策略/杀毒，不自动关闭客户端，不因检查失败修改真实 HOME 或系统设置。

## 7. 候选验收与发布门禁

以下为**完整适配的验收要求，尚未整体通过**；已验证能力仅限本页所列的双端预览。每条证据绑定 OS build、架构、文件系统、Shell、依赖/客户端版本、commit、输入夹具、预期与实际结果，截图只取无隐私样本。

| 层级 | 必测范围 | 通过条件 |
|---|---|---|
| L0 源码/静态 | 未知平台拒绝、六家准入、无 macOS 回退、参数列表启动子进程 | 审查与结构测试通过；不冒称 Windows 可用 |
| L1 跨平台合成 | bytes/编码、别名/链接、来源次数、等价、Context Keeper 替代反例、权限失败、占用、并发、各阶段故障 | 保护性失败零写或明确可恢复；完整往返不丢字节 |
| L2 Windows 隔离真实文件系统 | 普通用户临时根，NTFS、中文空格、不同盘、PowerShell；真实句柄占用和 ACL | 不是 mock sys.platform；完整安装→两轮共享→归还→卸载→恢复→fresh 成功 |
| L3 Windows 客户端真机 | 每家独立：强安装事实、Skill 发现、规则链、全新会话读到唯一测试标记 | 记录实际加载证据；有文件≠已读，模型口述≠完整链证明 |
| L4 用户旅程 | 用户从 README 普通请求开始，默认/部分选择、查看/拒绝、增量、项目、升级、退出 | 不需维护者隐藏命令；私文、未选项、Context Keeper 与备份符合范围 |
| macOS 回归 | 原有 Python unit/integration；代表性安装共享退出；插件受影响时其类型检查和测试 | 原支持不退化，Windows 分支不改变既有来源/权限语义 |

建议 CI：固定 Windows runner 镜像 x64（具体 OS 与 Windows 11 真机差异必须记录），Python 3.9、用户报告的 3.13 系列、实施时选定稳定版本；macOS 跑最低和主测 Python。3.9 无法在 runner 获取时不能静默删格，需单列兼容任务或评审提高最低版本。Git autocrlf=true/false/input 用独立配置组合，避免污染全局；PowerShell 主测，cmd 调用烟测。ARM64、网络盘、WSL 明确不在绿色矩阵内。

Windows 11 真机（实体或可交互完整虚拟机）至少两组：干净标准用户环境；已有六家中实际可获得客户端、混合私文/旧入口环境。无第三方发行或账号验收条件的客户端维持待验，不伪造安装证据。使用合成无隐私正文，不在开发者真实用户数据上做破坏性测试。

发布顺序：W00 事实门→平台/安全底座→完整生命周期→逐家准入→候选版真实旅程→macOS 回归→用户批准发布。门禁未关闭不得先移除生产保护。首个 Windows 候选可以只开放实验入口，但生产支持声明必须等已准入名单、恢复证据和回归齐全；“Windows 六家完整支持”必须六家全部 L3/L4 通过。

发布失败时停发该组合并保留证据；已有用户先走当前版本兼容的恢复/回滚，不通过降级忽略新 schema。性能基线在 L2 记录只读检查、共享和恢复耗时，不为追求速度省略全量字节校验；首批不承诺未经测量的 SLA。

## 8. 未支持能力与扩展条件

- 更多Windows版本、架构、客户端配置组合及原生入口，须逐项完成安装、实际新会话读取、共享和退出验收。
- 旧安装迁移、升级、回滚、自动融合归还和全机卸载，须验证来源链、schema、私文保全及核心删除后的独立恢复。
- SDK/ABI、case flags、别名/硬链接、权限失败及多路径冲突，需覆盖真实支持组合；辅助路径检查通过不直接授权写入。
- 注册Cloud Files根识别不等于排除所有同步软件。provider未知、推断错误映射或查询不可用不能整体放行，也不要求无限穷举第三方软件。
- ACL/DACL、属性和时间是不同组件。组件回读相同不代表全部安全描述符/metadata恢复；缺原像不猜值，不通过放宽断言获得准入。
- 逐文件快照与合作锁不是OS原子CAS；非合作写者、占用、杀毒及崩溃恢复需按具体承诺验证，不关闭防护、抢未知锁或自动提权。
- Windows Paseo插件、运行时供应及Context Keeper上游能力分别准入，不复用macOS资产冒称支持；这些不阻断已声明更窄的内核预览。

保持一个标准库内核和薄宿主适配。正式发行需固定干净来源、核验生成载荷与S/R身份；提交、推送、合并不是发布或部署。
