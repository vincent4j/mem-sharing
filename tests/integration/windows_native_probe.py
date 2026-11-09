import json,os,pathlib,sys,subprocess,traceback,time,hashlib
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'code/scripts'))
from agm_core import windows_native as w
out={'platform':sys.platform,'python':sys.version,'checks':[],'production_write_authorized':False}
def check(name,f):
 try: detail=f();out['checks'].append({'name':name,'status':'passed','detail':detail})
 except Exception as e:out['checks'].append({'name':name,'status':'failed','type':type(e).__name__,'code':getattr(e,'code',None),'winerror':getattr(e,'winerror',None),'message':str(e)})
def expect_refused(path):
 try:
  with w.inspect_path(str(path)):pass
 except w.NativeInspectionError as e:
  assert e.code=='reparse_refused',(e.code,e.winerror);return e.code
 raise AssertionError('reparse accepted')
a=root/'synthetic-home/中文 空格 r2';a.mkdir();p=a/'Sample.txt';p.write_bytes(b'ONLY SYNTHETIC\r\n')
def ordinary():
 with w.inspect_path(str(p),security=True) as x:
  assert x['filesystem']=='NTFS' and not x['directory'] and not x['race_free']
  out['first_identity']={k:x[k] for k in ('volume_id','file_id')}
  return {k:v for k,v in x.items() if k not in ('chain','security')}|{'security_sha256':x['security']['sha256'],'security_bytes':x['security']['bytes']}
check('unicode_file_ntfs_security',ordinary)
def directory():
 with w.inspect_path(str(a)) as x:assert x['directory'];return len(x['chain'])
check('ancestor_directory_chain',directory)
def casing():
 with w.inspect_path(str(p)) as x:
  with w.inspect_path(str(p).upper()) as y:assert w.same_node(x,y);return y['file_id']
check('case_alias_identity',casing)
def hardlink():
 alias=a/'hardlink.txt';os.link(p,alias)
 try:
  with w.inspect_path(str(p)) as x:
   with w.inspect_path(str(alias)) as y:assert w.same_node(x,y);return y['file_id']
 finally:alias.unlink()
check('hardlink_identity',hardlink)
def pinning():
 moved=a/'moved.txt';renamed=False;detected=False
 try:
  try:
   with w.inspect_path(str(p)):
    try:os.replace(p,moved);renamed=True
    except PermissionError as e:return {'blocked_winerror':e.winerror}
  except w.NativeInspectionError as e:
   if not renamed or e.code!='node_drift':raise
   detected=True
  assert detected,'Named rename went undetected'
  return {'rename_allowed':True,'named_recheck_detected':True}
 finally:
  if renamed:os.replace(moved,p)
check('rename_blocked_or_named_drift_detected',pinning)
def drift():
 with w.inspect_path(str(p)) as x:before=dict(x)
 temp=a/'replacement.txt';temp.write_bytes(b'SYNTHETIC replacement');os.replace(temp,p)
 with w.inspect_path(str(p)) as after:assert not w.same_node(before,after);return after['file_id']
check('replacement_identity_changes',drift)
def repeat_security():
 with w.inspect_path(str(p),security=True) as x:s=x['security']['sha256']
 with w.inspect_path(str(p),security=True) as x:assert s==x['security']['sha256'];return s
check('readonly_security_snapshot_repeatable',repeat_security)
def share_error():
 api=w._API();h=api.k.CreateFileW(str(p),0x80,0,None,3,0,None)
 assert h not in (None,w.C.c_void_p(-1).value)
 try:
  try:
   with w.inspect_path(str(p)):pass
  except w.NativeInspectionError as e:assert e.code=='node_open_failed';return {'code':e.code,'winerror':e.winerror}
  raise AssertionError('Exclusive sharing did not refuse second open')
 finally:api.k.CloseHandle(h)
check('sharing_conflict_fails_closed',share_error)
link=a/'junction';target=a/'target';target.mkdir();(target/'inside.txt').write_text('synthetic')
cp=subprocess.run([r'C:\Windows\System32\cmd.exe','/d','/c','mklink','/J',str(link),str(target)],capture_output=True,timeout=10)
if cp.returncode==0:
 check('junction_leaf_refused',lambda:expect_refused(link))
 check('junction_ancestor_refused',lambda:expect_refused(link/'inside.txt'))
 link.rmdir()
else:out['checks'].append({'name':'junction_creation','status':'unavailable','exit':cp.returncode})
for bad in ('D:relative',r'\\server\share',r'D:\bad:ads',r'D:\NUL.txt'):
 def syntax(bad=bad):
  try:w.path_chain(bad)
  except w.NativeInspectionError as e:return e.code
  raise AssertionError('unsafe syntax admitted')
 check('syntax_refused_'+str(len(out['checks'])),syntax)
out['not_covered']=['ACL write/restore or access-denied DACL injection','case-sensitive directory enabled by system change','atomic relative-handle walk','production lifecycle']
(root/'evidence/native-result-r2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':[(x['name'],x['status']) for x in out['checks']]}))
sys.exit(1 if any(x['status']=='failed' for x in out['checks']) else 0)
