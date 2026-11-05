# 操作路由

本页提供命令与故障定位，不复制产品需求或安装对话。安装流程以 [INSTALL](../INSTALL.md) 为准；共享菜单、原文提案和选择即执行以 [SKILL](../SKILL.md) 为准；全机退出以[卸载合同](uninstall-design.md)为准。

命令从当前已核验的持久 C 或完整固定干净来源执行。文中的绝对路径、Agent 和 JSON 文件须替换为实际值；示例不是用户批准，不对未知来源自动执行。

## 常用命令

| 目的 | 入口与要求 |
| --- | --- |
| 首次安装/补装 Agent | `python3 -B scripts/install.py --agent <agent>`；首次按 INSTALL 提供固定来源并预览，集中批准后执行；已安装 C 的无参调用只在完整核验后复用来源 |
| 当前项目接入 | `python3 -B scripts/agm.py enable-memory --project /absolute/project --agent <当前Agent>`；已登记项目不替未实际使用的其他 Agent 预建入口 |
| 批量接入 | `python3 -B scripts/agm.py enable-memory-batch --directory /absolute/projects`；扫描不跟随目录链接，汇总计划集中批准，失败停止后续 |
| 健康检查 | `python3 -B scripts/agm.py check-memory --project /absolute/project`；检查通过不是新会话读取证据 |
| 用户记忆共享 | `python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude`；先读完整来源、写提案，再按 Skill 展示与选择 |
| 项目规则共享 | `python3 -B scripts/memory_share.py share-project-memory --project /absolute/project`；只处理本项目，既有 AGENTS 公共项排除前须明确保留去向 |
| 安装后增量整理 | `python3 -B scripts/agm.py organize-user-memory`；使用返回的两块方案，不把安装批准当作融合同意 |
| 全机卸载 | `python3 -B scripts/agm.py uninstall-machine --backup-dir /absolute/new-backup`；先只读计划，再按原完整计划批准执行 |
| 卸载后恢复 | `python3 -B /absolute/new-backup/recover.py --manifest /absolute/new-backup/manifest.json`；独立恢复不依赖已删 C，按其预览与批准办理 |

六家 Agent 名称为 `codex/claude/workbuddy/dsh/zcode/opencode`。机器安装的 `--agent` 可重复；项目接入多个 Agent 按该命令自身解析合同传入，默认自动接入仍只传当前执行者。脚本 `--help` 为当前参数真源，不从旧发行稿复制未知 flags。

## 选择与执行

先检查依赖与六家实际名单，提示“按回车开始安装”；真实回车一次执行，EOF/非交互输入保持预览。外层已收到回车时直接绑定精确计划，不重复进入 TTY。安装静默，完成只报告已安装、公共路径与接入名单。内部完整批准与锁内漂移保护保留。

融合只展示非空的“建议合并的相同规则”“需要你确认是否合并”，来源缩写为 Agent（~/原生文件），不展示内部组 ID。Agent 完整阅读后通过本次 `--equivalent-sources-file` 声明精确等价来源，才能将不同标题合为一个稳定编号；保留原 context/次数，无永久别名。用户选择即执行，查看零写。CLI 用 `--selection`、`--selection-plan-file`、`--selection-reference` 绑定此前已展示计划与真实选择；现场或编号变化停止。

完成/暂不整理之后最后询问 Context Keeper，名单取全机实际安装者，不限本次接入者。只有明确“安装”算同意；跳过、空白、EOF、非交互输入均不算。用户选择安装后实时获取官方仓库 main 最新代码，按其安装器实际支持范围执行，不传未知 flags、不修改上游；实际安装后再提醒 `/context-keeper` 的使用和首次保存流程。Context Keeper 的具体安装命令见 INSTALL，不在这里复制。

## 项目保护

默认只处理 Git 主 checkout，linked worktree、非 Git、历史 disabled 跳过。重新接入 disabled 须明确计划；该状态不代表 Context Keeper 停用。已有 AGENTS 和原生正文完整保留。Claude 仅自身实际使用时补幂等 `@AGENTS.md`；WorkBuddy 原生 memory 目录未产生时不预建。批量执行保留已完成事务，不把未开始项目报完成。

## 故障与恢复

| 状态 | 处置 |
| --- | --- |
| 来源/版本/库存不匹配 | 保留现场，提供固定干净来源重新预览；不覆盖旧 C、手填 manifest 或吞掉损坏 export |
| 未知同名文件、链接、所有权或漂移 | 零写停止，给出具体路径和最小下一步；不按关键词删私文或认领文件 |
| 安装中断 | 使用当次 journal 和 source/tools 身份匹配的安装恢复入口，不能换内核回放旧计划 |
| 融合中断 | `recover-memory-fusion --manifest ABS`（整理路由）或 `recover-memory-share --manifest ABS`（共享路由）；先核原 manifest，再按其完整恢复计划批准 |
| 卸载中断 | 按外置备份的独立 recover.py 恢复，产品资产、宿主和 Context Keeper 结果分开报告 |
| 锁/活动 journal | 核对当前进程与事务，先恢复；不自动抢锁、删未知备份或绕过迁移门禁 |

## 保留的历史兼容入口

这些仍有活跃消费者，未作为文档整理的一部分删除功能。仅在明确命中旧合同、来源完整且当前内核支持时使用，未知旧现场先诊断。

- `migrate-policy [--project ABS]`：只退役产品自有旧政策控制；不恢复 disabled，不启用 Context Keeper。
- `reconcile-legacy-import --json`：只接受受信历史 public-layout producer、完整备份与独立 Context Keeper 块证据；不接受 arbitrary baseline/adopt。
- `migrate-user-entry-layout --json`：仅重排可证明的产品入口到顶部，原私文/权限/所有权不变。
- `scripts/retire_staging.py`、`scripts/uninstall_compat.py`：固定独立工具的窄范围 staging/旧卸载处理；预览、宿主身份、完整计划和明确批准不可省略，不替换活动 C。详细旧参数及安全约束从[固定历史操作说明（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/operations.md#独立退役旧-paseo-staging未发行工具)追溯，并先核对当前工具 help。

旧 `remove-memory`、`--memory`、`--no-memory` 不再支持新请求；旧 tombstone 仅用于诊断/退出。现行能力与运行缺口见[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)。
