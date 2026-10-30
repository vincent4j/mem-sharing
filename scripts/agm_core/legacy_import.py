"""Read-only v0 inventories and byte-preserving copy manifests (no execution)."""
import hashlib
import json
import os
import posixpath
import re
import stat
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

# v1.11(2026-10-30 裁定):R 不建 skills/、mcp/,v0 复制范围收窄为内容两目录;
# skills/mcp 原地不动、不复制、不镜像,仅登记进导入计划的排除清单。
ROOTS = ('memories', 'references')
PRESERVED_IN_PLACE = ('skills', 'mcp')


class LegacyError(ValueError):
    code = 'legacy_conflict'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _internal_target(root, rel, text):
    # Resolve only inside the approved three-directory tree. No stat/read of an
    # external target, including external links reached through internal links.
    stack=list(Path(rel).parent.parts)
    queue=list(Path(text).parts)
    seen=set()
    while queue:
        name=queue.pop(0)
        if name=='.':continue
        if name=='..':
            if not stack:return None
            stack.pop();continue
        candidate=root.joinpath(*stack,name)
        try:meta=candidate.lstat()
        except FileNotFoundError:return None
        if stat.S_ISLNK(meta.st_mode):
            if str(candidate) in seen:raise LegacyError('cyclic symlink: '+rel)
            seen.add(str(candidate));target=os.readlink(candidate)
            if os.path.isabs(target):return None
            queue=list(Path(target).parts)+queue
        else:
            stack.append(name)
            if queue and not stat.S_ISDIR(meta.st_mode):return None
    if not stack or stack[0] not in ROOTS:return None
    return root.joinpath(*stack)


def inventory(root, *, roots=ROOTS):
    """lstat walk; links never traversed. All collisions/special nodes stop."""
    root = Path(root)
    nodes = []
    def walk(path, rel):
        meta = path.lstat()
        item = {'path': rel, 'mode': stat.S_IMODE(meta.st_mode) & 0o777}
        if stat.S_ISLNK(meta.st_mode):
            text = os.readlink(path)
            item.update(type='symlink', text=text, sha256=digest(os.fsencode(text)), size=len(os.fsencode(text)))
            # Internal links must stay internal at every lexical step, not escape/reenter.
            parts = list(Path(rel).parent.parts)
            internal = not os.path.isabs(text)
            for part in Path(text).parts:
                if part == '..':
                    if len(parts) == 0:
                        internal = False
                    if parts: parts.pop()
                elif part != '.': parts.append(part)
            resolved = _internal_target(root, rel, text) if internal else None
            inside = resolved is not None
            item['active'] = internal and inside
            item['disposition'] = 'internal_link' if item['active'] else 'excluded_link'
        elif stat.S_ISDIR(meta.st_mode):
            item.update(type='directory', sha256=None, size=None)
            nodes.append(item)
            names = sorted(path.iterdir(), key=lambda p:p.name)
            keys = [unicodedata.normalize('NFC', p.name).casefold() for p in names]
            if len(set(keys)) != len(keys):
                raise LegacyError('case/Unicode collision: ' + rel)
            for child in names: walk(child, rel + '/' + child.name)
            return
        elif stat.S_ISREG(meta.st_mode):
            raw = path.read_bytes()
            item.update(type='file', sha256=digest(raw), size=len(raw))
        else:
            raise LegacyError('special node: ' + rel)
        nodes.append(item)
    for name in roots:
        path = root / name
        if os.path.lexists(path):
            if path.is_symlink() or not path.is_dir():
                raise LegacyError('expected real content directory: ' + name)
            walk(path, name)
    return {'nodes': nodes, 'tree_sha256': digest(encoded(nodes))}


def markdown_links(root, tree):
    """Conservative local link check; preserve text, flag existing broken links.

    Relative links with an originally valid target outside the copied layout
    cannot silently become broken in the reading package. External links are
    never fetched. No Markdown bytes are rewritten.
    """
    root = Path(root)
    active = {n['path'] for n in tree['nodes'] if n['type'] != 'symlink' or n['active']}
    reports = []
    for node in tree['nodes']:
        if node['type'] != 'file' or not node['path'].lower().endswith('.md'):
            continue
        text = (root / node['path']).read_bytes().decode('utf-8', errors='replace')
        targets = re.findall(r'!?\[[^\]]*\]\(\s*(<[^>]*>|[^\s)]+)', text)
        targets += re.findall(r'^\s*\[[^\]]+\]:\s*(<[^>]*>|\S+)', text, re.M)
        for target in targets:
            target = target.strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            local = unquote(parsed.path)
            source = root / node['path']
            actual = Path(local) if os.path.isabs(local) else source.parent / local
            exists = actual.exists()
            normalized = posixpath.normpath(posixpath.join(posixpath.dirname(node['path']), local))
            imported = not os.path.isabs(local) and normalized in active
            if exists and not imported and not os.path.isabs(local):
                raise LegacyError('reading package would break a valid link: ' + node['path'] + ' -> ' + target)
            reports.append({'source': node['path'], 'target': target,
                            'status': 'mirrored' if imported and exists else 'external_dependency' if exists else 'preexisting_broken'})
    return reports


def plan_import(root, operation_id):
    root = Path(root)
    tree = inventory(root)
    if (root / 'skills/agent-group-memory').exists() or (root / 'skills/agent-group-memory').is_symlink():
        raise LegacyError('v0 product-name Skill requires separate preservation/identity review')
    package = root / 'memories' / ('legacy-v0-' + operation_id)
    archive = root / 'backups' / ('v0-' + operation_id)
    if os.path.lexists(package) or os.path.lexists(archive):
        raise LegacyError('existing package/archive requires explicit same-op recovery')
    links = markdown_links(root, tree)
    items = []
    for node in tree['nodes']:
        target = str(package / node['path'])
        disposition = 'excluded' if node.get('disposition') == 'excluded_link' else 'copy'
        items.append(dict(node, source_relative_path=node['path'], sha256_or_link_text_hash=node['sha256'], target=target, disposition=disposition,
                          before={'kind': 'absent', 'fingerprint': None},
                          after=node['sha256'], completed=False))
        items.append(dict(node, source_relative_path=node['path'], sha256_or_link_text_hash=node['sha256'], target=str(root / node['path']), disposition='reuse',
                          before={'kind':node['type'], 'fingerprint':node['sha256']},
                          after=node['sha256'], completed=False))
    old_index = next((n for n in tree['nodes'] if n['path'] == 'memories/MEMORY.md'), None)
    if old_index is not None and old_index['type'] != 'file':
        raise LegacyError('legacy MEMORY index must be a regular file')
    index = ('# 公共记忆\n\n' + ('- [v0 原始记忆](legacy-v0-' + operation_id + '/memories/MEMORY.md)\n' if old_index else '')
             + '- [主题目录](topics/)\n').encode()
    for item in items:
        if item['target']==str(root/'memories/MEMORY.md'):
            item['disposition']='legacy_index';item['after']=digest(index)
    excluded = [n for n in tree['nodes'] if n.get('disposition') == 'excluded_link']
    for name in PRESERVED_IN_PLACE:
        # 原地保留登记:不在 ROOTS 内、不复制不镜像,只进排除清单供批准与报告展示。
        if os.path.lexists(root / name):
            excluded.append({'path': name, 'type': 'directory', 'disposition': 'preserved_in_place'})
    return {'identity_warning':'未发现可核验产品痕迹,不能排除历史台账被删。仅在确认这是 v0 手工目录后批准 confirmed_v0;否则停止恢复。禁止并发旧同步/管理写操作。', 'source': tree, 'source_root': str(root), 'source_tree_sha256': tree['tree_sha256'],
            'snapshot': str(archive / 'source'), 'manifest': str(archive / 'import-manifest.json'),
            'package': str(package), 'items': items, 'links': links,
            'excluded': excluded,
            'index_hex': index.hex(), 'index_before_sha256': old_index['sha256'] if old_index else None}
