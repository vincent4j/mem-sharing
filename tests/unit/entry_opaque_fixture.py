"""Exact non-owned byte proof for the approved top-entry semantics."""
from agm_core.entries import managed_span
from agm_core import user_entries

def remember_mode(test, path):
    import stat
    if not hasattr(test, '_opaque_modes'):test._opaque_modes={}
    test._opaque_modes[str(path)]=stat.S_IMODE(path.stat().st_mode)

def assert_opaque(test, raw, original, *, index, path):
    import stat
    test.assertEqual(stat.S_IMODE(path.stat().st_mode),test._opaque_modes[str(path)])
    spans=[]
    for marker in (user_entries.BASE_MARKER,user_entries.CLAUDE_FALLBACK_MARKER):
        span=managed_span(raw,**marker)
        if span:spans.append(span)
    token=('@'+str(index)).encode();offset=0
    for line in raw.splitlines(keepends=True):
        if line.rstrip(b'\r\n')==token:spans.append((offset,offset+len(line)))
        offset+=len(line)
    test.assertTrue(spans,'expected exact owned top unit')
    cursor=0;chunks=[]
    for start,end in sorted(spans):chunks.append(raw[cursor:start]);cursor=end
    chunks.append(raw[cursor:]);remainder=b''.join(chunks)
    # Only a newly required separator may precede the opaque original.
    bom = b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b''
    opaque = original[len(bom):]
    test.assertIn(remainder,(original,bom+b'\n'+opaque,bom+b'\n\n'+opaque))
    test.assertEqual(raw[:len(bom)],bom)
    test.assertTrue(raw.endswith(opaque))
