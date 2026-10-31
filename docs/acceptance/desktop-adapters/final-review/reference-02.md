# 02：安装接线独立只读审核

结论：**通过**。在本编号负责的 paths / detect / registry / install / user_install 接线范围内，没有发现可复现的本次新增阻断问题；没有为凑数提出非阻断建议。本结论仅覆盖源码与合成环境，不代表真实客户端验收。

## 候选身份

- 基线 HEAD：e6603730304de7352f4c6caef1615adb2ad74e97（按 manifest 标识）。
- 审查对象：本目录 ../snapshot，按 candidate.diff 区分新增与沿用逻辑。
- 已逐个计算 manifest 中 106 个文件的 SHA256，全部一致。
- manifest SHA256：0067dd93ef04b7b2a3bcb84b92217e532f6a8560f0258552706b3cb553f65fc2。
- candidate.diff SHA256：91d44e7b387234eafaf9d9d6e220cb211123ad0a2431ff95eba3c88579ecbf26。

## 核对结果

1. **能力全集与请求缺省分离正确。** `scripts/agm_core/paths.py:30` 定义五家 AGENT_ORDER 与旧三家 DEFAULT_AGENTS；`resolve_agents` 缺省只选旧三家。`detect_agents`、`installation_hints`、`allowed_user_paths(..., None)` 显式使用全集。`registry.py:19` 同源引用 AGENT_ORDER，用户对象路径仍逐条验证，没有为新 Agent 放开任意 HOME 路径。
2. **显式接线完整。** `scripts/install.py:build_parser / plan_machine` 接受 dsh/zcode，外层五家 agent_facts 能索引新目标；`user_install.py:_entry_request / _entry_plan / plan_install` 保留 agents 并通过既有用户入口子计划落盘。`user_entries.py:_run` 对显式目标非 installed 整单拒绝；默认目标不会因新桌面 app 存在而扩大。
3. **探测与多来源拒绝沿用既有保守规则。** `scripts/agents.json` 为两家声明 macOS app bundle、版本和签名 identifier 匹配要求。`detect.py:_check_app_bundle / _detect_one` 保留产品名、可执行、版本、静态签名核验以及多个 verified 候选→unknown；hint 单独存在不当作 installed。此次 detect 的算法变动仅为全量枚举入口，不放宽核验。本次未发现需要另报的既有缺陷。
4. **批准和源身份未被旁路。** `install.py:checkout_source / _approve / execute_machine`、`user_install.py:_source / execute_install` 仍校验源文件哈希、清洁 Git 来源（适用时）、精确计划、当前入口计划及检测指纹。`user_entries.py:_run` 在锁内重规划；允许写入位置由有效目标入口加 registry 限定。DSH_HOME 非默认根在 `_plan` 中整单拒绝且不回显值。
5. **幂等与私文保护成立。** 两个新 native 入口使用各自回退文案；合成安装后再次运行 user_entries 是 completed、changes=[]，HOME 文件树字节、mtime 和类型不变；未自动创建旧三家入口或 skills 目录。

## 本轮实际验证

未重复全量测试，未引用历史 578/74 作为当前通过证据。

- 从快照导入 `test_desktop_adapters.DesktopDetectionTests` 和 `DesktopInstallTests`，运行 **7/7 通过**。覆盖五家枚举、签名/版本/hint 失败、默认不接入、显式双端安装、私文字节保留、幂等、absent/unknown/错批准零写、DSH 根重定向及规范化。
- 另跑一条独立串联小实验，使用 `InstallFixture` 创建最小合成产品源，用 `DetectFixture.app_bundle` 在合成 Applications 中创建两个 app；**不替换 detect_agents**，仅注入 fake_codesign 签名后端，request 显式 agents=[dsh,zcode]、search_paths=[]、app_directories=[合成路径]。经过真实 `install.plan_machine → execute_machine`，报告 completed，connected=[dsh,zcode]，五家 facts 均存在。
- 同一小实验在执行前分别：篡改批准中的 requested_agents；修改合成源 SKILL.md；修改 ZCode 合成 executable；增加第二个 ZCode app 并通过 user_candidates 指定。四种情况均拒绝，合成 HOME 树快照完全不变。恢复夹具后原批准正常安装；随后用户入口重放零差异，旧三家目录均不存在。
- 所有运行使用 `python3 -B`；测试进程 HOME/TMPDIR/tempfile.tempdir 均指向自己的 `/tmp/captain02-*` 临时目录。临时夹具已清理。无真实安装、无真实配置读取、无客户端启动、无网络。

复核串联实验方法：从快照 tests/unit 导入上述 InstallFixture、DetectFixture、fake_codesign 与 test_desktop_adapters.snapshot；为两个 app 使用各自 agents.json 中的 bundle_name/product_name，version=1.0、bundle_id=com.example.fixture；request.detect_runner=fake_codesign(identifier=com.example.fixture)。批准使用 test_m404_install.approved(plan)。对各拒绝分支比较 snapshot(f.home) 前后全等；成功分支断言报告 connected 与再次 run_user_entries 的空 changes。产品源为 InstallFixture 的最小三文件 fixture，不能据此宣称完整发布包安装通过。

## 实际读取范围与未验证项

读取：snapshot/AGENTS.md、manifest.json、candidate-identity.json、candidate.diff 相关 hunks；agents.json、paths.py、detect.py、install.py；user_install.py 的源身份/场景/计划/执行及接线片段；registry.py 的枚举、用户路径和校验/提交调用点；user_entries.py 的 native 接线、DSH 根、计划和执行路径；相关测试夹具及两组桌面测试。对其余 agm_core 模块只搜索枚举和 allowed_user_paths 消费点，不声称完整审过其实现。

未验证：真实 app 签名有效性、桌面进程实际环境与自定义 preset、真实用户入口读取、Skill 实际加载、真实 HOME 安装/升级/恢复、完整发行包端到端安装、其他审核编号负责的迁移/项目生命周期全路径。真实桌面新会话验收仍 pending。

仅写本报告，未改主仓、快照或其他 Agent 工作区；未提交、推送、安装或改版本。

所用 manifest SHA256：0067dd93ef04b7b2a3bcb84b92217e532f6a8560f0258552706b3cb553f65fc2。
