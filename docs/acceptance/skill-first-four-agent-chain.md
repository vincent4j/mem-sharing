# Skill 优先四家扩展共享链验收

状态：四家源码与临时 HOME 合成链通过；真实原生新会话未验。日期：2026-11-03。基线：[两家共享链](skill-first-two-agent-chain.md) 提交 `ff645ffb` 之上的本切片改动，未提交。

## 范围

把已通过的两家（Codex/Claude Code）Skill 优先新共享/归还链扩展到 WorkBuddy、DeepSeek Harness（DSH）、ZCode、OpenCode。复用 `agents.json` 真实原生用户文件路径与各家已验证读取机制：Claude 的 `@` 引用仅属 Claude；四家均为各自原生文件（`.workbuddy/MEMORY.md`、`.dsh/AGENTS.md`、`.zcode/AGENTS.md`、`.config/opencode/AGENTS.md`）内同一受管指针块机制，未把 `@` 泛化。核心仍不依赖 installed registry/S/R，复用既有 Transaction/manifest，未新建台账或 share-records 目录。

## 环境边界（纳入实现与测试，不回显真实环境原值）

- DSH_HOME 重定向用户规则根时拒绝（fail closed）：空白视为未设置；`~/` 与 `~\` 前缀按目标 HOME 展开、仅转换此前缀分隔符后规范化，等于 `<home>/.dsh` 不算重定向。DSH_AGENTS_HOME 只影响 Skill 根，不阻断仍有效的用户入口。
- OpenCode：XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR 仅绝对且等于默认落点放行；OPENCODE_CONFIG 任何非空取值视为重定向。
- ZCode：规则根只由 HOME/USERPROFILE 后备 homedir 决定（CLI 经 `--home`/`Path.home()`）；ZCODE_HOME 不是规则根，不据此寻址也不据此阻断。
- 两个边界助手在 `memory_share.py` 内实现为纯函数（核心不 import 安装层模块，避免反向依赖 `user_entries` 拉入 registry），测试矩阵逐一断言与 `user_entries.dsh_home_redirected` / `opencode_config_redirected` 冻结合同行为一致，防两处漂移。

## 已有证据

计时口径：主阶段起点 2026-11-03 13:58:22 UTC（任务下发）；执行者实际开工 13:59:35 UTC；首段截止 14:13:22 UTC 前完成，未触发超时审核。

执行者报告的实际命令与结果（本切片，2026-11-03 14:07–14:08 UTC）：

| 命令 | 用例 | 退出码 |
| --- | --- | --- |
| `python3 -B -m unittest tests.unit.test_memory_share_four_agents` | 6 | OK |
| `python3 -B -m unittest tests.unit.test_memory_share tests.unit.test_fusion_phases tests.unit.test_fusion_recovery tests.integration.test_m202_transactions` | 48（既有冻结用例回归） | OK |

主验收（七 hash、diff、入口与断言抽查）通过后，按审核意见补宿主环境隔离并在普通与敌意环境（DSH_HOME/ZCODE_HOME/OPENCODE_CONFIG 外部注入）各重跑一次新增 6 用例，均 OK；仅重跑新增用例，未重跑其余回归。

新用例覆盖：四家临时 HOME 普通 CLI 预览/批准共享（退出码 5/0），完全同字节公共仅一份且四处来源逐处记录（同 public span、四条 migration）；各家原生入口块创建与 `memory_index_block` 记录；独有行保留、WorkBuddy CK 块与 OpenCode 旧兼容 `mem-sharing` 受管块逐字节保全；CLI 全量归还（in_place + remove_entries）后四家原文加一个分隔换行、入口剥离、公共回落 `# 用户记忆\n\n`；未知来源（非普通文件）单列并阻断执行（unknown_source）；DSH_HOME/OpenCode 重定向拒绝且错误信息不含环境原值，`~/.dsh`、`~\.dsh`、空白 DSH_HOME、DSH_AGENTS_HOME、ZCODE_HOME 均不误阻；边界助手与 user_entries 冻结合同逐值一致；hook 在删源阶段失败后全量回滚（四家原生文件与公共文件回到原状）。

## 冻结与改动文件

| 文件 | 状态 | SHA256 |
| --- | --- | --- |
| `SKILL.md` | 本切片更新（六家范围与环境边界说明） | `86a780ad30ea3f13d5054a1e590f74dd8bbf19f4669eb7be54de3eaebab134d3` |
| `scripts/agm_core/memory_share.py` | 本切片扩展 | `e06f676b2ea31bd1ad203c1503dcabdf100f46e11fb72533e98723f7bfab5f0f` |
| `tests/unit/test_memory_share_four_agents.py` | 本切片新增（审核后补宿主环境隔离，末次 hash） | `86527a2cc52df07fee5b35edfb97bd1d41327f9792a81ecf8950e342972a4825` |
| `docs/acceptance/skill-first-four-agent-chain.md` | 本切片新增（本文件，自不含 hash） | — |
| `scripts/agm_core/transaction.py`、`scripts/memory_share.py`、`tests/unit/test_memory_share.py`、`tests/unit/memory_share_crash_fixture.py` | 未改动，沿用两家链冻结 hash | 见两家链文档 |

`docs/context-keeper/` 改动为主 Agent 的 CK 记录，非本切片代码写者产物。

## 未完成范围

真实 Skill 对话与六家原生新会话加载（静态入口核验≠真实读取）、项目记忆新主线、旧安装向新主线的真实兼容、整机产品验收均待做。旧兼容代码保留；未生成发行物、未提交推送、未安装、未改真实 HOME；DSH 自定义配置与 Windows/Linux 未验证。测试中的 DSH_AGENTS_HOME/ZCODE_HOME 语义按 2026-11-03 主负责人补充的 OpenViking 经验与源码冻结合同落实，真实环境原值未读取也未输出。
