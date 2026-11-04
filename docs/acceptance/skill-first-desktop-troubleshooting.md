# WorkBuddy、DeepSeek Harness 与 ZCode 运行验收排障

日期：2026-11-04  
状态：CLI 排障未完成；三家都没有完整的运行时读取证据。GUI 不再是本轮验收前置条件。

## 范围与边界

用户在 2026-11-04 将路线改为允许通过各产品 CLI 验收，并批准当前用户下启动只读新会话。第二段窗口为 01:23:22–01:38:22 UTC。禁止读取旧会话正文、回显规则内容或凭据、修改真实记忆/配置、安装、切付费方案、切换更贵模型、提交或推送。仓库写集仅本文档；本轮未运行测试。

CUA 在前段的绑定尝试超时后，本段按用户指示没有再调用。原生 CLI 测试按产品自己的入口区分，不把 Paseo 子 Agent 回答当成目标 CLI 证据。

## WorkBuddy

入口取证：

- App 包内 CLI 包装器 `.../cli/bin/codebuddy` 和 `.../cli/bin/codebuddy-lowmem` 均因缺少相邻 `../dist/codebuddy` 返回 `MODULE_NOT_FOUND`。
- 直接 App 内可执行 bundle `node /Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/dist/codebuddy-lite-wb.mjs --help` 返回 0；帮助确认其支持 `--print`、`--output-format stream-json`、`--permission-mode plan` 与工具限制。
- 单次获准的补跑使用新 CLI 会话、计划模式和仅开放 `Read` 的工具集。脱敏命令形状：

```text
node <App>/Contents/Resources/app.asar.unpacked/cli/dist/codebuddy-lite-wb.mjs \
  --print --output-format stream-json --permission-mode plan \
  --tools Read --max-turns 3 <只读验收任务>
```

退出码 0，耗时 2.62 秒。事件顶层类型为 `system`、`assistant`、`result`。检查 bundle 中的转换逻辑确认：`assistant.message.content[]` 承载内容块，函数调用映射为 `{type:"tool_use", name, input}`；最终结果事件使用 `{type:"result", result:...}`。本次脱敏提取没有发现任何 `tool_use`，也没有解析出有效最终 JSON，因此不能证明 `Read` 实际运行。自动规则路径、自动 Skill 可用性、显式读取源码均 pending；exit 0 不等于读取验收通过。

脱敏回执（保留供复核，不含完整 stdout/工具结果）：

`/var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/skill-first-cli-20261104-k1mv2t4t/workbuddy-sanitized.json`

## DeepSeek Harness

本机 App 的 `dsh` headless CLI 与 Paseo 配置都可用，但两者的默认模型配置不同：

- Paseo 的 `dsh-pi` provider 状态为 available，实际命令指向 `/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh`；其模型目录列出 `clawpower/deepseek-flash`，对应 provider `clawpower` / model `deepseek-flash`。
- 原生 `dsh --profile headless --json <只读任务>` 建立了新 headless session 后退出 1，错误码为 `MISSING_CREDENTIAL`，路由指向 `deepseek-official`。
- 有界只读检查发现 headless patch 只有 `@deepseek-ai/dsh-llm-deepseek`，没有 ClawPower provider；web profile patch 则定义了 ClawPower 的 provider 路由、`deepseek-flash` 模型和环境变量名 `CLAWPOWER_API_KEY`。只核对了变量名与路由字段，没有读取凭据值。

因此这次错误只证明 headless 默认 profile 未配置当前可用路由，不能推出本机没有可用凭据或 Paseo 的 `dsh-pi` 不可用。本段没有改写 patch，也没有再发模型请求；Paseo `dsh-pi` 路由与原生 DSH headless 的 Skill/规则读取机制分开记录，二者没有相互冒充。

## ZCode

- App 内命令 `node /Applications/ZCode.app/Contents/Resources/glm/zcode.cjs --help` 返回 0，报告 CLI 版本 0.17.1，支持 `--prompt`、`--mode plan`、`--cwd`、`--json` 和 `skills list`。
- `zcode skills list` 返回 0，共列出 111 项；列表中没有精确名为 `mem-sharing` 或 `skill-first-runtime` 的 Skill。此结论仅针对该命令当前列出的本地技能，不外推为其他目录或自动上下文都没有。
- Paseo `zcode` provider 状态为 available；模型目录列出 `builtin:bigmodel-coding-plan\GLM-5.3` 与 `GLM-5.3-Flash`。配置 `/Users/vincent4j/.paseo/config.json` 对该 provider 只记录 enabled 状态及非凭据环境变量名，没有 launch command；`command -v zcode-acp-server` 未找到入口，但已在 Paseo 插件 checkout 发现 `node_modules/zcode-acp-server/dist/cli.js`，并找到 Paseo 生成的私有启动 shim：`/Users/vincent4j/.paseo/plugin-launch/paseo-plugin-zcode/2b4214a50ae6/zcode-acp-server`（权限 0700）。shim 设置 `ZCODE_BIN` 为 App 内 `zcode.cjs` 并导入该 bridge。没有读取或输出凭据。未创建 Paseo 子 Agent。
- 直接以 App 内 `zcode.cjs --prompt ... --mode plan --cwd <repo> --json` 运行在模型执行前失败：启动器无法定位内置 provider 配置。App 实际配置位于 `/Applications/ZCode.app/Contents/Resources/config/provider/zcode-builtin.json`，而直接脚本报告的候选路径位于 `Contents/Resources/glm/...`。
- 曾有一次临时目录入口路径适配尝试；命令返回 1、stdout 为空、stderr 为 65,631 字节。完整 stderr 没有保留，当前不能可靠给出最终异常类型/行号；本段不再重试或继续猜测路径。临时路径适配没有修改 App 或仓库，也未取得模型/工具调用证据。虽然随后确认了 Paseo 实际 ACP 启动 shim，本段没有向它发送 ACP 初始化/新会话请求，因此 ZCode 真实模型会话仍未运行。

## 分层验收结论

| 产品 | 真实新 CLI 会话 | 自动规则 / Skill | 工具读取证据 | 显式读取当前项目 `SKILL.md` |
|---|---|---|---|---|
| WorkBuddy | CLI 进程返回 0 | 未证实 | 未发现 `tool_use` | 未证实 |
| DeepSeek Harness | headless session 初始化后因默认 provider 缺凭据失败 | 未执行模型验证 | 无 | 无 |
| ZCode | `--prompt` 在 provider 配置解析前失败 | 本地 Skill 列表可用；其中无目标 Skill 名 | 无 | 无 |

本轮没有一家通过“实际读取并给出可核验文件路径/工具调用”的验收。ZCode 的下一步是用该 shim 作为 ACP stdio 命令，按插件使用的 ACP 协议初始化并创建一个只读新会话；shim/bridge 路径现已查实，但本段未执行协议请求。WorkBuddy 需要另行修复/确认 stream-json 响应内容解析，不能将空工具调用列表当成 Read。DSH 的具体阻塞是 headless profile 默认 `deepseek-official` 路由缺少对应凭据配置；Paseo `dsh-pi` 使用 ClawPower 的模型路由，二者机制不同。
