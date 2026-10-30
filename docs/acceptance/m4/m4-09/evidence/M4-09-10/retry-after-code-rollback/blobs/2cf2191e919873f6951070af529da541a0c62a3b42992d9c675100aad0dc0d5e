# knowwind 盘点与装配结果

状态：**阻断，未装配**。

- 路径 `/Users/vincent4j/Tools/Source/knowwind`；main 与本地 origin/main 比较 ahead=0、behind=0；未执行 fetch，不代表远端实时状态。
- 唯一既有 dirty 为未跟踪 `.zcode/acp/sandbox.json`，不在装配范围；保留原样，未读取或复制其内容，仅记录指纹。
- 既有 AGENTS.md、CLAUDE.md、.workbuddy、docs/context-keeper/；记录库含 memory-keeper/plans/worklogs/evolution。原 CLAUDE.md 是中文指引，尚无原生 @AGENTS.md 导入。未发现项目 .agents-group 目录。已有私有 WorkBuddy 目录只盘点路径及指纹，不复制内容。
- 初次真实 CLI 预览 rc=5；provider_source/store_path 为 null，源码未定位，尚不是完整可执行装配计划。见 preview-initial.stdout.json / stderr。
- 源码选择为本仓库已链接的真实 Git checkout `/Users/vincent4j/Tools/Source/context-keeper`，库位置指定已授权默认 docs/context-keeper/。source-selection-proposal.json 是向 CLI 提交源码定位以取得精确计划的提案，**不是完整批准文件**：尚未取得完整指纹/写集，不能用它声称已批准装配。
- 携提案运行真实 CLI 后 rc=2、status=failed、changes=[]，错误 `drift: Created unit template changed; explicit review required: /Users/vincent4j/.workbuddy/MEMORY.md`。原始输出见 preview-source.stdout.json。没有清理 registry、重写模板、补链接或手工 init。
- 原始 stdout 的 changes=[] 与本次已盘点入口/库文件 SHA-256、mtime 的前后空 diff 一致；Git 状态前后空 diff。该指纹证据限定于 inventory-before 列出的条目，不声称覆盖所有机器文件。

## 未执行与恢复条件

完整精确批准文件、装配、默认库 init、幂等重装、Codex/Claude/WorkBuddy 新会话均未执行；不能算部分通过或通过。

先审查用户级 WorkBuddy 现场与登记的模板差异，确定维护方式后重新预览；本任务未获授权擅自消除 drift。新的精确计划仍须核对范围与现场。本轮不修 CLI，也不把部分批准当完整批准。
