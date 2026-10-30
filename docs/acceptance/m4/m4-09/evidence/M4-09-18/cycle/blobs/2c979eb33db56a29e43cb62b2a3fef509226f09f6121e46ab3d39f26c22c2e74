# CK 重构：机器合同与删除轮交接

依据：decisions-m4.md §24—§26；§26 取代历史开发版转换承诺。本工作不提交、不推送、不改真实 HOME 或 CK 上游。所有写入型验收均使用临时目录与合成执行器。

## 实现

- 机器安装与持久发行库存的版本向量使用 registry schema=3；安装计划与 journal 自身的格式版本独立保留，不把格式号当活动台账版本。
- 删除 P 四哈希白名单、前驱扩路径读取、旧 product_id 内存规范化、旧投影注销及反向恢复分支。正式升级继续要求精确来源和转换表；入口合同变化仍无转换处理器，拒绝写入。
- `migrate.py` 仅保留严格只读诊断、历史档案只读定位和安装/升级共用的批准、原子写入与锁工具。旧迁移规划、执行、恢复和 journal 回放统一返回 `migration_unsupported`；不借旧恢复材料恢复已撤销的迁移承诺。
- 旧 schema1/2 经显式 diagnostic API 严格读取，保留原字段、字节、模式与时间；正常活动加载拒绝。机器巡检遇旧开发账仅报告保全与重装，不能当纯 v0 首装或正式升级前驱。
- 旧安装 journal 的版本向量不为3时拒绝回放；库存 target schema 非3拒绝，正式升级不接受开发版 SemVer 前驱，不支持 schema3→schema2。

## 定向证据

- `python3 -m unittest tests.unit.test_m403_migrate tests.unit.test_m404_install tests.unit.test_m407_upgrade tests.unit.test_m407_legacy_upgrade`：51 项通过，32.265 秒。随后新增的旧安装 journal 回放拒绝、schema 降级/开发版前驱拒绝、旧 product_id 不规范化3项单独通过；锁顺序/并发阻断补强后的1项单独通过。该组最终54项。
- `python3 -m unittest tests.integration.test_m407_real_upgrade`：4 项通过，116.477 秒。冻结合成 T0/T1 Git 发行对，schema3→schema3；T1 对3个实际内核文件加入合成发行修订。覆盖6阶段 continue/rollback、每个代码文件和 manifest 替换窗口、提交后仅收尾、同版零 mtime、持久发行回退、固定恢复工具在来源不可用且安装器已替换后的恢复。它是合成正式发行合同验收，不是已发布发行或真实宿主运行时验收。
- `test_m402_layout_registry.py`：20 项通过，4.960 秒。历史共享用户对象由明确合成 reused 对象建夹具，验证 remove 仅摘消费者而保留其原字节。
- `test_m406_cli.py`：7 项通过，0.016 秒；`test_m406_cli_lifecycle.py`：3 项通过，4.472 秒。旧四态退役不再报告 CK 源缺失健康缺口；`states.entries` 仍报告规则对象事实。
- `test_m403_migrate.py` 更新历史 product_id 原值诊断后：12 项通过，0.042 秒。
- `test_m406_lifecycle.py`：20 项通过，24.747 秒。保留原用例数量，按活动政策重写断言与夹具。
- `git diff --check` 通过。仓库最终全量由主 Agent 在并行写集冻结后执行，本分工不把上述定向结果冒充全量。

## 旧回归覆盖迁移

| 旧开发版迁移验证点 | 当前保留或补充的回归 |
|---|---|
| 精确批准、批准内容漂移 | `UpgradeTests.test_exact_approval_and_source_identity_bind_before_any_write`；`MigrationTests.test_exact_approval_helper_rejects_missing_extra_and_changed_values` |
| 锁顺序、第二写者、并发入口 | `UpgradeTests.test_upgrade_holds_writer_locks_and_blocks_competing_entries`（实际锁调用顺序为安装锁→写锁→事务锁，锁内调用项目/机器入口均零写拒绝）；`MachinePreservationTests.test_enable_and_remove_hold_the_same_writer_and_transaction_locks`、`test_remove_cannot_bypass_enable_writer_lock` |
| 来源/安装身份、未知前驱与现场漂移 | `UpgradeTests.test_unknown_future_dirty_and_approval_drift_rejected_before_writes`、`test_old_code_product_identity_is_never_normalized`、`test_schema_downgrade_or_development_predecessor_is_unsupported`；`InstallTests.test_source_and_destination_drift_stop_before_bootstrap` |
| 阶段故障、continue/rollback、提交后只收尾 | `UpgradeTests.test_six_phases_before_after_continue_and_rollback`、`test_every_file_and_inventory_registry_rename_window`；`RealUpgradeTests.test_real_six_phase_faults_continue_or_rollback`、`test_each_real_code_file_replacement_window_and_registry_commit` |
| 强退、过期锁精确移交、来源不可用 | `UpgradeTests.test_hard_exit_requires_approved_stale_lock_handoff`、`test_fixed_toolkit_recovers_without_source_or_active_installer`；`RealUpgradeTests.test_recovery_runs_from_fixed_toolkit_after_installer_self_replacement` |
| 档案 hash、第三态不覆盖 | `UpgradeTests.test_third_state_bad_backup_or_after_mixed_requires_manual_recovery`、`test_bad_ledger_and_foreign_inventory_are_never_repaired` |
| 用户字节、项目元数据、独立库存回退 | `UpgradeTests.test_upgrade_preserves_user_bytes_and_separate_versions`、`test_explicit_rollback_uses_installed_inventory_and_keeps_current_metadata`；`RealUpgradeTests.test_frozen_formal_chain_upgrade_noop_and_persistent_rollback`；`MachinePreservationTests.test_machine_metadata_unchanged_through_project_enable_remove` |
| 旧材料只读和禁止回放 | `MigrationTests.test_all_migration_and_old_journal_replay_routes_refuse_zero_writes`、`test_strict_legacy_diagnostic_preserves_original_bytes_and_metadata`；`MigrationProcessTests.test_old_journal_cannot_replay_in_fresh_process`；`InstallTests.test_old_installation_plan_cannot_replay_into_schema3` |

## 数量变化

本分工涉及的机器/布局/CLI/生命周期单测：112→101（净减11）。其中旧迁移27→12（改为诊断/拒绝/保全，通用事务保护移到正式发行合同）；旧迁移升级2→1；安装17→18；正式升级19→23；布局20、CLI7、项目生命周期20不变。

本分工集成：13→8（净减5）。旧迁移写入与恢复4→1只读拒绝回放；发行链6→4，按 §26 删除2个 P 专用白名单/惰性投影用例；CLI生命周期3项保留。没有删减正式升级内核的原19项通用故障/回滚/恢复用例。

## 已知边界

本分工不修改 CK 上游；遗留项目 Skill 别名可能使 CK 自己的 ensure 重建全文块。短协议与政策约束不等于上游脚本硬门禁。真实客户端新会话、真实 HOME 安装及首次正式发行的真实版本号/来源冻结仍由后续验收和用户裁定。
