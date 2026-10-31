# 03 所有权与正文保全审核

结论：**有阻断**。发现 1 项 P1，属于旧 HEAD 已有缺陷，本次桌面适配将同一整理路径扩展到 DSH/ZCode；不是本次新写出的算法缺陷。入口安装本身与公共布局迁移所验证路径通过，不应把此结论扩大为桌面运行验收失败。是否允许把既有缺陷另案处理由主 Agent 裁定。

## P1：规则整理未保护 Context Keeper 块，会拆散块并将正文移入公共源

- 位置：`scripts/agm_core/user_rules_organize.py:60-84`，`_protected`；后续 `_segments` / `_build` 生成移动操作。
- 触发：用户入口含完整 `<!-- context-keeper:start --> ... <!-- context-keeper:end -->`，正文含通用规则关键词，执行 organize-user-rules 的精确预览并批准。无需异常台账或恶意输入。
- 实际：`_protected` 只收集 mem-sharing 标记、已登记对象标记及 import 行，没有 CK 标记。合成例中 CK 开始标记被保留；CK 正文与结束标记一起成为 `公共 / move` 候选。执行返回 completed，入口只剩开始标记、标题和空行；正文及结束标记进入公共主题。Codex、DSH、ZCode 三者均实测复现。
- 预期：CK 所属块整体字节保留，不成为整理候选；损坏 CK 标记应拒绝整单且零写，不把其内容当普通规则。
- 影响：已有 CK 协议被拆散，执行器入口留下未闭合标记，并把非 memSharing 所属的内容导入公共源。集中批准不应绕过独有/外部受管块的保护边界。
- 来源判定：只读 `git show e6603730304de7352f4c6caef1615adb2ad74e97:scripts/agm_core/user_rules_organize.py` 核对 `_protected` 与候选相同；candidate.diff 本模块只新增 DSH/ZCode 专属词识别。**既有缺陷，新适配同样受影响。**
- 建议：显式加入 CK 标记对保护，按 managed_span 严格校验完整性、重复和顺序；不改写其内容，也不取得其所有权。
- 所需验证：五类入口的完整 CK 块逐字节不变；CK 块含公共关键词、列表、空行、CRLF 时都不被候选化；孤立起止标记、重复/交叉标记整单零写；原 mem-sharing 块与 import 行行为无回归。

最小复现（只写 TemporaryDirectory；PYTHONDONTWRITEBYTECODE 禁止快照 pycache）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'REPRO'
import os, sys, tempfile
from pathlib import Path
root = Path('/tmp/memsharing-eight-captains-20261031T101521Z/snapshot')
sys.path[:0] = [str(root/'scripts'), str(root/'tests/unit')]
from agm_core import paths, user_rules_organize as org
from runtime_fixture import seed_runtime
with tempfile.TemporaryDirectory(prefix='review03-') as tmp:
    os.environ['HOME'] = tmp
    for agent in ('codex', 'dsh', 'zcode'):
        home = Path(tmp)/agent
        home.mkdir()
        runtime = seed_runtime(home)
        (runtime.root/'memories').mkdir()
        (runtime.root/'memories/MEMORY.md').write_text('# public\n')
        entry = home/('.'+agent)/'AGENTS.md'
        entry.parent.mkdir()
        original = ('<!-- context-keeper:start -->\n## Context Keeper\n\n'
                    '- 失败也记录，保存前核验证据。\n<!-- context-keeper:end -->\n')
        entry.write_text(original)
        req = dict(home=str(home), agents=[agent],
                   platform_config=paths.select_platform(paths.load_agents_table(), 'darwin'))
        result = org.plan_organize(req)
        plan = result['approval_plan']
        print(agent, [(i['classification'], i['action'], i['text']) for i in plan['items']])
        approval = dict(plan, confirmed_at='2026-10-31T10:30:00Z', reference='synthetic review03 approval')
        done = org.execute_organize(plan, approval)
        print(done['status'], entry.read_text() == original, repr(entry.read_text()))
REPRO
```

实际输出要点：每个 agent 均为 `completed False`，入口余下 `<!-- context-keeper:start -->\n## Context Keeper\n\n`。

## 通过的检查与证据边界

- user_entries：native 模板按 agent 分派；受管块之外追加保留原始字节；机器块漂移预检，shared 块只引用，shared whole-file 终局保护；import 指纹绑定最终整文件而不赋予删除权。相关旧机制在 candidate.diff 未改。
- DSH_HOME：只返回布尔，错误文案不回传环境私值；空白、默认根、相对路径、tilde 及非默认路径的合成测试通过。
- public_layout：新增 native 模板为各 agent 精确模板；dsh/zcode 无旧模板时拒绝未知内容；Codex 历史模板仍可迁移。双端已登记新模板保持字节不变。
- transaction：候选无改动；读取审核了执行前输出快照比对、逐写校验、备份、回滚保护外国编辑的流程。组织器测试覆盖预览后源/公共源/台账漂移零写、整文件所有权阻断与事务失败恢复。并发开始执行后的回滚可能留事务元数据，不将其说成绝对零写。

## 实际读取/运行范围

- 读取 snapshot/AGENTS.md、manifest.json、candidate.diff 的 paths/user_entries/user_rules_organize/public_layout 相关差异；读取上述四个审核模块及 paths、tests/unit/runtime_fixture.py 和对应测试片段；只读主仓指定 HEAD 的 user_rules_organize 用于判定缺陷来源。
- 106 个 manifest 文件的 SHA256 全部复核匹配；未修改主仓、快照或真实用户配置。只读取任务前强制公共规则索引；未读取真实 Agent 私有正文/凭据。
- 当前候选专项：3 个 DesktopInstallTests（私有/CK 字节保留与幂等和漂移、重定向脱敏零写、根解析），完整 test_m408_organize 与 test_m405_user_entries，合计 **54 项通过**。
- 初次连同 test_public_layout 运行总计 125 项：54 通过，71 项在 fixture 初始化报错，因为快照无 .git；无断言失败，不能算这 71 项通过。
- 随后只在测试进程内替换 test_public_layout._git：允许 ls-tree/cat-file 从主仓读取旧版本 Git 对象，候选读取仍来自快照。定向 **6 项通过**：upgrade_runs_migration_to_v2_and_preserves_private_bytes、shared_convention_keeps_oid_scope_ownership_consumers、registered_new_native_entries_remain_byte_identical_during_migration、new_desktop_readers_are_scanned_and_private_files_preserved、existing_claude_fallback_keeps_trailing_private_context_keeper_bytes、unknown_symlink_reader_and_damaged_public_marker_fail_closed。中途一次按错测试类组装 suite，未执行用例；纠正为方法所属类后得到上述结果。
- 另有上述 3 个 agent 的独立合成 CK 整理复现，确认 P1。所有执行均设置临时 HOME，禁用 Python bytecode，测试写入均在临时目录。
- 未验证：其余公共布局用例、全量测试、真实安装、桌面新会话、原生 Skill 加载；不沿用此前 578/74 通过声明。

manifest SHA256：`0067dd93ef04b7b2a3bcb84b92217e532f6a8560f0258552706b3cb553f65fc2`
基准 HEAD：`e6603730304de7352f4c6caef1615adb2ad74e97`
