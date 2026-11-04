> 当前决定（2026-11-03 16:22 UTC）：用户明确“不用创建用户，就在当前用户测试就行”。下面A1/A2隔离建议不再是当前前置条件。改在当前用户真实环境测试；可启动测试所需新会话，不读取旧对话，不以临时HOME声称隔离。共享/归还仍须展示完整数据变更清单后确认；不安装卸载、不复制凭据。

# 六家原生运行前置盘点与隔离方案（只读证据版）

状态：本机只读盘点完成，隔离推荐路线与待授权清单成形；未启动任何 CLI/App/模型，未读取任何真实私文/凭据/账户配置/环境变量原值/进程命令行，未改真实宿主配置/私文；已写仓库内材料（本文档与 fixtures）并在纯临时目录试跑 staging 脚本。日期：2026-11-03 15:55:32 UTC 起（15:57–16:00 UTC 取证）。基于分支 `verify/skill-first-runtime`，仅新增本文档与 `tests/fixtures/skill-first-dialogue/`。

## 只读盘点证据（2026-11-03 15:57–16:00 UTC 实际执行）

命令均只读：`command -v`（仅查找，绝不执行目标）、`realpath`、`plutil -p`（Info.plist 键）、`codesign -dv`、`stat`、`file`、`uname`/`sw_vers`、指定名称的目录存在性检查。路径依据：仓库 `scripts/agents.json` 安装信号（executable/bundle 名）+ 有限常见安装目录（`/Applications`、`~/Applications`），未广扫 HOME。

### 机器

| 项 | 证据 |
| --- | --- |
| 架构/系统 | `uname -m` → arm64；`sw_vers` → macOS 26.6.2 (25G83) |

### 六家 CLI（command -v / realpath / 包元数据）

| 家 | 结果 |
| --- | --- |
| codex | `~/.local/bin/codex` → `~/.local/lib/node_modules/@openai/codex/bin/codex.js`；npm 包元数据 `@openai/codex 0.166.0`（与 agents.json 信号一致） |
| claude | `~/.local/bin/claude` → `~/.local/share/claude/versions/2.1.295`（239,695,888 字节可执行） |
| opencode | `~/.opencode/bin/opencode`（Mach-O arm64 可执行） |
| zcode / dsh / workbuddy | 本轮未在 PATH 找到 CLI（agents.json 对 zcode/dsh/workbuddy 也未定义 CLI 信号，仅 App） |

### 六家 App（/Applications，Info.plist + 签名可读）

| App | Bundle ID | 版本 | 签名 Team |
| --- | --- | --- | --- |
| WorkBuddy.app | com.tencent.workbuddy.mac | 5.9.3 | FN2V63AD2J |
| DeepSeek Harness.app | com.deepseek.dsh | 0.2.1-rc.5 | NAN929V4UM |
| ZCode.app | dev.zcode.app | 3.17.2 (3.17.2.9661) | 8A5X4JJ39T |
| OpenCode.app | ai.opencode.desktop | 2.2.5 | 5NZ4Q7NXJ4 |
| Codex.app / Claude.app | 常见目录本轮未找到（Claude 主形态为 CLI，已找到） |

**口径**：仅缺 PATH/App 元数据即为本轮未找到；不推定未安装、不推定未登录，不读取任何目录内容来判断安装/登录状态。

### VM 工具与安装介质

- `/Applications` 下按名未找到 UTM/Parallels Desktop/VMware Fusion/VirtualBox；`Install macOS *.app` 亦未找到（均仅限有限常见目录的按名检查）。
- 口径：**有限常见目录未找到不能断言本机无 VM**——仅表示本轮按此证据未发现；如需排除须另行授权更广的只读取证。
- VM 路线当前可判定的缺口：常见目录未见虚拟化工具与安装介质，两者均需用户授权下载/安装；工具选型的网页调研属章教授（经主转达），本轮不做。

### 隔离相关本地取证

- `man -w dscl` → 有手册（/usr/share/man/man1/dscl.1）；`sysadminctl` 无 man 页——若走 CLI 创建账户，其参数无法从本地文档取证，不猜参数。
- 候选测试用户名冲突只读检查（`dscacheutil -q user -a name`）：`memshare-acceptance`、`memshare_test` 均未被占用。

## 隔离方案评估与推荐

| 方案 | 边界 | 评估 |
| --- | --- | --- |
| 仅改 HOME/环境变量 | 同一账户、同一文件系统主体 | **不构成原生隔离**（runtime-next 既有裁定），仅可用于合成 fixture 测试，不可用于原生新会话验收 |
| 独立标准 macOS 用户 | 独立账户/HOME/登录会话 | **推荐候选**，但必须明示：标准用户仍可能读取其他用户"全员可读"权限的文件（如同机 /Users 下公开权限内容），不是强隔离；可验证边界=独立 HOME、独立登录上下文、独立 keychain |
| 本机 VM | 独立系统实例 | 独立系统边界；本轮有限盘点未找到可用工具和介质，是否已有其他安装仍未知 |

**推荐路线**：先走独立标准 macOS 测试用户（名称候选 `memshare-acceptance`，已核未占用）；VM 作为后续可选升级，待用户决定是否投入工具安装。每家原生会话启动前在测试用户会话内核查进程实际 HOME/配置根/数据根落在测试用户内且无外部私文访问路径，未核过不启动模型。

## 待授权动作（互不连带，逐项批准）

| # | 动作 | 写入类别 | 步骤与证据 | 回退 |
| --- | --- | --- | --- | --- |
| A1 | 创建测试用户 `memshare-acceptance`（经当前管理员认证、以系统设置→用户与群组的 GUI 路径创建**标准用户，不赋予管理员权限**） | 环境创建写入 | 新 HOME 确切为 `/Users/memshare-acceptance`；创建时不启用自动登录、远程登录、文件共享；不复制任何现有账号的配置、keychain 或数据；GUI 路径无需 CLI 参数，`dscl` 有 man 可作只读核验补充（如 `dscl . -read /Users/memshare-acceptance`）；不用 sysadminctl（无 man，不猜参数） | **删除该用户及其 HOME 是后续独立批准动作，本次创建授权不包含删除**；回退时经用户单独批准后在系统设置中删除，不触碰其他账户 |
| A2 | （可选）VM 工具与安装介质获取安装 | 环境创建写入 | **本轮尚无可用入口证据**：有限盘点未找到虚拟化工具与 macOS 安装介质；选型需网页调研→主转章教授；授权后另行给出具体步骤 | 删除 VM/App 及虚拟机盘 |
| B1–B6 | 在测试用户会话内逐家启动 CLI/App（codex/claude/opencode CLI；WorkBuddy/DSH/ZCode/OpenCode App）做可用性验证 | 环境使用（首次启动会产生该测试用户自己的配置写入） | 启动前核 HOME/配置/数据根；各家启动方式以其本地文档/`--help` 在测试用户内取证（本轮禁止，授权后才可）；不证明可用不进入后续 | 经后续独立批准删除测试用户及其 HOME；需先确认其中无待保留成果 |
| C1 | 测试用户内登录账号/调用付费模型 | 批准后写入（写入测试用户自己的凭据存储） | **单独授权**；凭据由用户在测试用户会话内亲自输入，我不获取、不转存、不回显 | 测试用户内登出/删除账户 |
| D | 真实 Skill 对话链（合成材料） | 见 fixtures 写入分类 | 材料与脚本已备：`tests/fixtures/skill-first-dialogue/`（见下）；在隔离环境就绪后执行 expected-flow 九步 | 合成临时目录整体删除；共享执行可用 return 命令全量归还 |

**写入分类口径**（不笼统说批准前零写）：环境创建写入=A1/A2/B 首启配置；提案临时写入=提案 JSON/批准文件（临时工作位置）；批准后写入=共享执行（限隔离环境内合成/原生目标）。

## 真实 Skill 对话材料（已备，仅生成文件未执行）

`tests/fixtures/skill-first-dialogue/`：`sources/` 三份合成中文原文（codex-AGENTS/claude-CLAUDE/workbuddy-MEMORY），最少一组同时覆盖四种区别——全覆盖默认（三家同文"提交信息使用中文"）、部分覆盖待选（仅两家"修改后运行相关测试"）、独有保留（各家独有条目）、同标题不同语境（# 缓存策略 下构建缓存 vs 会话缓存，提案 `same_content=false`，可作待选组但不得当 true 去重）；`stage-synthetic-home.sh`（默认无参数自行 mktemp 新建专用临时目录，或接收本次专用新建空目录；以 `-L` 拒绝目标/祖先符号链接与悬空链接、拒绝任何已有内容，拒绝时零写；已在纯临时 fixture 验证：正常布置 3 文件+sha256、非空拒绝零写、普通/悬空 symlink 目标拒绝、symlink 祖先拒绝、macOS `/var` 拼写拒收而 `/private/var` 拼写可用）；`expected-flow.md`（九步验收脚本：预览→两块稳定编号→查看零写→完整清单→人类实际批准→执行→字节核对，编号以实际输出为准不预设固定号码，含负向路径；现在全部未执行，不伪造 `confirmed_at`）。

六家原生新会话加载与上述对话链分开验收、分开报告。

## 剩余阻塞

1. A1 用户创建未授权；B/C 各家启动与登录授权未给。
2. VM 路线尚无本轮可用入口证据；若选此路线，先由章教授做选型调研。
3. zcode/dsh/workbuddy CLI 形态本轮未找到（App 在）；其 CLI 是否存在待测试用户内以本地文档取证，不在本机主用户会话内尝试。
4. 对话链 expected-flow 依赖隔离环境就绪；当前无任何真实私文读取或原生启动。

本阶段不 commit/push，未改源码/既有验收/CK/规则，未无据重跑测试。

## 主审核收口

2026-11-03 16:05 UTC：已核对脚本和方案修正，准备切片通过。脚本保护针对非并发、可信临时目录布置，不宣称可抵御恶意并发替换；默认mktemp路径沿用系统临时目录，仅显式路径检查全部祖先。当前准备成果不构成原生验收。A1创建用户须先由用户明确批准，管理员认证由用户处理；GUI操作交章教授，遇不可绑定或隐私边界停止。
