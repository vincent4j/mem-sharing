# M1-01 接口冻结与 dogfood 预检

状态：预检完成；M1 运行验收未执行。依据 DESIGN.md v1.1、docs/plan/tasks.md M1-01、architecture.md §0/6。本报告只批准自身文档交付，不构成后续安装、入口写入或建库授权。

## 1. 身份、执行范围与放行结论

- run_id：m1-01-20261029T103841Z；操作者：呱唧（本次受托 Codex 会话）。派工消息：360800af-089c-4be2-aa56-cb82656ae0c0。
- 观测时间：2026-10-29T10:38:41Z 起；macOS 26.6.2、arm64。
- 项目根/主 checkout：`/Users/vincent4j/Tools/Source/agent-group-memory`（下称 R）。Git common-dir 为 R/.git；worktree list 仅一个 main checkout。
- 项目 HEAD：`a43e31cdccd54a886f85aa16ae9b0c03e2f3667e`；开始时 `git status --short --untracked-files=all` 为空。DESIGN v1.1 文档基线为 53314d7，勿混为当前 HEAD。
- 已读取 `/Users/vincent4j/.agents-group/memories/MEMORY.md`。只读核对入口与上游代码；未读旧库正文、未执行 init/status/迁移/保存、未安装、未改用户入口或上游文件、未 commit/push。仅写本报告与 m1-acceptance.md 的实际值。

| 步骤 | 结论 | 放行前提/阻断范围 |
|---|---|---|
| M1-02 根 AGENTS.md 与 CLAUDE.md 基座 | 技术预检可放行，实际写入仍待授权 | 两个文件均缺失，无 override；可准备具体 diff。不能把本轮只读授权解释成写入批准 |
| M1-02 WorkBuddy 三家完整基座 | 暂不整体放行 | 用户入口缺公共源指针，且旧约定把“事实”放 AGENTS.md，需裁定追加例外的文本与写范围 |
| M1-03 项目 Skill / Codex、Claude bridge | 技术接口可用，执行待授权 | 固定源码与四个项目 Skill 落点；禁止 fallback 到用户级；不得顺手更新已有 Codex 用户块 |
| M1-03 第四态、M1-05 样本 | 阻断 | 本项目记忆选择与库位置未批准；无样本批准；不能置 ready 或搬运 |
| M1-04 WorkBuddy bridge | 阻断 | 用户旧约定与顶部规则块冲突，需明确追加例外；上游不支持此自动入口；新会话能力未验证 |
| M1-06/07 接力与负向验收 | 阻断实际执行 | 依赖装配/库授权、WorkBuddy 冲突解决、三家新会话可用及负向 fixture 授权；当前无运行证据 |

不存在源码缺失或当前解释器不兼容的阻断。Codex 用户块差异只阻断该既有块的自动更新/接管，不阻断获批后的独立项目基座；WorkBuddy 冲突阻断完整三家基座和后续桥接验收。

## 2. 三执行器入口盘点

下列用户文件只登记必要规则、大小和指纹，不在公开报告复制个人正文。已有对象按 reused/unknown 保护，不能记 created。

| 执行器/路径 | 已有、缺失与冲突 | 能力证据边界 |
|---|---|---|
| Codex `~/.codex/AGENTS.md` | 已有，共享规则读取指针存在；Keeper marker 配对各一次。现有块只有五条，与当前七条模板不同，无可信既有登记证明差异成因；按漂移候选保护 | CLI `/Users/vincent4j/.local/bin/codex`，`--version` rc=0：0.162.0；本次会话不算新接力会话 |
| Claude `~/.claude/CLAUDE.md` | 已有 `@/Users/vincent4j/.agents-group/memories/MEMORY.md`；无 Keeper marker；专属原文保留 | CLI `/Users/vincent4j/.local/bin/claude`，`--version` rc=0：2.1.295；未新开会话 |
| WorkBuddy `~/.workbuddy/MEMORY.md` | 已有 AGENTS.md 唯一规则来源约定，但同句含“事实”；限定项目 MEMORY.md 只放指针；未发现共享 MEMORY.md 指针或 Keeper 条款。与设计的记忆分离/顶部 bridge 冲突 | PATH 无 workbuddy 命令；`/Applications/WorkBuddy.app/Contents/Info.plist` 为 5.9.3（build 5.9.3）。只读元数据，不证明能启动、登录或执行新会话 |
| R/AGENTS.md、R/CLAUDE.md | 均缺失，可新建骨架与 `@AGENTS.md`；本轮不建 | 尚无项目规则/bridge |
| R/.workbuddy/、R/.workbuddy/memory/MEMORY.md | 目录及文件均缺失；不创建日志或记忆目录 | 顶部 bridge 可达性待 M1-04/06 |

根、祖先链及仓内文件名盘点未见 AGENTS.override.md；`~/.codex/AGENTS.override.md` 也缺失。仓内未见子目录 AGENTS.md/CLAUDE.md；WorkBuddy 子目录盲区仍按 DESIGN §4.3 接受，不能宣称已验证递归读取。

| 入口 | 整文件 SHA-256 | 字节 |
|---|---|---|
| `~/.codex/AGENTS.md` | `97995e9d0b5e3438685d52212d80e3b8a5efe68287231184850f3cbb9070b642` | 1502 |
| Codex 现有受控块（含两 marker，不含块外换行） | `d8188b8064a8d51afc373b7acb32bf2543b349ba9c43cb4496526f320edd7664` | — |
| `~/.claude/CLAUDE.md` | `186018d21b872984f42d20f7da3dcd8f241662b59a849d295f50157488ab6e2f` | 627 |
| `~/.workbuddy/MEMORY.md` | `9cb55e362fb7a7c57caef8d2f8359dda75b94c475b719d726deaa5ec10c59024` | 3114 |

三用户入口在预览后重复读回，上述指纹未变。没有修改它们来消除冲突。

### Skill 路径与所有权

源码 S = `/Users/vincent4j/Tools/Source/context-keeper`。

- `~/.agents/skills/context-keeper` → `~/.agents-group/skills/context-keeper` → S，解析到同一源码。
- `~/.claude/skills/context-keeper`、`~/.workbuddy/skills/context-keeper` 均为 symlink，最终解析到 S；已有用户对象只复用。`~/.codex/skills/context-keeper` 缺失，不等于 Codex Skill 不可用。
- 项目四落点 R/.agents/skills/context-keeper、R/.codex/skills/context-keeper、R/.claude/skills/context-keeper、R/.workbuddy/skills/context-keeper 全缺失；未发现项目复制目录/异源链接冲突。
- 现有 symlink 可解析只证明当前读取可用；本轮未新建 symlink，创建权限、失败恢复和 WorkBuddy 沙箱行为留实际安装验收。

## 3. Keeper 版本及实际接口冻结

S 工作区 `git status --short` 为空，HEAD `a8e584159b3853b11f96b0ec89036d04ce29dce2`（2026-10-29T17:31:16+08:00）；SKILL frontmatter version `1.0.0`，精确身份用 commit 加文件哈希，不只看此版本号。

| 文件（相对 S） | SHA-256 |
|---|---|
| SKILL.md | `1ba25f707cf403838975c0a01401b474599de79c3dae96ee047b66c70864c61a` |
| scripts/install.py | `2f8d62c59d4462275d87ed6a8a7edd20ba1b5b6ca188aa4d846abe76fcacd47e` |
| scripts/context_keeper_probe.py | `9c2731c1dc7c062dd9ea2cfabf72ae1a7052f54b7cddd25a53a9cb4ac580e567` |

实际 parser 位于 install.py:240–259（旧 architecture 行号已偏移）。参数：`--ensure-bridge --approved --skill-dir --root --all --codex --claude --cursor --workbuddy --hermes --opencode --openclaw --project --uninstall --bridge-only --codex-dir --claude-dir`。没有 `--skill-only`。

- 普通项目安装显式三家会准备四个 Skill 链接，并同时写 R/AGENTS.md、R/CLAUDE.md 的 bridge；不是“只装 Skill”。
- `--ensure-bridge` 只接受单个 Codex 或 Claude，不能混 `--all/--project/--uninstall/--codex-dir/--claude-dir`；WorkBuddy 自动入口拒绝写入。
- ensure 根据保留安装别名识别 user/project；源码实路径会搜当前/祖先/用户别名。项目别名尚不存在时不要调用 ensure，以免退到用户级；安装后逐家用项目别名调用并读回 scope=project 与预期路径。
- marker 为 `<!-- context-keeper:start -->` / `<!-- context-keeper:end -->`。上游检查配对/顺序/重复，不核验 AGM 所有权或已登记指纹；完整但手改的块仍可能被替换。AGM 必须事前判漂移。
- BRIDGE 七条语义：无项目聊天不自动记录；迁移 rc=3 停；限量历史检索；获授权库内自然节点记录；日志追加/主题可更新；当前主题优先与经验证据边界；事实来源与历史授权边界。模板原字节以该源码哈希为准。
- WorkBuddy 拟用独立 marker `<!-- context-keeper:workbuddy:start -->` / `<!-- context-keeper:workbuddy:end -->`，放项目 MEMORY.md 顶部，保留每日日志；上游不会生成它，本仓库模板仍待运行时验收。

### 实际只读命令与退出码

以下使用当前 `python3`，均无 `--approved`：

```text
python3 S/scripts/install.py --project R --codex --claude --workbuddy
rc=0，JSON approval_required=true，operation=安装
skill_entries=[R/.agents/skills/context-keeper,
 R/.codex/skills/context-keeper, R/.claude/skills/context-keeper,
 R/.workbuddy/skills/context-keeper]
rule_files=[R/AGENTS.md, R/CLAUDE.md]

python3 S/scripts/context_keeper_probe.py --help
rc=0，列出 migrate/init/record-path/record-guard/resume/search/
history-search/promote-evolution/status/compact/coverage/save-report
```

这里 S/R 是上述绝对路径的阅读缩写，执行时展开成参数数组。预览只证明目标检查可通过及候选写范围；rc=0 不等于安装完成。AGM 后续应将 `approval_required=true` 映射为待确认（草案 rc=5），不置 ready。未运行用户级 ensure，不请求更新既有漂移块。

### probe 迁移、init 与失败语义（源码核验，非运行用例通过）

- probe.py:1973 起 main 在任何非 migrate 命令分派前检查旧结构；`docs/memory-keeper.md`，非空 `docs/plans/`、`docs/worklogs/`、`docs/worklog/` 触发“需要迁移”并 rc=3。只检测路径/目录，不应读旧正文。出现后立即停止相关读写；迁移预览与后续批准单独处理。
- init 参数实际为 `--root --store-dir --migrate --approved`；默认/自定义位置未批准均 rc=5（RC_NEEDS_CONFIRMATION）。已存在且等于目标的库可 rc=0，因此 rc=0 本身也不代表项目已授权。
- init 内部先 `_discover_store(root)`，再处理 `--store-dir`；两个候选均像记录库时 rc=2，传自定义位置也不能消歧。save.md 所称“歧义时用 --store-dir”对 init 不成立。
- 改既有库位置需要 `--migrate`；目标非空、父子包含、历史证据链接改向等拒绝 rc=2，不能混作 rc=3。
- 新建分支异常清理仅在 migrated_from 为真时执行；普通新建失败可能留下部分目录、索引或配置，甚至以未捕获异常退出。不得只认 2/3/5，也不得回删库。保留现场并标 partial，停写后只做授权范围内的元数据/配置定位核对。

## 4. Python 与依赖边界（O8）

- 本次解释器 `/opt/homebrew/opt/python@3.14/bin/python3.14`，3.14.3，满足 AGM ≥3.9。
- 两个上游脚本在当前解释器内存 compile 通过；install 实际预览、probe `--help` 通过，均 rc=0。未用 py_compile 写上游缓存。
- AST 全部 import 仅标准库：安装器 argparse/hashlib/json/os/pathlib；探针另含 datetime/math/re/shutil/sqlite3/subprocess/tempfile/time/typing。没有 pip/yaml 依赖；此结论限本阶段依赖的两脚本，非整个仓库测试依赖承诺。
- 两脚本 Python 3.9 grammar 解析通过，使用 future annotations；Path.is_relative_to 为 3.9 接口。但未实际用 3.9 解释器执行，最低版本运行、完整命令分支及 Windows/Linux 均 not-run。现有 macOS symlink 解析可用，安装/卸载/恢复能力另验。
- 旧 sync.py 的 fcntl 锁不能当跨平台实现；本轮只读参考 block/put 和快照恢复，未导入或执行旧管理器。

## 5. 库状态、授权待办与 O4/O5/O8/O9

R/docs/context-keeper、R/context-keeper、R/context-keeper.json、上述四类旧结构均缺失（仅路径/元数据核对）；未发现实际库，也未从任何旧库正文取证。R/scripts/registry.json 缺失；仓库目前只有 CLI 骨架，不能冒充可用的工具化授权账本。

四态：source_available=ready（本地可读）；项目 skill_installed=missing（三家四落点）；project bridge_assembled=missing；store_authorized_ready=unknown/blocked（授权未知且库缺失）。用户级 Skill 可用与项目第四态无关。

| 开放项 | 本轮收敛结论 |
|---|---|
| O4 | 关闭解释歧义：项目内零新增状态指 AGM 纳管状态。Keeper 在自定义非候选库位置生成的 context-keeper.json 是 provider 配置，应保留，不删除、不另造。两默认候选位置可能不生成该文件。DESIGN 不在本任务擅改 |
| O5 | 本机 S 可读、提交/哈希已冻结，使用它作为 M1 候选来源；实际安装前仍需认可该具体来源与版本。通用获取策略待用户裁定：A 固定用户指定 checkout/commit，缺失即停止（建议）；B 用户明确指定远程来源及固定版本后另案获取。未批准不得下载 main 或换来源 |
| O8 | 当前 macOS/Python 3.14.3 的有限只读接口通过；两脚本标准库假设成立。3.9 仅语法检查；平台安装/恢复和新会话能力待 M2-09，不能扩大兼容性声明 |
| O9 | 确认上游 init 双候选提前 rc=2 与文档差异、新建异常可能残留。接入策略固定为遇歧义/部分失败即停、保留现场、不改上游/删库/借参数绕过。若真实发生双库，需要用户另裁保留库与修复范围，当前无双库，无需虚构迁移 |

后续授权清单（本轮不发起操作，也不视历史下一步为批准）：

1. M1-02 批准 R/AGENTS.md、R/CLAUDE.md 的具体骨架 diff；WorkBuddy 用户级公共源引用及原约定例外需另展示具体追加文本。建议保留原文，追加“本项目事实进入获授权 Keeper 库；项目 MEMORY.md 允许受控 bridge，其余仍只作指针”的明确例外；是否接受待用户裁定。
2. M1-03 批准上述 S/commit、四个项目 Skill 链接与两项目 bridge。已有用户级 Skill 记 reused；三个用户入口无全局更新授权。Codex 五条块要更新时须另案 diff，不被本项目安装顺带覆盖。
3. 本项目 memory_authorization=yes/no 与位置批准分别记录。建议候选 R/docs/context-keeper，尚未确认；也可用户指定自定义位置。批准后才 init，rc=0 再核对实际落点；未知/拒绝不保存。
4. M1-04 批准 R/.workbuddy/memory/MEMORY.md 顶部块和用户级记忆追加条款；用户旧约定冲突未裁定前不写。
5. M1-05 用户指定单份可公开样本、来源/目标/分类/可见性逐项批准；当前来源未知，不找私有内容补数。
6. M1-06/07 三家新会话环境与隔离 fixture 根/位置/写范围需落实；当前未创建 fixture。应用操作按环境委派边界交章教授，不可用则停止该应用验收。

## 6. 可执行顺序、备份与恢复

以下是后续获批操作计划，不是本轮已执行结果：

1. 重核 Git 根/common-dir、源码 commit/三文件哈希、入口指纹、override、Skill 目标与授权范围；有变化先重新核对。冻结当前 dirty 文件清单，只操作批准 allowlist。
2. 在本仓库 `scripts/backups/<UTC-操作ID>/`（已 gitignore）建立获批配置备份与 manifest：路径、原先是否存在、对象类型、整文件字节/模式、symlink 原始与解析目标、受控块和块外指纹、操作/授权依据、预期后指纹、读回与恢复状态。没有实际变更前不制造备份已完成的结论。
3. 基座获批后新建根 AGENTS.md 与 CLAUDE.md 的 `@AGENTS.md`；不塞历史事实。读回、块外字节核对、重复操作无新 diff。
4. 对 S 再跑显式三家项目预览；批准同一范围且指纹不变后原参数加 `--approved`。备份集含两项目入口、四链接及其父目录“原先是否存在”；不触碰既有用户 Skill 链路。安装会同时写两 bridge。
5. 安装后分别 ensure：Codex 用 `--skill-dir R/.agents/skills/context-keeper --root R --codex`；Claude 用 `--skill-dir R/.claude/skills/context-keeper --root R --claude`。只读预览应 unchanged，写入如有需要必须属于已批准范围；scope 非 project 或 bridge 路径不符即停。不向 WorkBuddy 传 ensure。
6. 库位置获批后按真实 init 参数创建；新库本体不进 AGM 删除/回滚集。自定义 provider 配置记路径/前后状态并保护，失败标 partial。无第四态不得继续保存与搬运。
7. 冲突裁定后部署 WorkBuddy 顶部块，备份其项目文件及 `~/.workbuddy/MEMORY.md`，保留原文/身份文件/每日日志。用户级只允许具体获批追加；运行时状态先 pending。
8. 单样本搬运与四新会话接力串行写同库，另存 session-id/真实来源/实际库 diff。N1/N2 用独立获批 fixture，基线与证据放库外；rc=3 后保留工具轨迹，不能用零 diff 证明“未读”。

恢复范围：只恢复本次配置备份，逐文件/链接比对后确认恢复结果；文件或块外出现新改动则停下人工核对，不整文件覆盖新内容。created 链接只有后指纹相符才移除；reused/unknown 永不删除。恢复新建入口时也须确认整文件仍等于本次输出，无新增内容才可撤销。用户级原有内容不能用模板重建。记录库、context-keeper.json 与 Keeper 源码均不因 AGM 回滚而删除或覆盖；init partial 保留现场。恢复失败保留 manifest 与现场，报 recovery_required；不循环重试或升级为 `--all --uninstall`。本轮未创建备份或测试恢复，不能声称恢复能力已验收。

## 7. 本轮验证与未验证范围

通过：Git 身份与干净基线、路径/入口/marker/哈希核对、当前 Python 的内存编译、3.9 语法检查、两 CLI 版本、WorkBuddy app 元数据、安装器只读预览与探针帮助。入口用户文件预览前后哈希一致。源码及用户配置均未写。

not-run：ensure 用户级/项目级写入、真实 Skill 安装/幂等/回滚、init/迁移用例、库授权与读写、新会话接力、负向 N1/N2、样本搬运、WorkBuddy 启动/加载/重置行为、Python 3.9 运行、Windows/Linux。缺失运行证据不能折算 passed；M1 总体验收仍未放行。
