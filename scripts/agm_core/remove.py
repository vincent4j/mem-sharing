"""Ownership-only removal. Never calls the upstream combined uninstaller.

Project choices/store metadata survive removal. O2 keeps user objects and their
creation evidence even with zero consumers. Plans are read-only; execution uses
exact approved snapshots, registry-last commit and Transaction recovery.
"""
import copy
from . import layout
from pathlib import Path

from .entries import block_fingerprint, link_fingerprint, remove_block, sha256, free_project_rules, lifecycle_span, remove_lifecycle_unit
from .paths import allowed_user_paths
from .project import resolve_project
from .registry import load_registry, commit_registry, serialize_registry, require_installed
from .transaction import Change, Transaction, read_snapshot, write_lock


class RemoveError(ValueError):
    def __init__(self, code, message, path=None):
        super().__init__(message)
        self.code, self.path = code, path


def _inside(path, root):
    return path == root or root in path.parents


def _protected(path, data):
    # A malformed ownership entry must never turn memory assets into outputs.
    for project in data['projects'].values():
        for assembly in project['checkouts'].values():
            store = assembly['store']['path']
            if store and (_inside(path, Path(store)) or _inside(Path(store), path)):
                return True
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
        if obj.get('marker',{})=={'start':'<!-- mem-sharing:memory-denied:start -->','end':'<!-- mem-sharing:memory-denied:end -->'} and project['memory_authorization']=='no':
            _verify_created(obj,read_snapshot(path)) if obj['ownership']=='created' else None
            warnings.append('保留 no 停用规则,防止历史 reused 指令在 remove 后重激活：%s' % path)
            continue
        if free_project_rules(obj) or path.name=='AGENTS.md' and obj['kind']=='skill_symlink':
            warnings.append('保留项目自由规则及历史基座证据：%s' % path)
            continue
        if obj['kind']=='file' and (path.name=='CLAUDE.md' or path.name=='MEMORY.md' and '.workbuddy' in path.parts):
            warnings.append('保留缺少独立引用/容器创建证据的旧入口：%s' % path)
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
    if changes:
        # Removed assembly units invalidate historical runtime acceptance.
        target['runtime_acceptance'] = {'status': 'pending', 'evidence_path': None}
        for name in ('skill_installed', 'bridge_assembled'):
            for agent in target['states'][name]:
                target['states'][name][agent] = {'status': 'unknown', 'observed_at': None, 'evidence': None}
    return updated, changes, warnings


def _check_approval(approval, identity, project, changes):
    assembly = project['checkouts'][str(identity.checkout)]
    expected = {'command': 'remove-memory', 'main_checkout': str(identity.main_checkout),
                'checkout': str(identity.checkout), 'git_common_dir': str(identity.git_common_dir),
                'agents': assembly['agents'], 'memory_authorization': None,
                'store_path': assembly['store']['path'], 'provider_source': project['provider_source']}
    for key, value in expected.items():
        if approval.get(key) != value:
            raise RemoveError('approval_mismatch', '批准与当前计划不符：' + key)
    actual = [{k: v for k, v in item.items() if k in
               ('path', 'operation', 'before_fingerprint', 'after_fingerprint')}
              for item in changes]
    if approval.get('changes') != actual:
        raise RemoveError('approval_mismatch', '批准变更集或前后指纹与当前计划不符')
    for item in approval.get('provider_fingerprints', []):
        path = Path(item['path'])
        source = project['provider_source']
        if source is None or not _inside(path, Path(source)):
            raise RemoveError('approval_mismatch', '源码指纹路径超出已登记来源')
        snapshot = read_snapshot(path)
        if snapshot.kind != 'file' or snapshot.fingerprint != item['sha256']:
            raise RemoveError('approval_mismatch', '批准的源码指纹已变化', str(path))


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
        result['warnings'] = warnings
        project = data['projects'].get(main)
        if project is not None:
            assembly = updated['projects'][main]['checkouts'][checkout]
            result['projects'] = [{'main_checkout': main, 'checkout': checkout,
                                   'states': assembly['states'], 'agents': assembly['agents'],
                                   'evidence': [str(path)], 'runtime_acceptance': assembly['runtime_acceptance']}]
        if updated == data:
            result['status'] = 'completed'
            return result
        registry_change = Change.file(path, serialize_registry(updated, allowed_user_paths=allowed), expected=before)
        summaries = [_summary(c) for c in changes] + [_summary(registry_change, 'registry')]
        result['changes'] = summaries
        approval = request.get('approval')
        if approval is None:
            result.update(status='approval_required', approval_required=True,
                          next_action='确认所列精确变更并通过 --approval-file 提供批准；记录库始终保留')
            return result
        _check_approval(approval, identity, project, summaries)

        def verify(event, output):
            if event == 'before_write':
                current = resolve_project(checkout)
                if (current.main_checkout, current.checkout, current.git_common_dir) != (identity.main_checkout, identity.checkout, identity.git_common_dir):
                    raise RemoveError('project_identity_mismatch', '锁内 Git 身份变化')
                _check_approval(approval, identity, project, summaries)

        tx = transaction_factory(lock_path=runtime.transaction_lock, backup_root=runtime.backups,
                                 allowed_roots=[identity.checkout, path], operation='remove-memory', hook=verify)
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
