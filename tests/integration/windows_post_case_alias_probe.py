"""Ordinary post-restore check plus read-only existing system-directory short alias."""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
PLAN=None

def need(value,message):
    if not value:raise RuntimeError(message)

def main():
    need(sys.flags.optimize==0 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'Use -I -S -B')
    need(PLAN is not None,'Unbound plan');root=Path(PLAN['root'])
    helper=root/'tmp/case-admin-fixture-v2-r2.py'
    need(hashlib.sha256(helper.read_bytes()).hexdigest()==PLAN['v2_helper_sha256'],'Helper changed')
    for path,digest in PLAN['sources'].items():need(hashlib.sha256((root/'code'/path).read_bytes()).hexdigest()==digest,'Import source drift')
    sys.path.insert(0,str(root/'code/scripts'))
    from agm_core import windows_native as w
    op=str(uuid.uuid4());result=dict(run_id=PLAN['run_id'],operation_id=op,started=time.time(),checks=[],production_write_authorized=False)
    cp=subprocess.run([sys.executable,'-I','-S','-B',str(helper),'check','--exclusive-fixture'],capture_output=True,timeout=25)
    result['post_check']=dict(exit=cp.returncode,stdout=cp.stdout.decode('utf8','replace'),stderr=cp.stderr.decode('utf8','replace'))
    need(cp.returncode==0,'Post-restore helper check failed')
    observed=json.loads(cp.stdout)
    need(observed['status']=='succeeded' and observed['before']['case_sensitive_directory'] is False and observed['after']['case_sensitive_directory'] is False,'Original case flag not restored')
    result['checks'].append(dict(name='post_restore_identity_security_empty_flag0',status='passed'))
    api=w._API();short_query=api.k.GetShortPathNameW;short_query.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,w.DWORD];short_query.restype=w.DWORD
    target='C:\\Program Files';buffer=ctypes.create_unicode_buffer(32768);size=short_query(target,buffer,len(buffer))
    if not size or size>=len(buffer) or buffer.value.casefold()==target.casefold():
        result['checks'].append(dict(name='system_directory_short_alias',status='unavailable',winerror=ctypes.get_last_error() if not size else None))
    else:
        alias=buffer.value
        with w.inspect_path(target) as long:
            h=api.k.CreateFileW(alias,0x80,3,None,3,0x02200000,None)
            need(h not in (None,ctypes.c_void_p(-1).value),'Short alias handle failed')
            try:
                info=api.info(h,18,w.FileIdInfo())
                need(long['volume_id']==info.volume and long['file_id']==bytes(info.file_id).hex(),'Alias physical identity differs')
            finally:api.k.CloseHandle(h)
            try:
                with w.inspect_candidate_path(alias,allowed_root='C:\\'):pass
            except w.NativeInspectionError as exc:
                need(exc.code=='path_alias_refused','Unexpected alias refusal: '+exc.code)
                result['checks'].append(dict(name='system_directory_short_alias',status='passed',alias=alias,long_path=target,same_physical_identity=True,code=exc.code,read_only=True))
            else:raise RuntimeError('Distinct short alias admitted')
    result['finished']=time.time()
    output=root/'evidence'/('post-case-alias-'+op+'.json')
    with output.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result))
    return 0
if __name__=='__main__':raise SystemExit(main())
