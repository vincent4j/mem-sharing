# M3 WorkBuddy 上游接管验收

2026-10-29，现场验证 UTC 14:33:55 起。产物均留工作区，未 commit/push；未修改真实用户级入口、registry、三项目桥接文件或记录库。上游根目录无 AGENTS.md，已读取 README.md、SKILL.md、references/install.md 和现有 unittest 测试约定。本次明确授权覆盖 AGM 原有“不改上游”规则，仅限 M3 文件范围。

## 变更清单与理由

上游 `/Users/vincent4j/Tools/Source/context-keeper`：

| 文件 | 改动理由 |
|---|---|
| `scripts/install.py` | 持有唯一 WorkBuddy 模板；增加项目 `.workbuddy/memory/MEMORY.md`/用户 `.workbuddy/MEMORY.md` 路径；install/ensure/bridge-only/uninstall 按 Agent 选择标记。缺失前置、旧块更新、完整性预检、当前块零写入。块外字节（含 CRLF）保留。其余四家维持自动入口停写。 |
| `tests/test_install.py` | all 安装现在包含第三个桥接；故障注入桩适配 agent 参数，保留回滚检查。 |
| `tests/test_workbuddy_install.py` | 创建/预览/幂等/旧块哈希/旧文案更新与移顶/重复损坏倒置标记/卸载保留原文/未知安装范围/四家停写/临时用户范围。 |
| `SKILL.md`、`references/install.md` | 说明 WorkBuddy ensure、路径、接管和未完成真机会话验收边界。 |

AGM：

| 文件 | 改动理由 |
|---|---|
| `scripts/agm_core/enable.py` | AST 读取上游 WorkBuddy 模板，无执行导入或私有兜底；保留事务预写、漂移/源码指纹检查；preview 输出集包含 WorkBuddy；取消 ensure 循环跳过 WorkBuddy，校验项目路径和 unchanged 回传。 |
| `templates/workbuddy-bridge.md` | 删除第二模板真源。 |
| `tests/unit/test_m204_enable.py`、`test_m207_faults.py`；`tests/integration/test_m204_subprocess.py`、`test_m207_cli_cycle.py` | provider 桩声明 WorkBuddy 模板/规则输出/ensure，不再复制已删模板。 |
| `tests/unit/test_m3_workbuddy.py` | 证明上游模板复用、既有块为 reused、漂移先停止且不调用上游、无模板即失败、WorkBuddy ensure 错路径回滚。 |
| `DESIGN.md` §5/§8（及目录树） | 配置桥接已由上游接管，真机新会话验收仍可选。 |
| `docs/acceptance/m3/` | 本交付证据；不是 context-keeper 记录库。 |

可直接审阅 `upstream.patch` / `agm.patch`（含新增测试），`source-manifest.json` 记录两仓库 HEAD 与交付源码哈希，便于验收时识别后续漂移。

## 接管策略

三项目现场采样与上游 `WORKBUDDY_BRIDGE` 的 marker-to-marker 字节完全一致。共同 SHA-256：

`5d464acc40d0bf2b30fc02dcffda1fdbf1cee80c5e3e742da9e85a1c871a8315`

三处块起始偏移均为 0，start/end 均恰好一个。块已经位于顶部且内容为当前版本时不写入，保留无末尾换行的现场文件；旧文案则经批准识别相同 marker 后更新，非顶部块移至顶部，绝不追加第二块。AGM 仍先按 registry 的既有指纹拦截漂移；上游支持更新不构成绕过 AGM 所有权/批准机制的许可。

`before.json` / `after.json` 保存整文件哈希、块哈希与位置/数量；`*.before.block.md` / `*.after.block.md` 为三处实际受控块，不含块外内容。它们只是验收快照，运行时不会读取这些文件作为模板。

## 验证结果

| 验证 | 结果与证据 |
|---|---|
| 上游全量 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` | 138 项通过，见 `upstream-all-tests.txt`；安装子集 34 项通过，见 `upstream-install-tests.txt`。 |
| AGM 单元 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit` | 原有 228 项通过，见 `agm-unit-tests.txt`。 |
| AGM 新增 `... discover -s tests/unit -p test_m3_workbuddy.py` | 4 项通过，见 `agm-m3-tests.txt`；与前一行合计 232 项。 |
| AGM 集成 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/integration` | 53 项通过，见 `agm-integration-tests.txt`；有一条文件句柄 ResourceWarning，不影响断言/退出码，本次未扩大范围修复。 |
| 真实上游安装器 + AGM 临时演练 | 临时 HOME、项目、provider checkout；probe 为临时桩。首轮完成，第二轮完成且 changes=[]；旧 WorkBuddy 整文件字节/mtime 均未变。真实上游 WorkBuddy ensure 调用 2 次。见 `takeover.json`。 |
| 本仓库实际 ensure | 经 AGM `_call` 的源码指纹与预检路径，调用上游安装器两次，均 scope=project、action=unchanged。不是对现场执行完整 enable（避免 init/registry 写入）。见 `takeover.json` 的完整命令。 |
| `python3 scripts/agm.py check-memory --all` | completed，退出码 0；agent-group-memory、knowwind、poster-fit 各 gaps=0，见 `check-all.json`。 |
| 现场保护 | 28 个受保护路径前后相同，含三项目 registry 对象、用户级入口、registry、三项目实际记录库；文件 hash/mtime、树内条目/内容 hash/mtime 聚合比较。见 `protected-before.json` / `protected-after.json`。 |

`verify_takeover.py` 可重放临时演练和受保护的现场 ensure/check，不对真实记录库调用 init/save/migrate。真实确保执行前校验安装来源、registry 管理对象、模板与现场块一致。真实 ensure 无写入，因此无需恢复；临时演练由 TemporaryDirectory 清理。

## 遗留与验证边界

- 未进行 WorkBuddy 真机新会话/自然续接验收；仍是用户可选项。配置、测试、check 全绿均不证明模型运行时行为。
- 上游 README 支持表仍是旧的停写描述；本次按上游文件白名单不修改 README，后续发布时应同步。已更新 SKILL 与安装 reference 的操作说明。
- 路径表中 WorkBuddy `bridge_owner=agent-group-memory` 暂留作为旧 schema 的 marker 选择兼容标签，check 的只读标记映射和登记所有权未迁移；它不持有模板，也不再决定桥接文案来源。本次未修改路径表/check 文件。
- 源码修改不会主动更新其他现存用户入口；本轮真实 ensure 只对本仓库 WorkBuddy 执行。knowwind/poster-fit 只采样并 check，未执行写操作。
- paseo-progress 启动失败（插件缺少 zod）；未修改插件或安装依赖。
