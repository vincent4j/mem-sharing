# 安装幂等与公共记忆去重：首段交接

2026-11-04；worktree `verify/skill-first-runtime`，基线 `4e8c2d53`。本轮仅源码与隔离 HOME 合成验证，未提交推送、未修改真实 HOME、未修改上游 Context Keeper，原 dirty 与 CK 保持原状。计时从 03:07:31 UTC 起，首段截止 03:22:31 UTC。

## 根因与实现

- `scripts/install.py::_report` 实际调用 `user_rules_organize.continuation`。旧 `_build` 在非公共组逐来源追加 context+raw，六份相同规则产生六份公共正文，安装本身并未安装六遍。
- 旧融合器现按同组、同语境和完全相同原文字节合并正文。每个来源、位置、重复次数、公共同文 offset 写入现有 Transaction 的 `operation_metadata.share_user_memory`。新共享器也按 scope+raw 区分变体。现有 return 消费器已识别旧融合器产生的这份 metadata。
- 增量整理会精确核查已提交来源元数据与当前公共 span，复用同语境同字节正文；独有和未选内容留原处，差异不覆盖。安装批准不代替融合批准。
- 同版已有接入零写返回“已安装，已接入”，不再触发融合。新增接入提供独立增量整理预览，入口安装阶段公共 memories 文件集、字节、mtime 不变。
- Codex、Claude 各按选择安装原生 `skills/mem-sharing/SKILL.md` 薄入口，指向持久 C/SKILL.md，纳入既有 file 台账/事务、原文归属、漂移保护与全机卸载。未登记同路径 Skill 不收编覆盖。其他四家 Skill 分发未在本轮新增。
- Codex 用户受管规则块只保留公共路径读取提示；公共索引简化为读取路由；使用约定按需指向唯一 Skill/卸载合同，保留 disabled、项目范围、原文保全与 Context Keeper 边界。

## 已通过证据

- `test_m408_installer.py`：22 项，日志 `/tmp/msf-install3.log`。
- `test_memory_share.py`：16 项，日志 `/tmp/msf-share3.log`（末尾复验另见 `/tmp/msf-share-final.log`）。已修测试以明确区分同名标题下的不同语境，归还到各自正确 public span。
- `test_fusion_claude_import.py`：7 项，日志 `/tmp/msf-fusion5.log`（末尾复验另见 `/tmp/msf-fusion-final.log`）。
- `test_ck_install.py`：32 项，日志 `/tmp/msf-ck2.log`；原来“没有 skills 目录”的断言改为“没有 context-keeper Skill”，维持 CK 独立安装保护。
- 新 `test_install_idempotency_cleanup.py`：3 项，日志 `/tmp/msf-cleanup8.log`。周一仅 Codex、周二 Claude 既有私文、周三补接入，公共文件集合/字节/mtime 不变；重复 Claude 零写且无融合；六家共 12 处同文→公共一份、增量第13处复用，现有 return 消费器按各来源次数归还；无融合时双原生 Skill 全卸载→fresh install。
- `git diff --check` 通过。初次失败日志 `/tmp/msf-{fusion,share,install,cleanup}*.log` 保留，未抹去失败证据。

## 尚未闭合：不能真机卸载重装

1. **融合后完整全机卸载仍 pending。** 旧整机卸载只归还公共全文，不消费新来源次数；为防止从公共一份归还时丢失原来的多处次数，有未消费来源引用时现已 fail closed。必须把来源清单的精确归还接入同一全机卸载计划，而不是要求用户逐 Agent 卸载。
2. 独立 `memory_share` 归还不维护旧安装 V 的 Claude whole-file import 观察指纹。合成复现：精确归还成功后，整机卸载报 `Native import whole-file fingerprint drift`，保持零写。应复用融合器已有的窄 `validate_reference_rebinding`，在同一归还/卸载事务中完成观察重绑，不降低漂移保护。
3. 旧生成前缀识别测试（如 `test_uninstall_fusion_generated.py`）、全量 Python 与新增 native Skill 的完整恢复反例仍待运行/收齐；不能用上述定向通过替代。源码尚非可安装交付状态。
4. 原生目录与 frontmatter 仅静态/合成发现布局证据；真实 `/mem-sharing` slash 调用未验，没有新增模型调用。

## 后续真实落地

先补齐以上源码闭环并复验，形成可核验固定安装来源。真实机器沿当前产品全机卸载零写预览，完整展示归还、备份、删除、宿主义务后获精确批准，再卸载并全新安装该固定来源；不得覆盖安装冒充全新安装，不绕宿主/恢复门禁。本轮未执行这些真实操作。

## 恢复执行后的第二段结果（截止 03:48:26 UTC）

- 按原预算继续，真实 HOME 仅只读核对主已修改后的短索引，未写真实入口/公共记忆/CK，无 commit/push。
- 已将每来源次数归还直接纳入全机卸载同一精确预览与事务；无需先手工 return。来源与当前公共 span、原生 after 指纹/备份前缀均核验，未知或真实改写仍拒绝。
- 独立 return 在安装 V 存在时复用 `validate_reference_rebinding`，同一事务只更新 Claude reused import 的观察指纹；注册表写失败回滚与恢复失败后的独立恢复均有合成通过。
- 标题 scope 已恢复深度栈；另以标题出现序号区分同名章节，不将同级兄弟标题累计为祖先。
- 新装不生成《使用约定》及索引条目，不硬编码六条个人规则；安装前无 user-rules 文件时不用悬空 Markdown 链接。旧发行的完整 contract/usage 模板冻结作识别，不主动生成。Skill 指向持久 C。
- **自动接入裁定仍待主/用户重新确认。** 已收到暂停该项的指令。当前工作树 `public_memory_contract_text` 没有自动项目触发；SKILL/INSTALL 本段曾写入“仅明确要求接入”，尚未获最终反向修订文本；未更改 enable 执行代码，未改真实 HOME。不能把这一项当成最终验收。

本段已通过：新综合 4 项（含直接融合→全机卸载保留来源次数、双 Skill 移除→fresh install；独立 return→V 重绑→全机卸载；回滚/恢复；scope），`test_memory_share` 16 项、安装 CLI 22 项、Claude 融合 7 项、首次安装 18 项、融合恢复 4 项、整机卸载 21 项。日志 `/tmp/msf-resume-{chain4,chain5,share3,install,fusion,m404,recovery,uninstall}.log`。最后新增精确生成 wrapper 退役后综合复验见 `/tmp/msf-resume-chain6.log`。

**仍有失败，不能报告全目标完成：** `test_uninstall_fusion_generated.py` 最新 `/tmp/msf-resume-old-fusion2.log` 为 3 项中 1 通过、1 失败、1 error。一项是旧导航标签断言（新正文展开尚带生成标签）；另一项是连续三次融合后原生源前缀重建不满足，当前安全拒绝，未闭合多次融合的全机卸载。原始日志保留。全量未跑，真实 slash 调用与真机卸载重装未做。时间到即停，不以 fail-closed 充当功能完成。

## 用户审阅定稿与提交检查点（2026-11-04）

用户要求先提交、推送当前增量，再按审阅定稿继续实现。本检查点保留上述失败，不代表发行或真机重装验收通过。

最终裁定替代本报告先前“仅明确要求接入”的过渡方案：保留未登记 Git 主目录自动项目接入；disabled、非 Git、linked worktree 跳过；当前 Agent 只补自身专属项目入口，不替其他 Agent 预建。保留已有内容，不自动安装/初始化 Context Keeper。

公共 MEMORY 保留读取、记忆归属、新主题索引、自动项目接入和指向持久 Skill 的简短操作入口。所有 Agent 适用的规则/偏好/长期事实放公共目录；Agent 专属留自身，项目规则/经历留项目。六条个人规则是用户数据，不写死在产品模板。菜单与详细流程仅在 Skill，不生成《使用约定》；安装 Skill 旧回指须同步清除。主已按用户批准修改真实公共 Markdown 并外置备份，执行者此前“真实 HOME 未写”仅描述其自身实现范围。

后续继续项：同步上述合同到模板/Skill/文档及测试；闭合旧生成导航和连续三次融合后的卸载反例；验证同机增量接入、同 Agent 重复安装零写、全机卸载与 fresh 重装。未授权发布、合并 main 或真实安装/卸载。

## 检查点 309dda6b 后的续行（04:14:10–04:29:10 UTC）

本节为最新结论，替代前文已解决的待办；历史失败不删除。无 commit/push、发布、真实安装卸载、真实 HOME 或 CK 写入。

### 实现与定稿

- 连续融合卸载的原反例已修复：同秒事务名尾部 UUID 无时间顺序，原来的字符串倒序会先恢复较早事务，随后误报源漂移。现以受管事务同路径 before/after 指纹关系构造依赖，逆依赖顺序归还；存在环或源/公共字节不匹配仍停止。未按 mtime 或随机 ID 猜顺序。
- 导航残留修复仅作用于有已提交来源证据的完整生成导航行；只在 Context Keeper 保护块外展开，不把自定义近似行认作产品归属。
- 公共模板恢复用户最终审阅稿的读取、保存归属、主题索引、自动接入、当前 Agent 专属入口、CK 独立及持久 Skill 路由。无 user-rules 时无悬空 Markdown 链接；六条个人规则不写入模板。新装不生成《使用约定》。SKILL/INSTALL 的“仅明确请求接入”过渡句已移除，README/架构/操作手册统一菜单只在 Skill。固定历史转换和旧模板精确认识保留，不据此改真实文件。
- 新增完整故事 fixture：Codex 已共享→新 Claude 自带用户正文→只补入口且公共文件集/字节/mtime不变→单独批准增量，同文复用、新文一份、专属保留→重复安装零写且不再融合→统一卸载两 Skill 并按来源归还。

### 本段定向证据

- 原 `test_uninstall_fusion_generated` 三项全部通过：`/tmp/msf-cont-fusion-generated.log`。
- 新综合五项全部通过：`/tmp/msf-cont-new-agent.log`。
- 用户入口 33、CLI 106、检测 40、桌面适配 10 项分别通过：`/tmp/msf-cont-entry-target3.log`、`/tmp/msf-cont-cli-fixed.log`、`/tmp/msf-cont-detect-fixed.log`、`/tmp/msf-cont-desktop-fixed3.log`。
- 集成定向：安装 CLI 5、发行 CLI 2、外置恢复 1（六个真实子进程中断恢复子场景）全部通过：`/tmp/msf-cont-installer-cli-fixed.log`、`/tmp/msf-cont-release-cli-fixed.log`、`/tmp/msf-cont-process-fixed.log`。
- 以上是分别定向结果，不拼成全量通过。真实 slash 发现/调用、原生新会话、真机卸载重装仍未做。

### 旧预期与断言改动证据

| 旧测试及证据 | 旧预期为何过时 | 实际断言差异与保留的保护 |
| --- | --- | --- |
| `test_cli` 两项允许路径；基线旧断言独立回放 `/tmp/msf-cont-cli-old-assertions.log` | 新批准合同增加 Codex/Claude 原生 Skill 受管文件 | 两条规则路径→精确四条规则+Skill 路径，不放宽到任意用户路径；修改后 106 项通过。 |
| `test_m405_detect.SignalTableTests.test_allowed_user_paths_contain_entries_only`；`/tmp/msf-cont-detect-target.log` | Claude 允许写集也须包含自己的原生 Skill | 精确单规则文件→规则文件与唯一 Skill 文件两条，保留其余检测强信号/漂移断言。 |
| `test_m405_user_entries` 原三失败；`/tmp/msf-cont-entry-target.log` | 已批准原生 Skill 分发，旧“没有 skills 目录”与纯规则对象数不再成立 | Codex/Claude 的精确对象集合加入 `#native-skill`；已有无关 Skill 的每个文件字节、mtime仍全等，新增集合只能是 `mem-sharing` 目录和其中 SKILL.md。 |
| `test_desktop_adapters`；`/tmp/msf-cont-desktop-fixed.log` | 移除说明后 CODEX_FALLBACK 为空；ZCode 入口也不再含 AGENTS.md 说明文字，旧 replace 实际没修改字节 | 禁止出现 Codex 说明改为非空历史说明字串；漂移注入改为把真实受管 MEMORY.md 路径改成 BROKEN.md，并明确 `assertNotEqual(original, mutated)`。仍要求失败且完整快照零写，未删除漂移反例。 |
| `test_m408_installer_cli`；完整 integration trace | 重复已接入者是真 no-op，不能再要批准 | rc=5/嵌套 noop 计划→rc=0、approval_required=false、plan=null、changes=[]、fusion=null，第二次重复仍核对全快照不变。 |
| `test_plugin_release_cli`；完整 integration trace | 重复安装不得再次触发融合 | fusion 非空→null；保留 active source 身份、零写和 source drift 拒绝。 |
| `test_uninstall_process` 六个子场景；完整 integration trace | detach 多了两个 Skill，不能把它们误算成六家私文 | 按 native_identities 精确选六家私文，另外断言两个 Skill 均计划删除；仍验证进程退出、外置独立恢复、真实锁拒绝、第三态私文漂移零写，以及 resume/restore 后完整快照。 |

### 完整测试轮次边界

04:17:27 启动的完整 integration 已终态：65 tests / 8 failure assertions，原始日志 `/tmp/msf-cont-integration-full.log`，未改称全绿。修正后的三套集成定向结果单列于上方。

同次完整 unit 日志 `/tmp/msf-cont-unit-full.log`，交回前仍在运行，已有 7 个 F 标记；这些标记与上述独立复现的旧断言相符，但未终态时不能把顺序映射当作该轮原始 traceback，也不能给出全量终态计数。源码/测试在完整测试运行期间有修改，因此本轮不是最终冻结快照验证。旧失败日志、定向复现 trace 与当前 diff 全部保留；仍须冻结后完整复验，不能把各次局部通过拼成全绿。

续行停测终态：04:28:31 UTC 为遵守 04:29:10 硬截止，向本轮唯一完整 unit runner PID 30249 发送 SIGINT；执行会话已返回 exit 130。该完整 unit 未完成，无 unittest terminal summary；后段已出现更多 F/E，因此前述“7F 与已复现旧断言相符”仅是中途定位，**不能据此断言全轮只剩这些旧预期**。全部进度、警告和中断 traceback 留在 `/tmp/msf-cont-unit-full.log`；仍需冻结后完整重跑并逐项收原始 trace。完整 integration 已终态、相关定向均已终态；不遗留测试继续运行，不自动续期。

## 最后窗口冻结验证终态（04:29:50–04:44:50 UTC）

本节是最终有效结果，替代此前未终态的判断；不更改历史日志。

- 先冻结并即时输出 traceback：50 个唯一测试复现 3 failure / 10 error assertions，`/tmp/msf-last-diagnostic.log` 与 `/tmp/msf-diagnostic-before-fixes.json`；修正历史夹具目录、持久 Skill 路由预期后，第二冻结轮 50 tests / 2 failure assertions、0 error，`/tmp/msf-last-diagnostic2.log`。两轮前后哈希均相同，诊断与修改分开。
- 实际实现缺陷：旧 `_standalone_memory` 只按旧行级规则退役说明，未识别新的完整常驻合同，导致独立副本残留持久 Skill 指令。现复用完整已知模板的 `strip_generated`，保留未知/自定义内容，并加入实际已发行完整使用约定的精确认识。旧/新模板、原始备份、六家私文、未知改写拒绝均在自然语言卸载套件验证。
- OpenCode 也保留漂移反例：改为确实存在的受管 MEMORY.md 路径变异，明确断言变异前后字节不同，再要求失败且整机快照零写。历史 fixture 显式建立 topics 目录模拟旧版本，不恢复新安装生成指南。保存/停用语义断言改为当前常驻合同，仍检查停用跳过和专属内容保护。
- 额外 public_layout 诊断在尝试 SIGINT 后未立刻退出；修改发生前未正确确认终止，已明确作废，不作为冻结通过证据。随后 TERM 终止并确认 exit 143，未删除其耗时用例。该日志 `/tmp/msf-public-layout-diagnostic.log` 保留；最后有效验证重新从修复后快照开始，未再修改源码/测试。

**最终有效快照 SHA-256：`28a8cb2c1f72619138c225b502889180418e36eaa903ef9b47933fdee00a2745`。** 两个最终 runner 从此相同快照开始，源码/测试与相关产品文档前后逐文件哈希相同；验收报告不属于实现快照。

| 最终验证 | 实跑唯一 ID | 结果 | 日志与逐文件清单 |
| --- | ---: | --- | --- |
| 受影响 unit，18 个套件模式 | 373 | 全部通过，0 failure / 0 error | `/tmp/msf-final-affected-unit.log`、`/tmp/msf-final-affected-unit.json` |
| 完整 integration | 65 | 全部通过，0 failure / 0 error | `/tmp/msf-final-integration.log`、`/tmp/msf-final-integration.json` |

唯一 ID 与 testsRun、unique_collected 已核对全等；此前 50 项诊断/复验和其他定向次数不叠加。最终快照的 unit 全集发现 972 个执行入口、去重 969 个 ID，其中实跑 373，未跑 **596**；未删除、跳过或把耗时测试计作通过。精确已跑/未跑 ID 与同快照核对结果在 `/tmp/msf-final-coverage.json`，全集发现记录 `/tmp/msf-final-unit-all-ids.json`。

完整旧轮 integration 65/8 和旧 unit 中断结果不被覆盖；本段给出的是修复后的独立冻结验证。实现与受影响合成回归已闭合；完整 unit 的 596 个唯一 ID 仍待验证，故不宣称完整 unit 全绿。真实 slash 运行、原生新会话、真实 HOME 卸载重装、发行发布仍未做。没有修改真实 HOME、CK、版本号；没有 commit/push。两组最终测试均已终态，无继续后台测试。
