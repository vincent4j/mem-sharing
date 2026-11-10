"""One bound CF-v3 fixture's Archive removal. Never general metadata recovery."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

PLAN = None


class BasicInfo(C.Structure):
    _fields_ = [('creation_time', C.c_int64), ('last_access_time', C.c_int64),
                ('last_write_time', C.c_int64), ('change_time', C.c_int64),
                ('attributes', C.c_uint32)]


def need(value, message):
    if not value:
        raise RuntimeError(message)


def guard(snapshot, plan, expected_attributes):
    need(snapshot['identity'] == plan['identity'] and snapshot['named_identity'] == plan['identity'], 'Identity drift')
    need(snapshot['security_sha256'] == plan['security_sha256']
         and snapshot['named_security_sha256'] == plan['security_sha256'], 'Security drift')
    need(snapshot['attributes'] == expected_attributes and snapshot['basic']['attributes'] == expected_attributes
         and snapshot['named_attributes'] == expected_attributes, 'Unexpected attribute bits; preserve')
    need(snapshot['reparse_tag'] == snapshot['named_reparse_tag'] == 0, 'Reparse tag drift')
    need(snapshot['entries'] == [], 'Nonempty fixture; preserve')


def exercise(runtime, save, plan):
    result = dict(status='failed', started=time.time(), write_attempted=False,
                  retry_attempted=False, automatic_rollback_attempted=False,
                  full_metadata_restored=False, production_write_authorized=False,
                  full_cf_gate_verified=False, race_free=False)
    try:
        result['before'] = runtime.snapshot()
        guard(result['before'], plan, 48)
        save('before', result['before'])
        save('write-intent', dict(result, request=dict(creation_time=0,last_access_time=0,last_write_time=0,change_time=0,attributes=16),
                                  baseline_receipts=plan['receipts'], source_sha256=runtime.source_sha256))
        result['immediate_before_write'] = runtime.snapshot()
        guard(result['immediate_before_write'], plan, 48)
        save('immediate-before-write', result['immediate_before_write'])
        result['write_attempted'] = True
        result['call_result'] = runtime.apply()
        need(result['call_result']['success'] is True, 'SetFileInformationByHandle failed')
        result['status'] = 'applied'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc),
                               winerror=getattr(exc, 'winerror', None))
    finally:
        if result['write_attempted']:
            try:
                result['after'] = runtime.snapshot()
                guard(result['after'], plan, 16)
                result['attributes_observed_restored'] = True
                result['timestamp_equal_to_before_setter'] = {
                    name:result['immediate_before_write']['basic'][name] == result['after']['basic'][name]
                    for name in ('creation_time','last_access_time','last_write_time','change_time')}
            except BaseException as exc:
                result.update(status='needs_inspection', attributes_observed_restored=False,
                              readback_error=dict(type=type(exc).__name__, message=str(exc)))
        result['finished'] = time.time()
        save('result', result)
    return result


def main():
    need(PLAN is not None and sys.argv[1:] == ['restore'], 'Only bound restore action')
    need(sys.flags.optimize == 0 and sys.flags.isolated and sys.flags.no_site
         and sys.dont_write_bytecode, 'Use -I -S -B')
    need(os.name == 'nt' and C.sizeof(C.c_void_p) == 8 and C.sizeof(BasicInfo) == 40,
         'Windows x64 BasicInfo ABI required')
    need({name:getattr(BasicInfo,name).offset for name,_ in BasicInfo._fields_}
         == dict(creation_time=0,last_access_time=8,last_write_time=16,change_time=24,attributes=32), 'BasicInfo offsets differ')
    need(PLAN['baseline_attributes'] == 16 and PLAN['expected_current_attributes'] == 48
         and PLAN['baseline_reparse_tag'] == 0, 'Only exact Archive-only difference is approved')
    root, target = Path(PLAN['root']), Path(PLAN['target'])
    need(str(target) == str(root/'synthetic-home'/('cf-register-'+str(uuid.UUID(PLAN['cf_operation_id'])))), 'Unbound target')
    os.environ.update(HOME=str(root/'synthetic-home'),USERPROFILE=str(root/'synthetic-home'),TEMP=str(root/'tmp'),TMP=str(root/'tmp'))
    for name,digest in PLAN['sources'].items():
        need(hashlib.sha256((root/'code'/name).read_bytes()).hexdigest() == digest, 'Source closure drift')
    for name,digest in PLAN['receipts'].items():
        need(hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, 'Approved CF receipt drift')
    cf_source = PLAN['cf_source']
    need(hashlib.sha256((root/cf_source['path']).read_bytes()).hexdigest() == cf_source['sha256'], 'Approved CF producer drift')
    baseline = json.loads((root/PLAN['baseline_receipt']).read_bytes())
    result_receipt = json.loads((root/PLAN['result_receipt']).read_bytes())
    need(baseline['root']['identity'] == PLAN['identity'] and baseline['root']['security_sha256'] == PLAN['security_sha256']
         and baseline['root']['attributes'] == 16 and baseline['root']['reparse_tag'] == 0, 'Baseline receipt inconsistent')
    need(result_receipt['operation_id'] == PLAN['cf_operation_id'] and result_receipt['register_hresult'] == 0
         and result_receipt['unregister_hresult'] == 0 and result_receipt['unregister_succeeded'] is True, 'Owned CF unregister result inconsistent')
    sys.path.insert(0,str(root/'code/scripts'))
    from agm_core import windows_native as w
    api = w._API()
    api.k.SetFileInformationByHandle.argtypes = [w.HANDLE,C.c_int32,C.c_void_p,w.DWORD]
    api.k.SetFileInformationByHandle.restype = w.BOOL
    api.k.GetCurrentProcess.argtypes = []; api.k.GetCurrentProcess.restype = w.HANDLE
    api.a.OpenProcessToken.argtypes = [w.HANDLE,w.DWORD,C.POINTER(w.HANDLE)]; api.a.OpenProcessToken.restype = w.BOOL
    api.a.GetTokenInformation.argtypes = [w.HANDLE,C.c_int32,C.c_void_p,w.DWORD,C.POINTER(w.DWORD)]; api.a.GetTokenInformation.restype = w.BOOL
    token = w.HANDLE()
    need(api.a.OpenProcessToken(api.k.GetCurrentProcess(),8,C.byref(token)), 'Token query failed')
    try:
        elevated,returned = w.DWORD(),w.DWORD()
        need(api.a.GetTokenInformation(token,20,C.byref(elevated),4,C.byref(returned)) and returned.value==4 and not elevated.value, 'Ordinary token required')
    finally:
        api.k.CloseHandle(token)
    evidence = root/'evidence'/('cf-attribute-recovery-'+str(uuid.UUID(PLAN['operation_id'])))
    evidence.mkdir()  # Exclusive single attempt; no stale-lock/retry protocol.
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def save(name,value):
        with (evidence/(name+'.json')).open('x',encoding='utf8') as f:
            json.dump(dict(value,operation_id=PLAN['operation_id'],target=str(target),
                           source_sha256=source_hash),f,indent=2)
            f.flush(); os.fsync(f.fileno())

    save('environment', dict(token_elevated=False, environment={x:os.environ.get(x) for x in ('HOME','USERPROFILE','TEMP','TMP','SystemRoot')},
                             sources=PLAN['sources'], baseline_receipts=PLAN['receipts']))
    with w.inspect_path(PLAN['case_path'],security=True,candidate_metadata=True) as anchor:
        need(w.same_node(anchor,PLAN['anchor_identity']) and anchor['security']['sha256']==PLAN['anchor_security_sha256']
             and not anchor['case_sensitive_directory'], 'Anchor drift')
        with w.inspect_path(str(target),security=True,candidate_metadata=True) as initial:
            need(initial['filesystem']=='NTFS' and initial['directory'] and not initial['case_sensitive_directory'], 'Unsupported target')
            need(w.same_node(initial,PLAN['identity']) and initial['security']['sha256']==PLAN['security_sha256'], 'Target drift')
        h = api.k.CreateFileW(str(target),0x80|0x100|0x20000,3,None,3,0x02200000,None)
        need(h not in (None,C.c_void_p(-1).value), 'Preheld attribute-write handle unavailable')
        try:
            def node(handle):
                info = api.info(handle,18,w.FileIdInfo())
                tag = api.info(handle,9,w.AttributeTagInfo())
                return dict(identity=dict(volume_id=info.volume,file_id=bytes(info.file_id).hex()),
                            attributes=tag.attributes,reparse_tag=tag.reparse_tag,
                            security_sha256=api.security(handle)['sha256'])

            class Runtime:
                source_sha256 = source_hash

                def snapshot(self):
                    held = node(h)
                    fresh = api.k.CreateFileW(str(target),0x80|0x20000,3,None,3,0x02200000,None)
                    need(fresh not in (None,C.c_void_p(-1).value), 'Named readback unavailable')
                    try:
                        named = node(fresh)
                    finally:
                        api.k.CloseHandle(fresh)
                    basic = api.info(h,0,BasicInfo())
                    basic_values = {name:getattr(basic,name) for name,_ in BasicInfo._fields_}
                    safe_to_list = (held['identity']==named['identity']==PLAN['identity']
                                    and held['security_sha256']==named['security_sha256']==PLAN['security_sha256']
                                    and held['reparse_tag']==named['reparse_tag']==0
                                    and held['attributes'] in (16,48) and named['attributes'] in (16,48))
                    return dict(held,named_identity=named['identity'],named_attributes=named['attributes'],
                                named_reparse_tag=named['reparse_tag'],named_security_sha256=named['security_sha256'],
                                basic=basic_values,entries=sorted(x.name for x in target.iterdir()) if safe_to_list else None)

                def apply(self):
                    request = BasicInfo()
                    request.attributes = 16  # Bound known DIRECTORY target; never NORMAL guessing.
                    success = api.k.SetFileInformationByHandle(h,0,C.byref(request),C.sizeof(request))
                    return dict(success=bool(success),winerror=C.get_last_error() if not success else None,
                                class_value=0,buffer_bytes=C.sizeof(request),
                                request={name:getattr(request,name) for name,_ in BasicInfo._fields_})

            result = exercise(Runtime(),save,PLAN)
        finally:
            api.k.CloseHandle(h)
    save('completion',dict(result,held_anchor_exit_revalidated=True))
    print(json.dumps(dict(status=result['status'],attributes_observed_restored=result.get('attributes_observed_restored'),evidence=str(evidence))))
    return 0 if result['status']=='applied' and result.get('attributes_observed_restored') else 2


if __name__=='__main__':
    raise SystemExit(main())
