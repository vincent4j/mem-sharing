"""Ordinary-token verification of one prepared, bound synthetic case directory."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

PLAN = None


def need(condition,message):
    if not condition:raise RuntimeError(message)


def save(path,value):
    with path.open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())


def main():
    need(sys.flags.optimize==0 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'Use -I -S -B without optimization')
    need(PLAN is not None,'Unbound fixture')
    root=Path(PLAN['root']);case=Path(PLAN['case_path'])
    for name,digest in PLAN['sources'].items():need(hashlib.sha256((root/'code'/name).read_bytes()).hexdigest()==digest,'Import closure drift')
    sys.path.insert(0,str(root/'code/scripts'))
    from agm_core import windows_native as w
    def snap(path,security=False,metadata=False):
        with w.inspect_path(str(path),security=security,candidate_metadata=metadata) as value:
            return {k:v for k,v in value.items() if k not in ('security','chain')}|({'security_sha256':value['security']['sha256']} if security else {})
    op=str(uuid.uuid4());evidence=root/'evidence'/('normal-case-verify-'+op);evidence.mkdir()
    result=dict(run_id=PLAN['run_id'],operation_id=op,started=time.time(),status='failed',checks=[],created=[],cleanup_errors=[],production_write_authorized=False)
    created=[]
    try:
        need(not (root/'tmp/case-admin-v2.lock').exists(),'Admin helper lock exists; do not overlap')
        before=snap(case,True,True);result['before']=before
        need(w.same_node(before,PLAN['identity']) and before['security_sha256']==PLAN['security_sha256'],'Fixture identity/security drift')
        need(before['case_sensitive_directory'] is True and not list(case.iterdir()),'Prepared sensitive directory required, empty')
        api=w._API();api.k.GetCurrentProcess.argtypes=[];api.k.GetCurrentProcess.restype=w.HANDLE
        api.a.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];api.a.OpenProcessToken.restype=w.BOOL
        api.a.GetTokenInformation.argtypes=[w.HANDLE,ctypes.c_int32,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)];api.a.GetTokenInformation.restype=w.BOOL
        token=w.HANDLE();need(api.a.OpenProcessToken(api.k.GetCurrentProcess(),8,ctypes.byref(token)),'Token open failed')
        try:
            elevated,returned=w.DWORD(),w.DWORD()
            need(api.a.GetTokenInformation(token,20,ctypes.byref(elevated),4,ctypes.byref(returned)) and returned.value==4,'TokenElevation query failed')
            result['token_elevated']=bool(elevated.value);need(elevated.value==0,'Ordinary token required')
        finally:api.k.CloseHandle(token)
        save(evidence/'intent.json',dict(result,planned_names=['Example.txt','example.txt']))
        for name,raw in [('Example.txt',b'UPPER SYNTHETIC CASE'),('example.txt',b'lower synthetic case')]:
            path=case/name;entry=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),identity=None)
            with path.open('xb') as stream:stream.write(raw)
            created.append((path,raw,entry));entry['identity']=snap(path);result['created'].append(entry)
        need(not w.same_node(created[0][2]['identity'],created[1][2]['identity']),'Case names not distinct physical files')
        result['checks'].append(dict(name='two_case_names_distinct',status='passed'))
        for label,path in [('sensitive_directory',case),('sensitive_ancestor',created[0][0])]:
            try:
                with w.inspect_candidate_path(str(path),allowed_root=str(case.parent)):pass
            except w.NativeInspectionError as exc:
                need(exc.code=='case_sensitive_directory_refused','Unexpected refusal: '+exc.code)
                result['checks'].append(dict(name=label,status='passed',code=exc.code))
            else:raise RuntimeError('Sensitive candidate accepted')
        result['status']='passed'
    except Exception as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc),winerror=getattr(exc,'winerror',None))
    finally:
        for path,raw,entry in reversed(created):
            try:
                need(entry['identity'] is not None,'Creation identity unavailable; preserve file')
                need(w.same_node(snap(path),entry['identity']) and path.read_bytes()==raw,'Created file drift; preserve')
                path.unlink()
            except Exception as exc:result['cleanup_errors'].append(dict(path=str(path),type=type(exc).__name__,message=str(exc)))
        try:
            after=snap(case,True,True);result['after']=after
            result['cleanup_complete']=not list(case.iterdir()) and not result['cleanup_errors'] and w.same_node(after,PLAN['identity']) and after['security_sha256']==PLAN['security_sha256'] and after['case_sensitive_directory'] is True
        except Exception as exc:
            result['cleanup_complete']=False;result['after_error']=str(exc)
        if not result.get('cleanup_complete'):result['status']='needs_inspection'
        result['finished']=time.time();save(evidence/'result.json',result)
    print(json.dumps({'operation_id':op,'status':result['status'],'checks':result['checks'],'cleanup_complete':result.get('cleanup_complete'),'evidence':str(evidence)}))
    return 0 if result['status']=='passed' else 2


if __name__=='__main__':raise SystemExit(main())
