# M4-08 代码交接（供主 Agent 独立验收）

基线 `fe1f832`，开工工作区干净。只写 `scripts/install.py`、`scripts/agm_core/user_install.py`、`scripts/agm.py`、两个新测试文件及本目录。README/SKILL/INSTALL.md/llms.txt 与 M4-09 文件为并行工作，未修改。未改旧测试断言、未 commit/push，未运行真实 HOME 的项目命令。

## 实现

- 新 `scripts/install.py`：机器级独立 CLI，不依赖 cwd 项目身份；先 `inspect_machine`，fresh/legacy_copy 调 `user_install`，升级/同版/M2-schema1 调 `upgrade`（M2 组合迁移复用 `migrate`），升级后的显式接入调 `user_entries.run_user_entries`。不增加第四个项目命令。
- 外层独立机器 schema1 批准封皮，完整包含内核计划、来源/完整 commit/文件清单、R/C/V、op、三版本、scene 总指纹、请求/有效执行器、精确 changes、元数据范围、reference_map、v0 身份。无批准零写规划；执行重新生成现场计划并逐字段比较，未知字段/漂移/HOME 改向/伪占位确认均拒绝。内部照用各内核自己的批准 schema，不混台账 schema2。
- 来源分两层：本地 clean Git checkout 只读核对 HEAD、所有 dirty 状态及受管清单；显式 verified source JSON 复用 `_source` 核验。非官方来源只记 `local-checkout:file://...`，不会将任意本地源谎记为官方，也不输出可能含凭据的任意 remote URL。官方来源获取是单独 `--acquire` 计划，获批才创建批准的 staging、写 acquisition.json intent、clone no-checkout、checkout 完整 SHA、核验清单；不 pull/reset、不运行下载代码。失败保留 staging/journal 并报 partial。取得源码仍 `installation_complete=false`，需再安装预览/批准。
- 后装 Agent 新裁定：同版/升级若用户未显式 `--agent`，不调用用户入口装配，不生成自动新增接入计划或提示。事实报告不驱动接入。显式 `--agent` 走代码 noop + 精确 entry 子计划；absent/unknown 仍先停。新首装默认只 installed 过滤。
- 最终报告：layout、三版本、来源、op/journal、metadata_scopes、connected/absent/unknown/unselected、v0 copies/code_copies/exclusions、显式项目根命令、runtime pending/connection_pending。新装代码已落位而接入失败报 partial + recovery_required，升级 V 已完成而后续接入失败也报 partial，不误称全部 ready。未传 `--project` 时命令含明确占位根并标 `project_root_required=true`，不将安装 cwd 当项目。
- `user_install.py`：新索引头 L0 恒读→需时 L1→不足 L2，索引行有主题名、当前结论和链接；首装在既有 Markdown 类型内生成使用约定主题，开头 L1 简列有效结论与待办。v0 只改新索引模板及对应批准 manifest 指纹，原文字节与镜像链接不改，不自动摘要。
- `agm.py`：仅未安装时 next_action 指向 INSTALL.md/scripts/install.py；三命令的状态、批准门与内核行为不改，不检测/提示后来新装执行器。

## 实际 CLI 参数面

| 模式 | 参数与约束 |
|---|---|
| 本地 checkout 预览 | `python3 -B /verified/source/scripts/install.py --source /absolute/clean-checkout --commit <full-sha> --version <SemVer>`；source 缺省本脚本所在 checkout；commit 缺省只读 HEAD 后固定；version 必填 |
| 清单源预览 | `--source-manifest /absolute/source.json`，JSON 恰为 `root/url/commit/version/files`；与 source/commit/version 或 request-file 内 source 二选一 |
| 发行/迁移输入 | `--request-file /absolute/request.json`；仅允许 source、conversions、legacy_registries、legacy_source_commits、evidence_files、legacy_identity；转换表精确格式沿 M4-07 内核（普通发行降级 API 不在本 CLI 参数面；崩溃回滚用独立 recover 模式） |
| 选择/报告 | `--operation-id <op>`；可重复 `--agent codex|claude|workbuddy`（重复同名拒绝）；`--project /absolute/actual-project` 仅用于结果示例，不写项目 |
| 执行 | `--approval-file /absolute/approval.json`；内容=整份 `approval_plan` 加真实 ISO 时区 confirmed_at 和 reference。可仅给批准文件，从封皮还原请求，仍按当前 HOME/配置/来源/现场重验；也可重复原参数，必须仍与原批准相同 |
| 独立恢复 | `--recover /absolute/journal.json --action continue|rollback` 先预览；加 `--approval-file` 执行；接受 install/upgrade/migrate journal，不混普通来源/选择/获取/项目参数。提交后恢复只收尾规则沿内核 |
| 单独获取 | `--acquire --staging /absolute/absent-stage --commit <full-sha> --version <SemVer>` 只出计划；加对应 approval-file 执行（或仅给该获取批准文件）。官方 URL 固定，不浮动 HEAD，不自动安装系统依赖 |
| 帮助 | `--help`，无持久写入；未知、重复单值及缩写参数拒绝 |

缺 Git/Python≥3.9 只说明手动步骤，不装系统依赖；Python 本身无法启动时仍由外层 Agent/用户先诊断。生产支持仍 macOS。获取与安装的批准文件不是用户确认本身，只承载已获真实授权。

## 验证与边界

全量 **426 单元 + 70 集成 = 496**，两个命令退出码均 0；新增 **18 单元 + 4 冷 CLI 集成**，无旧测试更改。最终参数/报告收敛后另重跑新增套件通过。同版代码 noop 的 recovery 为 null，不指向未创建 journal；用户入口事务证据仍记在 V。原始输出见 `unit.log`、`integration.log`、`targeted-unit.log`、`targeted-integration.log`，命令/退出码见 `commands.txt`。

关键映射：

- `test_blank_home_non_git_cwd_preview_apply_and_report` / 集成 `test_non_git_blank_environment_full_workflow_and_same_release`：空 HOME、非 Git cwd、精确批准、完整 R/C/V 报告、当前代码可执行、同版无 mtime/字节变化。
- `test_later_agent_requires_named_request_same_version_add_path`：后装不自动接入，显式命名经 detect 才接入。
- `test_schema1_routes_through_upgrade_migration_and_code_placement`：旧账走升级组合，旧写者 tombstone、授权证据保留、恢复材料路径等于获批迁移映射。
- `test_upgrade_cli_composition_and_partial_entries_failure` / `test_entry_failure_after_code_copy_is_partial_with_recovery`：升级后接入失败与首装代码落位后接入失败均 partial，保留恢复位置。
- `test_fresh_l0_l1_l2_templates_no_sidecars` / v0 字节回归：模板分层，不新增类型/自动摘要，v0 原文不变。
- `test_recovery_independent_preview_apply`：冷 CLI 恢复预览与批准执行；混模式/未知字段/无真实确认/相对批准路径拒绝。
- 集成 `test_acquisition_is_separate_approved_and_pinned_using_local_git_transport`：固定 commit clone→独立零写安装计划→批准安装；仅本地 Git transport，不是远程 GitHub 可达性证据。
- 集成 `test_three_project_commands_missing_product_guide_only_no_implicit_install`：三命令引导、无隐式机器写入；help/错误输入不建缓存。

未验收：真实远程网络取得、真实用户 HOME/v0、三执行器新会话读取、真实项目接力，以及并行文档最终一致性；这些仍由主 Agent 后续独立判定，不以本次合成夹具替代。

## v1.11 调整轮(skills/mcp 出局落地,基线 f179b9b;主 Agent 裁定 A 转换处理器)

本节由突突兔在 M4-08 调整轮追加。写集:`user_entries.py`、`user_install.py`、`install.py`、`agents.json`、`paths.py`、`legacy_import.py`(v0 复制收窄的唯一实现位置,不在点名清单亦不在禁改清单)、`upgrade.py`(仅裁定 A 授权的最小改动)及受影响测试。禁改文件(detect.py、user_rules_organize.py、README/SKILL/INSTALL/llms.txt/docs 正文)零触碰。

### 落地(裁定依据 decisions-m4 §14/§15/§16、df680e5、f179b9b)

- **产品 Skill 投影移除**:`paths.py` 删 `user_skill_roots`/`user_skill_paths`/`PRODUCT_SKILL_NAME`,`allowed_user_paths` 回到仅用户级入口文件(表内出现该字段即拒绝);`user_entries.py` 删 `skill_projection` 及登记/预检的 skill 分支,预置投影位不再是受管对象、零触碰;`user_install.py` 场景枚举去投影观察。
- **R 结构去 skills/mcp**:首装目录收窄为 memories(+topics)/references/backups/var;`legacy_import.ROOTS` 收窄为 `('memories','references')`,v0 skills/mcp 原地不动、不进快照/阅读包,以 `preserved_in_place` 记录进排除清单;v0 原文复制语义与 manifest 指纹逻辑未改(值随模板更新)。
- **规则文本与菜单**:公共源模板(首装索引、v0 新索引、使用约定主题)与用户级入口文本(Codex 公共源块/WorkBuddy 约定块)写入治理条款(①写入纪律 ②独有内容永不并入永不删除 ③默认启用——不预创建 CLAUDE.md、旧项目三类已有文件保全文只补块、不回溯历史、项目经历从启用时刻开始记)+ 按执行器兜底条款(Claude 缺引用自建唯一路径/WorkBuddy 原生目录出现后补块/Codex 首用建骨架)+ 六项 `/agent-group` 菜单(给项目启用记忆/添加新的 Agent/健康检查/停用记忆/整理用户规则/批量启用记忆,逐项映射既有 CLI 与 `install.py --agent`);术语一律"启用/停用"。
- **装完报告**(§14.4、df680e5):删 `runtime_acceptance` 自检提示;`agents` 增 `note`(已适配执行器默认全部接入,未适配不在覆盖范围);exclusions 文案同步。

### 裁定 A:v1.11 入口合同转换处理器(upgrade.py 最小改动)

- **精确白名单** `_ENTRY_CONTRACT_WHITELIST`:绑定 `scripts/agents.json` 与 `scripts/agm_core/user_entries.py` 的精确 before/after SHA256(P=27d6e26 哈希 ↔ 本发行哈希),双向各一条(P→T 升级、T→P 显式回退);任何其他哈希组合仍按"no handler"拒绝,无通用放行条件。
- **惰性语义**:旧 machine 账中的 skill_symlink 对象在白名单升级时**注销账内登记**——磁盘符号链接原地保留(记入 entry_facts,升级期间不触碰)、不再受管、不再校验,本发行不清理磁盘链接;回退到 P 后 P 装配器把同目标链接按 reused 重新登记。保留账内记录则 T 的收窄路径表无法装载/序列化账本(registry 冻结合同),注销是实现"惰性保留"的唯一途径。
- **读侧装载辅助** `_legacy_contract_load_paths`:白名单前驱账本装载时并入前驱自身 agents.json 展开的投影位;`user_install.inspect_machine` 对"已装 C 自带 user_skill_roots"的机器同样只读并入,使真实 P 机器经 install.py 可路由到升级通道。两处均零写入,写入授权仍由白名单把关。

### 验证

全量 **446 单元 + 72 集成**全绿(exit 0;集成含本轮新增 2 个真链用例)。关键新增映射:

- 集成 `test_upgrade_makes_legacy_projection_inert_and_idempotent`:P 带投影与旧合同装机→T 升级成功、用户内容字节不变(含旧入口块原文与投影链接)、账内旧投影登记注销而磁盘链接原样、T 下入口装配零差异不再触碰投影、同版重装幂等零写入。
- 集成 `test_entry_contract_hash_outside_whitelist_still_rejected`:user_entries.py 哈希落在白名单外(转换表其余部分完全合法)仍拒绝,零写入。
- 单测:test_cli/test_m405_detect 锁定表内出现 user_skill_roots 即拒、allowed 仅入口文件;test_m405_user_entries 投影位零触碰与模板文本;test_m404_install R 无 skills/mcp、v0 skills 原地+排除清单;test_m408_installer 装完报告无自检提示、模板含条款与菜单、agents.note。

未验收项不变(真实远程取得、真实用户 HOME/v0、三执行器新会话读取、真实项目接力);本轮仍未 commit/push。
