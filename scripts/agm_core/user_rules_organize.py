"""Optional, explicit user-rule organization; classifications are suggestions.

No imports trigger IO. Public memories are content, not V-managed objects.
One transaction edits content; only a verified reused Claude import's
observational whole-file fingerprint may be rebound, without ownership changes.
The cooperative machine lock serializes AGM writers, not arbitrary editors.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import entries, layout, paths, registry, detect, project, user_entries
from .transaction import Change, Snapshot, Transaction, TransactionError, read_snapshot, write_lock

COMMAND = 'organize-user-rules'
_SPECIFIC = re.compile(r'codex|claude|workbuddy|cursor|paseo|openai|anthropic|dsh|zcode|opencode|deepseek|DeepSeek Harness|ZCode|OpenCode|mcp|skills?|执行器专属|专属|agent专用|\.codex|\.claude|\.workbuddy|\.dsh|\.zcode|\.opencode|~/.dsh|~/.zcode|~/.config/opencode|[~/$][\w./-]+|`[^`]+`|\b(?:npm|npx|uvx|python\d*|git|bash|zsh)\s+[-\w]', re.I)
_MARKER = re.compile(rb'<!-- mem-sharing:([a-zA-Z0-9_-]+):start -->')


class OrganizeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise OrganizeError(code, message)


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def _meta(snap):
    return {'kind': snap.kind, 'sha256': snap.fingerprint, 'mode': snap.mode}


def _file(path, *, optional=False):
    snap = read_snapshot(path)
    if snap.kind == 'absent' and optional:
        return snap
    if snap.kind != 'file':
        _fail('path_conflict', 'Expected a regular file: '+str(path))
    try:
        snap.data.decode('utf-8')
    except UnicodeError:
        _fail('encoding_conflict', 'Rules must be valid UTF-8; bytes preserved without edits: '+str(path))
    return snap


def _objects(data):
    return list(data['shared_objects'].values())+list(data['machine']['objects'].values())


def _protected(data, path, runtime, objects):
    spans = []
    markers = {(match.group(0), b'<!-- mem-sharing:'+match.group(1)+b':end -->')
               for match in _MARKER.finditer(data)}
    # External CK blocks remain opaque, regardless of executor or registration.
    # The same strict parser rejects missing, duplicate and reversed markers;
    # the overlap check below also covers CK/CK and CK/AGM crossings.
    markers.update((b'<!-- context-keeper'+suffix+b':start -->',
                    b'<!-- context-keeper'+suffix+b':end -->')
                   for suffix in (b'', b':workbuddy'))
    # End-only/unknown damaged AGM markup must not become ordinary rule text.
    ends = re.findall(rb'<!-- mem-sharing:([a-zA-Z0-9_-]+):end -->', data)
    if set(ends) != {match.group(1) for match in _MARKER.finditer(data)}:
        _fail('entry_conflict', 'Incomplete AGM markers: '+str(path))
    for obj in objects:
        if obj['path'] == str(path) and obj.get('marker'):
            markers.add((obj['marker']['start'].encode(), obj['marker']['end'].encode()))
    for start, end in markers:
        span = entries.managed_span(data, start, end)
        if span:
            spans.append(span)
    offset = 0
    for line in data.splitlines(keepends=True):
        if line.strip() in (('@'+str(runtime.root/'memories/MEMORY.md')).encode(), b'@AGENTS.md'):
            spans.append((offset, offset+len(line)))
        offset += len(line)
    for a, b in spans:
        for c, d in spans:
            if (a, b) != (c, d) and a < c < b < d:
                _fail('entry_conflict', 'Crossed managed blocks')
    return sorted(spans)


def _segments(data, protected=()):
    """Paragraph/list-item ranges, retaining original byte offsets and newlines."""
    lines=[];offset=0
    for raw in data.splitlines(keepends=True):
        lines.append((offset,offset+len(raw),raw));offset+=len(raw)
    result=[];active=None;kind=None;fence=None;list_indent=0
    def close():
        nonlocal active, kind
        if active is not None:
            result.append(tuple(active));active=None;kind=None
    for left,right,raw in lines:
        body=raw.rstrip(b'\r\n'); stripped=body.strip()
        if any(left < end and right > start for start,end in protected):
            close();continue
        is_fence=re.match(rb'^\s*(```+|~~~+)', body)
        if fence is not None:
            active[1]=right
            if is_fence and is_fence.group(1)[:3] == fence:
                fence=None;close()
            continue
        if not stripped or re.match(rb'^\s*#{1,6}\s', body):
            close();continue
        if is_fence:
            close();active=[left,right];kind='code';fence=is_fence.group(1)[:3];continue
        bullet=re.match(rb'^\s*(?:[-*+]\s+|\d+[.)]\s+)', body)
        if bullet:
            indent=len(body)-len(body.lstrip())
            if active is not None and kind=='list' and indent>list_indent:
                active[1]=right
            else:
                close();active=[left,right];kind='list';list_indent=indent
        elif active is None:
            active=[left,right];kind='paragraph'
        else:
            active[1]=right
    close()
    return result


def _context(request, *, allow_active=False):
    runtime=layout.from_request(request)
    # HOME's own ancestry may be an environment alias (/var -> /private/var on
    # macOS). Anchor actual transaction paths canonically, after the shared
    # resolver has rejected links inside the managed chain below HOME.
    runtime=layout.resolve_layout(runtime.home.resolve())
    runtime.validate_paths()
    if not allow_active and runtime.backups.exists():
        for manifest in runtime.backups.glob('*/manifest.json'):
            snap = _file(manifest)
            saved = json.loads(snap.data,object_pairs_hook=registry._no_duplicates)
            if saved.get('operation') == COMMAND and saved.get('status') in ('prepared','applying','recovery_required'):
                _fail('recovery_required','请先恢复未完成的记忆融合：'+str(manifest))
    config=request['platform_config']
    allowed=paths.allowed_user_paths(config,None,home=str(runtime.home))
    snapshot=_file(runtime.registry)
    data=registry.require_installed(registry.load_registry(runtime.registry,allowed_user_paths=allowed))
    memories=runtime.root/'memories'
    if memories.is_symlink() or not memories.is_dir():
        _fail('path_conflict','Public memories must already be a real directory')
    topic_name=request.get('topic','user-rules.md')
    if not isinstance(topic_name,str) or not re.fullmatch(r'[\w-]+\.md',topic_name) or topic_name=='MEMORY.md':
        _fail('invalid_request','topic must be a simple Markdown filename other than MEMORY.md')
    return runtime, data, snapshot, memories, memories/topic_name


def _scope(data, start, protected=()):
    headings = []; offset = 0
    for raw in data[:start].splitlines(keepends=True):
        left = offset; offset += len(raw)
        if any(left < end and offset > begin for begin,end in protected): continue
        line = raw.decode().rstrip('\r\n')
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            depth = len(match[1])
            headings = [(d, t) for d, t in headings if d < depth]
            headings.append((depth, match[2].strip()))
    return [title for _, title in headings]


def _identity(text):
    # Formatting only: never erase punctuation, case or scope to guess semantics.
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    return re.sub(r"\s+", "", text)


def _participants(request, runtime, ledger):
    requested = paths.resolve_agents(request.get('agents'), default=paths.AGENT_ORDER)
    facts = detect.detect_agents(request['platform_config'], requested, home=str(runtime.home),
        search_paths=request.get('search_paths'), app_directories=request.get('app_directories'),
        user_candidates=request.get('user_candidates'), runner=request.get('detect_runner'))
    selected = [a for a in requested if facts['agents'][a]['status'] == 'installed'
        and ledger['machine']['agents'].get(a, {}).get('installation', {}).get('status') == 'installed']
    return selected, {a: detect.detection_fingerprint(facts['agents'][a]) for a in requested}


def _modern_claude_reference(obj, name, request, runtime, ledger):
    """A reused machine @index reference is not ownership of its whole body."""
    if (request.get('scope','user') != 'user' or obj.get('kind') != 'import'
        or obj.get('scope') != 'machine' or obj.get('ownership') != 'reused'
        or obj.get('marker') is not None or obj.get('agents') != ['claude']
        or obj.get('original_existed') is not True or obj.get('backup_manifest') is not None
        or obj.get('consumers') != []): return False
    expected = paths.expand_path(request['platform_config']['claude']['user_entry'],home=str(runtime.home))
    if name != expected: return False
    if (obj.get('fingerprint') or {}).get('value') != read_snapshot(name).fingerprint: return False
    state = user_entries.connection_status(runtime,request['platform_config'],ledger,['claude'])
    return state.get('claude',{}).get('status') == 'connected'


def validate_reference_rebinding(old_raw, new_raw, source_before, source_after, home):
    """Only the current reused Claude import observation may change in V."""
    config = paths.select_platform(paths.load_agents_table(),'darwin')
    runtime = layout.resolve_layout(Path(home))
    allowed = paths.allowed_user_paths(config,None,home=home)
    old = registry.validate_registry(json.loads(old_raw,object_pairs_hook=registry._no_duplicates),allowed_user_paths=allowed)
    new = registry.validate_registry(json.loads(new_raw,object_pairs_hook=registry._no_duplicates),allowed_user_paths=allowed)
    expected = copy.deepcopy(old)
    native = paths.expand_path(config['claude']['user_entry'],home=home)
    matched=[]
    for oid,obj in old['machine']['objects'].items():
        if (obj['path'] != native or obj['kind'] != 'import' or obj['scope'] != 'machine'
            or obj['ownership'] != 'reused' or obj['marker'] is not None or obj['agents'] != ['claude']
            or obj['original_existed'] is not True or obj['backup_manifest'] is not None or obj['consumers'] != []):continue
        if obj['fingerprint'] != {'algorithm':'sha256','basis':'file_bytes','value':source_before.fingerprint}:
            _fail('drift','Claude引用观察基线不等于本次批准before')
        expected['machine']['objects'][oid]['fingerprint']['value'] = source_after.fingerprint
        matched.append(oid)
    if len(matched)!=1 or expected!=new: _fail('ownership_conflict','只允许精确Claude reused import观察指纹重绑')
    line = ('@'+str(runtime.root/'memories/MEMORY.md')).encode()
    for snap in (source_before,source_after):
        if snap.kind!='file' or sum(l.strip()==line for l in snap.data.splitlines())!=1:
            _fail('entry_conflict','Claude公共引用必须完整唯一保留')
    for marker in (user_entries.CLAUDE_FALLBACK_MARKER,):
        a=entries.managed_span(source_before.data,**marker);b=entries.managed_span(source_after.data,**marker)
        if a is None or b is None or source_before.data[a[0]:a[1]]!=source_after.data[b[0]:b[1]]:
            _fail('entry_conflict','Claude兜底协议必须逐字节保留')
    return matched


def _build(request):
    import sys
    trusted = paths.select_platform(paths.load_agents_table(), 'darwin' if sys.platform == 'darwin' else sys.platform)
    if request.get('platform_config') != trusted:
        _fail('untrusted_platform_config', '路径配置必须来自当前受信任平台表，批准不能替换')
    if request.get('decisions'):
        _fail('invalid_request','旧action/replacement决策不再执行，请使用编号选择重新预览')
    runtime, ledger, vsnap, memories, topic = _context(request)
    selected, facts = _participants(request, runtime, ledger)
    mode = request.get('scope', 'user')
    if mode not in ('user', 'project'):
        _fail('invalid_request', 'scope must be user or project')
    root = None
    if mode == 'project':
        identity = project.resolve_project(Path(request['project']))
        root = identity.checkout
        topic = root / 'AGENTS.md'
    index = memories / 'MEMORY.md' if mode == 'user' else topic
    objects = _objects(ledger)
    if root:
        for rec in ledger['projects'].values():
            for checkout in rec['checkouts'].values():
                objects.extend(checkout['objects'].values())
    sources = {}
    for agent in selected:
        if root:
            key = 'project_bridge_entry' if agent == 'workbuddy' else 'project_rule_entry'
            name = paths.expand_path(request['platform_config'][agent][key], home=str(runtime.home), project=str(root))
        else:
            name = paths.expand_path(request['platform_config'][agent]['user_entry'], home=str(runtime.home))
        sources.setdefault(str(Path(name)), []).append(agent)
    if root:
        sources.setdefault(str(topic), [])  # Existing public base is always observed.
    snapshots = {str(runtime.registry): vsnap}
    observations = {str(runtime.registry): _meta(vsnap)}
    public_listing = []
    for path in sorted(memories.rglob('*')):
        if path.is_symlink(): _fail('path_conflict','Public content symlink: '+str(path))
        public_listing.append(str(path.relative_to(memories)))
        if path.is_file():
            snap = read_snapshot(path)
            snapshots[str(path)] = snap; observations[str(path)] = _meta(snap)
    items = []; unknown = []; protected_report = []; blocked = []
    for name, agents in sorted(sources.items()):
        try:
            snap = _file(Path(name), optional=True)
        except (OSError, UnicodeError) as exc:
            unknown.append({'path': name, 'reason': str(exc)}); continue
        except OrganizeError as exc:
            if exc.code != 'encoding_conflict': raise
            unknown.append({'path': name, 'reason': str(exc)}); continue
        snapshots[name] = snap; observations[name] = _meta(snap)
        if snap.kind == 'absent': continue
        spans = _protected(snap.data, Path(name), runtime, objects)
        protected_report.extend({'path': name, 'start': a, 'end': b} for a,b in spans)
        if any(o['path'] == name and o['kind'] in ('file', 'import')
               and not (root and entries.free_project_rules(o))
               and not _modern_claude_reference(o,name,request,runtime,ledger) for o in objects):
            blocked.append({'path': name, 'reason': '旧整文件受管入口须先转换，融合不改归属台账。'})
        for left,right in _segments(snap.data, spans):
            text = snap.data[left:right].decode()
            if text.lstrip().startswith(('<!--', '@', '```', '~~~')) or _SPECIFIC.search(text):
                continue
            scope = _scope(snap.data, left, spans)
            if any(_SPECIFIC.search(h) for h in scope): continue
            raw = snap.data[left:right]
            items.append({'source': name, 'agents': agents, 'start': left, 'end': right,
                'text': text, 'sha256': entries.sha256(raw), 'scope': scope})
    for path in (topic, index):
        if str(path) not in snapshots:
            snap = _file(path, optional=True); snapshots[str(path)] = snap; observations[str(path)] = _meta(snap)
    groups = {}
    for item in items:
        key = _encoded([_identity(item['text']), item['scope']]).decode()
        groups.setdefault(key, []).append(item)
    defaults = []; optional = []; single = []
    n = len(sources) if root else len(selected)
    for key, members in sorted(groups.items()):
        coverage = len({i['source'] for i in members})
        existing = bool(root and any(i['source'] == str(topic) for i in members))
        all_present = n >= 2 and coverage == n and not unknown
        group = {'group_id': entries.sha256(key.encode()), 'summary': members[0]['text'].strip().splitlines()[0],
            'sources': members, 'existing_public': existing, 'default': existing or all_present}
        (defaults if group['default'] else optional if coverage >= 2 else single).append(group)
    numbered = defaults + optional + single
    for number, group in enumerate(numbered, 1): group['number'] = number
    selection = request.get('selection', '按默认方案')
    if not isinstance(selection, str): _fail('invalid_selection', 'selection must be text')
    chosen = {g['number'] for g in defaults}
    view = re.fullmatch(r'\s*查看\s*(\d+)\s*', selection)
    declined = selection == '暂不整理'
    if declined: chosen = set()
    if not view and not declined and selection != '按默认方案':
        clauses = re.split(r'[,，;；](?=\s*(?:不共享|共享))', selection)
        for clause in clauses:
            match = re.fullmatch(r'\s*(不共享|共享)?\s*(\d+(?:\s*[、,，]\s*\d+)*)\s*', clause)
            if not match: _fail('invalid_selection', 'Use numbered choices, 不共享 n, 按默认方案 or 查看 n')
            nums = {int(v) for v in re.split(r'[、,，]', match[2])}
            if not nums <= {g['number'] for g in numbered}: _fail('invalid_selection', 'Unknown item number')
            if match[1] == '不共享': chosen -= nums
            else: chosen |= nums
    if view and int(view[1]) not in {g['number'] for g in numbered}:
        _fail('invalid_selection', 'Unknown item number')
    excluded_public = [g['number'] for g in defaults if g['existing_public'] and g['number'] not in chosen]
    retentions = request.get('retentions', {})
    if not isinstance(retentions, dict): _fail('invalid_request', 'retentions must map item numbers to native paths')
    if set(retentions) - {str(n) for n in excluded_public}:
        _fail('invalid_request', '保留位置仅用于已排除的公共条目')
    if excluded_public and not declined and any(str(n) not in retentions for n in excluded_public):
        _fail('retention_location_required', '已有公共条目须先确认保留位置：'+str(excluded_public))
    # Retention copies precede changes to the existing public base.
    outputs = {}; removals = {}; migrated = []; retention_paths = []
    content = snapshots[str(topic)].data or b''
    if mode == 'user' and any(g['number'] in chosen for g in numbered) and not view and not declined:
        if not content:
            content = '# 用户记忆\n\n## L1 概要\n\n当前有效结论：以下记忆经完整清单确认后共享；独有与未选内容保留。\n待办：记忆变化后更新概要和索引。\n\n## L2 原文与来源\n'.encode()
        elif not re.search(rb'^## L1 ',content,re.M):
            _fail('content_conflict','现有主题缺少L1概要，请保留内容并选择其他主题')
    public_removals = []
    if not declined and not view:
        for number in excluded_public:
            destination = retentions[str(number)]
            if not isinstance(destination,str): _fail('invalid_request','保留位置必须为路径')
            target = str((root / destination).absolute()) if not Path(destination).is_absolute() else destination
            if target not in sources or target == str(topic) or target in {str(runtime.registry), str(index)}:
                _fail('invalid_retention_location', '请选择当前项目已参与的独立原生文件保留')
            group = next(g for g in defaults if g['number']==number)
            original = [i for i in group['sources'] if i['source']==str(topic)]
            raw = outputs.get(target, snapshots[target].data or b'')
            for item in original:
                fragment = item['text'].encode()
                if not any(i['source']==target and i['text'].encode()==fragment for i in group['sources']):
                    context = ('\n'+'\n'.join('#'*(level+1)+' '+title for level,title in enumerate(item['scope']))+'\n').encode()
                    raw += context + fragment
                public_removals.append(item)
            outputs[target] = raw
            retention_paths.append(target)
        for item in sorted(public_removals,key=lambda i:i['start'],reverse=True):
            content = content[:item['start']] + content[item['end']:]

    public_added = b''
    for group in numbered:
        if view or group['number'] not in chosen: continue
        if not group['existing_public']:
            for item in group['sources']:
                raw = item['text'].encode()
                context = ('\n'+'\n'.join('#'*(level+1)+' '+title for level,title in enumerate(item['scope']))+'\n').encode() if item['scope'] else '\n# 用户记忆\n'.encode() if mode == 'user' else '\n# 项目记忆\n'.encode()
                chunk = context + b'\n' + raw
                content += chunk
                public_added += chunk
                migrated.append(item)
        for item in group['sources']:
            if item['source'] != str(topic): removals.setdefault(item['source'], []).append(item)
    phased = bool(set(retention_paths) & set(removals))
    if content != (snapshots[str(topic)].data or b''): outputs[str(topic)] = content
    if mode == 'user' and migrated:
        raw = snapshots[str(index)].data or '# 用户记忆\n'.encode()
        link = ('- 用户记忆：['+topic.name+']('+topic.name+')\n').encode()
        existing = [line for line in raw.splitlines(keepends=True) if ('('+topic.name+')').encode() in line]
        if existing and existing != [link]:
            _fail('content_conflict','已有主题链接含其他结论，保留原文并选择新主题')
        if not existing:
            outputs[str(index)] = raw + (b'' if raw.endswith(b'\n') else b'\n') + link
            if len(outputs[str(index)]) > 25*1024 or len(outputs[str(index)].splitlines()) > 200:
                _fail('content_conflict','L0索引超限，停止而不自动压缩')
    for name, members in removals.items():
        raw = outputs.get(name, snapshots[name].data)
        for item in sorted(members, key=lambda i:i['start'], reverse=True):
            if raw[item['start']:item['end']] != item['text'].encode(): _fail('drift', name)
            raw = raw[:item['start']] + raw[item['end']:]
        if raw != snapshots[name].data: outputs[name] = raw
    # Public content/index are written and read back before any source deletion.
    order = retention_paths + [str(topic), str(index)] + sorted(removals)
    changes = []
    for name in dict.fromkeys(order):
        if name not in outputs: continue
        changes.append({'path': name, 'before': _meta(snapshots[name]),
            'after_sha256': entries.sha256(outputs[name]), 'after_hex': outputs[name].hex()})
    # A single durable manifest binds every intermediate and final snapshot.
    steps = []
    if phased:
        phase1 = (snapshots[str(topic)].data or b'') + public_added
        state = dict(snapshots)
        def step(name, raw, stage):
            before = state[name]
            if before.kind == 'file' and before.data == raw: return
            steps.append({'path':name,'before':_meta(before),'after_hex':raw.hex(),
                          'after_sha256':entries.sha256(raw),'stage':stage})
            state[name] = Snapshot('file',raw,before.mode if before.kind=='file' else 0o600)
        step(str(topic),phase1,'public_copy')
        for name in dict.fromkeys(retention_paths+sorted(removals)):
            if name in outputs: step(name,outputs[name],'native_commit')
        step(str(topic),content,'public_remove')
    rebindings=[]
    if mode=='user':
        native=paths.expand_path(request['platform_config']['claude']['user_entry'],home=str(runtime.home))
        if native in outputs and outputs[native]!=snapshots[native].data:
            candidates=[(oid,o) for oid,o in ledger['machine']['objects'].items()
                        if o['path']==native and _modern_claude_reference(o,native,request,runtime,ledger)]
            if candidates:
                updated=copy.deepcopy(ledger)
                for oid,obj in candidates:
                    updated['machine']['objects'][oid]['fingerprint']['value']=entries.sha256(outputs[native])
                raw=registry.serialize_registry(updated,allowed_user_paths=paths.allowed_user_paths(request['platform_config'],None,home=str(runtime.home)))
                after=Snapshot('file',outputs[native],snapshots[native].mode)
                ids=validate_reference_rebinding(vsnap.data,raw,snapshots[native],after,str(runtime.home))
                rebindings=[{'object_id':oid,'path':native,'before':snapshots[native].fingerprint,'after':after.fingerprint} for oid in ids]
                changes.append({'path':str(runtime.registry),'before':_meta(vsnap),'after_hex':raw.hex(),'after_sha256':entries.sha256(raw)})
    saved = {k:copy.deepcopy(request[k]) for k in ('home','platform_config','agents','topic','scope','project','selection',
        'search_paths','app_directories','user_candidates','retentions') if k in request}
    saved['home'] = str(runtime.home)
    plan = {'schema_version': 2, 'command': COMMAND, 'layout': runtime.describe(), 'request': saved,
        'declined': declined, 'scope': mode, 'project': str(root) if root else None, 'agents': selected, 'agent_facts': facts,
        'groups': numbered, 'default_numbers': [g['number'] for g in defaults],
        'optional_numbers': [g['number'] for g in optional], 'single_numbers': [g['number'] for g in single],
        'selected_numbers': sorted(chosen), 'view': int(view[1]) if view else None,
        'unknown_sources': unknown, 'items': items, 'blocked_entries': blocked, 'protected_units': protected_report,
        'observations': observations, 'public_listing': public_listing, 'changes': changes,
        'phased_writes': phased, 'steps': steps, 'retention_paths': retention_paths, 'public_paths': list(dict.fromkeys([str(topic),str(index)])),
        'reference_rebindings':rebindings, 'registry_policy':'only verified reused import fingerprint; ownership and consumers preserved'}
    plan['plan_sha256'] = entries.sha256(_encoded(plan))
    return plan, snapshots


def _verify_readers(plan, request):
    runtime, ledger, *_ = _context(request, allow_active=True)
    if plan['scope'] == 'user':
        status = user_entries.connection_status(runtime, request['platform_config'], ledger, plan['agents'])
        if any(v['status'] != 'connected' for v in status.values()):
            _fail('entry_not_connected', '公共记忆读取入口未核验，原文不删除')
    else:
        root = Path(plan['project'])
        project.resolve_project(root)
        for item in plan['items']:
            name = item['source']
            if name == str(root/'AGENTS.md'): continue
            snap = read_snapshot(name)
            protected = _protected(snap.data, Path(name), runtime, _objects(ledger))
            if not any(b'AGENTS.md' in snap.data[a:b] for a,b in protected):
                _fail('entry_not_connected', '项目读取入口未核验，原文不删除：'+name)


def _result(**fields):
    result={'command':COMMAND,'status':'failed','approval_required':False,'next_action':None,
            'errors':[],'changes':[],'blocked_entries':[]}
    result.update(fields);return result


def plan_organize(request):
    """Read-only request→result; full plan contains unredacted user text locally."""
    try:
        plan,_=_build(request)
        editing = {c['path'] for c in plan['changes']}
        blocked = [b for b in plan['blocked_entries'] if b['path'] in editing]
        if blocked:
            return _result(status='failed',fusion_status='blocked',approval_plan=plan,prompt=present(plan).split('\n\n请告诉我')[0]+'\n当前被阻断，仅供只读诊断，不选择、不执行；可暂不整理。',
                blocked_entries=blocked,errors=[{'code':'ownership_conflict','message':'未知整文件受管入口不能进入融合修改，原文保留。'}],
                next_action='先核对 blocked_entries 的归属证据并另起精确治理；可选择暂不整理以保留现状。')
        if not plan['changes']:
            return _result(status='viewed' if plan.get('view') else 'completed',fusion_status='declined' if plan['declined'] else 'pending_selection' if plan['groups'] else 'unchanged',prompt=present(plan),approval_plan=plan,blocked_entries=plan['blocked_entries'])
        preview=dict(plan,confirmed_at='<UTC timestamp>',reference='<real user confirmation>')
        return _result(status='approval_required',approval_required=True,fusion_status='pending_confirmation',prompt=present(plan),approval_plan=plan,
                       changes=plan['changes'],blocked_entries=plan['blocked_entries'],
                       next_action=json.dumps(preview,ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return _result(errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc)}])


def execute_organize(plan,approval,*,request=None,hook=None):
    """One approval of the full itemized plan, re-plan under cooperative lock."""
    try:
        if plan.get('view'):_fail('view_only','查看不能执行修改')
        if not isinstance(approval,dict):_fail('approval_mismatch','Approval object required')
        evidence={k:approval.get(k) for k in ('confirmed_at','reference')}
        if any(not isinstance(v,str) or not v.strip() or v.startswith('<') for v in evidence.values()):
            _fail('approval_mismatch','Real confirmation evidence required')
        registry._evidence(evidence)
        expected=dict(plan,**evidence)
        if approval!=expected:_fail('approval_mismatch','Central approval must match the entire exact itemized plan')
        request=copy.deepcopy(request or plan['request'])
        current,_=_build(request)
        if current!=plan:_fail('drift','Scene or item plan changed since preview')
        editing={c['path'] for c in plan['changes']}
        blocked=[b for b in plan['blocked_entries'] if b['path'] in editing]
        if blocked:return _result(errors=[{'code':'ownership_conflict','message':'旧整文件受管入口须先转换，整单零写入。'}],blocked_entries=blocked)
        if not plan['changes']:return _result(status='completed',fusion_status='declined' if plan['declined'] else 'unchanged',blocked_entries=plan['blocked_entries'])
        runtime=_context(request)[0]
        with write_lock(runtime.lock):
            current,snapshots=_build(request)
            if current!=plan:_fail('drift','Scene changed while acquiring machine lock')
            state = dict(snapshots)
            changes = []
            ordered = plan['steps'] if plan.get('phased_writes') else plan['changes']
            for c in ordered:
                change = Change.file(c['path'],bytes.fromhex(c['after_hex']),expected=state[c['path']])
                if _meta(change.expected) != c['before']: _fail('drift','阶段批准输入不一致')
                changes.append(change); state[c['path']] = change.after
            progress = dict(snapshots)
            step_index = [0]

            tx=Transaction(lock_path=runtime.transaction_lock,backup_root=runtime.backups,
                           allowed_roots=[runtime.home,runtime.root]+([Path(plan['project'])] if plan.get('project') else []),operation=COMMAND,hook=hook)
            def guarded(event,path):
                if hook:hook(event,path)
                # V and all untouched evidence stay bound through the final write.
                if event in ('before_write','after_write'):
                    for name,meta in plan['observations'].items():
                        if name not in editing and _meta(read_snapshot(name))!=meta:
                            _fail('drift','Unedited evidence drift: '+name)
                    memories = runtime.root/'memories'
                    additions = {str(Path(c['path']).relative_to(memories)) for c in plan['changes']
                        if Path(c['path']).is_relative_to(memories) and c['before']['kind']=='absent'}
                    listing = {str(p.relative_to(memories)) for p in memories.rglob('*')}
                    if listing-additions != set(plan['public_listing']):
                        _fail('drift','Public content listing changed during fusion')
                    if plan.get('phased_writes'):
                        current_step = ordered[step_index[0]]
                        if str(path) != current_step['path']: _fail('drift','阶段顺序不一致')
                        for name, expected_snapshot in progress.items():
                            # The current output is read back separately below.
                            if event == 'after_write' and name == str(path): continue
                            if read_snapshot(name) != expected_snapshot:
                                _fail('drift','阶段间文件漂移：'+name)
                        if event == 'before_write':
                            stage = current_step['stage']
                            if stage in ('native_commit','public_remove'):
                                _verify_readers(plan,request)
                        else:
                            after = Snapshot('file',bytes.fromhex(current_step['after_hex']),
                                progress[str(path)].mode if progress[str(path)].kind=='file' else 0o600)
                            if read_snapshot(path) != after: _fail('drift','阶段输出读回失败')
                            progress[str(path)] = after
                            step_index[0] += 1
                        return
                    if event == 'before_write' and str(path) in plan['public_paths'] and plan.get('retention_paths'):
                        for name in plan['retention_paths']:
                            change = next(c for c in plan['changes'] if c['path']==name)
                            if read_snapshot(name).data != bytes.fromhex(change['after_hex']):
                                _fail('drift','保留位置未完整写入，公共原文不删除')
                    if event == 'before_write' and str(path) not in plan['public_paths']+plan.get('retention_paths',[]):
                        _verify_readers(plan, request)
                        for name in plan['public_paths']:
                            change = next((c for c in plan['changes'] if c['path'] == name), None)
                            snap = read_snapshot(name)
                            if change:
                                if snap.kind != 'file' or snap.data != bytes.fromhex(change['after_hex']):
                                    _fail('drift', '公共记忆未完整保存，保留原文：'+name)
                            elif _meta(snap) != plan['observations'][name]:
                                _fail('drift', '公共记忆发生变化：'+name)
            tx.hook=guarded
            metadata = next((c for c in changes if c.path==runtime.registry),None)
            if metadata and (not plan.get('reference_rebindings') or plan.get('phased_writes')):
                _fail('ownership_conflict','不允许通用或分阶段registry改写')
            result=tx.run([c for c in changes if c is not metadata],registry_change=metadata,phased_writes=plan.get('phased_writes',False))
        return _result(status='completed',fusion_status='completed',changes=plan['changes'],manifest=result['manifest'],
                       blocked_entries=plan['blocked_entries'],provenance='exact approved source spans and restricted reference observation; transaction manifest')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return _result(status='recovery_required' if getattr(exc,'code',None)=='recovery_required' else 'failed',
                       errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc),
                                'manifest':getattr(exc,'manifest',None)}],blocked_entries=plan.get('blocked_entries',[]))


def run_organize(request):
    if request.get('approval') is None:return plan_organize(request)
    approval=request['approval']
    if not isinstance(approval,dict):return _result(errors=[{'code':'approval_mismatch','message':'Approval object required'}])
    plan={k:v for k,v in approval.items() if k not in ('confirmed_at','reference')}
    return execute_organize(plan,approval,request=request,hook=request.get('hook'))


run=run_organize


def present(plan):
    lines = ['已找到 %d 个参与者/独立来源，本次融合尚未修改记忆内容。' % (len({i['source'] for i in plan['items']}) if plan['scope']=='project' else len(plan['agents']))]
    for label, numbers in [('默认共享', plan['default_numbers']), ('由你选择是否共享', plan['optional_numbers'])]:
        lines += ['', label]
        if not numbers: lines.append('暂无。')
        for group in plan['groups']:
            if group['number'] in numbers:
                lines.append('%d. %s（%s）' % (group['number'], group['summary'], '、'.join(sorted({i['source'] for i in group['sources']}))))
    lines += ['', '请告诉我你的选择（以下序号仅为输入示例，以本次实际编号为准）：',
              '- 3、4：保留默认项，并共享待选项 3、4。',
              '- 不共享 2：排除默认项 2。',
              '- 共享 3、4，不共享 2：增加待选 3、4，并排除默认项 2。',
              '- 按默认方案：只选默认项，不增加待选项。',
              '- 查看 3：只读查看完整原文及来源，不选择、不修改。',
              '也可暂不整理。选定后展示最终修改清单，确认后才执行。独有和未选内容保留。']
    if plan['single_numbers']: lines.append('单家内容默认留原处，可查看或明确指定共享：'+str(plan['single_numbers']))
    return '\n'.join(lines)


def continuation(request, *, scope='user', project_path=None):
    """Read-only next stage, never reuses installation approval as fusion consent."""
    req = dict(request, scope=scope)
    req.pop('approval', None)
    if project_path: req['project'] = str(project_path)
    stage = plan_organize(req)
    return {'status': 'pending_selection' if stage['status'] != 'failed' else 'blocked',
            'automatic_continue': stage['status'] != 'failed', 'can_decline': True,
            'command': 'organize-project-memory' if scope=='project' else 'organize-user-memory',
            'project': str(project_path) if project_path else None, 'preview': stage}


def cli(argv=None, *, home=None):
    import argparse
    import sys
    parser = argparse.ArgumentParser(prog='记忆共享', allow_abbrev=False)
    parser.add_argument('command', choices=['organize-user-memory','organize-project-memory','organize-user-rules'])
    parser.add_argument('--project')
    parser.add_argument('--topic')
    parser.add_argument('--agent', action='append', dest='agents')
    parser.add_argument('--selection', default=None)
    parser.add_argument('--decline', action='store_true')
    parser.add_argument('--approval-file')
    parser.add_argument('--retention-file',help='JSON对象：已排除公共条目编号到当前项目原生文件路径')
    ns = parser.parse_args(argv)
    try:
        config = paths.select_platform(paths.load_agents_table(), 'darwin' if sys.platform=='darwin' else sys.platform)
        request = {'home': str(Path(home or Path.home()).resolve()), 'platform_config': config}
        if ns.approval_file:
            approval = json.loads(Path(ns.approval_file).read_text(), object_pairs_hook=registry._no_duplicates)
            if approval['request'].get('platform_config') != config:
                _fail('untrusted_platform_config','批准不得覆盖受信任路径配置')
            request.update(approval['request'])
            if request['home'] != str(Path(home or Path.home()).resolve()):
                _fail('approval_mismatch','批准HOME与当前目标不一致')
            if ns.selection is not None or ns.decline or ns.agents or ns.retention_file or ns.topic:
                _fail('approval_mismatch','执行批准时不得同时改变选择或参与者')
            request['approval'] = approval
        else:
            request['scope'] = 'project' if ns.command=='organize-project-memory' else 'user'
            if ns.agents: request['agents'] = ns.agents
            if ns.project: request['project'] = ns.project
            if ns.topic: request['topic'] = ns.topic
            request['selection'] = '暂不整理' if ns.decline else ns.selection or '按默认方案'
            if ns.retention_file: request['retentions'] = json.loads(Path(ns.retention_file).read_text(),object_pairs_hook=registry._no_duplicates)
        expected_scope = 'project' if ns.command=='organize-project-memory' else 'user'
        if request.get('scope','user') != expected_scope:
            _fail('approval_mismatch','批准作用域与命令不一致')
        if ns.project and str(Path(ns.project).resolve()) != str(Path(request.get('project', ns.project)).resolve()):
            _fail('approval_mismatch','批准项目与命令不一致')
        result = run_organize(request)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result = _result(errors=[{'code':getattr(exc,'code','organize_failed'),'message':str(exc)}])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status']=='viewed' else 2 if result['status'] in ('failed','recovery_required') else 5 if result.get('approval_required') or result.get('fusion_status')=='pending_selection' else 0
