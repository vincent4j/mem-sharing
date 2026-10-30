"""Read-only discovery and one exact approval for sequential enable transactions.

Registered projects are never passed to enable, including disabled tombstones.
The machine writer lock covers re-preview and execution. Each project retains
enable's transaction/recovery boundary; a failure stops the remaining projects.
"""
import copy
import json
import os
from pathlib import Path

from . import enable, layout, paths, project, registry
from .transaction import TransactionError, read_snapshot, write_lock

COMMAND = 'enable-memory-batch'
PLAN_FIELDS = {'schema_version', 'command', 'directory', 'agents', 'registry_sha256', 'projects'}


def validate_approval(data, *, agents=None):
    """Validate the batch wrapper; nested plans use the existing CLI validator."""
    from agm import validate_approval as validate_enable
    if not isinstance(data, dict) or set(data) != PLAN_FIELDS | {'confirmed_at', 'reference'}:
        raise ValueError('批量批准文件字段不符')
    if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['command'] != COMMAND:
        raise ValueError('批量批准文件版本或命令不符')
    registry._path(data['directory'])
    registry._evidence({k: data[k] for k in ('confirmed_at', 'reference')})
    digest = data['registry_sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('批量批准文件 registry_sha256 非法')
    if data['agents'] is not None and (not isinstance(data['agents'], list) or
            not data['agents'] or paths.resolve_agents(data['agents']) != data['agents']):
        raise ValueError('批量批准文件 agents 非法')
    if data['agents'] is not None and data['agents'] != list(agents or []):
        raise ValueError('批量批准文件执行器与请求不符')
    if not isinstance(data['projects'], list):
        raise ValueError('批量批准文件 projects 必须为数组')
    seen = set()
    for row in data['projects']:
        if not isinstance(row, dict) or set(row) != {'path', 'state', 'action', 'notes', 'enable_plan'}:
            raise ValueError('批量项目行字段不符')
        root = registry._path(row['path'])
        if root != Path(data['directory']) and Path(data['directory']) not in root.parents:
            raise ValueError('批量项目超出扫描目录')
        if str(root) in seen:
            raise ValueError('批量项目重复')
        seen.add(str(root))
        if row['state'] not in ('new', 'enabled', 'disabled', 'excluded') or not isinstance(row['action'], str):
            raise ValueError('批量项目状态非法')
        if not isinstance(row['notes'], list) or any(not isinstance(n, str) for n in row['notes']):
            raise ValueError('批量项目信息非法')
        plan = row['enable_plan']
        if row['state'] == 'new':
            if not isinstance(plan, dict) or plan.get('main_checkout') != str(root) or plan.get('memory_policy') != 'follow_ck' or 'rebuild' in plan:
                raise ValueError('批量启用子计划非法')
            validate_enable(dict(plan, confirmed_at=data['confirmed_at'], reference=data['reference']),
                            command='enable-memory', agents=paths.resolve_agents(data['agents']), memory_choice=None)
        elif plan is not None:
            raise ValueError('跳过项目不得附带执行计划')
    return data


def _empty():
    return dict(status='completed', projects=[], changes=[], warnings=[], errors=[],
                approval_required=False, next_action=None)


def _child(request, root, approval=None):
    return dict(request, command='enable-memory', project=str(root), memory_choice=None,
                approval=approval, interactive=False)


def _scan(directory):
    """Never enter .git metadata or follow directory symlinks; inspect all roots."""
    requested = Path(directory).expanduser()
    if requested.is_symlink() or not requested.is_dir():
        raise ValueError('扫描目录必须是存在的真实目录')
    root = requested.resolve()
    def fail(exc):
        raise exc
    found = []
    for current, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        dirs[:] = sorted(d for d in dirs if d != '.git' and not (Path(current) / d).is_symlink())
        candidate = Path(current)
        if os.path.lexists(candidate / '.git'):
            found.append(candidate)
    return root, sorted(found)


def _preview(request, runtime, *, locked=False):
    if not runtime.registry.exists():
        raise enable.EnableError('machine_not_installed', 'Machine registry missing; use scripts/install.py')
    before = read_snapshot(runtime.registry)
    data = registry.load_registry(runtime.registry, allowed_user_paths=paths.allowed_user_paths(
        request['platform_config'], None, home=request['home']))
    registry.require_installed(data)
    directory, candidates = _scan(request['directory'])
    rows, errors = [], []
    for root in candidates:
        row = dict(path=str(root), state='excluded', action='跳过', notes=[], enable_plan=None)
        rows.append(row)
        try:
            identity = project.resolve_project(root)
        except project.ProjectError as exc:
            row['notes'].append(str(exc))
            continue
        prior = data['projects'].get(str(identity.main_checkout))
        if prior is not None:
            if prior['checkouts'][str(root)]['git_common_dir'] != str(identity.git_common_dir):
                errors.append(dict(code='project_identity_mismatch', path=str(root), message='Git identity changed; do not inherit registration', recovery=None))
                continue
            row['state'] = 'disabled' if prior['memory_policy'] == 'disabled' else 'enabled'
            row['action'] = '跳过：需显式单独重新启用' if row['state'] == 'disabled' else 'noop：已启用，不重跑'
            continue
        child = _child(request, root)
        preview = enable._run_locked(child, runtime, _empty(), locked=True) if locked else enable.run(child)
        if preview['status'] != 'approval_required' or preview.get('errors'):
            errors.extend(preview.get('errors') or [dict(code='batch_project_blocked', path=str(root), message='项目预览未产生可执行计划：' + preview['status'], recovery=None)])
            row['notes'].append('启用预览受阻，整批不执行')
            continue
        row.update(state='new', action='启用记忆', enable_plan=json.loads(preview['next_action']))
        row['enable_plan'].pop('confirmed_at')
        row['enable_plan'].pop('reference')
        if request.get('agents') is None:
            row['notes'].append('CLAUDE.md 保持原样，待 Claude 实际使用后由兜底条款补引用')
        if 'workbuddy' in row['enable_plan'].get('native_pending', []):
            row['notes'].append('WorkBuddy 原生目录不存在，待实际使用后兜底')
    if read_snapshot(runtime.registry) != before:
        raise enable.EnableError('drift', 'Registry changed during batch preview; re-preview')
    plan = dict(schema_version=1, command=COMMAND, directory=str(directory), agents=request.get('agents'),
                registry_sha256=before.fingerprint, projects=rows)
    return plan, errors


def _show(result, plan, errors=()):
    result['projects'] = copy.deepcopy(plan['projects'])
    result['errors'] = list(errors)
    result['changes'] = [dict(change, applied=False) for row in plan['projects'] if row['enable_plan']
                         for change in row['enable_plan']['changes']]


def _pending(result, plan):
    result.update(status='approval_required', approval_required=True,
                  next_action=json.dumps(dict(plan, confirmed_at='<UTC timestamp>', reference='<user confirmation reference>'), ensure_ascii=False))
    return result


def run(request):
    result = _empty()
    try:
        runtime = layout.from_request(request)
        result['runtime_layout'] = runtime.describe()
        if runtime.lock.exists():
            raise TransactionError('writer lock exists; do not steal a stale lock', code='lock_conflict')
        plan, errors = _preview(request, runtime)
        _show(result, plan, errors)
        if errors:
            result['status'] = 'failed'
            return result
        approval = request.get('approval')
        if approval is not None:
            validate_approval(approval, agents=paths.resolve_agents(request.get('agents')))
            if {k: approval[k] for k in PLAN_FIELDS} != plan:
                result['errors'].append(dict(code='approval_mismatch', path=None, message='批量现场与批准计划不符，请重新预览确认', recovery=None))
                return _pending(result, plan)
        if not any(row['state'] == 'new' for row in plan['projects']):
            result['changes'] = []
            for row in result['projects']:
                row['result'] = 'skipped'
            return result
        if approval is None:
            if not enable._confirm(request, plan):
                return _pending(result, plan)
            approval = dict(plan, confirmed_at=enable._now(), reference='interactive exact batch plan confirmation')
        with write_lock(runtime.lock):
            fresh, errors = _preview(request, runtime, locked=True)
            if errors or fresh != plan:
                _show(result, fresh, errors)
                result['errors'].append(dict(code='approval_mismatch', path=None, message='锁内复核发现批量计划漂移，整批未执行', recovery=None))
                return _pending(result, fresh)
            result['changes'] = []
            for row in result['projects']:
                row['result'] = 'not_started' if row['state'] == 'new' else 'skipped'
            for row in result['projects']:
                if row['state'] != 'new':
                    continue
                row['result'] = 'running'
                exact = dict(row['enable_plan'], confirmed_at=approval['confirmed_at'], reference=approval['reference'])
                applied = enable._run_locked(_child(request, row['path'], exact), runtime, _empty(), locked=True)
                row['result'] = applied['status']
                result['changes'].extend(applied['changes'])
                result['warnings'].extend(applied['warnings'])
                if applied['status'] != 'completed':
                    result.update(status=applied['status'], approval_required=applied.get('approval_required', False), next_action=applied.get('next_action'))
                    result['errors'].extend(applied['errors'])
                    break
        return result
    except (ValueError, OSError, EOFError, SyntaxError) as exc:
        result['status'] = getattr(exc, 'status', 'recovery_required' if getattr(exc, 'code', None) == 'recovery_required' else 'failed')
        for row in result['projects']:
            if row.get('result') == 'running':
                row['result'] = result['status']
        result['errors'].append(dict(code=getattr(exc, 'code', 'batch_enable_failed'), path=None,
                                     message=str(exc), recovery=getattr(exc, 'manifest', None)))
        result['next_action'] = '检查结果与恢复证据，重新预览未完成项目；已完成项目保留。'
        return result
