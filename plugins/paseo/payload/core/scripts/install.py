#!/usr/bin/env python3
"""Explicit machine installer. Preview is read-only; approvals bind exact plans.

Acquisition is a separate approved operation. It never updates a checkout and
never runs downloaded code. Network execution belongs to the invoking agent's
approved acquisition route; this CLI supplies a pinned Git transport for users.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import detect, legacy_import as legacy, migrate, paths, registry
from agm_core import upgrade, user_entries, user_install, ck_install, public_layout, plugin_release, versions

OFFICIAL = 'https://github.com/vincent4j/mem-sharing'
LEGACY_OFFICIAL = 'https://github.com/vincent4j/agent-group-memory'  # 远程改名前的旧 URL,仍视作官方来源
# Closed release manifest: the seven docs a C-side install can click through,
# plus scripts/. Acceptance records, Context Keeper worklogs and local state stay source-only.
SHIPPED_DOCS = plugin_release.SHIPPED_DOCS


def _managed_source(name):
    return plugin_release.managed_source(name)
INPUT_KEYS = {'source', 'conversions', 'legacy_registries', 'legacy_source_commits',
              'evidence_files', 'legacy_identity',
              # Explicit detection inputs: keep cold-CLI tests and M4-09/M4-10-A
              # rehearsals deterministic on machines with real executors installed.
              'search_paths', 'app_directories', 'user_candidates'}


class InstallError(ValueError):
    def __init__(self, message, code='invalid_arguments'):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InstallError(message)


def _absolute(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise InstallError('An absolute normalized path is required: ' + str(value))
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallError('Duplicate JSON key: ' + key, 'approval_invalid')
        result[key] = value
    return result


def _json(path):
    value = json.loads(_absolute(path).read_text(), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise InstallError('JSON object required')
    return value


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'), check=True)
    return result.stdout.strip()


def checkout_version(root, explicit=None):
    """Read tracked core metadata as data, never execute checkout code."""
    root = _absolute(root).resolve()
    name = 'scripts/core-version.json'
    tracked = _git(root, 'ls-files', '-z').split('\0')
    if name not in tracked:
        if explicit: return explicit  # Historical explicit-source contract.
        raise InstallError('Core version metadata missing; provide --version for this historical source')
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise InstallError('Core version metadata is not a regular tracked file', 'source_drift')
    data = _json(path)
    if set(data) != {'version'} or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', str(data['version'])):
        raise InstallError('Invalid core version metadata', 'source_drift')
    if explicit and explicit != data['version']:
        raise InstallError('Explicit version conflicts with fixed core source metadata', 'source_drift')
    return data['version']


def checkout_source(root, commit, version):
    """Read a user checkout; derive a closed product manifest from tracked files."""
    root = _absolute(root).resolve()
    actual = _git(root, 'rev-parse', 'HEAD')
    commit = commit or actual
    if actual != commit or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise InstallError('Checkout HEAD must equal the full pinned commit', 'source_drift')
    if _git(root, '-c', 'core.fsmonitor=false', 'status', '--porcelain'):
        raise InstallError('Dirty checkout: preserve it and supply a clean verified source', 'source_drift')
    names = _git(root, 'ls-files', '-z').split('\0')
    if plugin_release.ROOT_MANIFEST in names:
        raise InstallError('Release checkout requires the durable export stage; use the installer --source route', 'release_export_required')
    files = {}
    for name in names:
        if not name or not _managed_source(name):
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise InstallError('Nonregular managed source: ' + name, 'source_drift')
        files[name] = legacy.digest(path.read_bytes())
    origin = subprocess.run(['git', '-C', str(root), 'config', '--get', 'remote.origin.url'],
                            capture_output=True, text=True).stdout.strip()
    # Never echo an arbitrary remote URL: it may contain credentials. A local
    # checkout without the official origin is explicitly recorded as local.
    url = OFFICIAL if origin in (OFFICIAL, OFFICIAL+'.git', LEGACY_OFFICIAL, LEGACY_OFFICIAL+'.git') else 'local-checkout:' + root.as_uri()
    source = {'root': str(root), 'url': url, 'commit': commit, 'version': version, 'files': files}
    user_install._source({'source': source})
    return source


def active_source(home):
    """Resolve only this verified active C/V pair to its receipted durable source."""
    config = paths.select_platform(paths.load_agents_table(), sys.platform)
    runtime = user_install._runtime({'home': home})
    if Path(__file__).resolve() != runtime.code / 'scripts/install.py':
        raise InstallError('No explicit source: invoke the verified active installer or provide --source-manifest')
    allowed = paths.allowed_user_paths(config, None, home=home)
    data = registry.require_installed(registry.load_registry(runtime.registry, allowed_user_paths=allowed))
    product = data['product']
    user_install._code_matches(runtime, product)
    destination = runtime.home/'.local/share/mem-sharing-sources'/product['product_code_version']/product['source']['tree_sha256']
    user_install._real_chain(destination, runtime.home)
    if not os.path.lexists(destination):
        # Direct-checkout installs already retain a sealed version inventory.
        # Reuse verified active bytes; never invent a plugin export receipt.
        marker = _json(runtime.code/'.agm-code-manifest.json')
        source = dict(root=str(runtime.code), url=product['source']['url'],
                      commit=product['source']['commit'], version=product['product_code_version'],
                      files={item['path']: item['sha256'] for item in marker['files']})
        checked, files = user_install._source({'source': source})
        if {k: checked[k] for k in ('url', 'commit', 'tree_sha256')} != product['source']:
            raise InstallError('Active source differs from registered fixed identity', 'source_drift')
        try:
            versions.verify(runtime, versions.descriptor(runtime, checked, files))
        except ValueError as exc:
            raise InstallError('Registered source inventory unavailable or drifted: '+str(exc), 'source_drift') from None
        return source
    manifest = plugin_release._read_manifest(destination/'release.json')
    if (manifest['source']['version'] != product['product_code_version'] or
            {k: manifest['source'][k] for k in ('url','commit','tree_sha256')} != product['source']):
        raise InstallError('Active and durable source identity differ', 'source_drift')
    return plugin_release._export_source(destination, manifest)


def _evidence(approval):
    for key in ('confirmed_at', 'reference'):
        value = approval.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith('<'):
            raise InstallError('Real confirmation evidence required: ' + key, 'approval_invalid')
    try:
        registry._evidence({key: approval[key] for key in ('confirmed_at', 'reference')})
    except registry.RegistryError as exc:
        # One strict ledger-compatible format: UTC 'Z' suffix, never '+00:00'.
        raise InstallError(str(exc) + '; use UTC Z, e.g. 2026-10-31T08:00:00Z', 'approval_invalid') from None
    return {key: approval[key] for key in ('confirmed_at', 'reference')}


def _approve(plan, approval):
    evidence = _evidence(approval)
    if approval != dict(plan, **evidence):
        raise InstallError('Approval differs from the current exact plan; preview again', 'approval_mismatch')
    return evidence


def approval_without_evidence(approval):
    return {key: value for key, value in approval.items() if key not in ('confirmed_at', 'reference')}


def _seal(plan):
    plan['plan_sha256'] = legacy.digest(legacy.encoded(plan))
    return plan


def _entry_preview(request):
    result = user_entries.run_user_entries(dict(request, interactive=False))
    if result['status'] == 'approval_required':
        plan = json.loads(result['next_action'])
        plan.pop('confirmed_at'); plan.pop('reference')
        return plan, result
    if result['status'] != 'completed':
        raise InstallError(json.dumps(result['errors'], ensure_ascii=False), 'entry_preflight_failed')
    return None, result


def _upgrade_entry_preview(request, inner):
    migration = inner.get('migration_plan')
    runtime = user_install._runtime(request)
    snapshots = ({change.path: change.after for change in public_layout._build_changes(migration)}
                 if migration is not None else {})
    raw = bytes.fromhex(migration['v2_registry_hex'] if migration is not None else inner['after_registry_hex'])
    ledger = json.loads(raw, object_pairs_hook=registry._no_duplicates)
    registry.validate_registry(ledger, allowed_user_paths=inner['allowed_user_paths'],
        _pending_manifest=migration['manifest_path'] if migration is not None else None)
    snapshots[runtime.registry] = user_entries.Snapshot('file', raw, 0o600)
    with user_entries._installer_source(runtime.code, inner['source']['files']['SKILL.md'], preview=True):
        with user_entries._preview_state(runtime, ledger, snapshots):
            return _entry_preview(request)


def plan_machine(request):
    """Serializable outer approval; no fake project identity or implicit migration."""
    scene = user_install.inspect_machine(request)
    if scene['channel'] in ('fresh', 'legacy_copy'):
        inner = user_install.plan_install(request)
        entry = None  # First installation already stages/commits the entry subplan.
    elif scene['channel'] == 'upgrade':
        inner = upgrade.plan_upgrade(request)
        entry, _ = _upgrade_entry_preview(request, inner)
    else:
        raise InstallError('Machine scene %s: %s' % (scene['scene'], scene['errors']),
                           'machine_route_' + scene['scene'])
    source = inner['source']
    facts = detect.detect_agents(request['platform_config'], None, home=request['home'],
                                search_paths=request.get('search_paths'),
                                app_directories=request.get('app_directories'),
                                user_candidates=request.get('user_candidates'), runner=request.get('detect_runner'))
    agent_facts = {a: {'status': f['status'], 'fingerprint': detect.detection_fingerprint(f)}
                   for a, f in facts['agents'].items()}
    requested = paths.resolve_agents(request.get('agents'), default=paths.AGENT_ORDER)
    saved = {k: copy.deepcopy(v) for k, v in request.items() if k != 'detect_runner'}
    saved['operation_id'] = inner['operation_id']
    return _seal({'schema_version': 1, 'command': 'install-machine-cli',
        'operation_id': inner['operation_id'], 'layout': inner['layout'],
        'channel': inner['channel'], 'versions': {'schema_version': 3, 'product_structure_version': 1,
                                                'product_code_version': source['version']},
        'source': source, 'request': saved, 'scene': scene['scene'],
        'scene_sha256': legacy.digest(legacy.encoded(scene['observations'])),
        'requested_agents': requested,
        'effective_agents': [a for a in requested if agent_facts[a]['status'] == 'installed'],
        'agent_facts': agent_facts, 'legacy_identity': inner.get('legacy_identity'),
        'metadata_scopes': inner['metadata_scopes'],
        'reference_map': (inner.get('migration_plan') or {}).get('reference_map', {}),
        'plan': inner, 'entry_plan': entry,
        'entry_requested': inner['command'] == 'upgrade-machine',
        'entry_followup': False,  # Every entry change is bound before the first write.
        'changes': inner['changes'] + (entry or {}).get('changes', [])})


def _report(plan, status, *, result=None, entries=None, project=None):
    facts = plan['agent_facts']; requested = plan['requested_agents']
    imported = plan['plan'].get('legacy_import') or {}
    code = plan['layout']['code']
    command = [sys.executable, '-B', str(Path(code)/'scripts/agm.py'), 'enable-memory']
    if project:
        command += ['--project', str(_absolute(project))]
    else:
        command += ['--project', '/absolute/path/to/your/project']
    static = {}
    if status in ('completed', 'partial'):
        try:
            runtime = user_install._runtime(plan['request'])
            allowed = paths.allowed_user_paths(plan['request']['platform_config'], None, home=str(runtime.home))
            ledger = registry.require_installed(registry.load_registry(
                runtime.registry, allowed_user_paths=allowed))
            static = user_entries.connection_status(runtime, plan['request']['platform_config'], ledger, plan['effective_agents'])
        except (ValueError, OSError):
            static = {a: {'status': 'pending', 'reason': 'registry_unavailable', 'runtime_acceptance': 'pending'}
                      for a in plan['effective_agents']}
    connected = [a for a, fact in static.items() if fact['status'] == 'connected']
    if status == 'completed' and any(f['status'] != 'connected' for f in static.values()):
        status = 'partial'
    from agm_core.user_rules_organize import continuation
    unchanged = bool(plan['plan'].get('noop') and not plan['changes'])
    fusion = continuation(plan['request']) if status == 'completed' and not unchanged else None
    return {'fusion': fusion, 'schema_version': 1, 'command': 'install-machine', 'status': status,
        'layout': plan['layout'], 'versions': plan['versions'], 'source': plan['source'],
        'operation_id': plan['operation_id'],
        'message': ('已安装，已接入。' if unchanged and status == 'completed' else
                    '已安装，已补充接入。' if plan['plan'].get('noop') and status == 'completed' else status),
        'recovery': None if plan['plan'].get('noop') else plan['plan']['journal'],
        'metadata_scopes': plan['metadata_scopes'],
        'agents': {'connected': connected,
                   'absent': [a for a, f in facts.items() if f['status'] == 'absent'],
                   'unknown': [a for a, f in facts.items() if f['status'] == 'unknown'],
                   'unselected': [a for a in facts if a not in requested],
                   'note': '未指定 --agent 时按安装事实自动接入全部已核验安装的执行器(支持清单内 installed 者);显式 --agent 限定目标,显式指定且未核验为 installed 整单拒绝;未适配的执行器不在覆盖范围,由后续版本按路径表扩展'},
        'copies': imported.get('items', []),
        'code_copies': plan['plan']['source_files'],
        'exclusions': ['v0 skills/scripts/state/mcp stay in place; only memories/references are imported',
                       '~/.agents/skills remains in place; not migrated or adopted'],
        'project_commands': [shlex.join(command)],
        'project_root_required': project is None,
        'connection_pending': not connected or len(connected) != len(plan['effective_agents']) or status != 'completed',
        'entry_status': static,
        'changes': plan['changes'], 'result': result, 'entries': entries}


def execute_machine(plan, approval, *, request=None, project=None, hook=None):
    if project:
        _absolute(project)  # Report arguments must fail before the first write.
    evidence = _approve(plan, approval)
    request = request or copy.deepcopy(plan['request'])
    current = plan_machine(request)
    _approve(current, approval)
    inner = plan['plan']
    try:
        if inner['command'] == 'install-machine':
            result = user_install.execute_install(inner, dict(inner, **evidence), request=request)
            return _report(plan, 'completed', result=result, project=project)
        result = upgrade.execute_upgrade(inner, None if inner['noop'] else dict(inner, **evidence), request=request)
    except Exception as exc:
        # A code download/copy is not executor onboarding. Preserve the operation
        # journal and explicitly require recovery after any partially applied op.
        applied = Path(inner['bootstrap']).exists()
        report = _report(plan, 'partial' if applied else 'failed', project=project)
        report['recovery_required'] = applied
        report['errors'] = [{'code': getattr(exc, 'code', 'execution_failed'), 'message': str(exc)}]
        return report
    # Code and V now committed. New entry failure is partial, never installed-ready.
    # 0.13 public-memory-layout:同一外层批准驱动迁移子计划;只有 V2 读回才
    # completed,否则 partial + migration_phase=pending/recovery_required。
    migration = inner.get('migration_plan')
    if migration is not None:
        try:
            migration_result = public_layout.execute_migration(
                migration, dict(migration, **evidence), request=request, hook=hook)
        except Exception as exc:
            guard_pending = os.path.lexists(migration['guard'])
            report = _report(plan, 'partial', result=result, project=project)
            report['migration_phase'] = 'recovery_required' if guard_pending else 'pending'
            report['recovery_required'] = guard_pending
            report['errors'] = [{'code': getattr(exc, 'code', 'migration_failed'),
                                 'message': str(exc),
                                 'recovery': ('public_layout.plan_recovery(%s) 预览恢复' % migration['journal'])
                                 if guard_pending else '修正后重新预览外层计划'}]
            return report
        result = dict(result, migration=migration_result)
    if plan['entry_plan'] is None:
        return _report(plan, 'completed', result=result, project=project)
    try:
        entry_request = dict(request)
        if plan['entry_plan']:
            entry_request['approval'] = dict(plan['entry_plan'], **evidence)
        entries = user_entries.run_user_entries(entry_request)
        status = 'completed' if entries['status'] == 'completed' else 'partial'
    except Exception as exc:
        entries = {'status': 'failed', 'errors': [{'code': getattr(exc, 'code', 'entry_failed'), 'message': str(exc)}]}
        status = 'partial'
    return _report(plan, status, result=result, entries=entries, project=project)


def plan_acquisition(commit, staging, version):
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit or ''):
        raise InstallError('Acquisition requires a full pinned --commit')
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version or ''):
        raise InstallError('Acquisition requires --version MAJOR.MINOR.PATCH')
    stage = _absolute(staging)
    if stage != stage.resolve() or os.path.lexists(stage) or not stage.parent.is_dir():
        raise InstallError('Staging must be absent beneath an existing real parent')
    return _seal({'schema_version': 1, 'command': 'acquire-machine-source',
                  'source_url': OFFICIAL, 'commit': commit, 'version': version, 'staging': str(stage),
                  'changes': [{'path': str(stage), 'operation': 'clone_pinned_source_and_manifest'}]})


def execute_acquisition(plan, approval):
    _approve(plan, approval)
    _approve(plan_acquisition(plan['commit'], plan['staging'], plan['version']), approval)
    stage = Path(plan['staging'])
    stage.mkdir(mode=0o700)
    journal = {'schema_version': 1, 'plan': plan, 'approval': approval, 'status': 'acquiring'}
    manifest = stage/'acquisition.json'
    manifest.write_bytes(legacy.encoded(journal))
    try:
        checkout = stage/'checkout'
        subprocess.run(['git', 'clone', '--no-checkout', '--', OFFICIAL, str(checkout)], check=True,
                       capture_output=True, text=True)
        _git(checkout, 'checkout', '--detach', plan['commit'])
        source = checkout_source(str(checkout), plan['commit'], plan['version'])
        journal.update(status='acquired', source=source)
        manifest.write_bytes(legacy.encoded(journal))
        return {'status': 'acquired', 'source': source, 'acquisition_manifest': str(manifest),
                'next_action': 'Preview installation using --source %s --commit %s --version %s' %
                (shlex.quote(str(checkout)), plan['commit'], plan['version']),
                'installation_complete': False}
    except Exception:
        journal['status'] = 'partial'; manifest.write_bytes(legacy.encoded(journal))
        return {'status': 'partial', 'acquisition_manifest': str(manifest), 'installation_complete': False,
                'next_action': 'Inspect acquisition.json and preserved staging; do not assume installation succeeded'}


def build_parser():
    p = Parser(description='Machine installation: preview first; execute only an exact approved plan.', allow_abbrev=False)
    p.add_argument('--source', help='Absolute clean local Git checkout (default: this source checkout)')
    p.add_argument('--source-manifest', help='Absolute JSON file containing a verified source object')
    p.add_argument('--release-request', help='Absolute package-bound release delivery JSON; prepares a durable source before machine installation')
    p.add_argument('--commit', help='Full pinned source commit; local default is current verified HEAD')
    p.add_argument('--version', help='Target product code version MAJOR.MINOR.PATCH')
    p.add_argument('--request-file', help='Absolute JSON: conversions/legacy ledger identity/evidence inputs')
    p.add_argument('--operation-id')
    p.add_argument('--agent', action='append', choices=['codex', 'claude', 'workbuddy', 'dsh', 'zcode', 'opencode'],
                   help='限定接入目标;缺省按安装事实自动接入全部已核验安装的执行器')
    p.add_argument('--approval-file', help='Absolute JSON exact plan plus confirmed_at/reference')
    p.add_argument('--recover', help='Absolute operation journal; independent recovery mode')
    p.add_argument('--action', choices=['continue', 'rollback'], help='Recovery action')
    p.add_argument('--acquire', action='store_true', help='Separate official pinned-source acquisition plan')
    p.add_argument('--staging', help='Absolute absent acquisition directory')
    p.add_argument('--project', help='Actual absolute project root for reported follow-up commands only')
    p.add_argument('--context-keeper', action='store_true', help='Independent optional Context Keeper user-install plan')
    p.add_argument('--ck-preview-only', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--ck-source', help='Absolute independent Context Keeper checkout; fetch current official main')
    return p


def run(args):
    if args.project:
        _absolute(args.project)
    if sys.version_info < (3, 9):
        raise InstallError('Install Python >=3.9 manually, then rerun with that interpreter', 'runtime_missing')
    if shutil.which('git') is None:
        raise InstallError('Git missing. Install Git manually (macOS: xcode-select --install), then retry', 'runtime_missing')
    approval = _json(args.approval_file) if args.approval_file else None
    if approval and approval.get('command') == 'prepare-release-source':
        if any(getattr(args, name) for name in ('source', 'source_manifest', 'release_request', 'commit', 'version',
                'request_file', 'operation_id', 'agent', 'acquire', 'staging', 'project', 'context_keeper', 'ck_source', 'recover', 'action')):
            raise InstallError('Export approval must be applied independently with --approval-file')
        plan = approval_without_evidence(approval)
        if str(Path(os.environ.get('HOME', '')).resolve()) != plan['home'] or not os.environ.get('HOME'):
            raise InstallError('Export approval HOME mismatch', 'approval_mismatch')
        return plugin_release.execute_export(plan, approval)
    ordinary = any(getattr(args, name) for name in ('source', 'source_manifest', 'commit', 'version',
                    'release_request', 'request_file', 'operation_id', 'agent', 'acquire', 'staging', 'project'))
    if args.context_keeper:
        if any(getattr(args, name) for name in ('source', 'source_manifest', 'release_request', 'commit', 'version',
                'request_file', 'agent', 'acquire', 'staging', 'project', 'recover', 'action')):
            raise InstallError('--context-keeper cannot mix with recovery/acquisition/ordinary installation')
        if approval and approval.get('command') != 'install-context-keeper':
            raise InstallError('Context Keeper requires a separate install-context-keeper approval')
        home = os.environ.get('HOME')
        if not home:
            raise InstallError('Explicit HOME is required')
        request = {'home': str(Path(home).resolve()),
                   'platform_config': paths.select_platform(paths.load_agents_table(), sys.platform)}
        runtime = user_install._runtime(request)
        data = registry.load_registry(runtime.registry, allowed_user_paths=paths.allowed_user_paths(
            request['platform_config'], None, home=request['home']))
        op = args.operation_id or (approval or {}).get('main_operation_id') or data['product']['last_operation_id']
        source = args.ck_source or (approval or {}).get('source', {}).get('root')
        try:
            if not approval and not args.ck_preview_only:
                ck_install._scene(request, op)
                source = ck_install.prepare_source(request, source)
            plan = ck_install.plan_context_keeper(request, op, source)
        except ck_install.CKError as exc:
            if exc.code != 'ck_no_supported_agents':
                raise
            skipped = [{'agent': a, 'reason': 'upstream_unsupported'} for a in exc.agents]
            return {'command': 'install-context-keeper', 'status': 'skipped',
                    'reason': 'upstream_unsupported', 'skipped_upstream_agents': skipped,
                    'approval_required': False, 'context_keeper': {'status': 'skipped', 'reason': 'upstream_unsupported',
                                                                'skipped_upstream_agents': skipped}}
        if approval:
            return ck_install.execute_context_keeper(plan, approval, request=request)
        return {'command': 'install-context-keeper', 'status': 'approval_required',
                'approval_required': True, 'approval_plan': plan, 'context_keeper': {'status': 'not_started'}}
    if args.ck_source or args.ck_preview_only or (approval and approval.get('command') == 'install-context-keeper'):
        raise InstallError('Context Keeper source/approval requires --context-keeper')
    if approval and approval.get('command') == 'acquire-machine-source' and not ordinary and not args.recover and not args.action:
        return execute_acquisition(approval_without_evidence(approval), approval)
    if args.recover:
        if ordinary or not args.action:
            raise InstallError('--recover requires --action and cannot mix with installation/acquisition arguments')
        journal = str(_absolute(args.recover))
        command = _json(journal).get('plan', {}).get('command')
        module = {'install-machine': user_install, 'upgrade-machine': upgrade,
                  'migrate-machine': migrate, 'migrate-public-layout': public_layout}.get(command)
        if module is None:
            raise InstallError('Unknown recovery journal')
        # 标准 CLI 动作到迁移恢复的映射:continue=finish(仅 V2 已提交),
        # rollback=rollback(仅 V1);不造与现 CLI 无关的新命令。
        action = {'continue': 'finish'}.get(args.action, args.action) \
            if command == 'migrate-public-layout' else args.action
        plan = module.plan_recovery(journal, action=action)
        if approval is None:
            return {'status': 'approval_required', 'approval_required': True, 'approval_plan': plan}
        _approve(plan, approval)
        recover = {'install-machine': user_install.recover_install,
                   'upgrade-machine': upgrade.recover_upgrade,
                   'migrate-machine': migrate.recover_migration,
                   'migrate-public-layout': public_layout.recover_migration}[command]
        return recover(plan, approval)
    if args.action:
        raise InstallError('--action is only valid with --recover')
    if args.acquire:
        if any((args.source, args.source_manifest, args.release_request, args.request_file, args.operation_id, args.agent, args.project)) or not args.staging:
            raise InstallError('--acquire requires --staging, --commit, --version; no installation arguments')
        plan = plan_acquisition(args.commit, args.staging, args.version)
        if approval is None:
            return {'status': 'approval_required', 'approval_required': True, 'approval_plan': plan,
                    'acquisition': 'not_started', 'installation_complete': False}
        return execute_acquisition(plan, approval)
    if args.staging:
        raise InstallError('--staging is only valid with --acquire')
    saved = approval.get('request', {}) if approval else {}
    inputs = _json(args.request_file) if args.request_file else copy.deepcopy({k:v for k,v in saved.items() if k in INPUT_KEYS})
    if set(inputs) - INPUT_KEYS:
        raise InstallError('Unknown request fields: ' + str(sorted(set(inputs)-INPUT_KEYS)))
    home = str(Path(os.environ.get('HOME', '')).resolve())
    if not os.environ.get('HOME'):
        raise InstallError('Explicit HOME is required')
    operation_id = args.operation_id or saved.get('operation_id') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex
    delivery = None
    if args.release_request:
        if args.source or args.source_manifest or args.commit or args.version or 'source' in inputs:
            raise InstallError('--release-request cannot mix with source identity arguments')
        delivery = _json(args.release_request)
        if delivery.get('kind') != 'plugin-package':
            raise InstallError('--release-request requires a plugin-package delivery')
    elif args.source_manifest:
        if args.source or args.commit or args.version or (args.request_file and 'source' in inputs):
            raise InstallError('--source-manifest cannot mix with source identity arguments')
        inputs['source'] = _json(args.source_manifest)
    elif not (args.source or args.commit or args.version) and 'source' not in inputs:
        if Path(__file__).resolve() == Path(home)/'.local/share/mem-sharing/scripts/install.py':
            inputs['source'] = active_source(home)
        else:
            root = str(Path(__file__).resolve().parents[1])
            if plugin_release.ROOT_MANIFEST in _git(root, 'ls-files', '-z').split('\0'):
                version = plugin_release._read_manifest(Path(root)/plugin_release.ROOT_MANIFEST)['source']['version']
                delivery = plugin_release.checkout_delivery(root, None, version)
            else:
                inputs['source'] = checkout_source(root, None, checkout_version(root))
    elif args.source or args.commit or args.version:
        root = args.source or str(Path(__file__).resolve().parents[1])
        # HEAD/pin/clean keep their original meanings. Only after checking R do
        # we resolve S through the tracked release and a durable export.
        if plugin_release.ROOT_MANIFEST in _git(root, 'ls-files', '-z').split('\0'):
            version = args.version or plugin_release._read_manifest(Path(root)/plugin_release.ROOT_MANIFEST)['source']['version']
            delivery = plugin_release.checkout_delivery(root, args.commit, version)
        else:
            inputs['source'] = checkout_source(root, args.commit, checkout_version(root, args.version))
    if delivery:
        export = plugin_release.plan_export(delivery, home, operation_id)
        if not export['reused']:
            if approval:
                raise InstallError('Release export requires independent approval', 'approval_mismatch')
            return {'status':'approval_required','approval_required':True,'approval_plan':export,
                    'installation_complete':False,'source_trust':export['source_trust']}
        inputs['source'] = plugin_release.export_result(export)['source']
    config = paths.select_platform(paths.load_agents_table(), sys.platform)
    request = dict(inputs, home=home, platform_config=config,
                   agents=args.agent if args.agent is not None else saved.get('agents'),
                   operation_id=operation_id)
    plan = plan_machine(request)
    if approval is not None:
        return ck_install.tail(execute_machine(plan, approval, request=request, project=args.project), request)
    if plan['plan'].get('noop') and plan['entry_plan'] is None and not plan['changes']:
        report = _report(plan, 'completed', project=args.project)
        if report['status'] == 'completed' and not report['connection_pending']:
            report.update(approval_required=False, approval_plan=None)
            return report
    report = _report(plan, 'approval_required', project=args.project)
    report.update(approval_required=True, approval_plan=plan)
    # Pending/unknown connections and actual entry changes retain exact approval.
    return report


def interactive_install(args, report, *, stdin=None, stdout=None):
    """One real TTY newline approves the displayed, exact machine plan."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if not stdin.isatty():
        return report
    names = ck_install.PRODUCT_LABELS
    if report.get('approval_required'):
        plan = report.get('approval_plan') or {}
        if plan.get('command') != 'install-machine-cli':
            return report
        labels = '、'.join(names.get(a, a) for a in plan['effective_agents'])
        print('环境检查完成。将为以下 Agent 安装 memSharing：'+labels+'。', file=stdout)
        print('安装后，它们可以使用同一份公共用户记忆。按回车开始安装。', file=stdout, flush=True)
        answer = stdin.readline()
        if answer not in ('\n', '\r\n'):
            print('尚未安装。', file=stdout)
            return {'status':'skipped', 'reason':'not_consented', 'changes':[]}
        evidence = dict(plan, confirmed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                        reference='真实 TTY 回车；已展示实际安装名单：'+labels+'；精确计划 '+plan['plan_sha256'])
        report = execute_machine(plan, evidence, project=args.project)
    if report.get('status') != 'completed':
        return report
    labels = '、'.join(names.get(a,a) for a in report['agents']['connected'])
    print('memSharing 已安装。\n公共用户记忆：~/.mem-sharing/memories。\n已接入：'+labels, file=stdout, flush=True)
    if report.get('fusion') is None:
        return report
    from agm_core import user_rules_organize as org
    request = dict(plan['request'])
    stage = org.plan_organize(request)
    if stage['status'] == 'failed':
        report['fusion'] = stage
        return report
    shown = stage['approval_plan']
    if shown['groups']:
        print(stage['prompt'], file=stdout, flush=True)
        while True:
            answer = stdin.readline()
            if not answer:
                report['fusion'] = {'status':'pending_selection'}
                return report
            selected = dict(request, selection=answer.strip())
            choice = org.plan_organize(selected)
            if choice['status'] == 'failed':
                print('无法执行该选择：'+str(choice['errors']), file=stdout, flush=True)
                continue
            current = choice['approval_plan']
            if any(shown.get(k) != current.get(k) for k in ('layout','observations','groups','agents','scope','project')):
                raise InstallError('现场或编号已变化，请重新查看方案', 'drift')
            if current.get('view'):
                group = next(g for g in current['groups'] if g['number']==current['view'])
                for item in group['sources']:
                    print('来源：'+item['source']+'\n'+item['text'], file=stdout)
                stdout.flush()
                continue
            if choice.get('approval_required'):
                choice = org.execute_organize(current, dict(current,
                    confirmed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                    reference='真实 TTY 选择：'+answer.strip()), request=selected)
            report['fusion'] = {'status':choice.get('fusion_status'), 'result':choice}
            if choice['status'] != 'completed':
                return report
            print('已暂不整理，原有内容保留。' if current['declined'] else '公共用户记忆已整理完成。未选和专属内容保留。', file=stdout, flush=True)
            break
    else:
        report['fusion'] = {'status':'unchanged'}
    return ck_install.tail(report, request, stdin=stdin, stderr=stdout)


def main(argv=None):
    try:
        argv = list(sys.argv[1:] if argv is None else argv)
        seen = set()
        for token in argv:
            flag = token.split('=', 1)[0]
            if flag.startswith('--') and flag != '--agent':
                if flag in seen:
                    raise InstallError('Repeated single-use argument: ' + flag)
                seen.add(flag)
        args = build_parser().parse_args(argv)
        result = run(args)
        interactive = sys.stdin.isatty() and sys.stdout.isatty() and not args.approval_file
        if interactive:
            result = interactive_install(args, result)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        ck_route = any(token.split('=', 1)[0] == '--context-keeper' for token in argv)
        result = {'schema_version': 1, 'command': 'install-context-keeper' if ck_route else 'install-machine', 'status': 'failed',
                  'errors': [{'code': getattr(exc, 'code', 'install_failed'), 'message': str(exc)}]}
        if ck_route:
            result['context_keeper'] = {'status': 'unavailable' if getattr(exc, 'code', None) == 'ck_source_unavailable' else 'failed'}
    if not locals().get('interactive') or result.get('status') not in ('completed', 'skipped'):
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 5 if result['status'] == 'approval_required' else 0 if result['status'] in ('completed', 'configured', 'acquired', 'rolled_back', 'skipped') else 2


if __name__ == '__main__':
    raise SystemExit(main())
