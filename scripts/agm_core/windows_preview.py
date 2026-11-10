"""First-install preview for ZCode/WorkBuddy, ordinary local files only.

Reuses the core byte editor and recoverable transaction. No migration, fusion,
upgrades, automatic project integration, or general Windows support claim.
Cooperating writers use one lock; snapshot checks are not OS compare-and-swap.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

from . import entries, transaction as tx

START = '<!-- mem-sharing:windows-preview:start -->'
END = '<!-- mem-sharing:windows-preview:end -->'
SOURCE_FILES = (
    'scripts/windows_preview.py', 'scripts/agm_core/__init__.py',
    'scripts/agm_core/entries.py', 'scripts/agm_core/transaction.py',
    'scripts/agm_core/windows_preview.py', 'scripts/agm_core/windows_native.py',
    'scripts/agm_core/platform_diagnostics.py',
    'scripts/agm_core/paths.py',
)
NATIVE = ('.zcode/AGENTS.md', '.workbuddy/MEMORY.md',
          '.zcode/skills/mem-sharing/SKILL.md', '.workbuddy/skills/mem-sharing/SKILL.md')
CODE = '.local/share/mem-sharing'
PUBLIC = '.mem-sharing/memories/MEMORY.md'
RECEIPT = '.mem-sharing/preview-receipt.json'
BACKUPS = '.mem-sharing-preview-backups'
LOCK = '.mem-sharing-preview.lock'


class PreviewError(ValueError):
    code = 'preview_refused'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def absolute(value):
    p = Path(value)
    if not p.is_absolute() or str(p) != os.path.normpath(str(p)) or '..' in p.parts:
        raise PreviewError('需要规范的绝对路径')
    if os.name == 'nt':
        from .platform_diagnostics import windows_path_issue
        if windows_path_issue(str(p)):
            raise PreviewError('预览版不支持此路径语法')
    return p


def guard(path):
    """Observe all existing parents; never silently resolve a link or alias."""
    p = absolute(path)
    for node in reversed((p,) + tuple(p.parents)):
        try:
            s = node.lstat()
        except FileNotFoundError:
            continue
        attrs = getattr(s, 'st_file_attributes', 0)
        if stat.S_ISLNK(s.st_mode) or attrs & (0x400 | 0x1000 | 0x40000):
            raise PreviewError('链接/reparse/离线文件不支持：' + str(node))
        if not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)):
            raise PreviewError('非常规文件：' + str(node))
        if stat.S_ISREG(s.st_mode) and s.st_nlink != 1:
            raise PreviewError('硬链接文件不支持：' + str(node))
    if os.name == 'nt':
        # Existing read-only native observations: fixed NTFS, final names,
        # directory case flags. No Cloud Files calls or ACL mutation.
        from .windows_native import inspect_path
        existing = p
        while not os.path.lexists(existing):
            existing = existing.parent
        with inspect_path(str(existing), candidate_metadata=True) as observed:
            if any(n.get('case_sensitive_directory') for n in observed['chain']):
                raise PreviewError('大小写敏感目录不支持')
    return p


def snap(path):
    guard(path)
    s = tx.read_snapshot(path)
    if s.kind not in ('file', 'absent'):
        raise PreviewError('仅允许普通文件')
    if s.kind == 'file' and (not s.mode & 0o200 or getattr(Path(path).stat(), 'st_file_attributes', 0) & 1):
        raise PreviewError('只读文件不支持：' + str(path))
    return s


def packed(s):
    return {'kind': s.kind, 'sha256': s.fingerprint, 'mode': s.mode,
            'hex': s.data.hex() if s.kind == 'file' else None}


def unpacked(s):
    raw = bytes.fromhex(s['hex']) if s['kind'] == 'file' else None
    value = tx.Snapshot(s['kind'], raw, s['mode'])
    if value.fingerprint != s['sha256']:
        raise PreviewError('快照hash不符')
    return value


def file_snapshot(raw, before=None):
    return tx.Snapshot('file', raw, before.mode if before and before.kind == 'file' else (0o666 if os.name == 'nt' else 0o600))


def operation(home, relative, raw):
    before = snap(home / relative)
    after = tx.Snapshot('absent') if raw is None else file_snapshot(raw, before)
    return {'relative': relative, 'before': packed(before), 'after': packed(after)}


def source_manifest(source):
    source = absolute(source)
    result = {}
    for name in SOURCE_FILES:
        s = snap(source / name)
        if s.kind != 'file':
            raise PreviewError('预览依赖缺失：' + name)
        result[name] = {'sha256': s.fingerprint, 'size': len(s.data)}
    return result


def references(home):
    public = str(home / PUBLIC)
    return (START + '\n本机 memSharing Windows 预览版（仅显式新增共享，不迁移旧记忆）。\n'
            + '每次会话先读取公共记忆：<' + public + '>；它是跨 ZCode、WorkBuddy 的同一份文件。\n'
            + '用户明确要求共享新记忆时，读取本客户端的 mem-sharing Skill；不要自动改项目或私有记忆。\n'
            + END).encode('utf-8')


def skill(home):
    # JSON quoting is displayed as an argv array; no shell quoting assumptions.
    command = [sys.executable, '-I', '-S', '-B', str(home / CODE / 'scripts/windows_preview.py')]
    return ('---\nname: mem-sharing\ndescription: Windows预览版：显式新增并读取两端公共记忆\n---\n\n'
            + '公共记忆：<' + str(home / PUBLIC) + '>。先读该文件；保留旧私有记忆。\n'
            + '仅支持读取和用户明确要求的新增；不运行生产融合/升级/自动项目接入菜单。\n'
            + '新增时通过工具以参数数组执行以下命令，追加 add --home <本机HOME> --text <用户要共享的正文>：\n'
            + json.dumps(command, ensure_ascii=False) + '\n'
            + 'add 是用户显式新增动作，会备份及回读；失败停止并报告回执，不直接覆写公共文件。\n'
            + '退出先生成 exit-plan，再由已批准计划调用 apply；退出会导出保留公共记忆，不融合归还。\n').encode('utf-8')


def base_plan(action, home, run_id):
    home = guard(home)
    if not home.is_dir():
        raise PreviewError('HOME必须为现存普通目录')
    uuid.UUID(run_id)
    return {'schema': 'mem-sharing-windows-preview-1', 'action': action,
            'home': str(home), 'run_id': run_id, 'production_support': False,
            'backup_root': str(home / BACKUPS), 'operations': []}


def install_plan(home, source, *, run_id=None):
    p = base_plan('install', absolute(home), run_id or str(uuid.uuid4()))
    home, source = Path(p['home']), absolute(source)
    for name in ('.mem-sharing', CODE, '.agents-group'):
        guard(home / name)
        if os.path.lexists(home / name):
            raise PreviewError('首次预览拒绝既有安装/未知内容：' + str(home / name))
    p.update(source=str(source), source_files=source_manifest(source), interpreter=sys.executable)
    ops, native = p['operations'], {}
    for name in SOURCE_FILES:
        ops.append(operation(home, CODE + '/' + name, (source / name).read_bytes()))
    for name in NATIVE:
        before = snap(home / name)
        if '/skills/' in name:
            if before.kind != 'absent':
                raise PreviewError('已有未登记Skill：' + str(home / name))
            after = skill(home)
        else:
            raw = before.data or b''
            if b'mem-sharing' in raw.lower() or b'agent-group-memory' in raw.lower():
                raise PreviewError('已有共享入口/未知接入：' + str(home / name))
            # Keep every original byte, including BOM, CRLF, trailing newline.
            after = entries.render_block(raw, references(home), START, END)
        ops.append(operation(home, name, after))
        native[name] = {'before': packed(before), 'installed_sha256': digest(after)}
    ops.append(operation(home, PUBLIC, '# 公共记忆\n\n仅存放用户明确新增的共享内容。\n'.encode('utf-8')))
    receipt = {'schema': p['schema'], 'home': str(home), 'run_id': p['run_id'],
               'source_files': p['source_files'], 'native': native,
               'block_hex': references(home).hex(), 'source': str(source),
               'interpreter': sys.executable, 'public_sha256': ops[-1]['after']['sha256']}
    ops.append(operation(home, RECEIPT, encoded(receipt)))
    return p


def load_receipt(home):
    home = guard(absolute(home))
    raw = snap(home / RECEIPT)
    if raw.kind != 'file':
        raise PreviewError('没有本预览版回执')
    r = json.loads(raw.data)
    if (r.get('schema') != 'mem-sharing-windows-preview-1' or r.get('home') != str(home)
            or set(r['native']) != set(NATIVE) or set(r['source_files']) != set(SOURCE_FILES)
            or bytes.fromhex(r['block_hex']) != references(home)):
        raise PreviewError('预览版回执身份/范围不符')
    uuid.UUID(r['run_id'])
    # Unknown files in owned trees block removal, never get recursively deleted.
    for root, names in ((home / CODE, set(SOURCE_FILES)),
                        (home / '.mem-sharing', {'preview-receipt.json', 'memories/MEMORY.md'})):
        guard(root)
        for node in root.rglob('*'):
            guard(node)
            rel = node.relative_to(root).as_posix()
            if node.is_dir():
                if not any(n.startswith(rel + '/') for n in names):
                    raise PreviewError('自有目录出现未知目录：' + str(node))
            elif rel not in names:
                raise PreviewError('自有目录出现未知文件：' + str(node))
    for name, meta in r['source_files'].items():
        s = snap(home / CODE / name)
        if s.kind != 'file' or s.fingerprint != meta['sha256']:
            raise PreviewError('已安装代码漂移：' + name)
    return r, raw


def add_plan(home, text, *, run_id=None):
    if not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 65536 or '\x00' in text:
        raise PreviewError('新增正文须为非空UTF-8文本（最多64KB）')
    home = absolute(home)
    r, before = load_receipt(home)
    p = base_plan('add', home, run_id or str(uuid.uuid4()))
    public = snap(home / PUBLIC)
    if public.kind != 'file' or public.fingerprint != r['public_sha256']:
        raise PreviewError('公共记忆被外部修改，保留并停止')
    raw = public.data + ('\n## ' + p['run_id'] + '\n\n' + text + '\n').encode('utf-8')
    r['public_sha256'] = digest(raw)
    p['text'] = text
    p['operations'] = [operation(home, PUBLIC, raw), operation(home, RECEIPT, encoded(r))]
    return p


def exit_plan(home, *, run_id=None):
    home = absolute(home)
    r, before = load_receipt(home)
    p = base_plan('exit', home, run_id or str(uuid.uuid4()))
    public = snap(home / PUBLIC)
    if public.kind != 'file':
        raise PreviewError('公共数据缺失，停止退出')
    export = '.mem-sharing-preview-exports/' + p['run_id'] + '/MEMORY.md'
    if snap(home / export).kind != 'absent':
        raise PreviewError('导出目标已占用')
    p['export'] = {'path': str(home / export), 'sha256': public.fingerprint}
    # Export is first and verified by Transaction before any removal.
    ops = [operation(home, export, public.data)]
    for name, meta in r['native'].items():
        current = snap(home / name)
        if current.kind != 'file' or current.fingerprint != meta['installed_sha256']:
            raise PreviewError('入口外部编辑，保留全部并停止退出：' + str(home / name))
        original = unpacked(meta['before'])
        ops.append(operation(home, name, original.data))
    for name in SOURCE_FILES:
        ops.append(operation(home, CODE + '/' + name, None))
    ops.append(operation(home, PUBLIC, None))
    ops.append(operation(home, RECEIPT, None))
    p['operations'] = ops
    return p


def regenerate(p):
    if p['action'] == 'install':
        return install_plan(p['home'], p['source'], run_id=p['run_id'])
    if p['action'] == 'add':
        return add_plan(p['home'], p['text'], run_id=p['run_id'])
    if p['action'] == 'exit':
        return exit_plan(p['home'], run_id=p['run_id'])
    raise PreviewError('未知预览操作')


def execute(p, approved_sha256, *, hook=None):
    if digest(encoded(p)) != approved_sha256:
        raise PreviewError('批准hash与计划不符')
    if regenerate(p) != p:
        raise PreviewError('批准后源或现场漂移，请重新预览')
    home = Path(p['home'])
    allowed = {home / op['relative'] for op in p['operations']}
    guard(home / LOCK)
    guard(home / BACKUPS)
    def observe(event, path):
        guard(path)
        if hook:
            hook(event, path)
        guard(path)
    transaction = tx.Transaction(lock_path=home / LOCK, backup_root=home / BACKUPS,
                                 allowed_roots=sorted(allowed), operation='windows-preview-' + p['action'],
                                 hook=observe, operation_metadata={'plan_sha256': approved_sha256,
                                                                 'run_id': p['run_id']})
    changes = [tx.Change(home / op['relative'], unpacked(op['after']), unpacked(op['before']))
               for op in p['operations']]
    # Receipt last; export readback occurs before native/code removals.
    result = transaction.run(changes[:-1], registry_change=changes[-1])
    result.update(action=p['action'], production_support=False, run_id=p['run_id'])
    if p['action'] == 'exit':
        export = Path(p['export']['path'])
        if snap(export).fingerprint != p['export']['sha256']:
            raise PreviewError('导出读回失败，保留回执检查')
        result['export'] = p['export']
        # Deliberately retain empty directories, backups, and exports. Never
        # recursive-delete a tree that another program may have just populated.
    return result


def recover(home, manifest):
    home, manifest = absolute(home), guard(absolute(manifest))
    if manifest.parent.parent != home / BACKUPS or manifest.name != 'manifest.json':
        raise PreviewError('仅恢复本HOME的预览事务')
    m = json.loads(manifest.read_bytes())
    if m.get('operation') not in ('windows-preview-install', 'windows-preview-add', 'windows-preview-exit'):
        raise PreviewError('非预览事务')
    exact = {home / CODE / n for n in SOURCE_FILES} | {home / n for n in NATIVE + (PUBLIC, RECEIPT)}
    if m['operation'] == 'windows-preview-exit':
        rid = m['operation_metadata']['run_id']; uuid.UUID(rid)
        exact.add(home / '.mem-sharing-preview-exports' / rid / 'MEMORY.md')
    for item in m['entries']:
        if Path(item['path']) not in exact:
            raise PreviewError('恢复输出越界')
        guard(item['path'])
    # Directory intents are validated separately; only ancestors of exact outputs.
    scope = exact | {parent for n in exact for parent in n.parents if home in parent.parents}
    result = tx.recover_manifest(manifest, lock_path=home / LOCK, allowed_roots=scope,
                                 hook=lambda event, path: guard(path))
    return {'status': result['status'], 'manifest': str(manifest), 'production_support': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='DELL Windows 双端首次接入预览；不升级/融合旧安装')
    parser.add_argument('action', choices=('plan', 'apply', 'add', 'exit-plan', 'recover'))
    parser.add_argument('--home', required=True)
    parser.add_argument('--source')
    parser.add_argument('--output')
    parser.add_argument('--plan')
    parser.add_argument('--plan-sha256')
    parser.add_argument('--text')
    parser.add_argument('--manifest')
    args = parser.parse_args(argv)
    try:
        if sys.platform != 'win32':
            raise PreviewError('本入口仅Windows预览；普通生产安装仍仅macOS')
        if args.action in ('plan', 'exit-plan'):
            p = install_plan(args.home, args.source) if args.action == 'plan' else exit_plan(args.home)
            if not args.output:
                raise PreviewError('需显式--output，将精确计划保存在自有代码/公共目录外')
            out = guard(absolute(args.output))
            home = absolute(args.home)
            if any(out == home / n or home / n in out.parents for n in (CODE, '.mem-sharing')):
                raise PreviewError('计划不可放在安装或公共数据目录内')
            with out.open('xb') as f:
                f.write(encoded(p)); f.flush(); os.fsync(f.fileno())
            result = {'status': 'approval_required', 'plan': str(out), 'plan_sha256': digest(encoded(p)),
                      'file_count': len(p['operations']), 'backup_root': p['backup_root']}
        elif args.action == 'apply':
            raw = snap(absolute(args.plan)).data
            p = json.loads(raw)
            if p['home'] != str(absolute(args.home)):
                raise PreviewError('HOME与批准计划不一致')
            result = execute(p, args.plan_sha256)
        elif args.action == 'add':
            p = add_plan(args.home, args.text)
            result = execute(p, digest(encoded(p)))
        else:
            result = recover(args.home, args.manifest)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 5 if result['status'] == 'approval_required' else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'failed', 'code': getattr(exc, 'code', 'preview_failed'),
                          'message': str(exc), 'manifest': getattr(exc, 'manifest', None)}, ensure_ascii=False))
        return 2
