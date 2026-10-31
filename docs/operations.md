状态：文档版本 1.2；2026-10-31 公共记忆分层修订。命令形状以当前源码帮助为准，真实运行限制见验收总览。

# memSharing 操作手册

本手册供使用者与执行 Agent 使用，机制说明见 [系统架构](architecture.md)。
命令已核对 `scripts/agm.py --help`、各子命令帮助及 `scripts/install.py --help`。
示例中的绝对路径、完整 SHA 和版本号必须替换为实际核验值。

## 1. 环境与操作入口

当前实证平台为 macOS；Windows/Linux 不列为已验收平台。
需要 Python ≥3.9 和 Git，Python 无额外 pip 依赖。
缺失或版本不足时，执行 Agent 在安装汇总确认后用可用系统包管理器准备依赖。
Python CLI 本身只诊断，不负责自动安装 Python/Git。
包管理器缺失、权限受阻或依赖安装失败时停止，说明实际阻塞。

用户可直接说“安装 memSharing”，安装后可用 `/mem-sharing` 菜单或自然语言。
六个菜单入口为：添加新的 Agent、批量启用项目记忆、整理用户记忆、健康检查、给项目停用记忆、给项目启用记忆。
菜单由公共指南 `~/.mem-sharing/memories/topics/使用约定.md` 承载，各执行器用户文件只保留公共指针与自身规则，不要求安装 memSharing Skill；触发菜单或默认项目接入前先读指南。链接解析分两个根：索引 `MEMORY.md` 中的指南/主题相对链接以 `MEMORY.md` 所在目录解析；指南内部的链接以指南所在目录解析，或直接使用 C 内绝对路径（例如已安装产品脚本）；两个解析根不能混同。指南缺失时停止相关操作。
下文项目示例从源码根运行；已安装后可改用 C 中的脚本绝对路径。
C 为 `~/.local/share/mem-sharing`，R 为 `~/.mem-sharing`。

为什么这样设计：使用者表达意图，Agent 翻译为受控命令，不要求用户维护执行器差异。

## 2. 安装：五拍剧本与命令

1. 接收安装请求，说明先检查运行环境和本机 Agent。
2. 汇总 Python、Git、验证为已安装的 Agent 与待准备依赖，一次确认，回车开始。
3. 确认后静默获取、核验和安装；完成只报用户记忆中枢与实际接入名单。
4. 紧接着正向询问是否安装用户级 Context Keeper，回车同意，n 跳过。
5. 安装后提醒在所需项目使用 `/context-keeper`，首次按 Context Keeper 流程激活。

unknown 或仅有残留目录不列为已安装。
成功简报不罗列内部路径，不添加未安装 Agent 或新会话自检提示。

先使用核验过的干净本地 Git checkout 预览：

```bash
python3 scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
```

也可用 `--source-manifest /absolute/path/source.json` 提供固定来源对象。
它包含 `root/url/commit/version/files`，不要与 source/commit/version 混用。
不得 reset/pull 用户的 dirty checkout 来满足干净要求。
安装器只读判别全新、确认的 v0 内容复制、有效产品升级或异常停止。
v0 仅复制获准的 memories/references，旧目录 `~/.agents-group` 原地保留。

无批准时返回 `approval_plan`，不会安装。
Agent 展示完整计划并绑定真实确认，将计划连同 `confirmed_at/reference` 写入批准 JSON。
`confirmed_at` 使用真实 UTC 时间并以 `Z` 结尾，例如 `2026-10-31T02:23:47Z`（示例不得当作本次确认时间）；`reference` 指向真实确认。批准必须对应当前计划，不填写虚构确认，不将一次确认扩大成任意修改授权。

```bash
python3 scripts/install.py --approval-file /absolute/path/install-approval.json
```

支持 `codex/claude/workbuddy/dsh/zcode` 五家，缺省仍选择旧三家；新两家须显式选择。安装可重复 `--agent codex --agent claude` 或 `--agent dsh --agent zcode` 限定目标，仍须通过安装事实核验。来源与预览批准流程不变。

```bash
python3 scripts/install.py --source-manifest /absolute/path/source.json --agent dsh --agent zcode
```

`--project` 只用于报告后续项目命令，不表示安装时顺便启用项目。

为什么这样设计：先固定来源与现场再写入，安装请求能落实到可核对的精确变更。

## 3. 给单个项目启用记忆

进入未登记的 Git 主 checkout 时，用户级规则与公共指南驱动默认启用，由当前实际执行者以 `--agent <当前执行者>` 执行；不带 agent 参数按已安装事实处理，可能顺带补齐其他执行器已存在的原生目录，仅用于用户显式要求全体或批量接入，不改 CLI 语义。机器探测到执行器安装或原生目录存在，不等于当前执行者实际使用。这不是后台监听；非 Git 目录与 linked worktree 不触发。

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent <当前执行器>
```

新项目建立 `AGENTS.md` 骨架；已有规则正文保留，只补所需协议。
`AGENTS.md` 是共享项目规则基座，不依赖安装 Codex；只接入 Claude、WorkBuddy 或两者而无 Codex 的组合均成立。
不带 `--agent` 的通用 enable 完全不触碰 `CLAUDE.md`，包括已有文件；Claude 自身实际使用时按 `--agent claude` 精确接入，可幂等补 `@AGENTS.md` 引用（兜底规则在 Claude 自身用户文件）；其它执行者默认流程不预建。Codex 原生读取无需兜底。
有意接入 Claude 时可显式执行 `enable-memory --project ... --agent claude`。
WorkBuddy 只在 `.workbuddy/memory/` 原生目录存在时补规则指针，不预建目录。
原生目录缺失表示待实际使用；静态桥接不等于运行时加载通过。

启用不调用 Context Keeper 安装器、不安装项目级 Skill、不创建其记录库。
未装 Context Keeper 仍可使用用户记忆与项目规则，只是没有项目经历能力。
若需精确非交互批准，先查看预览，再加 `--approval-file /absolute/enable-approval.json`。
项目启用 `--agent codex claude` 或 `--agent dsh zcode` 可一次选择多个唯一值；未显式选择时仍只在默认旧三家中按已安装事实处理。

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent dsh zcode
```

写前发现受管单元漂移则停止，批准文件不能强制覆盖漂移保护。

为什么这样设计：规则接入与项目经历激活分开，默认流程不为未使用的执行器创建文件。

## 4. 批量启用项目

在菜单选“批量启用项目记忆”，提供需要扫描的目录：

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects
```

递归扫描包含目录自身，不进入 `.git`，不跟随目录符号链接。
仅 Git 主 checkout 可入选，linked worktree 排除。
汇总预览每项目一行，集中批准全部新项目的精确计划，不逐项目重复询问。
已启用项目跳过；disabled 项目保持停用，必须单独显式恢复。

```bash
python3 scripts/agm.py enable-memory-batch --directory /absolute/projects --approval-file /absolute/batch-approval.json
```

批准绑定扫描目录、完整清单、台账哈希和各项目计划，执行前锁内重新核对。
某项目执行失败即停止后续，已完成项目保留，未开始项目不会假报成功。

为什么这样设计：集中确认降低重复操作，同时保留每个项目的事务与故障边界。

## 5. 停用、禁止自动记录与重新启用

菜单“给项目停用记忆”对应撤销项目接入：

```bash
python3 scripts/agm.py remove-memory --project /absolute/path/project
```

只撤销有创建证据且允许撤销的入口与桥接，复用内容不获得删除权。
项目记为 disabled，默认启用条款不再自动触发。
规则正文、全部项目经历数据、用户级接入、机器产品及 Context Keeper 安装保留。
非交互执行须使用该计划的 `--approval-file`，不要把 stdin 的 yes 当作批准。

如果只想保留规则接入、禁止自动项目经历记录与初始化，使用进阶操作：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --no-memory
```

此政策优先于残留 Context Keeper 自动规则，但不是其脚本的硬拒写接口。
手动 Context Keeper 操作仍按用户明确请求与其自身流程进行。
缺省 enable 不会翻转 disabled；重新启用必须显式解除并批准精确计划：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --memory
```

为什么这样设计：撤销入口、阻止默认复开和暂停自动记录分别有明确结果，数据不随停用丢失。

## 6. 添加新的 Agent 与健康检查

先核验新 Agent 的安装事实，再通过机器安装入口的 `--agent` 接入用户记忆。
使用第 2 节安装预览流程限定目标；不是编辑 agents.json 来伪造安装事实。
已有项目需要该执行器时，可显式接入：

```bash
python3 scripts/agm.py enable-memory --project /absolute/path/project --agent claude
python3 scripts/agm.py check-memory --project /absolute/path/project
python3 scripts/agm.py check-memory --all
```

`--all` 读取已登记项目，不扫描整个磁盘寻找新项目。
check 只报告登记与现场缺口，不写锁、不备份、不修复、不触发安装。
入口字节、安装事实和执行器新会话加载应分别判定。
运行时验收仍需实际使用证据；WorkBuddy 无证据时保持 pending。

为什么这样设计：巡检可以安全重复，修复必须落实到另一次明确的写入计划。

### 桌面端默认根与验证边界

DeepSeek Harness（`dsh`）用户入口为 `~/.dsh/AGENTS.md`，ZCode（`zcode`）为 `~/.zcode/AGENTS.md`；均共用公共记忆索引，保留各自私文，项目原生读取根 `AGENTS.md`，无需额外桥接。默认项目接入仍由当前实际执行者显式使用自身 ID，不预建其他执行器入口，也不恢复 disabled。

DSH 本次限默认 coding `cordis` preset 与默认根。接入规划自动检查 `DSH_HOME`，非默认根拒绝默认入口接入，错误不回传变量值。`DSH_AGENTS_HOME` 影响共享 Skill 根，目前不自动检测，也不承诺默认共享 Skill 目录已被客户端发现。显式插件配置也可能覆盖根，自定义配置与桌面进程实际环境未验证。`ZCODE_HOME` 不是 ZCode 规则根，不能用它推导规则位置。

静态读取逻辑支持 DSH 的 `~/.dsh/skills`、ZCode 的 `~/.zcode/skills`，以及两者共用的 `~/.agents/skills`；项目侧也有各自隐藏目录与 `.agents/skills` 发现逻辑。memSharing 不创建、复制或投影这些 Skill。静态发现与符号链接支持不等于桌面实际加载通过。

原生入口证据见[桌面合同（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/desktop-agent-contracts.md)。原生入口静态证据不代表运行时加载通过；两款桌面端新会话的用户规则、项目规则和 Skill 加载验收均为 pending。

## 7. 用户记忆整理与 Context Keeper 激活

“整理用户记忆”由 Agent 调用 `user_rules_organize.py` 的预览与执行 API。
当前 `agm.py` 没有整理子命令，不使用虚构的 organize CLI。
向导把公共候选、重复规则、执行器独有内容和归属不明内容分开展示。
分类只是建议，独有与归属不明内容锁定保留，不能并入公共源或删除。
一次确认完整逐条计划，原文指纹逐项绑定；批准前候选可改判保留。
公共内容与入口编辑使用可恢复事务，整理不修改活动台账 V。

为什么这样设计：公共规则需要人工语义判断，不能用自动分类扩大共享范围。

Context Keeper 是独立可选引擎，主安装完成后才产生独立批准封皮。
独立路由示例：

```bash
python3 scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper
python3 scripts/install.py --context-keeper --approval-file /absolute/ck-approval.json
```

源码须为持久、干净且符合固定 pin 的 checkout，目前不自动下载。
只有真实交互回车表示同意，空格、EOF 或非交互输入不算。
同意后为已接入的 Codex、Claude Code、WorkBuddy 安装用户级 Context Keeper，落位由其自有安装器负责。固定 pin 安装器仅支持旧三家的 flags；`dsh`、`zcode` 明确跳过用户级 CK 安装（`reason=upstream_unsupported`），混合时旧三家仍可安装，不影响新两家的 memSharing 接入，不可宣称它们已安装 CK 或新会话已通过。
仅接入 `dsh/zcode` 时，`--context-keeper` 输出 `status=skipped`、`reason=upstream_unsupported` 与 `skipped_upstream_agents`；交互安装尾步的 `context_keeper` 同样为 `status=skipped`、`reason=upstream_unsupported`，主安装保持 `status=completed`。混合接入执行时，`agents` 仅列受支持的执行器；跳过项列于 `skipped_upstream_agents`，每项为 `{"agent":"dsh或zcode","reason":"upstream_unsupported"}`（`agent` 取实际 ID）。`upstream_unsupported` 是原因，不是顶层状态。

缺源、失败或结果不明分别报告，主产品成功保留，结果不明不自动重放。
在需要的项目首次运行 `/context-keeper`，按其流程确认并初始化项目经历库。
后续保存、续接、查找与迁移门禁全部遵守 Context Keeper；需要迁移时先停止相关读写。

为什么这样设计：可选引擎独立授权，安装成功不冒充项目记录库已激活。

## 8. 常见问题与恢复入口

**锁冲突：** 保留锁与 journal，核对是否仍有写者，不自动删锁或抢锁。
**入口漂移：** 保留当前字节，检查报告路径与受管单元，重新评估计划；不要手改台账绕过保护。
**台账缺失或损坏：** 停止写入，不能凭入口文件猜测原授权或静默重建为全新。
**旧开发版或旧标记：** 保全后重装；schema=3 首发基线不承诺开发版迁移，不提供逆 schema 转换。
**升级中断：** 用报告所指固定恢复工具，避免运行混版 C 中的安装器。
机器恢复先预览，确认后执行同一计划：

```bash
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue
python3 /absolute/verified-source/scripts/install.py --recover /absolute/journal.json --action continue --approval-file /absolute/recovery-approval.json
```

需要回滚时用 `--action rollback` 重新预览与批准；V 已提交且输出全为 after 时只收尾。
项目事务失败则按报告中的 manifest 与 recovery 指引处理，不套用机器 journal。
第三种字节、缺失材料或工具漂移一律停止，不覆盖未知修改。
为什么这样设计：恢复只能依据完整证据执行，重试不能把不确定结果放大。

### WorkBuddy 用户入口的接入边界

用户级 `~/.workbuddy/MEMORY.md` 的私人原文字节保留；精确批准计划后追加受管块，块内明确读取本机公共索引绝对路径及项目 `AGENTS.md`。已登记旧块仅在指纹匹配时，经精确批准更新；漂移、未登记旧块或不满足公共读取语义的共享用户块停止自动接入，交回原有治理路径。与当前模板完全相同的未登记块可保真登记为 reused，不取得删除权。安装器只拥有其新增受管块，不拥有私人全文；本次不提供机器卸载。

报告中的 installed 是安装探测，connected 是登记与实际入口语义的静态核验；缺口列于 `entry_status`，接入未全完成报告 partial。每项 `runtime_acceptance: pending` 仍需真实新会话证据。已有/noop 安装也重新核验静态入口，不凭应用存在宣称接入。需要更新 WorkBuddy 已登记约定时使用显式 `--agent workbuddy` 的精确预览/批准流程；不因同版无参数重跑而自动接入新 Agent。Context Keeper 尾步继续检查主操作、登记对象与指纹，不绕过缺口。本修复不修改私人规则、不预建 WorkBuddy 原生项目目录，不扩大旧版本迁移承诺。

### 0.1.0 → 0.1.1 的 WorkBuddy 入口合同转换

此专用通道只接受 `workbuddy-public-index-v1`，旧版本必须为 0.1.0、结构版本1/schema3，旧来源必须与代码中的 `WORKBUDDY_PREDECESSOR` 完全一致；新版本固定0.1.1。`agents.json` 固定不变，`user_entries.py` 仅允许审定的前后 SHA256。调用必须显式 `--agent workbuddy`，目标 commit/tree 通过外部精确 conversion 与完整批准绑定。不允许把任意合同变更写成 `entries=preserve` 放行，也不支持该转换的成功发行降级。公共记忆分层引起的 `user_entries.py` 指纹变化不适用本通道，另见 [INSTALL](../INSTALL.md) 的公共记忆分层发行转换边界（0.1.3 候选，接口与恢复命令已回填）。

下面是外部 request 清单的生成方式。`<干净来源>` 必须是修复已提交后的干净 checkout；`<完整SHA>` 为该提交，不能用未提交工作树配旧SHA。清单写到独立暂存目录，不修改用户规则或安装态。生成过程中只有读取与输出JSON；仍需随后预览、核对并批准完整安装计划。

```sh
umask 077
WB_RELEASE_DIR=$(mktemp -d)
WB_RELEASE_OP="wb-public-index-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -B - '<干净来源>' '<完整SHA>' "$WB_RELEASE_OP" > "$WB_RELEASE_DIR/request.json" <<'PY'
import copy, importlib.util, json, sys
from pathlib import Path
source_root = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location('release_installer', source_root/'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
from agm_core import layout, paths, registry, upgrade, user_install
source = installer.checkout_source(str(source_root), sys.argv[2], '0.1.1')
canonical, _ = user_install._source({'source': source})
runtime = layout.resolve_layout(Path.home())
config = paths.select_platform(paths.load_agents_table(), sys.platform)
allowed = paths.allowed_user_paths(config, None, home=str(runtime.home))
data = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
product = data['product']
conversion = {
    'before': {'schema_version': data['schema_version'],
               'product_structure_version': product['product_structure_version'],
               'product_code_version': product['product_code_version'], 'source': product['source']},
    'after': {'schema_version': 3, 'product_structure_version': 1, 'product_code_version': '0.1.1',
              'source': {k: canonical[k] for k in ('url', 'commit', 'tree_sha256')}},
    'direction': 'upgrade', 'entries': copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION),
}
# Reject wrong predecessors/targets before emitting a purported supported request.
request = {'home': str(runtime.home), 'platform_config': config, 'source': source,
           'agents': ['workbuddy'], 'conversions': [conversion],
           'operation_id': sys.argv[3]}
installer.plan_machine(request)
print(json.dumps({'source': source, 'conversions': [conversion]}, ensure_ascii=False, indent=2))
PY

python3 -B <干净来源>/scripts/install.py --request-file "$WB_RELEASE_DIR/request.json" --agent workbuddy --operation-id "$WB_RELEASE_OP"
# 上一步 approval_plan 加真实 confirmed_at/reference，保存到精确批准JSON；不要用 request 代替批准
python3 -B <干净来源>/scripts/install.py --approval-file <精确批准JSON绝对路径>
```

外层批准含完整代码计划与精确入口 `entry_plan`，包括原文件/新文件指纹、受管对象变化、安装探测指纹。执行前重建并核对整单；代码阶段不修改用户入口，代码提交后再调用已有入口事务，原始私人字节与旧 Context Keeper 块保留。入口失败或期间外部文件变化时报告 partial，保留已成功升级的代码，不自动回退或覆写外部修改。此时用同一固定0.1.1来源、显式 `--agent workbuddy` **重新预览并批准**；代码为noop，入口独立补齐。旧外层批准不能重放。

代码阶段中断继续使用升级操作中固定的 `recover.py` 与 toolkit 做只读恢复预览，再批准 continue 或 rollback。未提交代码台账时可按既有原子恢复回退；台账已提交则只能完成代码收尾。专用转换的代码恢复结果明确 `scope=product_code`、`entry_phase=not_run_by_upgrade_core`，**不代表 WorkBuddy 接入完成**；恢复后仍要进行同版显式入口预览/批准。外部台账、已登记入口、代码出现第三态时仍拒绝覆盖。

成功完成代码与入口之后，不承诺通过该专用转换自动降级为0.1.0；保留旧代码版本、台账/入口事务备份及恢复材料。撤回已成功新增的用户块必须另行精确计划，不能以恢复旧整文件覆盖后续私人内容。本通道不创建项目原生目录、不新增机器卸载、不更新上游 Context Keeper。
