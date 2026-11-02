# OpenCode v2 适配验证

日期：2026-11-01。工作区：`short-wolverine`。这是未提交、未发布的源码候选，不是机器安装或新会话加载验收。

阶段补记（2026-11-02）：“未提交、未发布”指本文写作时点状态；该适配随后经 `e1a7c39` 合入主线并包含于 0.1.5 候选 R 的 Python 内核，Paseo 选择器/RPC 亦在 `daee8d6` 扩至含 OpenCode 的六家。产品至今未发布，真实机器安装、新会话读取与模型请求依旧 pending；当前整体待验范围见[上线前清单](../release-readiness.md)，下文各节结论仍按原时点阅读。

## 范围与接替

支持列表扩至 Codex、Claude Code、WorkBuddy、DeepSeek Harness、ZCode、OpenCode。机器 fresh、再次安装与 upgrade 默认接入支持清单内全部已核验 installed 的对象；显式 `--agent` 限定目标，unknown/absent 不自动写入。项目命令仍缺省旧三家，专属项目入口由实际使用驱动，disabled 不自动恢复。

突突兔实现基础适配；呱唧串行实现 V2 内存预测与单次外层批准。后续因突突兔的 ZCode API `EPIPE Cannot connect to API write EPIPE` 故障，主 Agent 授权呱唧（GPT）接管剩余测试与文档，没有重放原任务或并行写入。进度面板因宿主插件缺 `zod` 无法启动，未修复宿主。

实现与审查子 Agent 不修改真实 HOME、产品版本、Orca、daemon、上游 Context Keeper、AGENTS 或 CK 记录；项目当前记忆和日志由主 Agent 维护，既有记录保留。无提交、推送或发布。

## 入口与防护

OpenCode 用户入口为 `~/.config/opencode/AGENTS.md`，项目原生读取 `AGENTS.md`，不创建专属项目桥接或 Skill 投影。原生 Mach-O 必须通过 Apple 签名要求：identifier `opencode`、团队 `5NZ4Q7NXJ4`；无静态版本元数据则版本 unknown。父 package.json 没有 name 不阻断原生识别，原生签名失败不回退 npm 包名放行；非 Mach-O 包装入口仍核验 `@opencode/cli` 包身份。

仅支持默认配置根：`XDG_CONFIG_HOME` 和 `OPENCODE_CONFIG_DIR` 可未设、空白，或分别指向默认绝对路径 `<home>/.config`、`<home>/.config/opencode`；相对值、字面 `~`、其他根拒绝。`OPENCODE_CONFIG` 非空拒绝。重定向错误整单零写，不回显原值。该保守边界不声称支持自定义配置或桌面进程的实际环境。

历史公共布局迁移复用现有字节构建器，在内存生成 V2 快照与台账并预测新增入口计划。两个子计划封入外层摘要，一次精确批准；显式范围限制新增接入，既有公共依赖完整迁移。预测能力不从请求恢复，不接受批准进入执行。真实执行重算并比较原批准，外来编辑仍拒绝；因真实漂移产生的 partial 不算成功。

历史 SOURCE 前身合同保持冻结；仅按当前六家和 user_entries 字节重冻结 TARGET，未修改 public_layout。既有同版本不同来源的替换仍被升级门禁拒绝。未登记公共读者仍在预览时整单零写拒绝。

Context Keeper 固定 pin 仍仅支持旧三家；dsh/zcode/opencode 返回 skipped / upstream_unsupported，不传未知上游 flag；混合名单仍安装受支持对象，不声称新三家已装 CK。

## 证据分层

- `/tmp/opencode-adapter-20261101/real-detect-report.json`：接替前生成的本机只读检测报告，时间为 `2026-11-01T05:57:53Z`。codex/workbuddy/dsh/zcode/opencode 为 installed；claude 因 nvm 断链为 unknown。未修改断链或真实安装，不把这份报告当作本次新会话验收。
- `test_opencode_adapter.py`：临时 HOME / 合成二进制和签名 runner，覆盖签名身份、原生优先、包身份、配置根、私文幂等、unknown/absent、显式未装、check/remove/disabled、大文件、迁移扫描、项目不预建、整理器专属保留。
- `test_upgrade_entry_projection.py`：真实历史 0.1.1/0.1.2 内核字节 + 临时 HOME + 合成检测，覆盖单次批准迁移接入、fresh、再次安装、显式范围、篡改与真实执行漂移。
- CK 定向回归覆盖含 OpenCode 的混合和全 unsupported 名单；项目策略与安全门禁回归继续保留。

原始日志统一位于 `/tmp/opencode-adapter-20261101/`。

首轮全量：unit 612 项，10 failures / 2 errors（588.566 秒）；integration 74 项通过（235.032 秒）。`full-attempt1-source-check.json` 记录 125 个文件前后哈希一致。失败定位为旧五家测试表、旧无 Codex 默认预期、新整理测试段落夹具和发行文档链接闭包；仅修测试与文档，未削减安全断言或改生产门禁。原始失败日志 `unit-attempt1.log` 与通过日志 `integration-attempt1.log` 保留。

修复后定向：CLI 106 项、OpenCode 18 项、发行文档闭包 2 项、only 矩阵 4 项、无 Codex 矩阵 3 项通过。CK 32 项、安装器 22 项在首轮全量前已通过。最终全量在固定源码上运行：

| 套件 | 数量 | unittest 耗时 | 退出码 | 原始日志 |
| --- | ---: | ---: | ---: | --- |
| unit | 612 | 631.661 秒 | 0 | `/tmp/opencode-adapter-20261101/unit-final.log` |
| integration | 74 | 237.266 秒 | 0 | `/tmp/opencode-adapter-20261101/integration-final.log` |

`final-results.json` 记录 status=passed，运行时间为 `2026-11-01T06:23:04Z` 至 `06:33:36Z`。`final-before.json` 与 `final-after.json` 的 125 个文件哈希全部一致，source_drift 为空；测试期未改源码、测试或文档。该哈希结论仅对应原始清单内文件。测试结束仅补本验证记录的结果与职责说明，另以交付清单记录该报告变化，不把它混入测试期的零漂移结论。

交付时修正了清单生成的文件名解析问题：原测试脚本未解码 Git 对中文路径的转义，17 份中文文件名 CK 日志未进入测试前后清单（包含历史已跟踪日志及本轮主 Agent 新日志）。不补造它们的运行前哈希，不把 125 文件零漂移扩大为这些日志的哈希证据。源码、测试和发行文档完整覆盖；主 Agent 已确认两轮测试期间未写任何 CK 或工作区文件。`manifest-coverage.json` 列明遗漏路径与证据边界，最终交付清单使用 Git NUL 分隔路径，正确列出所有改动。

`contract-check.json` 确认四组历史 SOURCE 常量 AST 与 HEAD 一致，TARGET 三文件匹配：agents.json `3fd21a12f2f04c3ec95d4ad68415fd4005267ed263b1f726f70116c3b29c679e`，user_entries.py `e5421b9147c15c5075ceae011fc17f951e556502d1765575c4d2df78f9e8529d`，public_layout.py `b1ab0123bcea50884a37bb6890e0e23938c73a470577d65ae654b1936016d96f`。独立只读复核未发现剩余生产阻断；已修文档矛盾与整理器专属分类 P2。该静态复核与本节实际运行证据分别计。

最终文件清单与 SHA256 在 `/tmp/opencode-adapter-20261101/delivery-manifest.json`，逐文件列表为 `delivery-files.md`；`candidate.patch` 包含实现、测试、文档的相对 HEAD 完整补丁（含新增文件），不包含主 Agent 的 CK 记录。`delivery-validation.json` 单列测试后的报告修改；首轮失败和各次定向日志均保留。

## 仍待验收

真实机器安装、真实 OpenCode 新会话读取用户/项目规则、模型请求、非默认根、其他平台均 pending。静态签名、合成测试和本机只读检测不替代这些证据。产品版本及实际发行来源未变；本轮不声称已有同版五家安装可直接替换为此候选。


## 2026-11-01 文档收尾窄修 v1（追加）

按用户对巴克队长 P2/P3 的修复授权，仅修订 DESIGN.md、llms.txt、INSTALL.md 的现行说明，并在此追加记录；未改生产源码、测试、产品版本、真实 HOME、Orca、daemon、AGENTS、上游或 CK 记录，未提交、推送或发布。DESIGN 日期更新为 2026-11-01，文档版本仍 v2.2。

DESIGN 完整同步六家（含 OpenCode）、机器 fresh/同来源再次安装/合法 upgrade 缺省全部已核验 installed、显式 --agent 限定新增、项目缺省旧三家及专属入口按实际使用/disabled 不恢复；后装 Agent 在再次调用安装器时探测并纳入精确预览批准，不是后台发现。补 OpenCode 默认用户入口、项目原生 AGENTS、default-root-only 与环境覆盖拒绝边界，保留真实新会话 pending；CK dsh/zcode/opencode 均 upstream_unsupported。llms.txt 仍为简短地图。INSTALL 仅纠正当前公共布局目标合同表述：SOURCE 历史前身保持冻结，TARGET 三文件按当前六家字节冻结；0.1.0→0.1.1 专用历史段逐字保持，不改其 agents.json 不变合同。

本次仅运行既有 test_release_closure 两项（通过），并检查七份随包文档的旧五家、机器默认三家、后装不自动发现、禁止 --agent 残句，现行合同无命中；剩余项目三家与专用历史不变说明分别核对保留。git diff --check 通过。修前/修后 63 个生产脚本与测试文件哈希零漂移；具体证据见 closing-doc-fix-v1/document-checks.json 与 before-core-tests.json。原全量 612/74 属于上文先前候选，本次没有重跑全量，不把此次文档窄验证标成新全量通过。

新证据独立存于 /tmp/opencode-adapter-20261101/closing-doc-fix-v1/：release-closure.log、document-checks.json、before-all.json、after-all.json、closing-doc-delta.patch、delivery-manifest.json、delivery-files.md、candidate.patch 与 evidence-check.json。新完整候选补丁包含未提交实现和此次文档增量，不含 CK，文件枚举使用 Git -z；清单按实际变更计数。此版本 supersedes 原交付的文档摘要与完整候选补丁引用，原 bfb5758a682558384095cad49ec51a8e808c20f6c0578e884da2143430fa610d 补丁、delivery-manifest、final-before/after/results、首轮及最终原始日志全部原样保留。文档中的源码仓库链接用于定位，不保证未发布链接已可访问。


## 桌面检测收尾（2026-11-01，desktop-finish-v1）

用户明确当前从未发布，无需继续升级准备。本轮已移除刚启动的 0.1.5 版本声明、CLI 版本选项、安装源版本 AST 守卫与历史来源白名单；三个文件逐字恢复到能力保全 checkpoint SHA。没有新增升级 handler、历史版本 fixture 或兼容路线；既有升级模块及 SOURCE 门禁保留。此前 preserve-014-v1 的十文件能力保全及 53 项定向证据仍有效，不宣称本轮重新跑过这 53 项。

桌面检测新增 OpenCode.app 强信号，固定 CFBundleName/DisplayName=OpenCode、BundleID=ai.opencode.desktop、CFBundleExecutable=OpenCode，两个 bundle 版本须非空且一致；codesign 使用 strict/deep、Apple 锚与团队 5NZ4Q7NXJ4 的固定身份要求。CLI 与桌面安装面分别列在 surfaces 中，CLI-only 不证明桌面安装。仅一个官方原生 CLI 与一个官方 App 独立核验通过且没有失败候选时收敛为 installed；多个 CLI、多个 App、npm/收据与 App 的混合来源仍沿用冲突门禁。CLI 无静态版本证据时不填造版本。默认配置根守卫及专属项目入口按实际使用的策略不变。

沿用章教授交付的桌面 2.2.5 安装、签名与引擎静态读取合同证据，私有证据目录为 /tmp/opencode-desktop-acceptance-20261101/。本实现阶段未再次检测真实安装、操作 App/UI 或发出认证／模型请求。真实 memSharing 接入、桌面新会话规则加载及模型调用验收由用户延后统一进行，均 pending；CLI 的历史 401 不能证明桌面账号状态。

本轮固定源码定向共 88 项通过：新增桌面 10、既有安装检测 40、OpenCode 18、CLI preview 8、升级入口投影 8、发行文档闭包 2、锁内来源漂移探针 2。原始日志、运行期前后哈希与零漂移结果独立存于 /tmp/opencode-adapter-20261101/desktop-finish-v1/。现有 TARGET 只同步 agents.json 的桌面信号字节哈希，user_entries.py/public_layout.py 哈希与历史 SOURCE 常量保持原值。之前 612/74 全量是旧阶段证据，本轮没有重跑，也不将其计为桌面增量的新全量。

README、SKILL、INSTALL、DESIGN、llms、architecture 与 operations 同步桌面／CLI 分面及验收暂停边界；本节为测试后证据补记。实现子 Agent 不修改 CK；主 Agent 维护项目当前记忆与协调日志。完整候选补丁与清单另存本阶段目录，不覆盖此前任何补丁、失败记录或原始日志；文档源码链接仅作定位，不保证未发布链接可访问。


### 并装检测报告口径窄修（summary-fix-v1）

按巴克队长最终窄审，检测注释与并装 summary 仅报告两个官方安装面各自的身份核验，不声称本次检测证明规则加载兼容性。输出明确“规则加载兼容性未由本次检测验证”，官方 pair→installed 逻辑不变，没有新增版本门禁。合成并装用例新增精确输出断言；本次仅重跑 test_opencode_desktop，10 项通过（0.021 秒），不是新全量。原始日志与本次三文件增量、当前完整 21 文件候选补丁／SHA 清单另存 /tmp/opencode-adapter-20261101/desktop-finish-v1/summary-fix-v1/，旧桌面证据保留。真实验收仍按用户要求暂停，未操作 CK、版本或真实环境，未提交推送。
