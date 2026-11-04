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
