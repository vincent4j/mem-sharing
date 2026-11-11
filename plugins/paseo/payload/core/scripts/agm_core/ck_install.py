"""Optional, separately approved Context Keeper user installation.

The upstream main branch is fetched only after an explicit installation request.
Its own installer owns Context Keeper writes; no upstream code is bundled here.
"""
import ast
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import detect, entries, layout, legacy_import as legacy, migrate, paths, registry, user_entries, user_install
from .transaction import Snapshot, _atomic_file, read_snapshot, write_lock

OFFICIAL = 'https://github.com/vincent4j/context-keeper.git'
PROMPT = '为了让 Agent 在新会话中接着上次的项目进展、决策和经验继续工作，需要再安装 Context Keeper。是否为本机已安装的{agents}安装？回复“安装”或“跳过”。'
PRODUCT_LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'workbuddy': 'WorkBuddy',
                  'dsh': 'DeepSeek Harness', 'zcode': 'ZCode', 'opencode': 'OpenCode'}
UPSTREAM_ORDER = ('codex', 'claude', 'workbuddy', 'zcode', 'dsh', 'opencode')
LABELS = {agent: PRODUCT_LABELS[agent] for agent in UPSTREAM_ORDER}
ROOTS = {'codex': ['.agents/skills', '.codex/skills'],
         'claude': ['.claude/skills'], 'workbuddy': ['.workbuddy/skills'],
         'zcode': ['.zcode/skills', '.agents/skills'],
         'dsh': ['.dsh/skills', '.agents/skills'], 'opencode': ['.config/opencode/skills']}
RULES = {'codex': '.codex/AGENTS.md', 'claude': '.claude/CLAUDE.md',
         'workbuddy': '.workbuddy/MEMORY.md', 'zcode': '.zcode/AGENTS.md',
         'dsh': '.dsh/AGENTS.md', 'opencode': '.config/opencode/AGENTS.md'}


class CKError(ValueError):
    def __init__(self, message, code='ck_install_invalid'):
        super().__init__(message)
        self.code = code


def _fail(message, code='ck_install_invalid'):
    raise CKError(message, code)


def _git(root, *args):
    return subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args],
                          capture_output=True, check=True, timeout=120,
                          env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')).stdout


def _durable_source(root, runtime):
    # Context Keeper links must not point into replaceable product code, operation staging,
    # or an OS temporary directory.
    forbidden = [runtime.root, runtime.code, Path(__file__).resolve().parents[2],
                 runtime.home/'.local/share/mem-sharing-versions',
                 Path('/tmp').resolve(), Path('/private/var/folders')]
    if any(root == p.resolve() or p.resolve() in root.parents for p in forbidden):
        _fail('Context Keeper source must be a durable independent checkout', 'ck_source_unavailable')
    if any(p.name.startswith('.mem-sharing-install-') for p in [root, *root.parents]):
        _fail('Context Keeper source cannot be installation staging', 'ck_source_unavailable')


def _source(root, runtime, *, require_main=True):
    root = Path(root)
    if not root.is_absolute() or '..' in root.parts or root != root.resolve():
        _fail('Context Keeper source must be an absolute real checkout', 'ck_source_unavailable')
    _durable_source(root, runtime)
    if not (root/'.git').is_dir() or (root/'.git').is_symlink():
        _fail('Context Keeper source requires its own Git checkout', 'ck_source_unavailable')
    if _git(root, 'rev-parse', '--show-toplevel').decode().strip() != str(root):
        _fail('Context Keeper source is not a repository root', 'ck_source_drift')
    commit = _git(root, 'rev-parse', 'HEAD').decode().strip()
    if _git(root, 'remote', 'get-url', 'origin').decode().strip() != OFFICIAL:
        _fail('Context Keeper source must use the official origin', 'ck_source_drift')
    if require_main and commit != _git(root, 'rev-parse', 'refs/remotes/origin/main').decode().strip():
        _fail('Context Keeper source differs from fetched upstream main', 'ck_source_drift')
    if _git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        _fail('Context Keeper source has local changes', 'ck_source_drift')
    files = {}
    for raw in _git(root, 'ls-files', '-z').split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8')
        path = root/name
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            _fail('Context Keeper source contains an unsafe tracked file', 'ck_source_drift')
        content = path.read_bytes()
        if content != _git(root, 'show', 'HEAD:'+name):
            _fail('Context Keeper tracked bytes differ from HEAD', 'ck_source_drift')
        files[name] = {'sha256': legacy.digest(content), 'mode': stat.S_IMODE(path.stat().st_mode)}
    if not {'SKILL.md', 'scripts/install.py'} <= set(files):
        _fail('Context Keeper source lacks required files', 'ck_source_unavailable')
    return {'root': str(root), 'commit': commit, 'files': files}


def discover_source(home):
    found = set()
    for relative in sorted({r for roots in ROOTS.values() for r in roots}):
        candidate = Path(home)/relative/'context-keeper'
        if candidate.is_symlink() and candidate.exists():
            found.add(str(candidate.resolve()))
    if len(found) > 1:
        _fail('Multiple Context Keeper checkouts found; select --ck-source', 'ck_source_ambiguous')
    if not found:
        _fail('Provide --ck-source or prepare the latest official main checkout', 'ck_source_unavailable')
    return found.pop()


def prepare_source(request, source=None):
    """Acquire current main outside memSharing, only on explicit Context Keeper install intent."""
    runtime = user_install._runtime(request)
    if source is None:
        try:
            source = discover_source(runtime.home)
        except CKError as exc:
            if exc.code != 'ck_source_unavailable': raise
            source = runtime.home/'.local/share/context-keeper/source'
    root = Path(source)
    if not root.is_absolute() or root != root.resolve() or '..' in root.parts:
        _fail('Context Keeper source must be an absolute real path', 'ck_source_unavailable')
    _durable_source(root, runtime)
    if root.exists():
        # Do not overwrite local work or repurpose a different repository.
        if not (root/'.git').is_dir() or (root/'.git').is_symlink():
            _fail('Context Keeper destination is not an independent checkout', 'ck_source_drift')
        if _git(root, 'remote', 'get-url', 'origin').decode().strip() != OFFICIAL:
            _fail('Context Keeper source origin is not official', 'ck_source_drift')
        if _git(root, 'status', '--porcelain', '--untracked-files=all').strip():
            _fail('Context Keeper source has local changes', 'ck_source_drift')
        _source(root, runtime, require_main=False)
        _git(root, 'fetch', '--no-tags', 'origin', '+refs/heads/main:refs/remotes/origin/main')
        # Fast-forward only; never reset a user's divergent branch.
        _git(root, 'merge', '--ff-only', 'refs/remotes/origin/main')
    else:
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--single-branch', '--branch', 'main',
                        OFFICIAL, str(root)], check=True, capture_output=True, timeout=120)
    _source(root, runtime)
    return str(root)


def supported_agents(identity):
    """Inspect declared CLI flags as data, before executing upstream code."""
    tree = ast.parse((Path(identity['root'])/'scripts/install.py').read_text())
    flags = {arg.value for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument'
             for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
    return [a for a in UPSTREAM_ORDER if '--'+a in flags]


def _invoke(argv, home, runner=None):
    proc = (runner or subprocess.run)(argv, capture_output=True, text=True, timeout=120,
        env={'HOME': str(home), 'PATH': os.environ.get('PATH', os.defpath),
             'PYTHONDONTWRITEBYTECODE': '1'}, cwd=str(Path(argv[3]).parent.parent))
    if proc.returncode:
        _fail('Context Keeper installer returned nonzero; inspect preserved operation before retry', 'ck_upstream_failed')
    try:
        result = json.loads(proc.stdout, object_pairs_hook=registry._no_duplicates)
    except (ValueError, TypeError) as exc:
        raise CKError('Context Keeper returned an invalid JSON result', 'ck_result_unknown') from exc
    if not isinstance(result, dict):
        _fail('Context Keeper result is not an object', 'ck_result_unknown')
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
        _fail('Context Keeper installation requires the current completed main operation', 'ck_main_incomplete')
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
                # whole-file baseline is not ownership of later user/Context Keeper text.
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
        _fail('No installed executors detected; verify installation evidence before installing Context Keeper', 'ck_no_agents')
    identity = _source(source or discover_source(runtime.home), runtime)
    supported = [a for a in supported_agents(identity) if a in agents]
    skipped = [a for a in agents if a not in supported]
    if not supported:
        error = CKError('Current upstream installer supports none of the detected agents', 'ck_no_supported_agents')
        error.agents = agents
        raise error
    agents = supported
    skills = list(dict.fromkeys(str(runtime.home/r/'context-keeper') for a in agents for r in ROOTS[a]))
    rules = [str(runtime.home/RULES[a]) for a in agents]
    observations = {}
    for name in skills+rules:
        user_entries._require_real_parents(name, runtime.home)
        node = user_install._node(name)
        if name in rules and node['kind'] not in ('file', 'absent'):
            _fail('Context Keeper rule target must be a regular file', 'ck_target_conflict')
        if name in skills and node['kind'] != 'absent' and not (
                node['kind'] == 'symlink' and Path(name).resolve() == Path(identity['root'])):
            _fail('Context Keeper Skill target is occupied by another source', 'ck_target_conflict')
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
        _fail('Context Keeper preview scope differs from the exact installed supported executor set', 'ck_scope_mismatch')
    if _source(identity['root'], runtime) != identity or any(
            user_install._node(name) != node for name, node in observations.items()):
        _fail('Context Keeper preview changed source or installation targets', 'ck_preview_drift')
    journal = runtime.var/('ck-install-'+main_operation_id+'.json')
    if journal.exists() or journal.is_symlink():
        _fail('Context Keeper operation already has a journal; inspect it, never replay an uncertain operation', 'ck_operation_exists')
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
        _fail('Context Keeper rule marker is malformed', 'ck_readback_failed')
    if not raw.count(start):
        return None
    first, last = raw.index(start), raw.index(end)+len(end)
    if last <= first:
        _fail('Context Keeper rule marker order is invalid', 'ck_readback_failed')
    return first, last


def _verify_rule(before, after, agent):
    position = _rule_range(after, agent)
    if position is None:
        _fail('Context Keeper rule block missing after execution', 'ck_readback_failed')
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
        _fail('Context Keeper changed bytes outside its approved rule block', 'ck_readback_failed')


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
        _fail('Exact Context Keeper plan and real confirmation evidence required', 'approval_mismatch')
    request = request or {'home': plan['home'], 'platform_config': plan['platform_config']}
    runtime = user_install._runtime(request)
    if plan_context_keeper(request, plan['main_operation_id'], plan['source']['root'], runner=runner) != plan:
        _fail('Context Keeper source, scope or target changed after approval; preview again', 'approval_mismatch')
    with write_lock(runtime.lock):
        fresh = plan_context_keeper(request, plan['main_operation_id'], plan['source']['root'], runner=runner)
        if fresh != plan:
            _fail('Context Keeper source, scope or target changed after approval; preview again', 'approval_mismatch')
        before = {name: Path(name).read_bytes() if Path(name).exists() else None for name in plan['rule_files']}
        journal = Path(plan['journal'])
        # Keep original rule bytes in memory only for readback. This wrapper
        # never rolls Context Keeper back and need not persist users' rule text in a journal.
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
                _fail('Source or targets changed immediately before Context Keeper execution', 'ck_execution_drift')
            result = _invoke(plan['argv'], runtime.home, runner)
            if 'approval_required' in result and type(result['approval_required']) is not bool:
                _fail('Context Keeper approval_required must be a boolean', 'ck_result_unknown')
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
                    _fail('Context Keeper result does not prove the approved user scope', 'ck_scope_mismatch')
                for name in plan['skill_entries']:
                    if not Path(name).is_symlink() or Path(name).resolve() != Path(plan['source']['root']):
                        _fail('Context Keeper Skill link readback failed', 'ck_readback_failed')
                for agent, name in zip(plan['agents'], plan['rule_files']):
                    if Path(name).is_symlink() or not Path(name).is_file():
                        _fail('Context Keeper rule readback is not a regular file', 'ck_readback_failed')
                    _verify_rule(before[name], Path(name).read_bytes(), agent)
                if legacy.digest(runtime.registry.read_bytes()) != plan['registry_sha256']:
                    _fail('Context Keeper changed the main registry', 'ck_readback_failed')
                user_entries._preflight_machine_units(registry.load_registry(runtime.registry,
                    allowed_user_paths=paths.allowed_user_paths(request['platform_config'], None, home=request['home'])))
                _source(plan['source']['root'], runtime)
                record['status'] = 'configured'
            record['result'] = result
        except Exception as exc:
            record['status'] = 'unknown'
            record['errors'] = [{'code': getattr(exc, 'code', 'ck_result_unknown'),
                                 'message': 'Context Keeper did not complete verified installation; inspect journal before retry'}]
        try:
            record['after'] = {name: user_install._node(name) for name in plan['skill_entries']+plan['rule_files']}
        except (ValueError, OSError):
            record['status'] = 'unknown'
            record['errors'] = [{'code': 'ck_readback_failed', 'message': 'Context Keeper target metadata cannot be verified; inspect journal'}]
        save()
    # Upstream remains the independent installer. Sharing is a later user choice.
    sharing = {'status': 'not_checked', 'eligible_agents': [], 'protected_agents': []}
    if record['status'] == 'configured':
        from . import ck_common_trigger as common
        sharing['status'] = 'pending_selection'
        for agent, name in zip(plan['agents'], plan['rule_files']):
            try:
                recognized = common.recognize(Path(name).read_bytes(), agent)
            except (ValueError, OSError):
                recognized = None
            sharing['eligible_agents' if recognized else 'protected_agents'].append(agent)
        sharing['next_action'] = 'organize-user-memory; present exact common trigger candidate and await selection'
    return {'command': 'install-context-keeper', 'status': record['status'],
            'common_trigger_sharing': sharing,
            'agents': list(plan['agents']),
            'skipped_upstream_agents': list(plan['skipped_upstream_agents']),
            'main_operation_id': plan['main_operation_id'], 'journal': str(journal),
            'approval_required': record['status'] == 'approval_required',
            'errors': record.get('errors', []), 'runtime_acceptance': 'pending'}


def tail(report, request, *, stdin=None, stderr=None):
    """Only the explicit TTY reply 安装 consents; a newline or EOF never does."""
    if report.get('status') != 'completed':
        return report
    if report.get('fusion', {}).get('status') not in (None, 'completed', 'declined', 'unchanged'):
        report['context_keeper'] = {'status':'deferred', 'reason':'user_memory_pending'}
        return report
    stdin, stderr = stdin or sys.stdin, stderr or sys.stderr
    try:
        if not stdin.isatty():
            agents = installed_agents(request)
            report['context_keeper'] = {
                'status': 'pending_selection',
                'reason': 'user_choice_required',
                'agents': agents,
                'prompt': PROMPT.format(agents='、'.join(PRODUCT_LABELS[a] for a in agents)),
                'choices': ['安装', '跳过'],
                'next_action': '向用户展示 prompt，等待实际选择；尚未选择不能视为跳过。',
            }
            return report
        runtime = user_install._runtime(request)
        data = registry.load_registry(runtime.registry, allowed_user_paths=paths.allowed_user_paths(
            request['platform_config'], None, home=request['home']))
        connected_all = installed_agents(request)
        # 主产品接入名单按六家 PRODUCT_LABELS 全量报告;Context Keeper 上游不支持者单独说明。
        connected = [PRODUCT_LABELS[a] for a in connected_all if a in PRODUCT_LABELS]
        message = '公共用户记忆流程已结束。'
        print(message, file=stderr, flush=True)
        print(PROMPT.format(agents='、'.join(connected)), file=stderr, flush=True)
        if stdin.readline().strip() != '安装':
            report['context_keeper'] = {'status': 'skipped', 'reason': 'not_consented'}
            return report
        _scene(request, data['product']['last_operation_id'])
        source = prepare_source(request)
        plan = plan_context_keeper(request, data['product']['last_operation_id'], source)
        if plan['skipped_upstream_agents']:
            print('当前 Context Keeper 上游尚未支持：'+ '、'.join(
                PRODUCT_LABELS[item['agent']] for item in plan['skipped_upstream_agents'])+'；这些执行器已跳过。', file=stderr)
        evidence = {'confirmed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'reference': '用户回复：安装；已展示本机实际安装名单：'+ '、'.join(connected)}
        report['context_keeper'] = execute_context_keeper(plan, dict(plan, **evidence), request=request)
        if report['context_keeper']['status'] == 'configured':
            print('已安装 Context Keeper。可在任意项目里输入 /context-keeper；首次保存按 Context Keeper 流程确认记录库位置，记录库随项目 Git 管理，所有 Agent 共用。', file=stderr)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        if getattr(exc, 'code', None) == 'ck_no_supported_agents':
            print('当前 Context Keeper 上游支持范围不包含这些执行器，已跳过。', file=stderr)
            report['context_keeper'] = {'status': 'skipped', 'reason': 'upstream_unsupported',
                'skipped_upstream_agents': [{'agent': a, 'reason': 'upstream_unsupported'} for a in exc.agents]}
            return report
        report['context_keeper'] = {'status': 'unavailable', 'errors': [
            {'code': getattr(exc, 'code', 'ck_install_unavailable'), 'message': str(exc)}],
            'next_action': 'Run scripts/install.py --context-keeper to fetch current official main and preview again'}
    return report
