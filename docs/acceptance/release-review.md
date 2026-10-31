# 发布前收尾质量报告

## 当前判定：0.1.3 公共记忆分层

2026-10-31，基线 `0f690ef7aabf747a23bacc7662c19bee34c4bf52`。**限定本地代码与合成场景验收通过，当前未提交工作树不可直接发布。** 下方0.1.2段落为此前收尾历史，0.1.2已形成上述提交；其中当时“SHA尚不存在”的叙述不代表当前状态。

本次公共索引保留公共规则、读取契约与主题指针，菜单/维护细则进入使用约定，各执行器专属规则留在自身用户入口。共享AGENTS规则不依赖安装Codex，覆盖Claude-only、WorkBuddy-only与两者组合。候选版本0.1.3由CLI/source输入承载，无新增版本文件。

固定迁移只认0.1.1 `04c32e24b9ab9504514908f2368cddca4356e478`/tree `15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179`和0.1.2上述提交/tree `1fb1e199c992e07747bbf031fcb83cd74d2b85b5c9c491cda7d2836fca1dd353`；目标31文件，新添public_layout模块，使用精确 `public-memory-layout-v1` 转换，禁止沿用preserve。命令及批准见[INSTALL](../../INSTALL.md)。

巴克队长独立核对所有权、精确来源、恢复材料及备份绑定、guard持久化窗口、动态读者与权限第三态、冻结工具包、提交后只收尾等关键差异；审查发现均退回修复并核对定向证据。equal-V以完整验证的持久committed manifest为提交界，不改last_operation_id或主安装日志。未知内容/读者拒绝，不自动归并或注册；私人正文、Context Keeper块、主题尾和legacy保全。

验证事实：全单元557项为556通过/1 error，全集成74项为72通过/2失败；错误为旧WorkBuddy返回范围说明遗漏及非013 noop误派迁移。局部修复后WB全套与相邻断言11项、原2集成失败路径均通过；新增1个单元方法，未重跑最终558全量。不宣称单轮全绿。主checkout整合15文件逐项SHA一致，打包闭包2项通过。后续按用户要求同步六项菜单名称、顺序与README安装文案；模板73项及迁移/冻结82项定向通过，旧前身模板字节未改，版本仍为0.1.3，候选文件与合同hash已更新。完整证据摘要/37项对应测试及文件清单收录[清单](release-review-files.json)的 candidate_013。

实际分工：GLM完成首阶段、迁移首版和文档；GPT完成高风险审查，并在GLM额度中断后由呱唧接续修复；巴克队长裁定、独立验收与整合。未以配置变更冒称派工。

仍未执行真实HOME升级、用户记忆修改、客户端会话、Context Keeper实际激活或接力。当前已知未登记Claude公共读者会阻断真实预览，必须另行显式接入后重新预览，不是本轮暗中补齐。暂停项目保持暂停。未commit/push/tag/发布。下一步仅在明确授权后按清单白名单本地提交，取得clean SHA再复算31文件tree；真实安装与发布须另行授权。

## 以下为0.1.2收尾历史

2026-10-31；审核与裁定：巴克队长。范围为仓库源码、测试、文档和静态发行材料。基线 HEAD 为 `04c32e24b9ab9504514908f2368cddca4356e478`；本轮修改尚未提交，也没有再次部署。

## 发布判定

**当前工作树不可直接正式发布。** 本轮已完成本地代码与审查材料交付，但0.1.2候选版本、内容树和从已安装0.1.1的精确升级路径已完成本地准备；仍须用户明确授权本地提交，产生干净完整SHA。真实运行暂停项保持未验；不能称 M4 全部完成或三家完整互通验收通过。

当前已安装 0.1.1 对应旧冻结 SHA 和27文件清单。本轮候选清单为30文件；不能借用同版幂等或旧窄转换把它当作已安装状态。提交、tag、push、发布及真实验收均不属于本轮操作。

运行结果唯一当前判定见 [M4-10](m4/m4-10-runtime/verdict.md)，历史里程碑范围见 [验收总览](index.md)，未来执行规格见 [发布清单](m4/m4-10-prep/release-checklist.md)。

## 盘点与保全

清理前备份110个文件，包含原有 dirty 文档及未跟踪 runtime/日志，同时保存 Git 状态与 tracked diff。备份位于仓库外权限0700目录：

`/var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/mem-sharing-pre-release-mg24k7j2`

该目录含 `repository/`、`manifest.json`、`status.txt`、`tracked.patch`。未提交证据的恢复依赖这份实际备份，不能声称 Git 可找回。备份不打包、不自动删除。

初始文件分类：源码/路径表23，测试33，CK12，运行证据28，其他文档/配置14。本轮处置为原样保留82、修改保留25、归并删除3，另新增5个文件。逐文件处置、理由与前后哈希见 [删合留清单](release-review-files.json)。哈希比较针对本轮起点，不抹去原有未提交成果。

## 问题与修复

| 问题 | 修复与判定 |
|---|---|
| C 中安装文档链接指向未打包 DESIGN/docs | 打包增加 DESIGN、architecture、operations；7份文档内指向验收/CK的链接改为明确标注“源码仓库”的官方路径；新增真实源码清单/本地链接闭合测试 |
| 安装外层接受 `+00:00`，台账只接受 `Z` | install 与 CK 共用 registry 严格证据校验；保持批准原字节，不规范化用户已批准字符串；CK交互自产 UTC Z；拒绝偏移、无时区、非法日期 |
| 坏账 product 非对象触发 AttributeError | 类型前置检查统一报告 RegistryError；不初始化或修复坏账；补列表/字符串/数字回归 |
| CLI/源码文案引用已删 docs/plan | 指向当前架构、操作手册与 --help；历史裁定用精确 Git 路径，不机械保留错误版本/章节编号 |
| DESIGN 混合旧布局、兼容承诺与当前合同 | 整合当前设计，机制/操作分工明确；固定旧决策的 Git 追溯位置；保留正式升级、私有字节与恢复边界 |
| 验收总览把 M1/M2 写成通过 | 对照 Git `f06db31` 原始 m1-07/evidence 与 m2-08/README second-run，恢复“部分通过”；M3等未重验结果说明来源边界 |
| runtime verdict 首段与后续部署事实矛盾 | 收敛现状表及历史索引；保留尝试、失败、部署、读回与暂停事实；不把 connected 改成 runtime passed |
| 重复准备材料、过期待办与固定临时路径 | 归并发布准备规格，更新主题记忆，示例改唯一 mktemp/操作ID；历史日志不改写 |

## 删、合、留裁定

删除3份重复过程文档，均先归并到 `m4/m4-10-prep/release-checklist.md`：

- `isolated-install-checklist.md`：保留环境身份、真实隔离/合成HOME区别、五拍安装、来源与before证据、v0保全和恢复边界；删除过期“本机未做”表述与重复命令模板。
- `new-session-verification.md`：保留三家读取判据、CK首次激活、真实页面路由、四会话接力及负向门禁；删除与当前状态冲突的全 pending 表。
- `synthetic-projects.md`：保留 fresh/legacy-agents/legacy-claude/legacy-workbuddy/CK独立夹具要求及原字节证据；不保留容易被整页盲跑的重复搭建脚本。

保留全部源码与测试文件。零字节 `agm_core/__init__.py` 是包入口，`runtime_fixture.py` 是共享夹具，不能因空或没有 test 方法删除。`migrate.py` 的旧入口拒绝函数及 registry v1/v2 校验仍承担诊断、恢复和失败保护；旧官方 URL 是来源身份的精确别名，删除会影响既有来源识别。未以调用搜索无命中单独裁定删除。

保留28份运行证据：原始JSON、合成标记、日志、恢复与部署读回相互交叉引用；5份阶段性Markdown加历史说明，verdict重整，integrity按最终字节更新。已有10份CK工作日志完整保留，原始操作和当时判断不覆盖；当前主题修正写入 memory-keeper，本轮另建日志并追加。

## 源码与测试审查范围

| 模块 | 审查重点与保留理由 |
|---|---|
| install / agm | 来源、批准、CLI路由及错误报告；安装清单/时间与文档问题已修 |
| registry / layout / paths / agents.json | schema/路径白名单、所有权、产品身份、只读解析；产品类型门禁已修 |
| entries / project | 标记与引用字节、Git main身份；防止混入私有内容或linked worktree |
| enable / remove / check / batch_enable | 默认实际使用、disabled保留、显式恢复、check零写、批量逐项目事务边界 |
| transaction | before/after、台账最后提交、第三态保护与恢复；原子替换是单文件，协作锁不是OS级CAS |
| user_install / legacy_import / migrate | R/C/V与旧源分离、只读快照、journal、固定恢复工具及旧开发版拒绝；不自动清旧源 |
| user_entries / user_rules_organize | 私人/归属不明保留、完整批准、标记保护；入口模板不改，维持窄升级绑定哈希 |
| versions / upgrade | 固定发行清单、六阶段、V提交点、code-only恢复与入口partial分离；不扩大兼容或降级承诺 |
| detect / ck_install | installed与runtime分层、CK独立批准、固定来源、失败不回滚主产品；只改时间口径 |
| 33份既有测试及新增闭合/升级测试 | 对照各套件覆盖的批准/漂移/私人字节/恢复/disabled/CLI行为；具体缺口加定向回归，不以测试数证明真实运行 |

源码审查覆盖各文件职责和关键写入/异常/恢复路径，测试按套件与关键用例核对，不声称形式化证明或所有输入穷举。未改 `user_entries.py` 与 `agents.json`，两者相对清理前备份字节一致。

## 验证证据

- 改前：突突兔执行 unit474 + integration74，均exit0；日志 `/tmp/memsharing-qa-eeChep/unit.log`、`integration.log`。
- 改后：479单元 + 74集成（553总计），均exit0；命令为 `python3 -m unittest discover -s tests/unit` 与 `python3 -m unittest discover -s tests/integration`。原始日志 `/tmp/memsharing-qa-eeChep/unit-r2.log`、`integration-r2.log`，已由审核者核对测试数、OK及退出码。定向与清单证据为同目录 `targeted.log`、`manifest30.txt`；文件哈希附在逐文件清单的 verification_evidence。
- 定向覆盖：release_closure 2、m408_installer 22、ck_install 29、m402 21、m404 18、m407 23、CLI106均通过。直接模块前缀运行m404曾因既有函数内import报ModuleNotFoundError；按项目标准discover方式18项通过，未改测试入口或掩盖该跑法限制。
- 本地静态：22份Python源码通过3.9语法解析；仅为语法兼容检查，不代表实际Python3.9完整运行矩阵。
- 历史证据一致性：Codex/Claude JSON的退出码、公共/项目标记与fixture相符；保存的AGENTS哈希与fixture相符。仅验证已有材料，没有启动会话。
- 凭据模式扫描：未命中私钥、长凭据赋值或GitHub token模式；人工核对源码命中为公开官方URL/参数说明，历史路径和合成标记保留。扫描不构成无遗漏保证。
- 最终静态：158个本地文档引用，新增/修改内容零断链；19个历史缺失目标全部通过Git cat-file核实存在于f06db31。最终文案收尾后仅补跑2项文档闭合测试通过（不重跑全量）；git diff --check通过；runtime integrity的27个payload哈希已更新。
- CK：save-report通过当前会话/历史保护/主题链接检查；coverage仍返回历史缺口：12个Markdown目标断链、2份旧日志缺session-id，11份缺历史摘要为提示项（包括新日志，不是必填）。通用扫描另计入7个txt/log/jsonl目标，共19处。未把全库coverage称为全通过。

## 0.1.2 候选冻结准备（续阶段）

建议版本 **0.1.2**：本批为打包/校验/异常报告与文档修复，无入口合同或台账结构变更。产品版本由 `install.py --version` 或发行输入 `source.version` 提供，写入 V 的 `product.product_code_version` 和版本库存 `release.json` 的 `versions.product_code_version`。C 的 `.agm-code-manifest.json` 只保存 source/files；CLI 的 `SCHEMA_VERSION=1` 是输出封皮版本，不是产品版本。没有新增 VERSION 文件或把0.1.2硬写为生产代码默认值。

| 身份 | 值 |
|---|---|
| 前身版本 / schema / structure | 0.1.1 / 3 / 1 |
| 前身完整提交 | `04c32e24b9ab9504514908f2368cddca4356e478` |
| 前身27文件树 | `15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179` |
| 候选版本 / schema / structure | 0.1.2 / 3 / 1 |
| 候选30文件树 | `1fb1e199c992e07747bbf031fcb83cd74d2b85b5c9c491cda7d2836fca1dd353` |
| 候选最终 Git SHA | **尚不存在**；清单写为null，等待明确授权提交后取得 |
| 官方来源 | `https://github.com/vincent4j/mem-sharing` |

候选新增 DESIGN.md、docs/architecture.md、docs/operations.md；修改9个既有发行文件，18个原样保留，没有删除发行文件。全部30文件的mode（均0644）、SHA256、精确转换草稿与提交白名单统一位于 [清单](release-review-files.json) 的 `candidate` / `proposed_commit`；项目证据与测试不打包。内容树算法为按path排序的path/sha256/mode对象数组，经现有 `legacy_import.encoded` 规范JSON序列化后SHA256，不是Git tree ID。

前身来自只读Git ls-tree/cat-file逐文件重建，已复算匹配提供的树；两个入口合同文件与候选一致：agents.json `9a4f127be6582956544ec10b605f33635fecb63a4c0e315246fb7bf4a7a508ab`，user_entries.py `eda73b02e99d8092f6f587d786d163efd4d8bbc72340e79de0ad1ffabd25c85a`。采用现有 exact conversions 的 `direction=upgrade, entries=preserve`，不新增处理器、不放宽门禁。不指定 `--agent`，外层 `entry_plan=None`，不接入新执行器。

本阶段只新增 `tests/unit/test_release_012_upgrade.py`，未更改30文件payload。先有57项定向通过（含当时新增5项），review指出preview空断言及恢复场景不足后，由GLM补强为7项；最终与m407_upgrade/WorkBuddy合同回归共37项通过，日志 `/tmp/memsharing-qa-eeChep/release012-targeted-r2.log`。57与37有重叠，不能累加为独立用例数；未声称新增测试后又跑过全量。前轮479单元/74集成仍是同一生产源码的全量证据。

最终新增套件验证：外层精确计划和执行、preview零写、3份文档与库存装配、WB私人正文/合成CK块/Codex入口/公共记忆逐字保全、同版noop；缺失/错前身/错目标/错方向/重复conversion、批准篡改、入口合同漂移均拒绝；新增文档已写后的rollback删除3文档并逐个恢复27文件；V已提交但未finalize时rollback被拒绝，continue返回finalized_only并保持0.1.2；新文档第三态修改阻断恢复并原地保留。

合成HOME使用真实内核与实际前身/候选payload，仅执行器探测为合成事实；目标commit采用明确标注的测试值，不冒充真实发行SHA。没有真实客户端、真实HOME升级或CK尾步执行。成功发行后的主动降级不是本次中断恢复测试的承诺；其他前身、未来版本与合同变更须另行核对。

### 一次本地提交的具体建议

55个提交路径精确列于清单 `proposed_commit.paths`，包含前轮未跟踪运行证据、3份删除及本轮新增升级测试；只按白名单暂存并核对cached diff，不使用git add .。建议消息：`fix: prepare 0.1.2 candidate and close release QA gaps`。这次批准只对应本地提交，不包含push/tag/安装/发布。原HEAD仍为04c32e24，index当前无暂存。

提交后读取真实完整SHA，核对clean状态、30文件mode/hash与候选树，再按[发布清单](m4/m4-10-prep/release-checklist.md#012-候选的精确升级请求)在仓库外生成精确request。不要把最终SHA回填同一提交内的文件导致自引用；本报告中的null是有意保留的未固定事实。真实升级仍需另行授权并针对当时现场取得完整approval_plan。

续阶段开始前的111文件另备份于 `/var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/mem-sharing-candidate-before-q2h13w44`，权限0700，未覆盖首轮备份。当前冻结准备已完成，剩余确需授权的动作是上述本地提交；M4真实验收暂停与正式发布门禁不因此解除。

## 遗留与停止边界

19处旧CK日志本地引用指向前轮已从工作树移除的验收材料（M1、M2、M4-02）。本轮没有新增此缺口；按只追加规则保留日志。可将日志相对路径解析为仓库路径，再用 `git show f06db31:<仓库路径>` 追溯，不将当前文件不存在解释为原证据不存在。没有为清零统计重建一套重复历史目录。

未在线访问外链；源码仓库链接表示发布后对应位置，不证明当前远端已有未提交新报告。未做真实安装/升级、CK尾步/激活、自动入口或新会话接力。Windows/Linux、缺依赖准备、独立macOS用户/VM首装仍未验。非协作写者最终检查与替换间存在竞争窗口，不宣传为完全并发隔离。

## 实际分工

突突兔以实际 zcode / GLM-5.3 配置承担基线测试、静态清单核对、明确缺陷修复与改后测试。巴克队长（GPT）承担逐文件审查、关键裁定、文档归并、证据复核及最终质量判定；没有把整包实现转交GPT，也没有重复GLM全量测试。普通类型校验和时间/清单修复没有升级为额外GPT实现任务。
