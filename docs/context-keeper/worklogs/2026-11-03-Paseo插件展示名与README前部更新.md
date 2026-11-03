<!-- context-keeper: session-id=zcode-tutu-20261103-displayname -->
# Paseo插件展示名与README前部更新

- **目标与背景：** 主 Agent（巴克队长）转达用户授权，在 release/next-version-preparation 工作区（HEAD d29b36c8）做下一版本前的最小配置/文档修改：Paseo 插件展示名改 Memory Sharing & Fusion，指令 memSharing、内部 id 与协议不变；README 前部简洁写明六家支持并提及可作为 Paseo 插件安装。任务中途追加用户明确要求：删除 README 与插件用户侧介绍（OVERVIEW）中「当前实证平台为 macOS，其他平台尚未验证」这类平台实证/未验提示，不反向宣称全平台已验证，不改 AGENTS 项目规则或历史验收证据。
- **操作与方法：** 只改 3 个文件。① `plugins/paseo/paseo-plugin.json`：`name`（英）与 `translations.zh-CN.name` 由 memSharing 系名称改为 "Memory Sharing & Fusion"（zh-CN 原为「memSharing 公共记忆」，按用户指定串统一，未自造中文译名）；`id: memsharing`、两语 description、package.json `memsharing-paseo-plugin` 均不动。② `README.md` 头部在副标语后新增一行「支持 Codex、Claude Code、WorkBuddy、DeepSeek Harness（`dsh`）、ZCode 和 OpenCode v2 六家，也可作为 Paseo 插件安装。」（与既有 79 行详述同措辞，不重复长段、不写安装方法）；安装节删除「当前实证平台为 macOS，其他平台尚未验证；」，保留 INSTALL.md 链接句。③ `plugins/paseo/OVERVIEW.md`：H1 标题同步为新展示名（正文未重写）；使用条件段删「目前面向 macOS，」与英文 "Requires macOS"；文末删除中英两段「已验证本机 macOS…仍待验证 / remain unverified」。
- **指令核对结论：** 插件侧命令中心条目与屏幕标题均为 "memSharing"（camelCase，`index.client.tsx` 未改动），与用户「指令仍 memSharing」一致；但技能侧原技术指令为 `/mem-sharing`（SKILL.md `name: mem-sharing`），与用户口头 "memSharing" 不同——按授权保留原技术协议，未做全局替换。zh-CN 展示名采用用户指定英文串未保留「公共记忆」后缀，属判断项。
- **观察与当时判断：** git diff --check 通过；paseo-plugin.json JSON 解析通过，id=memsharing 未变、name=Memory Sharing & Fusion；README 与 OVERVIEW 中 macOS/尚未验证/remain unverified 关键词 grep 计数均为 0；最终 diff 为 3 文件 +8/-10。OVERVIEW 删除「Requires macOS」与中文「目前面向 macOS」对应用户「这类平台实证/未验提示」的范围判断，中英对称同删；删除后文案不宣称任何平台验证状态。
- **后续与证据：** 展示名改动未在真实 Paseo 宿主重新加载验证（本轮授权不含安装/发行）；平台提示删除未扫 INSTALL.md、docs/ 等其他文件（用户限定不扩大扫描）。不升级版本、不提交推送、不网页操作。证据：`git diff`（工作区未提交）、`plugins/paseo/index.client.tsx` 命令注册现状。

## 追加记录 2026-11-03 13:32:26 +08:00

- **目标与背景：** 用户追加明确修改：README 六家列举改为表格（列 Agent / 原有用户记忆入口 / 原有项目记忆入口），表底简洁汇总接入后用户记忆与项目记忆如何统一；Paseo 插件保留简短一句；避免别处重复六家长列举。
- **操作与方法：** 以 `scripts/agents.json`（darwin 平台六家的 `user_entry`/`project_rule_entry`/`project_bridge_entry`）并核对 `agm_core/paths.py`（`RULE_MODES = native/import_agents/user_convention`）确认路径与桥接语义，WorkBuddy 项目入口取自 `project_bridge_entry` = `{project}/.workbuddy/memory/MEMORY.md`（未猜测）。README 三处最小编辑：①头部一行替换为六行表格+表底汇总（含「不是各家记忆体系完整清单」非穷尽声明、「公共用户记忆共用一份、独有内容原生保留」「项目记忆以根 `AGENTS.md` 为唯一共享来源、原生读取或引用/桥接接入」）+「也可作为 Paseo 插件安装。」一句；②原 79 行六家长列举改为「支持上表六家。」；③原 81 行三家用户入口路径列举改为「原生读取项目 `AGENTS.md`，用户入口见上表」。
- **观察与当时判断：** git diff --check 通过；Claude 项目入口按 agents.json `project_rule_entry` 为 `CLAUDE.md`（import_agents 引用），表格「原有项目记忆入口」列展示各家原生项目文件、接入方式由表底「引用/桥接」覆盖，与源码语义一致。
- **后续与证据：** 保留此前展示名与平台提示删除改动；CK 体积提醒（约 25KB）按指令不自行压缩、不阻塞。证据：`git diff README.md`、`scripts/agents.json` L6-85、`scripts/agm_core/paths.py` L41-48。

## 追加记录 2026-11-03 13:35:21 +08:00

- **目标与背景：** 用户进一步调整：六家表格抽象为「工作原理」章节紧放「安装」下，原「三种记忆」并入，更新导航锚点；用户经主 Agent 调用 /clawpower-image（GPT Image 2.5 Flare）生成工作原理配图。
- **操作与方法：** ①头部六家表格与表底文字整体移出，导航锚点 [三种记忆]→[工作原理]；②原「三种记忆」章节原位升为「## ⚙️ 工作原理」，开场句 + 三种记忆表 + 六家表 + 表底汇总（含 Paseo 插件一句并入）+ 原「跟着人走/仓库走」段保留；③收到主 Agent 验收过的真实图路径后，先 `file`/`ls` 核实（PNG 1752×897、1,581,733 字节、`docs/assets/` 新目录未跟踪），在开场句后以相对路径嵌入 Markdown 图片并写 alt 描述（六家读写汇聚两统一体、独有原位保留、CK 可选独立）。
- **观察与当时判断：** git diff --check 通过；章节顺序核为 为什么需要→安装→工作原理→使用菜单→你可能想知道→用户记忆中枢→设计理念；`三种记忆` 锚点在 README/llms.txt/INSTALL 中无残留引用；图引用路径 `docs/assets/memory-sharing-workflow.png` 与实际文件一致，未占位未虚构。SendMessage 直达主 Agent 失败（无活动本地任务），架构确认与配图标签建议随本轮交付文本回传。
- **后续与证据：** 图来源：GPT Image 2.5 Flare，生成 82.458 秒，主 Agent 目视验收可用后发来路径；真实渲染效果（GitHub 页面）未验。交付后停止，不 commit/push。证据：`git diff README.md`、`git status --short`（docs/assets/ 未跟踪）。

## 追加记录 2026-11-03 13:36:55 +08:00

- **目标与背景：** 主 Agent 核对 README 与图后整体认可，仅两处收尾调整。
- **操作与方法：** ①汇总段末「；也可作为 Paseo 插件安装」移出，改在安装章节作独立句「也可作为 Paseo 插件安装，插件名称为 Memory Sharing & Fusion。」（不写安装步骤）；②图 alt「两个统一体」改「两个共享来源」。
- **观察与当时判断：** git diff --check 通过；README L41 独立句、L52 alt、L69 汇总段末无 Paseo 挂靠，三处定位核对一致。
- **后续与证据：** 任务按主 Agent 指示完成即回报并停止，不新增测试、不 commit/push。证据：`git diff --check`、`grep -n "Paseo 插件安装\|共享来源" README.md`。

## 追加记录 2026-11-03 13:39:46 +08:00

- **目标与背景：** 用户纠正：manifest 原 zh-CN description「通过 Paseo 接入共享记忆和项目规则，预览并确认机器与项目变更。」没有产品价值，要求精确替换为用户完整文案；英文用主 Agent 建议句。
- **操作与方法：** 仅改 `plugins/paseo/paseo-plugin.json` 两语 description 字段（逐字使用给定文案，未改写）；README/OVERVIEW/package/ID/name/指令均未动，不提交推送。
- **观察与当时判断：** JSON 解析通过；id=memsharing、name=Memory Sharing & Fusion（两语）、icon 与 paseo>=0.13.2 不变；git diff --check 通过；diff 精确为两 description 行（叠加此前 name 改动共 4 行变更）。
- **后续与证据：** 真实宿主商店/列表描述展示未验。交付后停止。证据：`git diff plugins/paseo/paseo-plugin.json`。

## 追加记录 2026-11-03 13:42:03 +08:00

- **目标与背景：** 用户新增要求：README 与 OVERVIEW 均加「卸载后可以原样还原，之前的公共记忆不会丢失」语义；主 Agent 给准确落地文案并限定边界（不承诺安装前逐字回滚、不把仅删 Paseo 插件当完整卸载）。
- **操作与方法：** 定点核对 `docs/uninstall-design.md`（memory_return=native-direct-v1：公共记忆原文直接合并归还六家原生文件、独有正文/CK 协议/字节保全，非逐字回滚），确认文案与合同一致。①README FAQ「怎样卸载？」行插入还原句（保留原「不能把 disabled 当全卸载」提醒）；②OVERVIEW「文件和数据」章末尾新增中英对应两段。
- **观察与当时判断：** git diff --check 通过；两文件文案逐字采用落地建议；英文自译 "goes back to its original way of using memory… nothing is lost"，未用 "restore to pre-install state" 类逐字回滚表述；未把移除插件等同完整卸载。
- **后续与证据：** 不跑测试、不真实卸载、不网页；保留全部未提交改动，不 commit/push。交付后停止。证据：`git diff README.md plugins/paseo/OVERVIEW.md`、`docs/uninstall-design.md` L1-14。

## 追加记录 2026-11-03 13:47:08 +08:00

- **目标与背景：** 用户指出 README 末尾「### 直接说“卸载 memSharing”」独立段太突兀，要求去掉独立标题、把自然语言入口并入「使用菜单」整机卸载说明；FAQ 保留归还/不丢失结果、避免重复长段；合同链接与关键语义（同一路由、预览批准、不误删项目）保留，技术细节不堆门面。
- **操作与方法：** 三处最小编辑：①使用菜单「整机卸载」bullet 并入自然语言入口（“卸载 memSharing”同一路由）、预览批准后执行、“卸载这个项目”先澄清不删除当前项目、disabled 不算、合同链接；②FAQ「怎样卸载？」行精简为入口一句+归还/不丢失结果句，去掉与使用菜单重复的 Paseo 移除细节；③删除 README 末尾独立标题及其后两段（自然语言路由细节段与 migrate-policy/宿主义务技术段），「了解更多」后合同链接行保留并把「自然语言触发」纳入链接说明。
- **观察与当时判断：** git diff --check 通过；README 结尾现在为「了解更多」+ 合同链接行，无悬空标题；被删技术段的关键事实（宿主义务、migrate-policy、CK 独立征询）均在 docs/uninstall-design.md 与 SKILL.md 有权威承载，门面只留链接。
- **后续与证据：** 不改其他产品文件，未 commit/push，既有改动全部保留。交付后停止。证据：`grep -n "卸载 memSharing\|整机卸载\|uninstall-design" README.md`（L87/94/116/155）、`tail -6 README.md`。

## 追加记录 2026-11-03 13:49:19 +08:00

- **目标与背景：** 用户指出使用菜单后两大段太长、普通用户看不懂，要求精确删除「支持上表六家。机器安装、再次安装及升级…」与「`AGENTS.md` 是共享项目记忆基座…」两段，替换为一句「安装时会识别并接入你已安装的受支持 Agent；以后换工具，也可以随时添加。」
- **操作与方法：** 两段整体删除、逐字替换为用户指定句；被删段中的 installed/unknown/absent/--agent、迁移/桥接、OpenCode CLI/App 校验、pending 等实现与验收细节未换说法回流 README，由 docs/operations.md、SKILL.md、INSTALL.md 等现有文档承载；「添加新的 Agent」bullet 与 FAQ 行中既有 installed 表述属其它内容，按指令保留。
- **观察与当时判断：** git diff --check 通过；替换句位于使用菜单 bullet 列表与「想要项目经历？」段之间，上下文通顺；其余表格、工作原理、CK 可选说明及全部未提交修改保留。
- **后续与证据：** 未改技术文档、未新增长文、未 commit/push。交付后停止。证据：`sed -n '88,100p' README.md`、`grep -n "installed\|unknown\|absent\|--agent\|migrate\|CLI-only\|pending" README.md`（仅 L89/L113 既有内容）。

