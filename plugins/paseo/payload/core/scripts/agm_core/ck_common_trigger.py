"""Read-only recognition of the audited CK common trigger, never ownership.

This module does not relax protected spans. Callers must still bind the whole
proposal, obtain the user's selection, and prove reading/return paths before
using a recognized body as a migration candidate. Upstream installers remain
independent; changed or unknown upstream text stays protected until audited.
"""
import re
from pathlib import Path

from . import entries


# Audited public BRIDGE_RULES from upstream 66d7e919 (not an installer pin).
COMMON_SHA256 = 'e58e12c8e7587ddf7049bea6f7946c738bf6fd33df52a8215795bc5842bae323'
COMMON_SIZE = 729
MARKERS = (
    (b'<!-- context-keeper:start -->', b'<!-- context-keeper:end -->',
     '## Context Keeper'),
    (b'<!-- context-keeper:workbuddy:start -->',
     b'<!-- context-keeper:workbuddy:end -->',
     '## Context Keeper（WorkBuddy 桥接，待运行时验收）'),
)


def recognize(data, agent):
    """Return the exact common body span or None; malformed blocks raise.

    The native title and both markers are outside the returned span. Duplicate,
    reversed, mixed, nested and mid-line markers are never treated as ordinary
    movable text. Unknown but well-formed bodies return None, remaining opaque.
    No filesystem access, writes, normalization or semantic equivalence occurs.
    """
    if agent not in ('codex', 'claude', 'workbuddy', 'zcode', 'dsh', 'opencode'):
        raise entries.EntryConflict('Unknown CK host')
    found = []
    for start, end, title in MARKERS:
        span = entries.managed_span(data, start, end)
        if span:
            found.append((span, start, end, title))
    if not found:
        return None
    if len(found) != 1:
        raise entries.EntryConflict('Mixed CK blocks')
    (left, right), start, end, title = found[0]
    expected = MARKERS[1 if agent == 'workbuddy' else 0]
    if start != expected[0]:
        return None
    if (left and data[left-1:left] != b'\n') or (right < len(data) and data[right:right+1] != b'\n'):
        raise entries.EntryConflict('CK markers must occupy complete lines')
    prefix = start + b'\n' + title.encode() + b'\n\n'
    if not data[left:right].startswith(prefix):
        return None
    body_start, body_end = left + len(prefix), right - len(end)
    body = data[body_start:body_end]
    if len(body) != COMMON_SIZE or entries.sha256(body) != COMMON_SHA256:
        return None
    return {'start': body_start, 'end': body_end, 'text': body.decode(),
            'sha256': COMMON_SHA256, 'block_start': left, 'block_end': right}


KIND = 'ck_common_trigger'
READ_RULE = '开始任务前读取并遵守本目录的 user-rules.md（存在时）'.encode()


def candidate(data, agent, protected=()):
    result = recognize(data, agent)
    if result is None:
        return None
    from . import memory_share as ms
    marker = MARKERS[agent == 'workbuddy'][0]
    if any(m.start() < result['block_start'] < m.end() for m in re.finditer(rb'<!--[\s\S]*?-->', data)):
        return None
    if result['block_start'] not in ms._unfenced_offsets(data, marker):
        return None
    for left, right in protected or ms._protected_spans(data):
        if left < result['end'] and right > result['start'] and (left != result['block_start'] or right > result['block_end'] + 1):
            return None
    return dict(result, kind=KIND)


def shared_span(runtime, public, topic):
    """Reuse only an outstanding, exact producer-proven common body span."""
    from . import memory_share as ms
    from .user_rules_organize import _created_public_span
    consumed = ms._consumed_index(runtime)
    spans = set()
    records = ms._available_migrations(runtime)
    creators = {(r['public_offset'], r['public_end']) for r in records.values()
                if r.get('kind') == KIND and r.get('topic') == str(topic)
                and _created_public_span(r, bytes.fromhex(r['text_hex']))}
    for ref, record in records.items():
        if ref in consumed or record.get('kind') != KIND:
            continue
        if record.get('topic') != str(topic):
            raise entries.EntryConflict('CK common trigger already shared to another topic')
        raw = bytes.fromhex(record['text_hex'])
        left, right = record['public_offset'], record['public_end']
        if (entries.sha256(raw) != COMMON_SHA256 or public[left:right] != raw):
            raise entries.EntryConflict('Shared CK common trigger drift; explicit return required')
        if (left, right) not in creators:
            raise entries.EntryConflict('Missing CK public producer proof')
        spans.add((left, right))
    if len(spans) > 1:
        raise entries.EntryConflict('Multiple public CK copies require explicit review')
    if spans:
        return next(iter(spans))
    # Recognizing text is not ownership proof. Never silently duplicate or claim it.
    if COMMON_SHA256 == entries.sha256(public):
        raise entries.EntryConflict('Unproven public CK common trigger')
    for start in range(len(public)):
        if public[start:start+1] == b'\xe4' and entries.sha256(public[start:start+COMMON_SIZE]) == COMMON_SHA256:
            raise entries.EntryConflict('Unproven public CK common trigger')
    return None


def require_reader(index):
    from . import memory_share as ms
    full = READ_RULE + '；其他主题按需读取。相关文件无法读取时，说明并停止依赖该内容的操作。'.encode()
    valid = ms._unfenced_offsets(index, full)
    protected = ms._protected_spans(index)
    if not any((pos == 0 or index[pos-1:pos] == b'\n') and
               (pos+len(full) == len(index) or index[pos+len(full):pos+len(full)+1] in (b'\r', b'\n'))
               and not any(left <= pos < right for left, right in protected)
               and not any(m.start() <= pos < m.end() for m in re.finditer(rb'<!--[\s\S]*?-->', index))
               for pos in valid):
        raise entries.EntryConflict('CK sharing requires the mandatory user-rules.md reading contract')


def superseded_sources(runtime, migrations):
    from . import memory_share as ms
    paths = {r['path'] for r in migrations if r.get('kind') == KIND}
    if not paths:
        return []
    consumed = ms._consumed_index(runtime)
    return [{'manifest': ref[0], 'migration': ref[1],
             'manifest_sha256': entries.sha256(ms.read_snapshot(Path(record['manifest_path'])).data)}
            for ref, record in ms._available_migrations(runtime).items()
            if ref not in consumed and record.get('kind') == KIND and record['path'] in paths]


def validate_replacement(runtime, manifest, data, record):
    """Replay the source deletion from durable transaction evidence, read-only."""
    from . import memory_share as ms
    path = record['path']
    rows = [row for row in data.get('entries', []) if row.get('path') == path]
    if not rows or any(row.get('attempted') is not True for row in rows):
        raise entries.EntryConflict('Missing CK replacement source transaction')
    first, last = rows[0], rows[-1]
    before = first['before']
    backup = before.get('backup')
    if before.get('kind') != 'file' or not isinstance(backup, str) or Path(backup).name != backup:
        raise entries.EntryConflict('Missing CK replacement before backup')
    snap = ms.read_snapshot(manifest.parent / backup)
    if snap.kind != 'file' or snap.fingerprint != before['fingerprint']:
        raise entries.EntryConflict('CK replacement backup drift')
    prior = snap.data
    body = candidate(prior, record['agent'])
    if body is None or (body['start'], body['end']) != (record['start'], record['end']):
        raise entries.EntryConflict('Replacement did not migrate a native CK body')
    meta = data['operation_metadata']['share_user_memory']
    members = [r for r in meta['migrations'] if r['path'] == path]
    raw = prior
    boundary = len(raw)
    for r in sorted(members, key=lambda r: r['start'], reverse=True):
        if not 0 <= r['start'] < r['end'] <= boundary or raw[r['start']:r['end']].hex() != r['text_hex']:
            raise entries.EntryConflict('CK replacement source spans drift')
        boundary = r['start']
        raw = raw[:r['start']] + raw[r['end']:]
    raw = ms.clean_native_navigation(record['agent'], raw, runtime, original=prior, migrated=members)
    created = [r for r in meta.get('entries_created', []) if r['path'] == path]
    if created:
        block = ms._entry_bytes(record['agent'], runtime)
        if len(created) != 1 or created[0]['bytes_hex'] != block.hex():
            raise entries.EntryConflict('Invalid CK replacement native entry')
        raw += (ms._separator(raw) or b'\n') + block
    if (last['after'].get('kind') != 'file' or entries.sha256(raw) != last['after']['fingerprint']
            or any(a['after']['fingerprint'] != b['before']['fingerprint'] for a,b in zip(rows, rows[1:]))):
        raise entries.EntryConflict('CK replacement deletion cannot be reproduced')
    if not ms._entry_ok(record['agent'], raw, runtime):
        raise entries.EntryConflict('CK replacement lost its public reader')
