"""Direct native return. Product templates are provenance, never keyword ownership.

Unknown product-looking prose is a review conflict, not permission to delete it.
No files are written by these planners.
"""
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import uninstall_recovery as recovery

RETURN_SCHEMA = 'native-direct-v1'
# Exact historical generated return prefix, including the whole governance unit.
# These are product text, even though individual sentences look like user rules.
LEGACY_GENERATED_GOVERNANCE = (
    '# 公共记忆\n\n'
    'Agent 独有内容保留于各自用户文件，永不并入公共或自动删除。\n'
    '首次 /context-keeper 进入 Context Keeper 流程，首次保存按其流程确认位置。\n'
    '项目经历由 Context Keeper 独立管理。\n'
    '各 Agent 只维护自身专属项目入口（Claude 的 CLAUDE.md、WorkBuddy 的原生 memory 指针），由各自实际使用时补齐，其他执行器不得预建。\n'
    'AGENTS.md 是共享项目规则基座，不依赖 Codex，无 Codex 的机器同样成立。'
).encode()


def protected_parts(raw, *, assembled=False):
    """Typed byte slices, never placeholders. Source markers must be unique.

    Composition may contain several independently validated complete spans;
    nested, reversed or incomplete spans are never legitimate composition.
    """
    start=b'<!-- context-keeper:start -->';end=b'<!-- context-keeper:end -->'
    tokens=list(re.finditer(re.escape(start)+b'|'+re.escape(end),raw))
    if not tokens:return [(False,raw)]
    parts=[];cursor=0;opening=None;count=0
    for token in tokens:
        if token.group()==start:
            if opening is not None:raise recovery.Conflict('Nested Context Keeper markers')
            parts.append((False,raw[cursor:token.start()]))
            opening=token.start()
        else:
            if opening is None:raise recovery.Conflict('Incomplete/reversed Context Keeper markers')
            parts.append((True,raw[opening:token.end()]))
            cursor=token.end();opening=None;count+=1
    if opening is not None:raise recovery.Conflict('Incomplete Context Keeper markers')
    if count>1 and not assembled:raise recovery.Conflict('Duplicate source Context Keeper markers')
    parts.append((False,raw[cursor:]))
    return parts


def map_text(raw, transform, *, assembled=False):
    return b''.join(data if protected else transform(data)
                    for protected,data in protected_parts(raw,assembled=assembled))


def contains_text(raw, token, *, assembled=False):
    return any(token in data for protected,data in protected_parts(raw,assembled=assembled) if not protected)


def public_sources(runtime):
    original={}
    for name in ('memories','references'):original.update(recovery.tree(runtime.root/name))
    if (original[str(runtime.root/'memories')]['kind']!='directory'
            or original.get(str(runtime.root/'memories/MEMORY.md'),{}).get('kind')!='file'):
        raise recovery.Conflict('Complete public memory/index required')
    return original


def require_no_product_dependency(raw, roots, *, home=None, document=None):
    # Immutability never exempts a span from dependency safety. Ambiguous bare
    # product paths conservatively require review; no inert-path guessing.
    absolute=[Path(root) for root in roots if Path(root).is_absolute()]
    tokens=[str(root).encode() for root in roots]
    if home is not None:
        tokens += [('~/'+str(root.relative_to(home))).encode() for root in absolute
                   if root.is_relative_to(home)]
    if any(token in raw for token in tokens):
        raise recovery.Conflict('Active/ambiguous product dependency; preserve and review required')
    if document is None:return
    targets=re.findall(rb'(?m)^[ \t]*(?:\xef\xbb\xbf)?@([^\s]+)',raw)
    targets+=re.findall(rb'\]\(\s*(<[^>]+>|[^\s)]+)',raw)
    targets+=re.findall(rb'(?m)^[ \t]*\[[^\]]+\]:[ \t]*(<[^>]+>|\S+)',raw)
    for target in targets:
        text=unquote(target.decode('utf-8',errors='surrogateescape').strip('<>')).split('#',1)[0]
        if not text or urlsplit(text).scheme:continue
        if text.startswith('~/') and home is not None:resolved=Path(home)/text[2:]
        else:resolved=Path(document).parent/text
        resolved=Path(os.path.normpath(str(resolved)))
        if any(resolved==root or resolved.is_relative_to(root) for root in absolute):
            raise recovery.Conflict('Active product import/link dependency; preserve before uninstall')


def strip_generated(raw, runtime, *, public=False, historical_proof=False):
    return map_text(raw,lambda part:_strip_generated_text(part,runtime,public=public,
                                                         historical_proof=historical_proof))


def _strip_generated_text(raw, runtime, *, public=False, historical_proof=False):
    from . import user_entries, public_layout, policy_migration
    if historical_proof:
        if raw.count(LEGACY_GENERATED_GOVERNANCE) > 1:
            raise recovery.Conflict('Duplicate historical generated governance; review required')
        raw = raw.replace(LEGACY_GENERATED_GOVERNANCE, b'', 1)
    if public:
        templates = {user_entries.public_memory_contract_text(runtime.code).encode(), user_entries.public_memory_contract_text().encode(), user_entries.LEGACY_RUNTIME_CONTRACT.encode()}
        for name in ('contract', 'old_contract', 'pre_route_contract'):
            templates.add(policy_migration.legacy(name, runtime))
        # Header/index ownership follows a recognized complete producer unit.
        recognized=False
        for template in sorted(templates, key=len, reverse=True):
            if template in raw:
                if raw.count(template) != 1:
                    raise recovery.Conflict('Duplicate generated public contract')
                complete='# 公共记忆\n\n'.encode()+template
                if complete in raw:raw=raw.replace(complete,b'',1)
                else:raw = raw.replace(template, b'', 1)
                recognized=True
        if recognized:
            prefix='# 公共记忆\n\n'.encode()
            if raw.startswith(prefix):raw=raw[len(prefix):]
            known_indexes=(
                '- 使用约定：操作与项目接入前读取。[概要与全文](topics/使用约定.md)\n'.encode(),
                '- 使用约定：中枢已初始化，主题结论由 Agent 经确认后手写维护。[概要与全文](topics/使用约定.md)\n'.encode(),
                '- 使用约定：操作指南与维护规则。[概要与全文](topics/使用约定.md)\n'.encode())
            for line in known_indexes:raw=raw.replace(line,b'')
        if b'topics/'+ '使用约定.md'.encode() in raw:
            raise recovery.Conflict('Unknown product topic navigation; review required')
        generated = {user_entries.GOVERNANCE_RULES_TEXT,
                     policy_migration.LEGACY_TEMPLATES['governance'],
                     getattr(public_layout, '_OLD_GOVERNANCE', '')}
        kept = []
        for line in raw.splitlines(keepends=True):
            text = line.decode('utf-8', errors='surrogateescape').rstrip('\r\n')
            if text in generated:
                continue
            # Similar but nonidentical generated-looking material needs review.
            if (line.rstrip(b'\r\n') in LEGACY_GENERATED_GOVERNANCE.splitlines()[2:]
                    or text.startswith(('用户规则治理：', '读取契约：', '预算：', '按需操作指南：'))):
                raise recovery.Conflict('Unknown/customized product instructions; review required')
            kept.append(line)
        raw = b''.join(kept)
    return raw


def retire_legacy_product_instructions(raw, runtime):
    return map_text(raw,lambda part:_retire_legacy_text(part,runtime),assembled=True)


def _retire_legacy_text(raw, runtime):
    """Frozen old-manager instruction fragments; retain surrounding user prose.

    Only called inside the inventoried legacy-v0 public source scope. Unknown
    path variants remain conflicts, not a regexp-based user-text rewrite.
    """
    raw=raw.replace('公共源修改后运行同步工具。'.encode(),b'')
    handoff=('`'+str(runtime.home/'.agents-group'/'tmp/<任务 ID>/handoff.md')+'`').encode()
    raw=raw.replace(handoff,'临时交接文件'.encode())
    product=('用户级共享用 `~/.agents-group/manage.py`，项目级共享用 '
             '`~/.agents-group/project_manage.py --project <项目根>`，后者只投影该项目；').encode()
    raw=raw.replace(product,b'')
    raw=raw.replace('直接编辑公共源后须显式运行管理命令或 `sync.py`，不会自动生效。'.encode(),b'')
    kept=[]
    for line in raw.splitlines(keepends=True):
        if (line.startswith('- 临时交接文件、Skill/MCP 安装同步、ClawPower 凭据的具体操作，按需读取 '.encode())
                and b'`~/.agents-group/references/operations.md`' in line):
            continue  # Its complete user reference body is independently expanded.
        kept.append(line)
    return b''.join(kept)


# Frozen complete producer unit; never classify individual headings as ownership.
FUSION_GENERATED_PREFIX = (
    '# 用户记忆\n\n## L1 概要\n\n'
    '当前有效结论：以下记忆经完整清单确认后共享；独有与未选内容保留。\n'
    '待办：记忆变化后更新概要和索引。\n\n## L2 原文与来源\n'
).encode()


class FusionEvidenceReader:
    """Same proof reads from disk or an explicit immutable uninstall snapshot map."""
    def __init__(self, nodes=None):
        self.nodes = nodes

    def safe(self, value):
        if self.nodes is None: return recovery.safe(value)
        path = Path(value)
        if not path.is_absolute() or os.path.normpath(str(path)) != str(path):
            raise recovery.Conflict('Noncanonical snapshot path')
        for parent in (path, *path.parents):
            if self.nodes.get(str(parent),{}).get('kind') == 'symlink':
                raise recovery.Conflict('Symlink in snapshot evidence')
        return path

    def file(self, path):
        path = self.safe(path)
        if self.nodes is None: return not path.is_symlink() and path.is_file()
        return self.nodes.get(str(path),{}).get('kind') == 'file'

    def read(self, path):
        path = self.safe(path)
        if not self.file(path): raise recovery.Conflict('Missing regular snapshot evidence')
        return path.read_bytes() if self.nodes is None else bytes.fromhex(self.nodes[str(path)]['hex'])

    def manifests(self, root):
        root = self.safe(root)
        if self.nodes is None: return list(root.glob('*/manifest.json'))
        return [Path(p) for p in self.nodes if Path(p).name=='manifest.json' and Path(p).parent.parent==root]

    def children(self, root):
        root = self.safe(root)
        if self.nodes is None: return {p.name for p in root.iterdir()}
        if self.nodes.get(str(root),{}).get('kind') != 'directory':
            raise recovery.Conflict('Missing snapshot evidence directory')
        return {Path(p).name for p in self.nodes if Path(p).parent==root}


def fusion_generated_units(runtime, original, *, evidence=None):
    """Prove topic wrappers through a closed committed fusion topic chain.

    Only exact connected before/after states count; an ambiguous producer chain requires
    review. Native user text and Context Keeper spans are outside this classifier.
    """
    import json
    from . import registry
    evidence = evidence or FusionEvidenceReader()
    index = runtime.root/'memories/MEMORY.md'
    index_raw = bytes.fromhex(original[str(index)]['hex'])
    units = {}
    signature = '当前有效结论：以下记忆经完整清单确认后共享'.encode()
    for name, state in original.items():
        path = Path(name)
        if state['kind'] != 'file' or path == index: continue
        raw = bytes.fromhex(state['hex'])
        parts = [part for protected,part in protected_parts(raw) if not protected]
        looks_generated = any(signature in part or '待办：记忆变化后更新概要和索引。'.encode() in part for part in parts)
        if not looks_generated: continue
        if (path.parent != index.parent or not raw.startswith(FUSION_GENERATED_PREFIX)
                or sum(part.count(FUSION_GENERATED_PREFIX) for part in parts) != 1):
            raise recovery.Conflict('Unknown/customized fusion governance; review required')
        link = ('- 用户记忆：['+path.name+']('+path.name+')\n').encode()
        if (sum(line == link for line in index_raw.splitlines(keepends=True)) != 1
                or index_raw.count(('('+path.name+')').encode()) != 1):
            raise recovery.Conflict('Missing/duplicate fusion navigation; review required')
        candidates = evidence.manifests(runtime.backups)
        if len(candidates) > 256: raise recovery.Conflict('Bounded fusion producer evidence exhausted')
        from . import paths
        config = paths.select_platform(paths.load_agents_table(),'darwin')
        allowed = set(paths.allowed_user_paths(config,None,home=str(runtime.home)))
        topic_rows = []
        index_rows = []
        def previous_bytes(row, manifest):
            before = row['before']
            if before['kind'] == 'absent': return None
            saved = before.get('backup')
            if before['kind'] != 'file' or not isinstance(saved,str) or Path(saved).name != saved:
                raise recovery.Conflict('Invalid fusion before evidence; review required')
            backup = manifest.parent/saved
            if not evidence.file(backup): raise recovery.Conflict('Missing fusion backup; review required')
            value = evidence.read(backup)
            if recovery.digest(value) != before['fingerprint']: raise recovery.Conflict('Fusion backup drift; review required')
            return value
        for manifest in candidates:
            if not evidence.file(manifest): continue
            data = json.loads(evidence.read(manifest),object_pairs_hook=registry._no_duplicates)
            if data.get('operation') != 'organize-user-rules' or data.get('status') != 'committed': continue
            rows = data.get('entries',[])
            if not any(r['path']==name for r in rows): continue
            expected_keys = {'schema_version','operation','status','registry_path','created_directories','entries','error'}
            if data.get('phased_writes') is True: expected_keys.add('phased_writes')
            if set(data)!=expected_keys or data['schema_version']!=1 or data['error'] is not None:
                raise recovery.Conflict('Unknown fusion history schema; review required')
            if len({r['path'] for r in rows})!=len(rows) and not data.get('phased_writes'):
                raise recovery.Conflict('Duplicate fusion outputs; review required')
            if any(not evidence.safe(d).is_relative_to(index.parent) for d in data['created_directories']):
                raise recovery.Conflict('Unexpected fusion created directory; review required')
            if data.get('registry_path') not in (None,str(runtime.registry)):
                raise recovery.Conflict('Invalid fusion registry scope; review required')
            expected = {'manifest.json'}
            for row in rows:
                target = evidence.safe(row['path'])
                if (row['path'] not in allowed and target != runtime.registry
                        and not (target.is_relative_to(index.parent) and target.suffix=='.md')):
                    raise recovery.Conflict('Invalid fusion history target; review required')
                if row.get('attempted') is not True or row['after']['kind'] != 'file':
                    raise recovery.Conflict('Incomplete fusion history; review required')
                previous_bytes(row,manifest)
                if row['before']['kind']=='file':expected.add(row['before']['backup'])
            if evidence.children(manifest.parent) != expected:
                raise recovery.Conflict('Fusion history closure drift; review required')
            # Retain the existing exact Claude observation-only delta contract.
            if data.get('registry_path') is not None:
                import copy
                vrows=[r for r in rows if r['path']==str(runtime.registry)]
                native=paths.expand_path(config['claude']['user_entry'],home=str(runtime.home))
                nrows=[r for r in rows if r['path']==native]
                if len(vrows)!=1 or rows[-1] is not vrows[0] or len(nrows)!=1 or data.get('phased_writes'):
                    raise recovery.Conflict('Invalid fusion reference history; review required')
                old=registry.validate_registry(json.loads(previous_bytes(vrows[0],manifest)),allowed_user_paths=allowed)
                updated=copy.deepcopy(old);matched=[]
                for oid,obj in old['machine']['objects'].items():
                    if (obj['path']==native and obj['kind']=='import' and obj['scope']=='machine'
                            and obj['ownership']=='reused' and obj['marker'] is None and obj['agents']==['claude']
                            and obj['original_existed'] is True and obj['backup_manifest'] is None and obj['consumers']==[]
                            and obj['fingerprint']=={'algorithm':'sha256','basis':'file_bytes','value':nrows[0]['before']['fingerprint']}):
                        updated['machine']['objects'][oid]['fingerprint']['value']=nrows[0]['after']['fingerprint'];matched.append(oid)
                if len(matched)!=1 or recovery.digest(registry.serialize_registry(updated,allowed_user_paths=allowed))!=vrows[0]['after']['fingerprint']:
                    raise recovery.Conflict('Fusion reference history changes ownership; review required')
            elif any(r['path']==str(runtime.registry) for r in rows):
                raise recovery.Conflict('Unbound fusion registry history; review required')
            topic_rows += [(r,manifest) for r in rows if r['path']==name]
            index_rows += [(r,manifest) for r in rows if r['path']==str(index)]
        creations=[pair for pair in topic_rows if pair[0]['before']['kind']=='absent']
        if len(creations)!=1: raise recovery.Conflict('Unproven/ambiguous fusion creation; review required')
        current_pair=creations[0];visited=set();states=[]
        while True:
            row,manifest=current_pair
            identity=(str(manifest),id(row))
            if identity in visited: raise recovery.Conflict('Cyclic fusion history; review required')
            visited.add(identity)
            matches=[pair for pair in topic_rows if pair[0]['before']['kind']=='file'
                     and pair[0]['before']['fingerprint']==row['after']['fingerprint']
                     and pair[0]['before']['mode']==row['after']['mode']]
            if len(matches)>1: raise recovery.Conflict('Ambiguous fusion history; review required')
            after=previous_bytes(*matches[0]) if matches else raw
            if (recovery.digest(after)!=row['after']['fingerprint'] or not after.startswith(FUSION_GENERATED_PREFIX)
                    or (not matches and state['mode'] != row['after']['mode'])):
                raise recovery.Conflict('Incomplete/customized fusion history; review required')
            if after.count(FUSION_GENERATED_PREFIX)!=1:
                raise recovery.Conflict('Duplicate fusion governance; review required')
            if states and [p for protected,p in protected_parts(states[-1]) if protected] != [p for protected,p in protected_parts(after) if protected]:
                raise recovery.Conflict('Protected fusion history changed; review required')
            states.append(after)
            if not matches:break
            current_pair=matches[0]
        if len(visited)!=len(topic_rows):raise recovery.Conflict('Disconnected fusion history; review required')
        # The navigation itself was added by the same creation transaction.
        creation_manifest=creations[0][1]
        nav=[pair for pair in index_rows if pair[1]==creation_manifest]
        if len(nav)!=1:raise recovery.Conflict('Missing fusion navigation proof; review required')
        previous=previous_bytes(*nav[0])
        if previous is None or link in previous or previous+(b'' if previous.endswith(b'\n') else b'\n')+link != index_raw:
            raise recovery.Conflict('Fusion navigation history needs review')
        if recovery.digest(index_raw)!=nav[0][0]['after']['fingerprint']:
            raise recovery.Conflict('Fusion navigation drift; review required')
        units[name] = link
    return units


def public_body(runtime, original, *, evidence=None):
    """Expand a closed public document graph; no return directory or index link."""
    from . import user_entries, policy_migration
    base = runtime.root
    topic = base/'memories/topics/使用约定.md'
    known = {user_entries.usage_convention_topic_text(runtime.code).encode(), user_entries.legacy_usage_convention_topic_text(runtime.code).encode()}
    known.update(policy_migration.legacy(n, runtime) for n in
                 ('pre_route_topic', 'topic', 'old_topic'))
    visiting, done, chunks = set(), set(), []
    fusion_units = fusion_generated_units(runtime, original, evidence=evidence)

    def read(path):
        key = str(path)
        if key in visiting:
            raise recovery.Conflict('Cyclic public memory reference')
        if key in done:
            return b''
        state = original.get(key)
        if not state:
            raise recovery.Conflict('Missing/outside public memory reference: '+key)
        if state['kind'] != 'file' or path.suffix.lower() != '.md':
            raise recovery.Conflict('Nonregular public document; explicit review required: '+key)
        visiting.add(key)
        raw = bytes.fromhex(state['hex'])
        protected_parts(raw)
        if path == topic:
            def retire_topic(part):
                if not part.strip():return part
                for template in known:
                    if part.startswith(template) and not part[len(template):].strip():
                        return part[len(template):]
                raise recovery.Conflict('Unknown/customized product topic; review required')
            raw=map_text(raw,retire_topic)
        else:
            relative=path.relative_to(base)
            historical_index=(len(relative.parts)==4 and relative.parts[0]=='memories'
                              and relative.parts[1].startswith('legacy-v0-')
                              and relative.parts[2:]==('memories','MEMORY.md'))
            producer_index=path==base/'memories/MEMORY.md' or historical_index
            if not producer_index and contains_text(raw,LEGACY_GENERATED_GOVERNANCE):
                raise recovery.Conflict('Governance signature outside producer scope; review required')
            raw = strip_generated(raw, runtime, public=producer_index,
                                  historical_proof=producer_index)
        if path.is_relative_to(base/'memories') and path.relative_to(base/'memories').parts[0].startswith('legacy-v0-'):
            raw=retire_legacy_product_instructions(raw,runtime)
        if str(path) in fusion_units:
            raw = raw[len(FUSION_GENERATED_PREFIX):]
        if path == base/'memories/MEMORY.md':
            # Only proven complete navigation lines lose their generated label.
            for target, line in fusion_units.items():
                expanded_topic = read(Path(target))
                raw = map_text(raw,lambda part:b''.join(expanded_topic if row == line else row
                    for row in part.splitlines(keepends=True)))
        def expand(match):
            target = unquote(match.group(2).decode().strip('<>')).split('#', 1)[0]
            if urlsplit(target).scheme or not target:
                return match.group(0)
            resolved = Path(os.path.normpath(str(path.parent/target)))
            if not resolved.is_relative_to(base):
                raise recovery.Conflict('Public topic path escape')
            expanded=read(resolved)
            return (match.group(1)+b'\n'+expanded) if expanded else b''
        raw = map_text(raw,lambda part:re.sub(rb'\[([^\]\n]*)\]\(\s*(<[^>]+>|[^\s)]+)\s*\)', expand, part))
        def expand_import(match):
            target=unquote(match.group(1).decode())
            resolved=Path(os.path.normpath(str(path.parent/target)))
            if not resolved.is_relative_to(base):raise recovery.Conflict('Native public import escape')
            return read(resolved)
        raw=map_text(raw,lambda part:re.sub(rb'(?m)^[ \t]*@([^\s]+)[ \t]*\r?$',expand_import,part),assembled=True)
        if any(re.search(rb'(?m)^[ \t]*\[[^\]]+\]:',part) for protected,part in protected_parts(raw,assembled=True) if not protected):
            raise recovery.Conflict('Reference-style user links need explicit expansion review')
        require_no_product_dependency(raw,(runtime.root,runtime.code,'.agents-group/','memsharing-return/'),home=runtime.home,document=path)
        visiting.remove(key)
        done.add(key)
        return raw

    index = base/'memories/MEMORY.md'
    chunks.append(read(index))
    # Do not discard unlinked user originals because they are called historical.
    for key, state in sorted(original.items()):
        if state['kind'] in ('directory','absent'):
            continue
        if key not in done:
            chunks.append(read(Path(key)))
    return b'\n\n'.join(chunk for chunk in chunks if chunk.strip())


def _scoped_layout(raw):
    """Byte-preserving Markdown sections and items outside opaque CK spans."""
    from .user_rules_organize import _segments
    protected=[];offset=0
    for opaque,data in protected_parts(raw,assembled=True):
        if opaque:protected.append((offset,offset+len(data)))
        offset+=len(data)
    sections=[{'scope':(), 'headers':(), 'end':len(raw)}];stack=[];offset=0;fence=None;covered=list(protected);heading_spans=[]
    for line in raw.splitlines(keepends=True):
        start=offset;offset+=len(line)
        if any(start<b and offset>a for a,b in protected):continue
        stripped=line.lstrip();mark=re.match(rb'(```+|~~~+)',stripped)
        if mark:
            token=mark[1][:3]
            if fence is None:fence=token
            elif fence==token:fence=None
            continue
        if fence:continue
        match=re.match(rb'^(#{1,6})[ \t]+(.+?)\r?\n?$',line.removeprefix(b'\xef\xbb\xbf') if start==0 else line)
        if match:
            covered.append((start,offset));heading_spans.append((start,offset))
            depth=len(match[1]);title=match[2].rstrip(b'\r\n')
            stack=[entry for entry in stack if entry[0]<depth]+[(depth,title,line)]
            sections[-1]['end']=start
            sections.append({'scope':tuple(t for _,t,_ in stack),'headers':tuple(h for _,_,h in stack),'end':len(raw),'start':offset})
    items=[];section=0
    for left,right in _segments(raw,protected):
        # The item splitter deliberately has a smaller heading grammar. A BOM
        # heading can therefore also occur in an item span: subtract the already
        # classified exact heading bytes instead of duplicating them as prose.
        ranges=[(left,right)]
        for a,b in heading_spans:
            ranges=[piece for lo,hi in ranges for piece in
                    ([(lo,min(a,hi))] if lo<a else [])+([(max(b,lo),hi)] if hi>b else [])]
        for left,right in ranges:
            if left>=right or not raw[left:right].strip():continue
            covered.append((left,right))
            while section+1<len(sections) and left>=sections[section]['end']:section+=1
            sections[section].setdefault('items',[]).append(raw[left:right])
            items.append((sections[section]['scope'],raw[left:right],sections[section]['headers']))
    cursor=0
    for left,right in sorted(covered):
        if left>cursor and raw[cursor:left].strip():raise recovery.Conflict('Unclassified Markdown content; review required')
        cursor=max(cursor,right)
    if raw[cursor:].strip():raise recovery.Conflict('Unclassified Markdown content; review required')
    return sections,items,protected


def _merge_scoped_native(opaque, body):
    sections,items,protected=_scoped_layout(opaque)
    incoming_sections,_,incoming_ck=_scoped_layout(body)
    def key(scope,text):return scope,text.replace(b'\r\n',b'\n').rstrip(b'\r\n')
    present={key(scope,text) for scope,text,_ in items}
    positions={section['scope']:section['end'] for section in sections}
    occurrences={}
    for section in sections:occurrences[section['scope']]=occurrences.get(section['scope'],0)+1
    streams={};known=set(positions);inserted=set();introduced_scopes=set()

    def destination(scope):
        candidates=[prefix for prefix in positions if prefix and scope[:len(prefix)]==prefix]
        ancestor=max(candidates,key=len) if candidates else ()
        if scope==():ancestor=()
        if ancestor or scope==():
            if occurrences[ancestor]!=1:raise recovery.Conflict('Ambiguous repeated native scope; review required')
            position=positions[ancestor];context=ancestor
        else:
            position=len(opaque);context=sections[-1]['scope']
        if any(a<position<b for a,b in protected):raise recovery.Conflict('Insertion inside Context Keeper forbidden')
        stream=streams.setdefault(position,{'scope':context,'chunks':[]})
        return stream

    def emit(stream,kind,raw):
        if not raw:return
        chunks=stream['chunks']
        if kind=='header' and chunks and chunks[-1][0]=='header':
            chunks[-1]=('header',chunks[-1][1]+raw)
        else:chunks.append((kind,raw))

    # Process each source section once in source order, including empty parents.
    # A stream records its current hierarchy so siblings reuse only their common
    # prefix; a child can never cause its parent heading to be emitted twice.
    for section in incoming_sections:
        scope=section['scope'];headers=section['headers']
        pending=[]
        for text in section.get('items',[]):
            identity=key(scope,text)
            if identity not in present:pending.append(text);present.add(identity)
        if not pending and (not scope or scope in known):continue
        stream=destination(scope);current=stream['scope']
        common=0
        while common<min(len(scope),len(current)) and scope[common]==current[common]:common+=1
        if common==len(scope) and len(current)>len(scope):
            if not scope:raise recovery.Conflict('Cannot reset unscoped content; review required')
            common-=1  # Reopen an ancestor only when content actually returns to it.
        emit(stream,'header',b''.join(headers[common:]))
        if scope not in positions:introduced_scopes.add(scope)
        stream['scope']=scope
        known.update(scope[:depth] for depth in range(1,len(scope)+1))
        for text in pending:
            emit(stream,'item',text);inserted.add(key(scope,text))
    keeper={opaque[a:b] for a,b in protected}
    for a,b in incoming_ck:
        chunk=body[a:b]
        if chunk not in keeper:
            stream=streams.setdefault(len(opaque),{'scope':sections[-1]['scope'],'chunks':[]})
            emit(stream,'opaque',chunk);keeper.add(chunk)
    result=opaque
    for position,stream in sorted(streams.items(),reverse=True):
        chunks=[raw for _,raw in stream['chunks']]
        if not chunks:continue
        payload=b'\n\n'.join(chunks)
        left=result[:position];right=result[position:]
        result=left+(b'' if not left or left.endswith(b'\n\n') else b'\n' if left.endswith(b'\n') else b'\n\n')+payload+(b'' if payload.endswith(b'\n\n') else b'\n' if payload.endswith(b'\n') else b'\n\n')+right
    # Raw heading levels can differ from the inferred title path. Refuse rather
    # than silently place original text under a different scope.
    final_sections,final_items,_=_scoped_layout(result)
    if not introduced_scopes.issubset({section['scope'] for section in final_sections}):
        raise recovery.Conflict('Inserted heading hierarchy cannot be preserved; review required')
    if not inserted.issubset({key(scope,text) for scope,text,_ in final_items}):
        raise recovery.Conflict('Inserted scope cannot be preserved; review required')
    return result


def merge_native(opaque, body, *, scoped=False):
    """Protected spans are complete dedup units; paragraph logic never sees them."""
    if scoped:return _merge_scoped_native(opaque,body)
    old_parts=protected_parts(opaque,assembled=True)
    new_parts=protected_parts(body,assembled=True)
    if not body.strip() or body in opaque:return opaque
    delimiter=rb'(\r?\n(?:[ \t]*\r?\n)+)'
    present={entry for protected,data in old_parts if not protected
             for entry in re.split(delimiter,data)[::2]}
    keeper={data for protected,data in old_parts if protected}
    additions=[]
    for protected,data in new_parts:
        if protected:
            if data not in keeper:additions.append(data);keeper.add(data)
            continue
        parts=re.split(delimiter,data)
        for index in range(0,len(parts),2):
            entry=parts[index];separator=parts[index+1] if index+1<len(parts) else b''
            if not entry.strip():
                additions.append(entry+separator)
            elif entry not in present:
                additions.append(entry+separator);present.add(entry)
    addition=b''.join(additions)
    if not addition.strip():return opaque
    return opaque+(b'\n' if opaque.endswith(b'\n') else b'\n\n')+addition


def retire_legacy_pointer(raw, native_path, *, proven):
    return map_text(raw,lambda part:_retire_legacy_pointer_text(part,native_path,proven=proven))


def _retire_legacy_pointer_text(raw, native_path, *, proven):
    index = Path(native_path).parent/'memsharing-return/memories/MEMORY.md'
    token = str(index).encode()
    if token not in raw:
        return raw
    if not proven:
        raise recovery.Conflict('Unproven legacy return dependency')
    known = {('@'+str(index)).encode(),
             ('开始任务前读取并遵守 %s；按索引按需读取主题，路径不可用时说明。' % index).encode(),
             ('开始任务前读取并遵守 %s；读不到就说明。' % index).encode()}
    lines = raw.splitlines(keepends=True)
    hits = [line for line in lines if token in line]
    if len(hits)!=1 or hits[0].strip() not in known:
        raise recovery.Conflict('Unknown legacy return instruction; review required')
    return raw.replace(hits[0],b'',1)


def source_returns(runtime, original, native_paths):
    """Plan exact outstanding source-count restoration inside machine uninstall."""
    from . import memory_share as share
    import copy
    available = share._available_migrations(runtime)
    consumed = share._consumed_index(runtime)
    records = {ref: r for ref, r in available.items() if ref not in consumed}
    restored = {}; residual = copy.deepcopy(original); spans = {}
    by_manifest = {}
    for ref, record in records.items():
        if record['path'] not in native_paths or record.get('topic') not in original:
            raise recovery.Conflict('Unknown source return target')
        topic = record['topic']; state = original[topic]
        raw = bytes.fromhex(state['hex']) if state['kind']=='file' else b''
        left, right = record['public_offset'], record['public_end']
        text = bytes.fromhex(record['text_hex'])
        if raw[left:right] != text or recovery.digest(text) != record['text_sha256']:
            raise recovery.Conflict('Public source span drift; explicit current-byte return plan required')
        spans.setdefault(topic,set()).add((left,right))
        by_manifest.setdefault(record['manifest'],{}).setdefault(record['path'],[]).append(record)
    for manifest, paths in sorted(by_manifest.items(), reverse=True):
        for path, members in paths.items():
            state = recovery.snapshot(path)
            raw = restored.get(path, bytes.fromhex(state['hex']) if state['kind']=='file' else b'')
            if recovery.digest(raw) != share._after_sha(runtime,members[0]):
                # Later approved shares may append content. Prove the old after
                # prefix from its own backed-up before bytes, never from prose.
                import json
                manifest_path=Path(members[0]['manifest_path'])
                producer=json.loads(manifest_path.read_bytes())
                row=next((r for r in producer['entries'] if r['path']==path),None)
                saved=row['before'].get('backup') if row else None
                if not isinstance(saved,str) or Path(saved).name!=saved:
                    raise recovery.Conflict('Native source drift; missing prefix proof: '+path)
                prior=(manifest_path.parent/saved).read_bytes()
                if recovery.digest(prior)!=row['before']['fingerprint']:
                    raise recovery.Conflict('Native source drift; backup mismatch: '+path)
                all_members=[r for r in producer['operation_metadata']['share_user_memory']['migrations'] if r['path']==path]
                for r in sorted(all_members,key=lambda r:r['start'],reverse=True):
                    if prior[r['start']:r['end']]!=bytes.fromhex(r['text_hex']):
                        raise recovery.Conflict('Native source drift; invalid source proof: '+path)
                    prior=prior[:r['start']]+prior[r['end']:]
                if recovery.digest(prior)!=share._after_sha(runtime,members[0]) or not raw.startswith(prior):
                    raise recovery.Conflict('Native source drift; explicit current-byte return plan required: '+path)
            ordered = sorted(members,key=lambda r:r['start'])
            inserts=[];removed=0
            for record in ordered:
                inserts.append((record['start']-removed,bytes.fromhex(record['text_hex'])))
                removed += record['end']-record['start']
            for offset,text in reversed(inserts):
                if not 0 <= offset <= len(raw):raise recovery.Conflict('Invalid original source offset')
                raw=raw[:offset]+text+raw[offset:]
            restored[path]=raw
    for topic, positions in spans.items():
        raw=bytes.fromhex(residual[topic]['hex'])
        positions=sorted(positions)
        if any(c<b for (a,b),(c,d) in zip(positions,positions[1:])):
            raise recovery.Conflict('Overlapping source public spans')
        for left,right in reversed(positions):raw=raw[:left]+raw[right:]
        # Retire only the exact wrapper emitted by the known legacy producer.
        expected='# 用户规则\n'.encode()
        by_span={}
        for record in records.values():
            if record['topic']==topic:
                by_span.setdefault((record['public_offset'],record['public_end']),record)
        for _,record in sorted(by_span.items()):
            context=('\n'+'\n'.join('#'*(level+2)+' '+title for level,title in enumerate(record['scope']))+'\n').encode() if record['scope'] else b'\n'
            expected += context+b'\n'+bytes.fromhex(record['text_hex'])
        if bytes.fromhex(original[topic]['hex'])==expected:
            raw=b''
        residual[topic]['hex']=raw.hex()
    return restored,residual
