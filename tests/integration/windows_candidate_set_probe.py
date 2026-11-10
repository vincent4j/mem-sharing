"""New R2 gap checks only; synthetic fixtures and read-only handle preflight."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import uuid

root = Path(sys.argv[1]); run_id = str(uuid.UUID(sys.argv[2]))
sys.path.insert(0, str(root/'code/scripts'))
from agm_core import windows_native as w
fixtures = root/'synthetic-home'/('set-'+run_id); fixtures.mkdir()
evidence = root/'evidence'/('native-'+run_id+'.json')
if evidence.exists():raise FileExistsError('Refuse overwrite')
result = dict(run_id=run_id, argv=sys.argv, started=time.time(), platform=sys.platform,
              python=sys.version, checks=[], production_write_authorized=False)


def check(name, operation):
    base = fixtures/name; base.mkdir()
    allowed = base/'允许 中文'; allowed.mkdir()
    one = allowed/'first-long-synthetic-name.txt'; one.write_bytes(b'ONE SYNTHETIC\r\n')
    two = allowed/'second.txt'; two.write_bytes(b'TWO SYNTHETIC\r\n')
    try:
        detail=operation(allowed,one,two)
        status='unavailable' if isinstance(detail,dict) and detail.get('availability')=='unavailable' else 'passed'
        result['checks'].append(dict(name=name,status=status,detail=detail))
    except Exception as exc:result['checks'].append(dict(name=name,status='failed',type=type(exc).__name__,code=getattr(exc,'code',None),winerror=getattr(exc,'winerror',None),message=str(exc)))


def refused(paths, allowed):
    try:
        with w.inspect_candidate_set(paths, allowed_root=str(allowed)):pass
    except w.NativeInspectionError as exc:
        assert exc.code=='candidate_overlap',(exc.code,exc.winerror)
        return exc.code
    raise AssertionError('Overlap accepted')


def disjoint(allowed,one,two):
    with w.inspect_candidate_set([str(one),str(two)],allowed_root=str(allowed)) as observed:
        assert observed['candidate_count']==2 and not observed['production_write_authorized'] and not observed['race_free']
        assert observed['registered_cloud_roots_checked']
        return {k:observed[k] for k in ('candidate_count','production_write_authorized','race_free')}


def nested(allowed,one,two):
    return [refused(paths,allowed) for paths in ([str(allowed),str(one)],[str(one),str(allowed)])]


def set_drift(allowed,one,two):
    moved=allowed/'moved.txt';renamed=False
    try:
        try:
            with w.inspect_candidate_set([str(one),str(two)],allowed_root=str(allowed)):
                try:os.replace(one,moved);renamed=True
                except PermissionError as exc:return {'blocked_winerror':exc.winerror}
        except w.NativeInspectionError as exc:
            assert renamed and exc.code=='node_drift',(exc.code,exc.winerror)
            return dict(rename_allowed=True,drift_detected=True)
        raise AssertionError('Set drift not detected')
    finally:
        if renamed:os.replace(moved,one)


def short_alias(allowed,one,two):
    api=w._API();f=api.k.GetShortPathNameW
    f.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,w.DWORD];f.restype=w.DWORD
    buf=ctypes.create_unicode_buffer(32768);size=f(str(one),buf,len(buf))
    if not size:return dict(availability='unavailable',winerror=ctypes.get_last_error())
    assert size<len(buf),'short name buffer too small'
    short=buf.value
    if short.casefold()==str(one).casefold():return dict(availability='unavailable',reason='no_distinct_short_name')
    def identity(path):
        h=api.k.CreateFileW(path,0x80,3,None,3,0x02200000,None)
        assert h not in (None,ctypes.c_void_p(-1).value)
        try:
            info=api.info(h,18,w.FileIdInfo())
            return info.volume,bytes(info.file_id)
        finally:api.k.CloseHandle(h)
    assert identity(str(one))==identity(short),'short alias identity mismatch'
    try:
        with w.inspect_candidate_path(short,allowed_root=str(allowed)):pass
    except w.NativeInspectionError as exc:
        assert exc.code=='path_alias_refused',(exc.code,exc.winerror)
        return dict(alias_same_identity=True,code=exc.code)
    raise AssertionError('Distinct short-name candidate accepted')


def cloud_observation(allowed,one,two):
    with w.inspect_candidate_path(str(one),allowed_root=str(allowed),registered_cloud_check=True) as observed:
        assert observed['registered_cloud_root_checked'] and not observed['registered_cloud_root_present']
        assert not observed['storage_provider_verified'] and not observed['production_write_authorized']
        return {key:observed[key] for key in ('registered_cloud_hresult','cloud_hresult_mapping_inferred','registered_cloud_root_checked','storage_provider_verified','production_write_authorized')}


def drive_mapping(allowed,one,two):
    api=w._API();query=api.k.QueryDosDeviceW
    query.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,w.DWORD];query.restype=w.DWORD
    buffer=ctypes.create_unicode_buffer(32768);size=query(allowed.drive,buffer,len(buffer))
    assert size and size<len(buffer),ctypes.get_last_error()
    return dict(readonly_mapping_observed=True,logical_mapping=buffer.value.startswith('\\??\\'),mapping_counterexample_created=False)


check('disjoint_set',disjoint)
check('duplicate_object',lambda allowed,one,two:refused([str(one),str(one)],allowed))
check('case_alias_duplicate',lambda allowed,one,two:refused([str(one),str(one).upper()],allowed))
check('ancestor_descendant_both_orders',nested)
check('held_set_named_drift',set_drift)
check('short_name_alias',short_alias)
check('registered_cloud_root_observation',cloud_observation)
check('drive_mapping_readonly',drive_mapping)
result['not_covered']=['enabled case-sensitive directory requires elevated fixture','short names depend on native availability','drive mappings not created','registered cloud root positive fixture not created; unregistered syncing unknown','write/ACL/atomic transaction']
result['finished']=time.time()
with evidence.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
print(json.dumps([(r['name'],r['status']) for r in result['checks']]))
sys.exit(1 if any(r['status']=='failed' for r in result['checks']) else 0)
