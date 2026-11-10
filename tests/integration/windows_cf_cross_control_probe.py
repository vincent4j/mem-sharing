"""One bounded cross-control after C/D divergence; no repeated original matrix cells."""
import ctypes
import json
import ntpath
import os
from pathlib import Path
import sys
import time
import uuid
root=Path(sys.argv[1]);uid=str(uuid.UUID(sys.argv[2]));sys.path.insert(0,str(root/'code/scripts'))
from agm_core import windows_native as w
fixture=root/'synthetic-home'/('cf-'+uid);fixture.mkdir();leaf=fixture/'synthetic.txt';leaf.write_bytes(b'SYNTHETIC CF DIAGNOSTIC\r\n')
output=root/'evidence'/('native-'+uid+'.json')
if output.exists():raise FileExistsError('Refuse evidence overwrite')
result=dict(run_id=uid,argv=sys.argv,started=time.time(),python=sys.version,windows_version=list(sys.getwindowsversion()),matrix=[],checks=[],production_write_authorized=False)
api=w._API();library=ctypes.WinDLL('CldApi.dll',winmode=0x800);query=library.CfGetSyncRootInfoByHandle
module_path=ctypes.create_unicode_buffer(32768)
module_query=api.k.GetModuleFileNameW
module_query.argtypes=[w.HANDLE,ctypes.c_wchar_p,w.DWORD];module_query.restype=w.DWORD
module_size=module_query(library._handle,module_path,len(module_path))
assert 0<module_size<len(module_path),'Loaded module path unavailable/truncated'
expected=ntpath.join(os.environ['SystemRoot'],'System32','CldApi.dll')
assert module_path.value.casefold()==expected.casefold(),'Unexpected CldApi source; stop interpretation'
result['loaded_module_path']=module_path.value
class PlatformInfo(ctypes.Structure):
    _fields_=[('build',w.DWORD),('revision',w.DWORD),('integration',w.DWORD)]
platform_info=PlatformInfo();platform_query=library.CfGetPlatformInfo
platform_query.argtypes=[ctypes.POINTER(PlatformInfo)];platform_query.restype=ctypes.c_int32
platform_status=platform_query(ctypes.byref(platform_info))
result['cloud_platform_info']=dict(hresult=platform_status&0xffffffff,structure_bytes=ctypes.sizeof(platform_info))
if platform_status==0:result['cloud_platform_info'].update(build=platform_info.build,revision=platform_info.revision,integration=platform_info.integration)
result['cloud_platform_info']['not_dll_file_version']=True
query.argtypes=[w.HANDLE,ctypes.c_int32,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)];query.restype=ctypes.c_int32
# Same documented BASIC class, compare resource type/access/size once per cell.
for label,path in [('loaded-system-dll',module_path.value),('D-volume-root','D:\\')]:
    for access in (0x80,0x20080):
        for size in (8,64):
            row=dict(resource=label,access=access,buffer_bytes=size,exploratory=label!='synthetic-file' or size!=8)
            h=api.k.CreateFileW(path,access,3,None,3,0x02200000,None)
            if h in (None,ctypes.c_void_p(-1).value):
                row.update(opened=False,winerror=ctypes.get_last_error())
            else:
                try:
                    buffer=ctypes.create_string_buffer(size);returned=w.DWORD()
                    status=query(h,0,ctypes.byref(buffer),size,ctypes.byref(returned))
                    row.update(opened=True,hresult=status&0xffffffff,returned_length=returned.value)
                    try:row['classification']=w.classify_registered_cloud_result(status,returned.value)
                    except w.NativeInspectionError as exc:row['classification']=dict(code=exc.code,winerror=exc.winerror)
                    fs=ctypes.create_unicode_buffer(64);serial,max_component,flags=w.DWORD(),w.DWORD(),w.DWORD()
                    ok=api.k.GetVolumeInformationByHandleW(h,None,0,ctypes.byref(serial),ctypes.byref(max_component),ctypes.byref(flags),fs,len(fs))
                    row['volume']=dict(query_succeeded=bool(ok),filesystem=fs.value,flags=flags.value)
                finally:api.k.CloseHandle(h)
            result['matrix'].append(row)
result['abi']=dict(DWORD=ctypes.sizeof(w.DWORD),HRESULT=ctypes.sizeof(ctypes.c_int32),HANDLE=ctypes.sizeof(w.HANDLE),BASIC_buffer=8)
result['not_proven']=['registered CF positive/negative reference environment','DLL file version not queried; platform info is distinct','cause of HRESULT','provider coverage','production safety']
result['finished']=time.time()
with output.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
print(json.dumps({'rows':len(result['matrix']),'statuses':sorted({hex(r['hresult']) for r in result['matrix'] if r.get('opened')}),'checks':result['checks']}))
