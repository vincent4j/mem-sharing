"""Explicit retirement of memSharing-owned project-experience controls.

The schema-3 disabled value remains a historical rule-accession tombstone only.
This module never installs/enables Context Keeper or reconstructs old entries.
"""
import argparse
import copy
import json
from pathlib import Path

from . import paths, registry, user_entries
from .entries import managed_span, remove_block, remove_lifecycle_unit
from .layout import resolve_layout
from .transaction import Change, Snapshot, Transaction, read_snapshot, write_lock
from . import uninstall_recovery as recovery

COMMAND = 'migrate-policy'
DENIED = {'start': '<!-- mem-sharing:memory-denied:start -->',
          'end': '<!-- mem-sharing:memory-denied:end -->'}


def config():
    return paths.select_platform(paths.load_agents_table(Path(__file__).parent.parent / 'agents.json'), 'darwin')


def retire_controls(ledger, *, project=None):
    """Pure planner; return updated ledger, exact file changes, observations."""
    updated = copy.deepcopy(ledger)
    changes, observations = {}, {}
    for main, record in updated['projects'].items():
        if project is not None and str(project) not in (main, *record['checkouts']):
            continue
        for checkout, assembly in record['checkouts'].items():
            registered = set()
            for oid, obj in list(assembly['objects'].items()):
                if obj.get('marker') != DENIED:
                    continue
                path = obj['path']
                registered.add(path)
                before = read_snapshot(path)
                observations[path] = recovery.snapshot(path)
                expected = (obj.get('fingerprint') or {}).get('value')
                if obj['ownership'] != 'created' or not expected:
                    raise recovery.Conflict('Unknown/private policy ownership: ' + path)
                if registry._unit_fingerprint(before, obj) != expected:
                    raise recovery.Conflict('Policy control drift: ' + path)
                raw = changes.get(path, before.data)
                after = (remove_lifecycle_unit(raw, obj) if obj.get('lifecycle') else
                         remove_block(raw, **DENIED, expected_fingerprint=expected))
                changes[path] = after
                del assembly['objects'][oid]
            # A marker alone never establishes ownership.
            for path in (Path(checkout)/'AGENTS.md', Path(checkout)/'CLAUDE.md',
                         Path(checkout)/'.workbuddy/memory/MEMORY.md'):
                state = read_snapshot(path)
                observations[str(path)] = recovery.snapshot(path)
                if state.kind == 'file' and managed_span(state.data, **DENIED) is not None and str(path) not in registered:
                    raise recovery.Conflict('Unregistered policy control; preserve and resolve: ' + str(path))
    return updated, changes, observations


def legacy(name, runtime):
    templates = user_entries.PRE_UNINSTALL_ROUTE_TEMPLATES if name.startswith('pre_route_') else LEGACY_TEMPLATES
    return templates[name].replace('__CODE__',str(runtime.code)).replace(
        '__INDEX__',str(runtime.root/'memories/MEMORY.md')).encode()


def require_route_capability(ledger, runtime, observations):
    """Do not install new instructions pointing at an incompatible executor."""
    from . import user_install
    user_install._code_matches(runtime, ledger['product'])
    source = Path(__file__).resolve().parents[2]
    required = ('SKILL.md', 'docs/uninstall-design.md', 'scripts/agm.py',
                'scripts/agm_core/user_entries.py', 'scripts/agm_core/uninstall.py',
                'scripts/agm_core/uninstall_recovery.py')
    for rel in required:
        path = runtime.code / rel
        state = recovery.snapshot(path)
        if state['kind'] != 'file' or state['hex'] != (source / rel).read_bytes().hex():
            error = recovery.Conflict('Installed code cannot carry this uninstall route; update code through the exact install/upgrade flow first: ' + str(path))
            error.code = 'route_code_incompatible'
            raise error
        observations[str(path)] = state
    observations[str(runtime.code / '.agm-code-manifest.json')] = recovery.snapshot(runtime.code / '.agm-code-manifest.json')


def migrate_generated(ledger, runtime, files, observations):
    """Known generated control text only; never blanket regex-edit private prose."""
    require_route_capability(ledger, runtime, observations)
    index = runtime.root/'memories/MEMORY.md'
    topic = runtime.root/'memories/topics/使用约定.md'
    for path, names, desired in (
            (index,('pre_route_contract','contract','old_contract'),user_entries.public_memory_contract_text().encode()),
            (topic,('pre_route_topic','topic','old_topic'),user_entries.usage_convention_topic_text(runtime.code).encode())):
        state = read_snapshot(path)
        observations[str(path)] = recovery.snapshot(path)
        if state.kind!='file':raise recovery.Conflict('Generated memory input missing: '+str(path))
        raw = state.data
        if path==index:
            for name in names:
                old = legacy(name,runtime)
                if old in raw:
                    if raw.count(old)!=1:raise recovery.Conflict('Duplicate legacy public contract')
                    raw=raw.replace(old,desired,1)
                    break
            else:
                if desired not in raw:
                    raise recovery.Conflict('Unknown/customized public contract; preserve: '+str(path))
        elif raw not in (desired,*[legacy(name,runtime) for name in names]):
            raise recovery.Conflict('Unknown/customized generated usage topic; preserve: '+str(path))
        else:raw=desired
        if raw!=state.data:files[str(path)]=raw
    for scope in ('machine','shared_objects'):
        objects = ledger['machine']['objects'] if scope=='machine' else ledger['shared_objects']
        for obj in objects.values():
            marker = obj.get('marker')
            if marker not in (user_entries.BASE_MARKER,user_entries.CLAUDE_FALLBACK_MARKER):continue
            path = obj['path'];state=read_snapshot(path)
            observations[path]=recovery.snapshot(path)
            if state.kind!='file':raise recovery.Conflict('User control entry missing: '+path)
            span=managed_span(state.data,**marker)
            unit=b'' if span is None else state.data[span[0]:span[1]]
            if registry._unit_fingerprint(state,obj)!=(obj.get('fingerprint') or {}).get('value'):
                raise recovery.Conflict('User control fingerprint drift: '+path)
            agents=obj['agents']
            if len(agents)!=1:raise recovery.Conflict('Ambiguous control host: '+path)
            agent=agents[0]
            names = ('claude',) if marker==user_entries.CLAUDE_FALLBACK_MARKER else (
                ('workbuddy','old_workbuddy') if agent=='workbuddy' else (agent,'old_codex') if agent=='codex' else (agent,))
            if marker==user_entries.CLAUDE_FALLBACK_MARKER:
                desired=user_entries._wrap_block(marker,user_entries.CLAUDE_FALLBACK_TEXT)
            elif agent=='workbuddy':
                desired=user_entries._wrap_block(marker,'\n'.join([user_entries.public_read_text(runtime.root/'memories/MEMORY.md'),
                    user_entries.WORKBUDDY_CONVENTION_TEXT,user_entries.WORKBUDDY_FALLBACK_TEXT]))
            else:desired=user_entries.native_public_source_block(agent,runtime.root/'memories/MEMORY.md')
            if unit==desired:continue
            if obj['ownership']!='created' or unit not in [legacy(name,runtime) for name in names]:
                raise recovery.Conflict('Unowned/customized legacy control; preserve: '+path)
            raw=files.get(path,state.data)
            from .entries import render_block
            files[path]=render_block(raw,desired,**marker,expected_fingerprint=obj['fingerprint']['value'])
            obj['fingerprint']['value']=recovery.digest(desired)
    # Claude import fingerprints cover the whole file, including fallback blocks.
    for obj in ledger['machine']['objects'].values():
        if obj['kind']=='import' and obj['path'] in files:
            before=read_snapshot(obj['path'])
            if registry._unit_fingerprint(before,obj)!=(obj.get('fingerprint') or {}).get('value'):
                raise recovery.Conflict('Native import baseline drift')
            obj['fingerprint']['value']=recovery.digest(files[obj['path']])


def preview(*, home, project=None):
    runtime = resolve_layout(home)
    runtime.validate_paths()
    allowed = paths.allowed_user_paths(config(), None, home=str(runtime.home))
    ledger = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    if project is not None:
        target=Path(project)
        if not target.is_absolute() or str(target)!=str(target.absolute()) or '..' in target.parts or str(target.resolve())!=str(target):
            error=recovery.Conflict('Project must be a canonical absolute registered path')
            error.code='invalid_target';raise error
        if not any(str(target)==main or str(target) in record['checkouts'] for main,record in ledger['projects'].items()):
            error=recovery.Conflict('Project is not registered: '+str(target))
            error.code='invalid_target';raise error
    updated, files, observations = retire_controls(ledger, project=project)
    migrate_generated(updated,runtime,files,observations)
    observations[str(runtime.registry)] = recovery.snapshot(runtime.registry)
    body = {'schema_version': 1, 'command': COMMAND, 'home': str(runtime.home),
            'project': None if project is None else str(project),
            'observations': observations, 'files': {p: b.hex() for p,b in files.items()},
            'after_registry': updated}
    return recovery.seal(body)


def view(plan):
    return {'command': COMMAND, 'home': plan['home'], 'project': plan['project'],
            'scope':'selected project controls plus machine-wide generated user governance',
            'plan_sha256': plan['plan_sha256'],
            'changes': [{'path': p, 'after_sha256': recovery.digest(bytes.fromhex(b))}
                        for p,b in plan['files'].items()],
            'context_keeper': 'unchanged', 'disabled_semantics': 'historical_rule_accession_only'}


def execute(approval, *, home, project=None):
    runtime = resolve_layout(home)
    with write_lock(runtime.lock):
        plan = preview(home=home, project=project)
        recovery.approve(approval, view(plan))
        approved={}
        for path,state in plan['observations'].items():
            if state['kind']=='file':snapshot=Snapshot('file',bytes.fromhex(state['hex']),state['mode'])
            elif state['kind']=='symlink':snapshot=Snapshot('symlink',target=state['target'])
            elif state['kind']=='absent':snapshot=Snapshot('absent')
            else:raise recovery.Conflict('Unexpected migration observation type')
            approved[path]=snapshot
            if read_snapshot(path)!=snapshot:raise recovery.Conflict('Approved migration input drift: '+path)
        if not plan['files']:
            return {'status': 'completed', 'changes': [], 'context_keeper': 'unchanged'}
        tx = Transaction(lock_path=runtime.transaction_lock, backup_root=runtime.backups,
                         allowed_roots=[runtime.registry, *[Path(p) for p in plan['files']]],
                         operation=COMMAND)
        for path,snapshot in approved.items():
            if read_snapshot(path)!=snapshot:raise recovery.Conflict('Approved migration input drift: '+path)
        changes = [Change.file(p, bytes.fromhex(raw), expected=approved[p])
                   for p,raw in plan['files'].items()]
        allowed = paths.allowed_user_paths(config(), None, home=str(runtime.home))
        # The existing transaction retains byte-preserving backups and commits V last.
        result = registry.commit_registry(runtime.registry, plan['after_registry'], transaction=tx,
                    expected=approved[str(runtime.registry)], changes=changes,
                    allowed_user_paths=allowed,
                    previous=json.loads(approved[str(runtime.registry)].data))
        return {'status': 'completed', 'changes': result['changed'], 'context_keeper': 'unchanged'}


def cli(argv, *, home=None):
    parser = argparse.ArgumentParser(prog=COMMAND)
    parser.add_argument('command', choices=(COMMAND,))
    parser.add_argument('--project')
    parser.add_argument('--approval-file')
    parser.add_argument('--json',action='store_true')
    args = parser.parse_args(argv)
    home = Path.home() if home is None else Path(home)
    try:
        if args.approval_file:
            result = execute(json.loads(Path(args.approval_file).read_text()), home=home, project=args.project)
        else:
            plan = preview(home=home, project=args.project)
            result = {'status': 'approval_required', 'approval_required': True, 'plan': view(plan),
                      'approval': {'plan': view(plan), 'reference': '<user approval>', 'confirmed_at': '<UTC timestamp>'}}
        print(json.dumps(result, ensure_ascii=False))
        return recovery.exit_code(result)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'failed', 'errors': [{'code': getattr(exc,'code','policy_migration_failed'), 'message': str(exc)}]}, ensure_ascii=False))
        return 2


# Frozen baseline 8ffb66f generated bytes. Do not regenerate from new templates.
LEGACY_TEMPLATES = {'governance': '用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 Context Keeper 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。', 'contract': '读取契约：L0 恒读本索引 → 需要该主题时读其 L1 概要段 → 仍不足才读 L2 全文；相对链接以本文件所在目录解析，指向的内容缺失时停止相关操作。\n预算：L0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB；增加主题文件，不加长索引；摘要在记忆整理时手写，不自动生成。\n用户规则治理：公共内容只写公共指定文件（R/memories），Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 Context Keeper 记录库、不调用 Context Keeper 安装或初始化；首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 Context Keeper 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建；AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立，其默认建立遵本治理条款；非 Git 目录和 linked worktree 不触发。\n按需操作指南：/mem-sharing 菜单、绝对命令与公共记忆维护规则由主题《使用约定》承载（[使用约定](topics/使用约定.md)）；仅在用户明确 /mem-sharing、提出同义自然语言操作或默认项目接入前读取；该指南不回指其他菜单。\n', 'topic': '# 使用约定\n\n## L1 概要\n\n当前有效结论：公共记忆采用索引与主题文件，摘要由 Agent 手写，不自动生成。\n本主题即操作指南：/mem-sharing 菜单、绝对命令与公共记忆 L0/L1/L2 维护规则都在本文件正文，不回指其他菜单。\n待办：有新事实且获准记录时，更新对应主题结论与索引行。\n\n## L2 正文\n\n### /mem-sharing 菜单\n\n/mem-sharing 菜单:\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n批量启用项目记忆：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n整理用户记忆：公共与独有分开，逐条计划后一次批准 → 治理流程见 __CODE__/SKILL.md\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n给项目停用记忆：撤项目记忆入口并保留数据 → python3 __CODE__/scripts/agm.py remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n给项目启用记忆：显式恢复已停用项目或手动启用项目记忆 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --memory；新 Git 主 checkout 默认启用、disabled 不自动恢复语义不变\n\n### 公共记忆维护（L0/L1/L2）\n\nL0 索引一主题一行：主题名 + 一句话当前结论 + 链接，≤200 行 / 25KB；增加主题文件，不加长索引。\nL1 位于主题文件开头，简列当前有效结论与待办；L2 为全文及 references/ 手册，仅在概要不足时读取。\n摘要在记忆整理时手写，不自动生成。本指南内相对链接以本文件所在目录（topics/）解析；受管产品命令与 Skill 路径使用安装代码的绝对路径。\n\n### 项目接入约定\n\n规则驱动的默认接入由当前实际执行器发起：python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --agent <当前执行器>；执行前先检查项目政策，已 disabled 的项目跳过、不由本路径恢复（解除 disabled 须用户显式 --memory 并批准精确计划）；各 Agent 专属项目入口按当前执行器自身用户文件中的规则维护，公共指南不承载执行器专属细节。\n当前会话不得无参数顺带改动其他执行器的入口。用户显式授权的全体接入或批量启用沿用现有命令语义，本约定不改变任何命令默认。\n', 'old_contract': '读取契约：L0 恒读 → 需要时读该主题 L1 概要段 → 仍不足才读 L2 全文。\nL0 一主题一行：主题名 + 一句话当前结论 + 链接；索引 ≤200 行 / 25KB。\nL1 位于主题文件开头，简列当前有效结论与待办；L2 为全文及 references/ 手册。\n摘要在记忆整理时手写，不自动生成；增加主题文件，不加长索引。\n用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。\n仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。\n/mem-sharing 菜单:\n给项目启用记忆：为当前项目建立共享规则入口 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --memory\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n停用记忆：撤入口并保留数据 → python3 __CODE__/scripts/agm.py remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n批量启用记忆：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n\n\n', 'old_topic': '# 使用约定\n\n## L1 概要\n\n当前有效结论：公共记忆采用索引与主题文件，摘要由 Agent 手写，不自动生成。\n用户规则治理条款、兜底接入条款与 /mem-sharing 菜单全文见索引头部。\n待办：有新事实且获准记录时，更新对应主题结论与索引行。\n\n## L2 正文\n\n主题文件全文及 references/ 手册仅在概要不足时读取。\n用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。\n仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。\n/mem-sharing 菜单:\n给项目启用记忆：为当前项目建立共享规则入口 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --memory\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n停用记忆：撤入口并保留数据 → python3 __CODE__/scripts/agm.py remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n批量启用记忆：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n\n', 'old_codex': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\n用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。\n仅 Codex 首次实际使用时，按默认启用条款补缺失 AGENTS.md；已 disabled 项目不自动恢复。\n/mem-sharing 菜单:\n给项目启用记忆：为当前项目建立共享规则入口 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --memory\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n停用记忆：撤入口并保留数据 → python3 __CODE__/scripts/agm.py remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n批量启用记忆：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n\n<!-- mem-sharing:rules:end -->', 'old_workbuddy': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\n项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。\n用户规则治理:公共内容只写公共指定文件(R/memories)，Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。进入 Git 主 checkout 时，未登记项目默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，已有全文保留。默认启用不创建 CK 记录库、不调用 CK 安装或初始化；首次 /context-keeper 进入 CK 流程，首次保存按其流程确认位置。项目政策已为 disabled 时，默认流程不得重新启用入口、自动记录经历或初始化；已有 CK 自动规则也不能覆盖此政策。重新启用须用户显式执行 enable-memory；解除 disabled 须显式 enable-memory --memory 并批准精确计划。Claude 和 WorkBuddy 项目入口只由各自实际使用时补齐，其他执行器不得预建；非 Git 目录和 linked worktree 不触发。\n仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用、政策非 disabled 时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。\n/mem-sharing 菜单:\n给项目启用记忆：为当前项目建立共享规则入口 → python3 __CODE__/scripts/agm.py enable-memory --project <项目绝对路径> --memory\n添加新的 Agent：接入已安装的执行器 → python3 __CODE__/scripts/install.py --agent <执行器名>\n健康检查：只读检查已登记入口 → python3 __CODE__/scripts/agm.py check-memory --project <项目绝对路径>\n停用记忆：撤入口并保留数据 → python3 __CODE__/scripts/agm.py remove-memory --project <项目绝对路径>；仅禁自动项目经历记录、保留入口用 enable-memory --no-memory\n整理用户规则：公共与独有分开，逐条计划后一次批准 → 按 SKILL.md 治理流程执行\n批量启用记忆：扫描给定目录，汇总预览后一次批准 → python3 __CODE__/scripts/agm.py enable-memory-batch --directory <目录绝对路径>\n\n<!-- mem-sharing:rules:end -->', 'claude': '<!-- mem-sharing:claude-fallback:start -->\n仅 Claude Code 在本项目实际使用且项目已启用、政策非 disabled 时补引用：CLAUDE.md 不存在才创建仅含 @AGENTS.md 的文件；已有正文必须完整保留，仅追加缺失的 @AGENTS.md 引用行，重复执行不改字节。\n<!-- mem-sharing:claude-fallback:end -->', 'workbuddy': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\n项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。\n仅 WorkBuddy 在本项目实际使用产生原生 .workbuddy/memory 目录，且项目已启用、政策非 disabled 时，补顶部 AGENTS.md 指针；保留已有正文字节，不预建原生目录。\n<!-- mem-sharing:rules:end -->', 'codex': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\nCodex 原生读取共享项目规则基座 AGENTS.md，自身无额外专属项目入口；该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。\n<!-- mem-sharing:rules:end -->', 'dsh': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\nDeepSeek Harness 原生读取共享项目规则基座 AGENTS.md，自身无额外专属项目入口；该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。用户入口仅支持默认根 ~/.dsh/AGENTS.md，DSH_HOME 重定向时不接入。\n<!-- mem-sharing:rules:end -->', 'zcode': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\nZCode 原生读取共享项目规则基座 AGENTS.md 与用户级 ~/.zcode/AGENTS.md，自身无额外专属项目入口；该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。\n<!-- mem-sharing:rules:end -->', 'opencode': '<!-- mem-sharing:rules:start -->\n开始任务前读取并遵守 __INDEX__;读不到就说明。\nOpenCode 原生读取共享项目规则基座 AGENTS.md 与用户级 ~/.config/opencode/AGENTS.md，自身无额外专属项目入口；该基座默认建立遵公共治理条款，已 disabled 项目不自动恢复。仅支持默认配置根，配置被 XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR/OPENCODE_CONFIG 重定向或覆盖时不接入。\n<!-- mem-sharing:rules:end -->'}
