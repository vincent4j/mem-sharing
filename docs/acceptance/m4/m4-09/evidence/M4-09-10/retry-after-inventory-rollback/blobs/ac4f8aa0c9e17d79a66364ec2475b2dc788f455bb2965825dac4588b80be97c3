# CK 集成重构实施交接

2026-10-30。实现与合成环境验证完成，等待主 Agent 验收；不据此宣布 M4-09 冻结或 M4-10 真机通过。

开工代码基线为 `dc0b38f6d3281bdceacbe2c4a06932ced9714621`，工作区干净。期间其他主线工作提交了仅文档的 `40cc1442aa99d30e38a34df0ef3143e0506f9ce0`；本任务保留该提交，没有 commit、push 或暂存改动。最终代码 diff 以该 HEAD 为父，与开工代码基线一致。

## 实现与接口

- 活动台账显式使用 schema=3，项目政策仅 `follow_ck`／`disabled`；provider、store、授权字段和四态退出项目合同。v1/v2 仅严格只读诊断，保留原值，所有旧开发版迁移及 journal 回放拒绝。P 白名单、扩路径、旧 product_id 规范化和旧投影注销／恢复分支删除。
- `enable-memory` 不读取或运行 CK 源码、安装器、probe、init、ensure，也不创建 CK 库或项目 Skill。AGENTS 只有位置／入口／职责三行项目经历协议；旧 CK 块的 created／reused 处置列入原字节、指纹、所有权均绑定的精确计划，漂移整单零写。
- 缺省不预建或补写 Claude 项目入口；本次显式 `--agent claude` 才接入，保留已有正文，仅补 `@AGENTS.md`。未登记引用是等待实际使用，已登记引用缺失或漂移仍报错。WB 须存在真实原生目录才补 AGENTS 指针，不创建该目录。
- `--no-memory` 写 disabled 并保留 CK 安装和全部记录数据；缺省不翻转，解除须显式 `--memory` 和精确批准。`remove-memory` 撤受管入口、写 disabled，并留下本地停用保护；用户正文、原生目录和数据保留。remove 的 `next_action` 为精确 JSON 封皮，绑定原台账 SHA，模块层也校验证据，不能绕过 CLI 缺证据写入。
- check 只观察项目规则入口、身份及字节证据；未装 CK、无记录库、主动停用、WB 尚未产生原生目录均不作为 CK 健康缺口。用户级条款已区分默认规则启用与 CK 首次保存，菜单为六行短路由。
- 新增 `agm_core/ck_install.py`。主安装 completed 后，TTY 先显示实际已接入名单的简报，再显示含“与本产品出自同一作者”的正向问句；仅真正换行同意，EOF／非 TTY／空格均不算。独立封皮为 `command=install-context-keeper`，不预填未来同意。
- 独立入口：`scripts/install.py --context-keeper [--ck-source /absolute/durable/context-keeper] [--operation-id <已完成主操作>] [--approval-file <独立批准>]`，与普通安装、acquire、recover 互斥。缺独立批准先返回具体计划；仅传全部实际接入者的开关，不用 `--all`／`--project`／init／ensure。
- 封皮绑定主 operation、严格 committed 的主日志及指纹、台账、全部接入者、CK 完整 pin／受执行内容、解释器、精确 argv、目标及父链前指纹。升级待恢复标记或未完成／缺失／异操作主日志均拒绝。独立意图日志权限 600，文件和目录 fsync；结果不明不重放。CK 失败保留主产品 completed，独立报告状态，不调用主产品回滚。

详细接口和保护映射分别见 [项目侧交接](project-side-handoff.md)、[安装尾步交接](ck-installer.md)、[机器合同交接](machine-contract.md)。

## 最终验证

全部写入测试使用合成 HOME、执行器及 Git 源；未执行真实 CK 安装器，没有改真实 HOME 或 CK 上游。

| 检查 | 最终结果 | 原始证据 |
|---|---|---|
| `python3 -m unittest discover -s tests/unit` | 441 通过，unittest 139.626 秒，墙钟 139.854 秒 | [日志](unit.log)、[元数据](unit-result.json) |
| `python3 -m unittest discover -s tests/integration` | 69 通过，墙钟 174.193 秒 | [日志](integration.log)、[元数据](integration-result.json) |
| 测试期间源码 | 两套开始指纹相同，结束后均未变化，当前源码仍一致 | [最终核验](verification.json) |
| Python 3.9 语法 | 23 个 Python 文件全部通过 | [最终核验](verification.json)；实际全量运行于 Python 3.14，未执行 Python 3.9 运行时 |
| diff／写集 | whitespace 检查通过；锁定公开文档及 AGENTS 与开工基线相同；无暂存改动 | [最终核验](verification.json) |
| CK 上游 | HEAD 仍为 `695074ee4b6ddb9999be858093f833d6377bd641`，工作树干净 | [最终核验](verification.json) |

单元基线 446→441（净减 5），集成基线 72→69（净减 3）。变化来自 provider／四态／旧迁移合同退役与新政策、尾步、审查负例增加，逐文件方法数见 [计数映射](test-counts.json)。原 19 项通用升级回归保留并补至 23 项；锁、批准、身份、回滚、固定恢复工具、第三态停止和用户字节保护没有随 P 专用链删除。真实 Git 用例使用合成 T0→T1 冻结发行对，不能视为已发布正式发行或真实宿主验收。

定向证据包含项目侧原 128 项、B04 修复相关 97 项、CK 尾步最终 29 项、安装器单元 19 项、安装器集成 5 项，以及机器／CLI／生命周期套件；具体命令、范围和时间见上述三份分工交接。最终全量数字优先于较早分工快照。

## 独立审查与修正

初次稳定树全量为 432 单元／68 集成通过，仍被审查发现两个测试漏项。原始结果保留为 `pre-b04-*`，不当作最终版本通过证据。

1. B04：缺省目标集因检测到 Claude 安装便预建 CLAUDE。已限定显式项目接入；新增缺省无文件、已有正文、旧块作用域和冷 CLI 负例。独立复现确认缺省不创建、已有字节及 mtime 不变，已登记引用漂移仍拒绝。
2. B05：CK 独立路由在主产品升级待恢复时仍可写规则。已复用恢复标记门禁，并要求确定路径的主日志严格 committed，绑定身份和指纹。独立复现确认计划前及批准后新增标记均拒绝，合成 HOME 完全不变且不建立 CK 日志；补充未完成、缺失、异操作主日志负例。

机器侧独立只读审查未发现阻断，另复验 5 项旧账／旧恢复／降 schema／身份负例。两项修正完成后才运行本页最终全量，未以初次绿色测试替代审查。

## B01—B08 核销交接

| 编号 | 实施结果与证据边界 |
|---|---|
| B01 | schema=3 落地；旧账严格诊断、旧写入和回放拒绝；不提供开发版转换或逆 schema。registry／migration／upgrade／布局测试覆盖，待主 Agent 验收。 |
| B02 | 继承改名基线的 O/R 分离，真实 v0 两目录导入和源字节保全回归继续通过；没有执行本机真实 v0。 |
| B03 | 生成条款不默认建 CK 库，disabled 不自动恢复；`test_m405_user_entries.py` 与项目启用测试覆盖。锁定文档中的旧文留后续文档轮。 |
| B04 | 缺省 Claude 预建漏项已修；显式项目接入与 WB 原生目录前提覆盖，独立复核关闭原缺陷。真实客户端实际调用链仍待验。 |
| B05 | 独立路由、同意、封皮、主完成态、恢复门禁、失败分层均落地；29 项 CK 单元及冷 CLI 集成覆盖，独立复核关闭原缺陷。 |
| B06 | 新短协议、Claude 引用、WB 指针及旧块显式转换落地；漂移零写、原字节、所有权和事务出处回归覆盖。 |
| B07 | remove 撤入口且持久 disabled；no-memory 保留入口并禁止自动经历；memory 精确批准解除。三种语义及数据／安装保留分别覆盖。 |
| B08 | 本轮实现测试已补齐 §24／§26 与审查负例；正式 M4-09 案例矩阵、公开操作说明及最终冻结由巴克队长／主 Agent 后续文档轮核销，本轮不改其锁定文件。 |

此表交接实施证据，不代替主 Agent 的放行裁定。T/D 文档项和 M4-10 仍按主线分工处理。

## 已知边界

- 遗留项目级 CK Skill 别名全部保留，CK 后续 ensure 可能再次重建全文块。本轮不改 CK 上游、不加额外硬门禁，不承诺始终只有三行协议，留用户后续裁定。
- CK 不读取 memSharing 的 disabled。停用由 Agent 遵守优先项目规则，不能声称 CK 脚本有硬拒写接口；手动 CK 操作仍按用户明确请求与其自身门禁处理。
- CK 来源须是既存、干净、固定 pin 的独立持久 checkout；可从唯一用户级别名发现或显式提供。本轮不自动下载。缺源时独立报告 unavailable 和下一步，主产品保持成功；CK 自身回滚不由 memSharing 提供，结果不明日志禁止自动重放。
- configured 仅为安装和字节读回；真实 HOME 首装、执行器新会话、disabled 行为遵守、三家四会话经历接力及正式发行身份冻结均未执行。本轮不作运行时／发布验收结论。

## Diff 与计时

[实现 diff](implementation.diff) 含 36 个已跟踪代码／测试文件及 2 个新增文件；不含交接文档自身。SHA-256：`6553ff8540130ed5ac46a8188ec8cf73050274d4e0b2ee92d52badb01f120224`。详见 [实现清单](implementation.json)。

可核验墙钟窗口为 15:06:02—15:33:34.952 UTC，共 27 分 32.952 秒；首次计时点前的规则读取与预读未计时，不伪报精确总时长。

| 阶段 | 墙钟窗口 | 用时与交叠 |
|---|---|---|
| 实施、定向验证与写集冻结 | 15:06:02—15:20:28 | 约 14 分 26 秒，三个分工并行 |
| 初次稳定树全量 | 15:20:28—15:23:30 | 约 3 分 2 秒，独立审查同时进行 |
| 审查修复与定向复验 | 15:23:30—15:29:43 | 约 6 分 13 秒，两项漏项修复 |
| 最终全量 | 15:29:43—15:32:37 | 约 2 分 54 秒，单元／集成并行 |
| 指纹、写集与证据核对 | 15:32:37—15:33:34.952 | 约 58 秒；本交接排版与消息发送另计 |

测试、配置、客户端读取与真实经历接力分别留证；本轮只交付已实现代码及合成验证结果，等待主 Agent 验收。

## 验收轮修复(主 Agent,2026-10-30)

独立复跑在本机(真实装有 WorkBuddy.app)暴露 1 项集成失败:`test_context_keeper_route_is_independent_and_uses_synthetic_pinned_source` 断言 `connected=['codex']` 实得 `['codex','workbuddy']`。根因不是产品 bug,是测试密闭性缺陷:CLI 层此前无探测输入注入口,`detect` 回落到系统 `/Applications`,宿主机真实安装的执行器泄露进 connected(执行者沙箱无该 App 故全绿)。

修复两处(主 Agent 执行,原执行者会话已关闭):
1. `scripts/install.py` `INPUT_KEYS` 纳入 `search_paths`/`app_directories`/`user_candidates`——显式探测输入经 `--request-file` 注入并随批准封皮回放,冷 CLI 测试与 M4-09/M4-10-A 演练从此可在装有真实执行器的机器上确定性运行;
2. 该集成测试首步预览传 `{"app_directories":[]}`,探测范围收窄到受控 PATH。

修后本机单测定向绿;全量复跑见 verdict。
