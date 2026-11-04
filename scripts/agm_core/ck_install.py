"""Optional, separately approved Context Keeper user installation.

Only the pinned, clean upstream installer is executed. No download, project
initialization, provider probe, or automatic recovery belongs to this module.
"""
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import detect, entries, layout, legacy_import as legacy, migrate, paths, registry, user_entries, user_install
from .transaction import Snapshot, _atomic_file, read_snapshot, write_lock

PIN = '695074ee4b6ddb9999be858093f833d6377bd641'
PROMPT = '为了让 Agent 在新会话中记住项目进度、决策和经验，接着上次的工作继续，需要另外安装 Context Keeper。是否为本机已安装的{agents}安装？回复“安装”或“跳过”。'
# 上游安装器(pinned PIN)仅认这三家(LABELS/ROOTS/RULES 的键集即上游 --agent
# flags)。dsh/zcode/opencode 已接入时:不冒支持、不传上游未知 flags、不改上游
# ——在计划里明确列为 skipped(upstream_unsupported)并照常为旧三家安装;三家均
# 不在场才显式拒绝,该拒绝不回滚也不影响主产品安装结果。
LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'workbuddy': 'WorkBuddy'}
# 主产品接入名单(六家)独立于上游 LABELS:tail 的"已装上入口"描述本产品接入
# 范围,不得用上游支持集过滤后冒称全部接入;CK 上游不支持者另行单独说明。
PRODUCT_LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'workbuddy': 'WorkBuddy',
                  'dsh': 'DeepSeek Harness', 'zcode': 'ZCode', 'opencode': 'OpenCode'}
ROOTS = {'codex': ['.agents/skills', '.codex/skills'],
         'claude': ['.claude/skills'], 'workbuddy': ['.workbuddy/skills']}
RULES = {'codex': '.codex/AGENTS.md', 'claude': '.claude/CLAUDE.md',
         'workbuddy': '.workbuddy/MEMORY.md'}


class CKError(ValueError):
    def __init__(self, message, code='ck_install_invalid'):
        super().__init__(message)
        self.code = code


def _fail(message, code='ck_install_invalid'):
    raise CKError(message, code)


def _git(root, *args):
    return subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args],
                          capture_output=True, check=True,
                          env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')).stdout


def _durable_source(root, runtime):
    # CK links must not point into replaceable product code, operation staging,
    # or an OS temporary directory. Explicit sources are never downloaded here.
    forbidden = [runtime.root, runtime.code,
                 runtime.home/'.local/share/mem-sharing-versions',
                 Path('/tmp').resolve(), Path('/private/var/folders')]
    if any(root == p.resolve() or p.resolve() in root.parents for p in forbidden):
        _fail('CK source must be a durable independent checkout', 'ck_source_unavailable')
    if any(p.name.startswith('.mem-sharing-install-') for p in [root, *root.parents]):
        _fail('CK source cannot be installation staging', 'ck_source_unavailable')


def _source(root, runtime):
    root = Path(root)
    if not root.is_absolute() or '..' in root.parts or root != root.resolve():
        _fail('CK source must be an absolute real checkout', 'ck_source_unavailable')
    _durable_source(root, runtime)
    if not (root/'.git').is_dir() or (root/'.git').is_symlink():
        _fail('CK source requires its own Git checkout', 'ck_source_unavailable')
    if _git(root, 'rev-parse', '--show-toplevel').decode().strip() != str(root):
        _fail('CK source is not a repository root', 'ck_source_drift')
    if _git(root, 'rev-parse', 'HEAD').decode().strip() != PIN:
        _fail('CK source HEAD differs from the integration pin', 'ck_source_drift')
    if _git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        _fail('CK source has local changes', 'ck_source_drift')
    files = {}
    for raw in _git(root, 'ls-files', '-z').split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8')
        path = root/name
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            _fail('CK source contains an unsafe tracked file', 'ck_source_drift')
        content = path.read_bytes()
        if content != _git(root, 'show', 'HEAD:'+name):
            _fail('CK tracked bytes differ from HEAD', 'ck_source_drift')
        files[name] = {'sha256': legacy.digest(content), 'mode': stat.S_IMODE(path.stat().st_mode)}
    if not {'SKILL.md', 'scripts/install.py'} <= set(files):
        _fail('CK source lacks required files', 'ck_source_unavailable')
    return {'root': str(root), 'commit': PIN, 'files': files}


def discover_source(home):
    found = set()
    for relative in sorted({r for roots in ROOTS.values() for r in roots}):
        candidate = Path(home)/relative/'context-keeper'
        if candidate.is_symlink() and candidate.exists():
            found.add(str(candidate.resolve()))
    if len(found) != 1:
        _fail('Provide --ck-source /absolute/durable/context-keeper (clean checkout at '+PIN+'); no source is downloaded automatically', 'ck_source_unavailable')
    return found.pop()


def _invoke(argv, home, runner=None):
    proc = (runner or subprocess.run)(argv, capture_output=True, text=True, timeout=120,
        env={'HOME': str(home), 'PATH': os.environ.get('PATH', os.defpath),
             'PYTHONDONTWRITEBYTECODE': '1'}, cwd=str(Path(argv[3]).parent.parent))
    if proc.returncode:
        _fail('CK installer returned nonzero; inspect preserved operation before retry', 'ck_upstream_failed')
    try:
        result = json.loads(proc.stdout, object_pairs_hook=registry._no_duplicates)
    except (ValueError, TypeError) as exc:
        raise CKError('CK returned an invalid JSON result', 'ck_result_unknown') from exc
    if not isinstance(result, dict):
        _fail('CK result is not an object', 'ck_result_unknown')
    return result


def installed_agents(request):
    facts = detect.detect_agents(request['platform_config'], home=request['home'],
        **{k:request[k] for k in ('search_paths','app_directories','user_candidates') if k in request})
    return [a for a in paths.AGENT_ORDER if facts['agents'].get(a, {}).get('status') == 'installed']


def _scene(request, main_operation_id):
    migrate._op(main_operation_id)
    runtime = user_install._runtime(request)
    layout.from_request(request)  # Same pending-upgrade fence as project writers.
    allowed = paths.allowed_user_paths(request['platform_config'], None, home=request['home'])
    data = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    product = data['product']
    if not product or product['installation_status'] != 'complete' or product['last_operation_id'] != main_operation_id:
        _fail('CK installation requires the current completed main operation', 'ck_main_incomplete')
    main_journal = runtime.home/('.mem-sharing-install-'+main_operation_id)/'journal.json'
    user_install._real_chain(main_journal, runtime.home)
    saved = migrate._json(main_journal)
    if not isinstance(saved, dict) or saved.get('status') != 'committed':
        _fail('Main journal is not completed; recover the main operation first', 'ck_main_incomplete')
    command = saved['plan'].get('command') if isinstance(saved.get('plan'), dict) else None
    if command == 'install-machine':
        saved, bound = user_install._load_journal(main_journal)
    elif command == 'upgrade-machine':
        from . import upgrade
        saved, bound = upgrade._load_journal(main_journal)
    else:
        _fail('Unknown completed main operation', 'ck_main_incomplete')
    if bound != runtime or saved['operation_id'] != main_operation_id:
        _fail('Main journal identity differs from the active product', 'ck_main_incomplete')
    user_install._code_matches(runtime, product)
    user_entries._preflight_machine_units(data)
    agents = [a for a in paths.AGENT_ORDER if a in data['machine']['agents']
              and data['machine']['agents'][a]['installation']['status'] == 'installed']
    if set(agents) != set(data['machine']['agents']):
        _fail('Machine agent entries are incomplete', 'ck_main_incomplete')
    static = user_entries.connection_status(runtime, request['platform_config'], data, agents)
    if any(fact['status'] != 'connected' for fact in static.values()):
        _fail('Connected agent lacks a verified public-memory entry', 'ck_main_incomplete')
    for agent in agents:
        objects = [obj for obj in data['machine']['objects'].values() if agent in obj['agents']]
        if not objects:
            _fail('Connected agent has no registered machine entry', 'ck_main_incomplete')
        for obj in objects:
            target = Path(obj['path'])
            if target.is_symlink() or not target.is_file():
                _fail('Connected agent entry is missing or drifted', 'ck_main_incomplete')
            raw = target.read_bytes()
            if obj['kind'] == 'file' and str(target).endswith('/skills/mem-sharing/SKILL.md'):
                intact = obj['ownership'] == 'created' and legacy.digest(raw) == obj['fingerprint']['value']
            elif obj['kind'] == 'import':
                # Machine Claude imports the public memory index. Its historic
                # whole-file baseline is not ownership of later user/CK text.
                line = ('@'+str(runtime.root/'memories/MEMORY.md')).encode()
                intact = sum(part.strip() == line for part in raw.splitlines()) == 1
            elif obj['kind'] in ('block', 'user_convention'):
                intact = entries.block_fingerprint(raw, **user_entries._marker_args(obj['marker'])) == obj['fingerprint']['value']
            else:
                intact = False
            if not intact:
                _fail('Connected agent entry is missing or drifted', 'ck_main_incomplete')
    return runtime, data, installed_agents(request)


def plan_context_keeper(request, main_operation_id, source=None, *, runner=None):
    """Read-only plan, independent of the earlier main-product approval."""
    runtime, data, agents = _scene(request, main_operation_id)
    if not agents:
        _fail('No installed executors detected; verify installation evidence before installing CK', 'ck_no_agents')
    supported = [a for a in agents if a in LABELS]
    skipped = [a for a in agents if a not in LABELS]
    if not supported:
        _fail('已接入执行器(%s)均不在 Context Keeper 上游安装器支持范围(仅 Codex/Claude Code/'
              'WorkBuddy);明确跳过 CK 用户级安装,不影响本产品接入,也不修改上游' % ', '.join(agents),
              'ck_no_supported_agents')
    agents = supported
    identity = _source(source or discover_source(runtime.home), runtime)
    skills = [str(runtime.home/r/'context-keeper') for a in agents for r in ROOTS[a]]
    rules = [str(runtime.home/RULES[a]) for a in agents]
    observations = {}
    for name in skills+rules:
        user_entries._require_real_parents(name, runtime.home)
        node = user_install._node(name)
        if name in rules and node['kind'] not in ('file', 'absent'):
            _fail('CK rule target must be a regular file', 'ck_target_conflict')
        if name in skills and node['kind'] != 'absent' and not (
                node['kind'] == 'symlink' and Path(name).resolve() == Path(identity['root'])):
            _fail('CK Skill target is occupied by another source', 'ck_target_conflict')
        observations[name] = node
        parent = Path(name).parent
        while parent != runtime.home:
            observations[str(parent)] = user_install._node(parent)
            parent = parent.parent
    main_journal = runtime.home/('.mem-sharing-install-'+main_operation_id)/'journal.json'
    observations[str(main_journal)] = user_install._node(main_journal)
    observations[str(runtime.home/'.mem-sharing-upgrade.json')] = {'kind': 'absent'}
    interpreter = str(Path(sys.executable).resolve())
    argv = [interpreter, '-I', '-B', str(Path(identity['root'])/'scripts/install.py')]+['--'+a for a in agents]
    preview = _invoke(argv, runtime.home, runner)
    if preview.get('approval_required') is not True or preview.get('skill_entries') != skills or preview.get('rule_files') != rules:
        _fail('CK preview scope differs from the exact installed supported executor set', 'ck_scope_mismatch')
    if _source(identity['root'], runtime) != identity or any(
            user_install._node(name) != node for name, node in observations.items()):
        _fail('CK preview changed source or installation targets', 'ck_preview_drift')
    journal = runtime.var/('ck-install-'+main_operation_id+'.json')
    if journal.exists() or journal.is_symlink():
        _fail('CK operation already has a journal; inspect it, never replay an uncertain operation', 'ck_operation_exists')
    plan = {'schema_version': 1, 'command': 'install-context-keeper', 'scope': 'user',
        'main_operation_id': main_operation_id, 'home': str(runtime.home),
        'platform_config': request['platform_config'], 'registry_path': str(runtime.registry),
        'registry_sha256': legacy.digest(runtime.registry.read_bytes()), 'agents': agents,
        'skipped_upstream_agents': [{'agent': a, 'reason': 'upstream_unsupported'} for a in skipped],
        'main_journal': {'path': str(main_journal), 'fingerprint': observations[str(main_journal)]},
        'source': identity, 'preview_argv': argv, 'argv': argv+['--approved'],
        'interpreter': {'path': interpreter, 'fingerprint': user_install._node(interpreter)},
        'upstream_preview': preview, 'observations': observations,
        'skill_entries': skills, 'rule_files': rules, 'journal': str(journal),
        'metadata_scopes': [str(journal)],
        'changes': [{'path': p, 'before': observations[p], 'operation': 'upstream_user_install'} for p in skills+rules]}
    plan['plan_sha256'] = legacy.digest(legacy.encoded(plan))
    return plan


def _rule_range(raw, agent):
    middle = ':workbuddy' if agent == 'workbuddy' else ''
    start = ('<!-- context-keeper'+middle+':start -->').encode()
    end = ('<!-- context-keeper'+middle+':end -->').encode()
    if raw.count(start) != raw.count(end) or raw.count(start) > 1:
        _fail('CK rule marker is malformed', 'ck_readback_failed')
    if not raw.count(start):
        return None
    first, last = raw.index(start), raw.index(end)+len(end)
    if last <= first:
        _fail('CK rule marker order is invalid', 'ck_readback_failed')
    return first, last


def _verify_rule(before, after, agent):
    position = _rule_range(after, agent)
    if position is None:
        _fail('CK rule block missing after execution', 'ck_readback_failed')
    first, last = position
    block = after[first:last]
    old = _rule_range(before or b'', agent)
    if before is None:
        expected = block+b'\n\n'
    elif old:
        a, b = old
        expected = (block+b'\n\n'+before[:a]+before[b:] if agent == 'workbuddy' and a
                    else before[:a]+block+before[b:])
    elif agent == 'workbuddy':
        expected = block+b'\n\n'+before
    else:
        expected = before+(b'\n' if before.endswith(b'\n') else b'\n\n')+block+b'\n'
    if after != expected or (agent == 'workbuddy' and first != 0):
        _fail('CK changed bytes outside its approved rule block', 'ck_readback_failed')


def execute_context_keeper(plan, approval, *, request=None, runner=None):
    # Same exact-evidence contract as the CLI, without importing its entrypoint.
    evidence = {k: approval.get(k) for k in ('confirmed_at', 'reference')}
    valid = all(isinstance(v, str) and v.strip() and not v.startswith('<') for v in evidence.values())
    if valid:
        try:
            registry._evidence(evidence)  # Strict ledger format: UTC 'Z' suffix only.
        except ValueError:
            valid = False
    if not valid or approval != dict(plan, **evidence):
        _fail('Exact CK plan and real confirmation evidence required', 'approval_mismatch')
    request = request or {'home': plan['home'], 'platform_config': plan['platform_config']}
    runtime = user_install._runtime(request)
    if plan_context_keeper(request, plan['main_operation_id'], plan['source']['root'], runner=runner) != plan:
        _fail('CK source, scope or target changed after approval; preview again', 'approval_mismatch')
    with write_lock(runtime.lock):
        fresh = plan_context_keeper(request, plan['main_operation_id'], plan['source']['root'], runner=runner)
        if fresh != plan:
            _fail('CK source, scope or target changed after approval; preview again', 'approval_mismatch')
        before = {name: Path(name).read_bytes() if Path(name).exists() else None for name in plan['rule_files']}
        journal = Path(plan['journal'])
        # Keep original rule bytes in memory only for readback. This wrapper
        # never rolls CK back and need not persist users' rule text in a journal.
        record = {'plan': plan, 'approval': approval, 'status': 'running'}
        expected_journal = Snapshot('absent')
        def save():
            nonlocal expected_journal
            _atomic_file(journal, legacy.encoded(record), 0o600, expected=expected_journal)
            directory = os.open(journal.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            expected_journal = read_snapshot(journal)
        save()  # Durable intent before invoking any upstream writer.
        try:
            if (_source(plan['source']['root'], runtime) != plan['source'] or
                    user_install._node(plan['interpreter']['path']) != plan['interpreter']['fingerprint'] or
                    any(user_install._node(name) != node for name, node in plan['observations'].items())):
                _fail('Source or targets changed immediately before CK execution', 'ck_execution_drift')
            result = _invoke(plan['argv'], runtime.home, runner)
            if 'approval_required' in result and type(result['approval_required']) is not bool:
                _fail('CK approval_required must be a boolean', 'ck_result_unknown')
            if result.get('approval_required') is True:
                record['status'] = 'approval_required'
            else:
                if (not {'scope', 'project', 'configured_agents', 'installed', 'removed', 'bridges'} <= set(result) or
                    result.get('scope') != 'user' or result.get('project') is not None or
                    result.get('configured_agents') != [LABELS[a] for a in plan['agents']] or
                    result.get('installed') != plan['skill_entries'] or result.get('removed') != [] or
                    not isinstance(result.get('bridges'), list) or any(not isinstance(item, dict) or
                        item.get('action') not in ('created', 'unchanged', 'updated', 'prepended', 'appended')
                        for item in result.get('bridges', [])) or
                    [item.get('file') for item in result.get('bridges', [])] != plan['rule_files']):
                    _fail('CK result does not prove the approved user scope', 'ck_scope_mismatch')
                for name in plan['skill_entries']:
                    if not Path(name).is_symlink() or Path(name).resolve() != Path(plan['source']['root']):
                        _fail('CK Skill link readback failed', 'ck_readback_failed')
                for agent, name in zip(plan['agents'], plan['rule_files']):
                    if Path(name).is_symlink() or not Path(name).is_file():
                        _fail('CK rule readback is not a regular file', 'ck_readback_failed')
                    _verify_rule(before[name], Path(name).read_bytes(), agent)
                if legacy.digest(runtime.registry.read_bytes()) != plan['registry_sha256']:
                    _fail('CK changed the main registry', 'ck_readback_failed')
                user_entries._preflight_machine_units(registry.load_registry(runtime.registry,
                    allowed_user_paths=paths.allowed_user_paths(request['platform_config'], None, home=request['home'])))
                _source(plan['source']['root'], runtime)
                record['status'] = 'configured'
            record['result'] = result
        except Exception as exc:
            record['status'] = 'unknown'
            record['errors'] = [{'code': getattr(exc, 'code', 'ck_result_unknown'),
                                 'message': 'CK did not complete verified installation; inspect journal before retry'}]
        try:
            record['after'] = {name: user_install._node(name) for name in plan['skill_entries']+plan['rule_files']}
        except (ValueError, OSError):
            record['status'] = 'unknown'
            record['errors'] = [{'code': 'ck_readback_failed', 'message': 'CK target metadata cannot be verified; inspect journal'}]
        save()
    return {'command': 'install-context-keeper', 'status': record['status'],
            'agents': list(plan['agents']),
            'skipped_upstream_agents': list(plan['skipped_upstream_agents']),
            'main_operation_id': plan['main_operation_id'], 'journal': str(journal),
            'approval_required': record['status'] == 'approval_required',
            'errors': record.get('errors', []), 'runtime_acceptance': 'pending'}


def tail(report, request, *, stdin=None, stderr=None):
    """Only a real newline from a TTY consents; main completion is independent."""
    if report.get('status') != 'completed':
        return report
    if report.get('fusion', {}).get('status') not in (None, 'completed', 'declined', 'unchanged'):
        report['context_keeper'] = {'status':'deferred', 'reason':'user_memory_pending'}
        return report
    stdin, stderr = stdin or sys.stdin, stderr or sys.stderr
    if not stdin.isatty():
        report['context_keeper'] = {'status': 'skipped', 'reason': 'non_interactive',
            'next_action': 'Run scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper'}
        return report
    try:
        runtime = user_install._runtime(request)
        data = registry.load_registry(runtime.registry, allowed_user_paths=paths.allowed_user_paths(
            request['platform_config'], None, home=request['home']))
        connected_all = installed_agents(request)
        # 主产品接入名单按六家 PRODUCT_LABELS 全量报告;CK 上游不支持者单独说明。
        connected = [PRODUCT_LABELS[a] for a in connected_all if a in PRODUCT_LABELS]
        ck_skipped = [a for a in connected_all if a not in LABELS]
        message = '公共用户记忆流程已结束。'
        if ck_skipped:
            message += '（%s 不在 Context Keeper 上游支持范围，跳过其 CK 用户级安装，不影响本产品接入。）' \
                % '、'.join(PRODUCT_LABELS.get(a, a) for a in ck_skipped)
        print(message, file=stderr, flush=True)
        print(PROMPT.format(agents='、'.join(connected)), file=stderr, flush=True)
        failure = None
        try:
            plan = plan_context_keeper(request, data['product']['last_operation_id'])
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            failure = exc
            print('CK 安装预览暂不可用：'+str(exc), file=stderr, flush=True)
        if failure is None:
            print('CK 预览：'+json.dumps({'agents': plan['agents'], 'source': plan['source']['root'],
                'skipped_upstream_agents': plan['skipped_upstream_agents'],
                'commit': plan['source']['commit'], 'files': plan['skill_entries']+plan['rule_files'],
                'plan_sha256': plan['plan_sha256']}, ensure_ascii=False), file=stderr, flush=True)
        if stdin.readline().strip() != '安装':
            report['context_keeper'] = {'status': 'skipped', 'reason': 'not_consented'}
            return report
        if failure is not None:
            raise failure
        evidence = {'confirmed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'reference': '用户回复：安装；已展示本机实际安装名单：'+ '、'.join(connected)}
        report['context_keeper'] = execute_context_keeper(plan, dict(plan, **evidence), request=request)
        if report['context_keeper']['status'] == 'configured':
            print('已安装 Context Keeper。可在任意项目里输入 /context-keeper；首次保存按 CK 流程确认记录库位置，记录库随项目 Git 管理，所有 Agent 共用。', file=stderr)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        if getattr(exc, 'code', None) == 'ck_no_supported_agents':
            report['context_keeper'] = {'status': 'skipped', 'reason': 'upstream_unsupported',
                'skipped_upstream_agents': [{'agent': a, 'reason': 'upstream_unsupported'} for a in ck_skipped]}
            return report
        report['context_keeper'] = {'status': 'unavailable', 'errors': [
            {'code': getattr(exc, 'code', 'ck_install_unavailable'), 'message': str(exc)}],
            'next_action': 'Run scripts/install.py --context-keeper --ck-source /absolute/durable/context-keeper after supplying a clean source at '+PIN}
    return report
