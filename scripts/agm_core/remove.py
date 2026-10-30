"""Revoke project entries, retain CK/data and persist an explicit disabled guard.

Exact approved snapshots, registry-last commit and transaction recovery protect
bytes and ownership. User shared objects survive even with zero consumers.
"""
import copy
import json
from . import layout
from pathlib import Path

from .entries import block_fingerprint, link_fingerprint, remove_block, sha256, free_project_rules, lifecycle_span, remove_lifecycle_unit
from .paths import allowed_user_paths
from .project import resolve_project
from .registry import load_registry, commit_registry, serialize_registry, require_installed, _evidence
from .transaction import Change, Transaction, read_snapshot, write_lock


class RemoveError(ValueError):
    def __init__(self, code, message, path=None):
        super().__init__(message)
        self.code, self.path = code, path


def _inside(path, root):
    return path == root or root in path.parents


def _protected(path, data):
    # A malformed ownership entry must never turn memory assets into outputs.
    return ('context-keeper.json' == path.name or
            ('.codex' in path.parts and 'memories' in path.parts) or
            ('.claude' in path.parts and ('projects' in path.parts or 'memory' in path.parts)) or
            any(name in path.parts for name in ('context-keeper', '.git')) and
            not (path.name == 'context-keeper' and path.is_symlink()))


def _fingerprint(snapshot, path):
    if snapshot.kind == 'symlink':
        return link_fingerprint(path.parent / snapshot.target)
    return snapshot.fingerprint


def _summary(change, ownership='created'):
    return {'path': str(change.path),
            'operation': 'remove' if change.after.kind == 'absent' else 'update',
            'ownership': ownership,
            'before_fingerprint': _fingerprint(change.expected, change.path),
            'after_fingerprint': _fingerprint(change.after, change.path),
            'applied': False}


def _verify_created(obj, snapshot):
    path = Path(obj['path'])
    expected = obj['fingerprint']['value']
    actual = None
    try:
        if obj.get('lifecycle') and snapshot.kind=='file':
            left,right=lifecycle_span(snapshot.data,obj);actual=sha256(snapshot.data[left:right])
        elif obj['kind'] in ('block', 'user_convention') and snapshot.kind == 'file':
            actual = block_fingerprint(snapshot.data, **obj['marker'])
        elif obj['kind'] == 'file' and snapshot.kind == 'file':
            actual = sha256(snapshot.data)
        elif obj['kind'] == 'skill_symlink' and snapshot.kind == 'symlink':
            resolved = (path.parent / snapshot.target).resolve()
            if str(resolved) == obj['link_target']:
                actual = link_fingerprint(resolved)
    except ValueError as exc:
        raise RemoveError('drift', str(exc), str(path)) from exc
    if actual != expected:
        raise RemoveError('drift', 'created 对象丢失、类型冲突或指纹漂移；保留原账本', str(path))


def plan_remove(data, identity):
    """Return updated ledger, grouped per-path changes and preservation notices.

    No disk writes. Any created drift (including missing/ambiguous units) aborts
    the entire plan. Multiple blocks in one file produce exactly one change.
    """
    updated = copy.deepcopy(data)
    main, checkout = str(identity.main_checkout), str(identity.checkout)
    project = data['projects'].get(main)
    if project is None:
        return updated, [], ['项目未登记；没有可撤销的所有权对象']
    assembly = project['checkouts'][checkout]
    if assembly['git_common_dir'] != str(identity.git_common_dir):
        raise RemoveError('project_identity_mismatch', 'Git common-dir 与登记不符', checkout)
    target = updated['projects'][main]['checkouts'][checkout]
    snapshots, units, warnings = {}, {}, []
    for oid, obj in assembly['objects'].items():
        path = Path(obj['path'])
        if obj.get('marker',{})=={'start':'<!-- mem-sharing:memory-denied:start -->','end':'<!-- mem-sharing:memory-denied:end -->'} :
            _verify_created(obj,read_snapshot(path)) if obj['ownership']=='created' else None
            warnings.append('保留 no 停用规则,防止历史 reused 指令在 remove 后重激活：%s' % path)
            continue
        if free_project_rules(obj) or path.name=='AGENTS.md' and obj['kind']=='skill_symlink':
            warnings.append('保留项目自由规则及历史基座证据：%s' % path)
            continue
        if obj['kind']=='file' and (path.name=='CLAUDE.md' or path.name=='MEMORY.md' and '.workbuddy' in path.parts):
            warnings.append('保留缺少独立引用/容器创建证据的旧入口：%s' % path)
            continue
        if obj['kind']=='skill_symlink' and path.name=='context-keeper':
            warnings.append('保留 CK 安装：%s' % path)
            continue
        if obj['ownership'] != 'created':
            warnings.append('保留 %s 对象：%s' % (obj['ownership'], path))
            continue
        if _protected(path, data):
            raise RemoveError('protected_memory_asset', '拒绝触碰记录库或私有记忆资产', str(path))
        if path not in snapshots:
            snapshots[path] = read_snapshot(path)
        _verify_created(obj, snapshots[path])
        units.setdefault(path, []).append(obj)
        del target['objects'][oid]
    changes = []
    for path, objects in units.items():
        snapshot = snapshots[path]
        whole = [o for o in objects if o['kind'] in ('file', 'skill_symlink')]
        preserved = [o for o in assembly['objects'].values()
                     if o['path'] == str(path) and o['ownership'] != 'created']
        if whole:
            if len(objects) != 1 or preserved:
                raise RemoveError('ownership_conflict', '整文件撤销与其他单元所有权重叠', str(path))
            change = Change.delete(path, expected=snapshot)
        else:
            content = snapshot.data
            for obj in objects:
                if obj.get('lifecycle'):content=remove_lifecycle_unit(content,obj)
                else:content = remove_block(content, **obj['marker'],
                                       expected_fingerprint=obj['fingerprint']['value'])
            # A proven new thin container may disappear only when every byte
            # was one of this tool's independently created units/separators.
            removed_ids={oid for oid,obj in assembly['objects'].items() if obj in objects}
            allowed_ids=set().union(*(set(o.get('lifecycle',{}).get('container_units',[])) for o in objects))
            pure_container=(not content and not preserved and path.name!='AGENTS.md' and removed_ids<=allowed_ids
                            and any(o.get('lifecycle',{}).get('file_created') for o in objects))
            change = Change.delete(path,expected=snapshot) if pure_container else Change.file(path, content, expected=snapshot)
        changes.append(change)
    for oid in list(target['shared_object_ids']):
        obj = updated['shared_objects'][oid]
        if obj['ownership'] == 'created':
            _verify_created(obj, read_snapshot(Path(obj['path'])))
        obj['consumers'].remove(checkout)
        warnings.append('O2 保留用户级共享对象（剩余消费者 %d）：%s' %
                        (len(obj['consumers']), obj['path']))
    target['shared_object_ids'] = []
    updated['projects'][main]['memory_policy'] = 'disabled'
    target['runtime_acceptance'] = {'status': 'pending', 'evidence_path': None}
    return updated, changes, warnings


def _check_approval(approval, identity, project, changes, registry_sha256):
    fields = {'schema_version','command','main_checkout','checkout','git_common_dir','agents','memory_policy','registry_sha256','changes','confirmed_at','reference'}
    if not isinstance(approval, dict) or set(approval) != fields or type(approval['schema_version']) is not int or approval['schema_version'] != 1:
        raise RemoveError('approval_mismatch', 'Remove approval must match the exact versioned envelope')
    try:
        _evidence({k: approval[k] for k in ('confirmed_at', 'reference')})
    except ValueError as exc:
        raise RemoveError('approval_mismatch', 'Remove approval requires valid confirmation evidence') from exc
    assembly = project['checkouts'][str(identity.checkout)]
    expected = {'command': 'remove-memory', 'main_checkout': str(identity.main_checkout),
                'checkout': str(identity.checkout), 'git_common_dir': str(identity.git_common_dir),
                'agents': assembly['agents'], 'memory_policy': 'disabled', 'registry_sha256':registry_sha256}
    for key, value in expected.items():
        if approval.get(key) != value:
            raise RemoveError('approval_mismatch', '批准与当前计划不符：' + key)
    actual = [{k: v for k, v in item.items() if k in
               ('path', 'operation', 'before_fingerprint', 'after_fingerprint')}
              for item in changes]
    if approval.get('changes') != actual:
        raise RemoveError('approval_mismatch', '批准变更集或前后指纹与当前计划不符')


def run(request, *, registry_path=None, transaction_factory=Transaction, _locked=False):
    """CLI dispatch entry. Missing approval returns a concrete read-only preview.

    HOME/runtime_layout isolate tests. The legacy registry_path Python argument
    is accepted only when equal to that layout; it cannot redirect active state.
    """
    result = {'status': 'failed', 'projects': [], 'changes': [], 'warnings': [],
              'errors': [], 'approval_required': False, 'next_action': None}
    try:
        runtime = layout.from_request(request)
        result['runtime_layout'] = runtime.describe()
        if registry_path is not None and Path(registry_path) != runtime.registry:
            raise RemoveError('runtime_layout_invalid', 'registry_path must match the injected HOME/layout')
        identity = resolve_project(request.get('project'))
        main, checkout = str(identity.main_checkout), str(identity.checkout)
        approval = request.get('approval')
        if approval is not None:
            for key, expected in (('command', 'remove-memory'), ('main_checkout', main),
                                  ('checkout', checkout), ('git_common_dir', str(identity.git_common_dir))):
                if approval.get(key) != expected:
                    raise RemoveError('approval_mismatch', '批准目标不符：' + key)
        # An approved call replans with the same product writer lock as enable.
        if request.get('approval') is not None and not _locked:
            require_installed(load_registry(runtime.registry,
                allowed_user_paths=allowed_user_paths(request['platform_config'], None, home=str(request['home']))))
            with write_lock(runtime.lock):
                return run(request, registry_path=registry_path, transaction_factory=transaction_factory, _locked=True)
        path = runtime.registry
        allowed = allowed_user_paths(request['platform_config'], None, home=str(request['home']))
        before = read_snapshot(path)
        if before.kind == 'absent':
            result.update(status='failed', errors=[{'code': 'machine_not_installed', 'path': str(path),
                'message': 'Machine registry missing; use INSTALL.md and scripts/install.py', 'recovery': None}])
            return result
        data = require_installed(load_registry(path, allowed_user_paths=allowed))
        updated, changes, warnings = plan_remove(data, identity)
        tx = transaction_factory(lock_path=runtime.transaction_lock, backup_root=runtime.backups,
                                 allowed_roots=[identity.checkout, path], operation='remove-memory', hook=lambda event, output: None)
        if main in updated['projects']:
            from .enable import _Plan
            target = updated['projects'][main]['checkouts'][checkout]
            guard = _Plan(target, updated['shared_objects'], identity.checkout, tx)
            for change in changes:
                guard.before[change.path], guard.after[change.path] = change.expected, change.after
            guard.authorization('disabled')
            guard.finalize_lifecycle()
            changes = guard.changes()
        result['warnings'] = warnings
        project = data['projects'].get(main)
        if project is not None:
            assembly = updated['projects'][main]['checkouts'][checkout]
            result['projects'] = [{'main_checkout': main, 'checkout': checkout,
                                   'memory_policy': 'disabled', 'agents': assembly['agents'],
                                   'evidence': [str(path)], 'runtime_acceptance': assembly['runtime_acceptance']}]
        if updated == data:
            result['status'] = 'completed'
            return result
        file_summaries = [_summary(c) for c in changes]
        registry_change = Change.file(path, serialize_registry(updated, allowed_user_paths=allowed, _pending_manifest=str(tx.manifest_path)), expected=before)
        summaries = [_summary(c) for c in changes] + [_summary(registry_change, 'registry')]
        result['changes'] = summaries
        approval = request.get('approval')
        if approval is None:
            result.update(status='approval_required', approval_required=True,
                          next_action=json.dumps(dict(schema_version=1, command='remove-memory', main_checkout=main, checkout=checkout,
                            git_common_dir=str(identity.git_common_dir),agents=project['checkouts'][checkout]['agents'],memory_policy='disabled',
                            registry_sha256=before.fingerprint, changes=[{k:v for k,v in c.items() if k in ('path','operation','before_fingerprint','after_fingerprint')} for c in file_summaries],
                            confirmed_at='<UTC timestamp>',reference='<user confirmation reference>'),ensure_ascii=False))
            return result
        _check_approval(approval, identity, project, file_summaries, before.fingerprint)

        def verify(event, output):
            if event == 'before_write':
                current = resolve_project(checkout)
                if (current.main_checkout, current.checkout, current.git_common_dir) != (identity.main_checkout, identity.checkout, identity.git_common_dir):
                    raise RemoveError('project_identity_mismatch', '锁内 Git 身份变化')
                _check_approval(approval, identity, project, file_summaries, before.fingerprint)

        prior_hook = tx.hook
        def combined_hook(event, output):
            verify(event, output)
            prior_hook(event, output)
        tx.hook = combined_hook
        receipt = commit_registry(path, updated, transaction=tx, expected=before, changes=changes,
                                  allowed_user_paths=allowed, previous=data)
        result['status'] = 'completed'
        for item in summaries:
            item['applied'] = item['path'] in receipt['changed']
    except (ValueError, OSError) as exc:
        code = getattr(exc, 'code', 'remove_failed')
        result['status'] = 'recovery_required' if code == 'recovery_required' else 'failed'
        result['errors'].append({'code': code, 'path': getattr(exc, 'path', None),
                                 'message': str(exc), 'recovery': getattr(exc, 'manifest', None)})
    return result
