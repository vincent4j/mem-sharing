# DeepSeek Harness 与 ZCode 桌面原生入口合同

核对日期：2026-10-31。范围为本机应用包的只读静态源码、Info.plist 与 codesign 身份输出。未联网、未启动应用或新会话、未读取账号凭据或聊天记录、未修改真实 HOME。本文证明候选入口的静态读取逻辑，不证明当前运行进程已加载，也不证明桌面新会话验收通过。

## 适配合同

| 字段 | DeepSeek Harness | ZCode |
| --- | --- | --- |
| 建议 Agent ID | `dsh` | `zcode` |
| `user_entry` | `{home}/.dsh/AGENTS.md` | `{home}/.zcode/AGENTS.md` |
| `project_rule_entry` | `{project}/AGENTS.md` | `{project}/AGENTS.md` |
| `project_bridge_entry` | `{project}/AGENTS.md` | `{project}/AGENTS.md` |
| `rule_mode` | `native` | `native` |
| 项目 Skill 默认根 | `.dsh/skills`、`.agents/skills`（项目根） | `.zcode/skills`、`.agents/skills`（cwd 至 Git 根） |
| 用户 Skill 默认根 | `~/.dsh/skills`、`~/.agents/skills` | `~/.zcode/skills`、`~/.agents/skills` |
| `runtime_status` | `pending` | `pending` |

这里的 `native` 沿用现有 Codex 枚举。两家均无需为了引用公共项目规则而新建一份隐藏目录项目规则。Skill 默认根可供发现，不表示 memSharing 应创建或复制 Skill 投影。

## 产品身份

| 字段 | DeepSeek Harness | ZCode |
| --- | --- | --- |
| 应用位置 | `/Applications/DeepSeek Harness.app` | `/Applications/ZCode.app` |
| `CFBundleName` | `DeepSeek Harness` | `ZCode` |
| `CFBundleDisplayName` | `DeepSeek Harness` | `ZCode` |
| `CFBundleIdentifier` / codesign Identifier | `com.deepseek.dsh` | `dev.zcode.app` |
| `CFBundleShortVersionString` | `0.2.1-rc.5` | `3.16.3` |
| `CFBundleVersion` | `0.2.1-rc.5` | `3.16.3.8992` |
| 签名 TeamIdentifier | `NAN929V4UM` | `8A5X4JJ39T` |
| 签名发行主体 | Hangzhou DeepSeek Artificial Intelligence Co., Ltd | Beijing Knowledge Atlas Technology Joint Stock Company Limited |

身份来源为各包 `Contents/Info.plist` 和 `codesign -dv --verbose=2 <app>`。这次只显示签名元数据，没有执行完整签名有效性验证，不把元数据输出升级为真实性验收。

## DeepSeek Harness 静态证据

下列内部路径均位于 `/Applications/DeepSeek Harness.app/Contents/Resources/app.asar`；行号以包内文件解码后的文本计算。

- `dsh/node_modules/@deepseek-ai/dsh-home-paths/lib/index.js`：`defaultDshHome`、`defaultAgentsHome`、`resolveRoot`、`resolveDshHome`、`resolveAgentsHome` 定义默认 `.dsh` 与 `.agents`。优先级为显式配置 > 非空环境变量 > 默认目录。对应环境变量为 `DSH_HOME`、`DSH_AGENTS_HOME`；空白变量按未设置处理，支持 `~` 展开。
- `dsh/node_modules/@deepseek-ai/dsh-agent-instructions/lib/index.js:646` 的 `discoverInstructionFiles` 先枚举两个用户全局根的 `AGENTS.md`，再从项目根到 cwd 枚举各目录候选；`:674` 同时遍历普通和 local 候选。默认普通候选为 `AGENTS.md`、`CLAUDE.md`，local 候选为 `AGENTS.local.md`、`CLAUDE.local.md`。因此不是只加载遇到的第一份项目文件。
- 同文件 `:1188` 说明首次请求前准备 baseline；`:1406` 注册 `agent/pre-step`，通过 `compose` 计算指令并写入请求消息。读取依赖文件系统 provider；provider 缺失时不会据此加载。
- `dsh/node_modules/@deepseek-ai/dsh-skill-filesystem/lib/index.js:149` 的 `roots` 枚举项目 `.dsh/skills`、`.agents/skills`、`customSkillDirs`、用户两根以及可选 bundled 根。默认 `includeDefaultRoots=true`。`:766` 的 `nodeEntryKind` 对 symlink 调用 `stat`，支持跟随目录/文件链接；读取还会使用 `realpath`。这是静态实现证据，未实测桌面链接加载。
- `dsh/node_modules/@deepseek-ai/dsh-base/cordis.patch.yml:303` 注册 agent-instructions；`:311` 注册 skill-filesystem。需同时查看 web 层：`dsh-web-app/cordis.patch.yml` 禁用了基础全局 agent-instructions/skill-filesystem，由 preset 接管；`dsh-web-app/presets/cordis.patch.yml:18`、`:122` 为 `cordis` coding preset 重新注册对应插件。不能据此承诺任意自定义 preset 都加载相同入口。
- `lib/main.js:79` 的 `resolveDesktopPaths` 使用 `resolveDshHome()`，桌面 profile 位于 `<dshHome>/profiles/desktop`；桌面自身路径与共享数据根分开。该文件还携带 web 产品 bundle 集合和桌面 host package 声明。

## ZCode 静态证据

主要读取器是 `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`。该文件压缩，以下为解码后的字符偏移和函数名，升级后须重新定位，不能把偏移当作跨版本稳定接口。

- 偏移约 `2208400–2213300`：`resolveUserInstructions`（`uks`）、`findInstructionFile`（`hks`）、`findDefaultUserInstructionFile`（`gks`）、`resolveUserHomeDir`（`_ks`）、`NodeContextSourceAdapter`。默认 `priorityFiles=["AGENTS.md"]`，用户文件为 `(HOME || USERPROFILE || homedir())/.zcode/AGENTS.md`；项目从 cwd 向上到最近 `.git` 根寻找首个 `AGENTS.md`。`mergeInstructionSources` 合并用户和项目内容，用户在前；单文件默认上限 100 KiB。没有项目文件时仍可加载用户文件。
- 偏移约 `13207508`：运行时初始化调用 `contextSourcePort.resolveContextSources`，将配置的 `userInstructions` 传入；偏移约 `14195891` 的运行时组装填入 `userInstructions:{...S, workingDirectory:...}`。读取链不是仅靠 onboarding 文案推断。
- 偏移约 `4257195–4258800`：`resolveDefaultSkillRoots`（`aao`）、`resolveProjectSkillDirectories`（`EKs`）、`skillRootsForBase`（`gyn`）。用户根为 `homedir()` 下 `.zcode/skills`、`.agents/skills`，项目根从 cwd 向上到 Git 根逐层枚举；另外支持额外目录、显式 roots 和内部 `homeDirectory` option。
- 偏移约 `4258800–4260400`：`scanSkillFilesUnderRoot`（`dao`）及同步版本，`followSymbolicLinks` 默认 true；根、子目录和 `SKILL.md` 通过 `stat` 检查，静态支持链接。
- `/Applications/ZCode.app/Contents/Resources/app.asar` 内 `out/host/index.js` 偏移约 `1477926` 的 `getUserZcodeAgentsFilePath` 同样返回 `homedir()/.zcode/AGENTS.md`；该处主要服务 Claude 用户文件迁移，只作为交叉核对，不代替实际读取器证据。`package.json` 明确 `@zcode/desktop`、`productName=ZCode`。
- `/init` 提示中提到项目 `.zcode/AGENTS.md`、`.agents/AGENTS.md` 是已有隐藏候选提醒；上述默认读取器仅按 `priorityFiles=[AGENTS.md]` 搜索目录根。不能据 `/init` 文案把隐藏文件认作默认项目读取入口。

## 默认根支持与环境覆盖边界

此次 memSharing 合同只支持表中的默认用户根。接入规划自动检查 `DSH_HOME`，按上游规则解析后与默认用户根比对；非默认根拒绝默认入口接入，错误不回传变量值。`DSH_AGENTS_HOME` 影响共享 Skill 根，目前没有自动检测或路径比较，不能据安装结果宣称默认共享 Skill 目录已被客户端发现；它不影响默认 `DSH_HOME` 下有效的用户规则入口接入。显式插件 home 配置也会覆盖环境变量，未读真实用户配置，本次不证明它未设置。

本次仅以布尔值检查当前 Agent 进程的 `DSH_HOME`、`DSH_AGENTS_HOME`、`ZCODE_HOME`，均未设置；未输出变量值。此检查不能证明 Finder 或其他启动器启动的桌面进程环境相同。

ZCode 上述用户规则读取器不使用 `ZCODE_HOME`，该名字在本次 `zcode.cjs` 中唯一命中属于遥测路径；`ZCODE_STORAGE_DIR` 另用于产品存储，不足以推断规则根跟随它。规则读取器本身使用 `HOME` / `USERPROFILE`，Skill 使用 `homedir()` 或内部 option，二者不能无条件视为同一个覆盖合同。当前桌面进程的实际配置和环境未验证。

## 后续验收

1. 合成 HOME：明确选择新增 Agent，验证探测、安装、检查、撤销、迁移读者扫描与白名单；保留旧默认 Agent 行为，不能以默认三家枚举漏掉显式新 Agent。
2. 真机安装：需主 Agent 按授权另行执行，核对实际写入位置、默认根约束与公共入口。
3. 桌面新会话：使用目标桌面产品原生新会话证明用户规则、项目规则和 Skill 发现分别生效。DSH 需注明实际 preset；不以 CLI、ACP 或静态源码结果代替。

上述静态合同形成后，本机0.1.3真实升级与DSH/ZCode用户入口接入已完成，原文字节保全、幂等预览通过；后续机器已更新0.1.4。桌面新会话与Skill实际加载仍pending。当前分层结果见[验收总览](index.md)，历史安装摘要可用 `git show 0906d7a:docs/acceptance/desktop-adapters/runtime/verification.md` 取回。

## 主 Agent 检测器补验

2026-10-31，主 Agent 用现有 `detect._check_app_bundle` 读取以上应用，设置 `require_bundle_version=true`、`require_signature_identifier_match=true` 并调用原生只读 `codesign --verify` 后，两者均返回 `verified`。该检查仍未启动桌面端或模型请求。可执行文件 SHA-256 分别为：

- DeepSeek Harness：`b7ca6fc3356ebdb4daa79827e6433c4c1a9cdd2196014a693ee873bae54d9949`。
- ZCode：`7be4230fdbd1467f9e0cb4a872d0dec88224f64e98e10a7a5ba407c05b7c5951`。
