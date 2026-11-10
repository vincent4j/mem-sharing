"""Prepare only this run's synthetic fixture; no client/daemon or global policy changes."""
import base64
import ctypes
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid
root=Path(sys.argv[1]);uid=str(uuid.UUID(sys.argv[2]));sys.path.insert(0,str(root/'code/scripts'))
from agm_core import windows_native as w
sha=lambda raw:hashlib.sha256(raw).hexdigest()
fixtures=root/'synthetic-home'/('dell-fixture-'+uid);fixtures.mkdir()
backup=fixtures/'backup';backup.mkdir()
case=fixtures/'case';case.mkdir()
baseline=fixtures/'baseline.txt';original=b'\xef\xbb\xbfSYNTHETIC BASELINE\r\n';baseline.write_bytes(original)
copy=backup/'baseline.before';copy.write_bytes(original)
assert copy.read_bytes()==baseline.read_bytes()==original,'Backup readback mismatch'
output=root/'evidence'/('native-'+uid+'.json')
if output.exists():raise FileExistsError('Refuse evidence overwrite')
result=dict(run_id=uid,argv=sys.argv,started=time.time(),checks=[],capabilities={},protected_scope='Paseo daemon/session/credentials and client entries not touched',production_write_authorized=False)
api=w._API()
def inspect(path,security=False,metadata=False):
    with w.inspect_path(str(path),security=security,candidate_metadata=metadata) as value:return value
before=inspect(case,True,True);baseline_before=inspect(baseline)
result['baseline']=dict(bytes=len(original),sha256=sha(original),backup_verified=True,case_directory_identity={k:before[k] for k in ('volume_id','file_id')},case_flag=before['case_sensitive_directory'],security_sha256=before['security']['sha256'])
# Prefer an installed target SDK enum over an unverified numeric selector.
elevation_class=None
sdk_base=Path(r'C:\Program Files (x86)\Windows Kits\10\Include')
if sdk_base.is_dir():
    for version in sorted(sdk_base.iterdir(),reverse=True)[:3]:
        header=version/'um/winnt.h'
        if not header.is_file():continue
        raw=header.read_bytes()
        if len(raw)>8*1024*1024:continue
        text=raw.decode('utf8','replace')
        match=re.search(r'typedef\s+enum\s+_TOKEN_INFORMATION_CLASS\s*\{(.*?)\}\s*TOKEN_INFORMATION_CLASS',text,re.S)
        if not match:continue
        body=re.sub(r'/\*.*?\*/|//[^\n]*','',match.group(1),flags=re.S)
        current=-1
        for field in body.split(','):
            token=re.fullmatch(r'\s*(Token\w+)\s*(?:=\s*(0x[0-9a-fA-F]+|[0-9]+))?\s*',field)
            if not token:break
            current=int(token.group(2),0) if token.group(2) else current+1
            if token.group(1)=='TokenElevation':
                elevation_class=current
                result['capabilities']['token_enum_source']=dict(path=str(header),sha256=sha(raw),value=current,source='local_sdk_header_not_web_or_signature_verified')
                break
        if elevation_class is not None:break
shell=ctypes.WinDLL('Shell32.dll',winmode=0x800)
shell.IsUserAnAdmin.argtypes=[];shell.IsUserAnAdmin.restype=w.BOOL
result['capabilities']['administrator_group_membership']=dict(value=bool(shell.IsUserAnAdmin()),not_elevation_proof=True)
api.k.GetCurrentProcess.argtypes=[];api.k.GetCurrentProcess.restype=w.HANDLE
api.a.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];api.a.OpenProcessToken.restype=w.BOOL
api.a.GetTokenInformation.argtypes=[w.HANDLE,ctypes.c_int32,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)];api.a.GetTokenInformation.restype=w.BOOL
token=w.HANDLE();elevated=None
if elevation_class is None:
    result['capabilities']['elevation']=dict(state='unknown',reason='TokenElevation_numeric_class_not_verified_no_SDK_enum')
elif not api.a.OpenProcessToken(api.k.GetCurrentProcess(),8,ctypes.byref(token)):
    result['capabilities']['elevation']=dict(state='unknown',winerror=ctypes.get_last_error())
else:
    try:
        value,returned=w.DWORD(),w.DWORD()
        ok=api.a.GetTokenInformation(token,elevation_class,ctypes.byref(value),ctypes.sizeof(value),ctypes.byref(returned))
        if ok and returned.value==4:
            elevated=bool(value.value);result['capabilities']['elevation']=dict(state='observed',elevated=elevated)
        elif not ok:result['capabilities']['elevation']=dict(state='unknown',winerror=ctypes.get_last_error())
        else:result['capabilities']['elevation']=dict(state='unknown',returned_bytes=returned.value)
    finally:api.k.CloseHandle(token)

def command(label,args):
    cp=subprocess.run(args,capture_output=True,timeout=10)
    row=dict(label=label,argv=args,exit=cp.returncode,stdout_base64=base64.b64encode(cp.stdout).decode('ascii'),stderr_base64=base64.b64encode(cp.stderr).decode('ascii'))
    result.setdefault('commands',[]).append(row)
    return cp
fsutil=str(Path(os.environ['SystemRoot'])/'System32/fsutil.exe')
command('case-query-before',[fsutil,'file','queryCaseSensitiveInfo',str(case)])
command('D-8dot3-query',[fsutil,'8dot3name','query','D:'])
command('C-8dot3-query',[fsutil,'8dot3name','query','C:'])
# No elevation request: setter only runs if this process already has elevation.
created=[];enabled=False
try:
    if elevated is not True:
        result['checks'].append(dict(name='enabled_case_directory',status='unavailable',reason='process_not_elevated_or_unknown_no_setter_called'))
    else:
        cp=command('case-enable',[fsutil,'file','setCaseSensitiveInfo',str(case),'enable'])
        current=inspect(case,metadata=True);enabled=current['case_sensitive_directory']
        if cp.returncode!=0 or not enabled:
            result['checks'].append(dict(name='enabled_case_directory',status='unavailable',exit=cp.returncode,flag_observed=enabled))
        else:
            for name,raw in [('Example.txt',b'UPPER SYNTHETIC'),('example.txt',b'lower synthetic')]:
                path=case/name
                with path.open('xb') as stream:stream.write(raw)
                identity=inspect(path);created.append((path,raw,identity))
            assert not w.same_node(created[0][2],created[1][2]),'Distinct case files not distinct nodes'
            try:
                with w.inspect_candidate_path(str(created[0][0]),allowed_root=str(fixtures)):pass
            except w.NativeInspectionError as exc:
                assert exc.code=='case_sensitive_directory_refused',(exc.code,exc.winerror)
                result['checks'].append(dict(name='enabled_case_directory',status='passed',code=exc.code,two_case_nodes_distinct=True))
            else:raise AssertionError('Enabled case directory accepted')
finally:
    for path,raw,identity in reversed(created):
        assert path.read_bytes()==raw and w.same_node(inspect(path),identity),'Fixture drift; refuse cleanup'
        path.unlink()
    if enabled:
        assert not list(case.iterdir()),'Not empty; refuse case disable'
        cp=command('case-disable',[fsutil,'file','setCaseSensitiveInfo',str(case),'disable'])
        assert cp.returncode==0,'Case restore failed'
    after=inspect(case,True,True)
    assert w.same_node(before,after) and not after['case_sensitive_directory'],'Case identity/flag not restored'
    assert after['security']['sha256']==before['security']['sha256'],'Directory security snapshot changed'
    assert baseline.read_bytes()==copy.read_bytes()==original and w.same_node(baseline_before,inspect(baseline)),'Baseline changed'
    result['restoration']=dict(case_directory_same_identity=True,case_flag_restored=True,case_directory_empty=not list(case.iterdir()),security_hash_unchanged=True,baseline_bytes_and_identity_unchanged=True,backup_readback_verified=True,ACL_write_restore_tested=False)
result['finished']=time.time()
with output.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
print(json.dumps({'checks':result['checks'],'capabilities':result['capabilities'],'restoration':result['restoration']}))
