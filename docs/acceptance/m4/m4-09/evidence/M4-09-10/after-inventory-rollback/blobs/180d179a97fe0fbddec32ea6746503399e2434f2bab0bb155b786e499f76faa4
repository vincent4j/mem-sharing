# CK 装机尾步实施交接

本轮对应 decisions-m4 §17—§26、上游只读核验及 B05。未运行真实 CK 安装器，未修改上游或真实 HOME；全部执行测试使用临时合成 HOME、合成 Git 源和合成 CK 安装器。未提交或推送。

## 交付接口

- `scripts/agm_core/ck_install.py`：独立预览、精确批准、执行、读回及装机尾步。
- `scripts/install.py --context-keeper [--ck-source /absolute/durable/context-keeper] [--operation-id <已完成主操作>] [--approval-file <独立批准>]`：独立路由。与普通安装、acquire、recover 互斥；不接受主安装封皮冒充 CK 同意。
- 首次调用返回 `command=install-context-keeper` 的 `approval_plan` 和退出码 5。精确批准须在该计划上补真实 `confirmed_at`、`reference`，然后重新执行同一路由。`--ck-source` 未给出时，只解析既存 CK Skill 别名；没有唯一来源则给出可操作诊断，不猜本机绝对路径，不自动下载。
- 生产参考 pin 固定为 `695074ee4b6ddb9999be858093f833d6377bd641`。CLI 不提供绕过 pin、持久路径检查或来源校验的参数；测试明确替换这两处边界以使用临时合成 Git 源。

## 同意与范围

主安装 completed 后，非 TTY 只返回 `context_keeper.status=skipped`，不会读取输入或运行 CK。TTY 先报用户记忆中枢和台账中全部已接入执行器，再显示含“与本产品出自同一作者”的固定正向问句及 CK 预览摘要。仅真正读到换行同意；EOF、空格、`n`、`yes` 均不等于回车。缺来源时仍显示正向问句；回车后报告 unavailable 和独立 CLI 下一步，保留已完成主产品。

封皮绑定：实际已提交主操作的 `product.last_operation_id`、主台账 SHA、确定路径且严格解析为 committed 的主安装／升级日志及其 SHA、已完成安装状态、当前产品代码身份、台账中全部接入者、独立 CK 来源真实路径及完整 commit、每个 tracked 文件的工作树与 HEAD blob 字节及权限、真实 Python 解释器路径与指纹、精确 argv、Skill/规则文件及父链前指纹、CK 预览返回值和独立日志路径。同版 noop 绑定此前实际提交的主操作，不把新请求的操作号冒充已提交身份。

只传实际接入者的 `--codex`／`--claude`／`--workbuddy`，不传 `--all`、`--project`、init 或 ensure。argv 使用固定解释器、`-I -B`，cwd 固定为已核验 CK 源。CK 必须处于独立持久 checkout；C、R、产品版本库存、bootstrap 及系统临时目录均拒绝。

## 写入与失败边界

批准前预览零写入。执行前先只读重建计划，再在机器写锁内重建；CK 预览后和写入前再次核对来源、解释器及目标。独立日志位于 `R/var/ck-install-<主操作>.json`，权限 600，经临时文件、文件 fsync、原子替换及父目录 fsync 写入执行意图。日志只持久化指纹、批准与结果；用户规则原文仅留在内存用于读回，不另存入日志。

执行成功需完整验证 user scope、显式 `project=null`、安装／规则路径清单、全部执行器名称、链接实际目标、CK 标记与块外原字节、memSharing 受管单元，以及台账和来源没有变化。Claude 用户级公共源 import 行按其原始合同验证；CK 追加正文不会被误判为对整文件取得所有权。

`rc=0, approval_required=true` 仍是 approval_required，绝不报告 configured。非布尔 approval_required、缺 project 等结果字段、非 JSON、非零、超时、范围不符或读回失败均不能成功；已启动写入的结果不明为 unknown。已有同主操作日志立即停止，不自动重放或换新操作号；日志供人工检查，不提供 CK 自动恢复／回滚。CK 失败不调用主产品 rollback，主报告保持 completed 并独立报告 CK 状态。

configured 仅说明合成测试中的安装与文件读回符合合同，`runtime_acceptance=pending`。真实上游执行、真实 HOME 和各执行器新会话均 pending；不能用文件存在替代运行时证据。

## 定向验证

- `python3 -B -m unittest discover -s tests/unit -p test_ck_install.py`：29 例，覆盖精确封皮、三家全名单、父链／来源／台账／解释器漂移、隐藏 tracked 改动、生产持久路径拒绝、并发锁、同意边界、缺源问句、块外字节、pending、缺字段、非布尔、非 JSON、非零、超时、结果不明及主产品保留。
- `python3 -B -m unittest discover -s tests/unit -p test_m408_installer.py`：19 例通过。旧 schema1 升级成功断言按 §26 改为严格拒绝、原字节保全；其余批准、恢复、身份、场景与字节保护用例保留。
- `python3 -B -m unittest discover -s tests/integration -p test_m408_installer_cli.py`：5 例通过，新增独立 CK 冷进程预览／批准／读回和互斥路由。测试专用 shim 替换 pin 与临时路径限制，生产 CLI 无此开关。
- `python3 -B -m unittest discover -s tests/unit -p test_cli.py`：106 例通过，封皮断言采用 follow_ck／disabled，remove 绑定台账 SHA，退役 provider/store 字段保持拒绝。

全量数字与逐项 B01—B08 核销由主 Agent 的最终验收报告汇总。源码已经冻结；本交接不更新 DESIGN、决策单、公开操作文档或 CK 上游。

## 独立复审修补：机器操作未收尾时停止 CK

首次全量绿色不覆盖全部状态门禁。复审实证 `product.installation_status=complete` 可以与升级待恢复标记、尚未 committed 的主日志同时存在：主产品在 V 写入后仍有激活回执等收尾步骤。最初 CK 入口只验证活动账与代码，确实可绕过这两类未收尾状态；本轮已补上同一只读入口的拒绝条件。

- `_scene` 复用 `layout.from_request` 的 `machine_upgrade_pending` 门禁，普通标记及 dangling symlink 一律拒绝；预览前存在或批准后新增都不调用 CK、不建独立日志、不改文件。
- 操作号复用既有 `migrate._op`；只检查当前 `last_operation_id` 的确定路径 `HOME/.mem-sharing-install-<op>/journal.json`。日志必须存在，并由既有安装／升级 `_load_journal` 严格只读解析为 committed，且 runtime 和 operation_id 匹配。running、outputs_verified、recovery_required、异操作、缺失或畸形日志都拒绝。
- 主日志指纹与升级标记“应当缺失”加入独立封皮 observations，预览后和真正调用 CK 前再次核对；不新增迁移、恢复或状态重建框架。同版 noop 继续绑定此前实际提交的主操作。
- 独立 CLI 异常按 `command=install-context-keeper` 报告独立 failed／unavailable，避免把 CK 来源或门禁错误误标为主安装失败；主产品 completed 的尾步报告语义不变。

修补后的定向结果：CK 单元 29 例、安装器单元 19 例、安装器集成 5 例。最终全量由主 Agent 在源码和测试冻结后统一重跑。
