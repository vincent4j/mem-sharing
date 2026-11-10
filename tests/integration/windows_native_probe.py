import json,os,pathlib,sys,subprocess,traceback,time,hashlib,uuid
root=pathlib.Path(sys.argv[1]);run_id=str(uuid.UUID(sys.argv[2]));sys.path.insert(0,str(root/'code/scripts'))
from agm_core import windows_native as w
evidence=root/'evidence'/('native-'+run_id+'.json')
if evidence.exists():raise FileExistsError('Refuse evidence overwrite')
fixture_root=root/'synthetic-home'/('fixtures-'+run_id);fixture_root.mkdir()
out={'run_id':run_id,'argv':sys.argv,'fixture_root':str(fixture_root),'started':time.time(),'platform':sys.platform,'python':sys.version,'checks':[],'production_write_authorized':False}
def check(name,f):
 global a,p
 a=fixture_root/(name+' 中文 空格');a.mkdir();p=a/'Sample.txt';p.write_bytes(b'ONLY SYNTHETIC\r\n')
 try: detail=f();out['checks'].append({'name':name,'status':'passed','detail':detail,'fixture':str(a)})
 except Exception as e:out['checks'].append({'name':name,'status':'failed','type':type(e).__name__,'code':getattr(e,'code',None),'winerror':getattr(e,'winerror',None),'message':str(e)})
def expect_refused(path):
 try:
  with w.inspect_path(str(path)):pass
 except w.NativeInspectionError as e:
  assert e.code=='reparse_refused',(e.code,e.winerror);return e.code
 raise AssertionError('reparse accepted')

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
def sharing(access,share,expect_conflict):
 api=w._API();h=api.k.CreateFileW(str(p),access,share,None,3,0,None)
 assert h not in (None,w.C.c_void_p(-1).value)
 try:
  contender=api.k.CreateFileW(str(p),0x80000000,3,None,3,0,None)
  if contender in (None,w.C.c_void_p(-1).value):
   error=w.C.get_last_error()
   assert expect_conflict and error==32,error
   return {'winerror':error,'access':access,'share':share,'contender_access':0x80000000}
  try:
   assert not expect_conflict,'Data-access sharing conflict was not refused'
   return {'opened':True,'access':access,'share':share,'contender_access':0x80000000,'exclusive_lock_proven':False}
  finally:api.k.CloseHandle(contender)
 finally:api.k.CloseHandle(h)
# Metadata-only access is not a data-access lock. Keep this as an observation,
# not a refusal assertion; old r2 exit 1 remains historical counterevidence.
def metadata_sharing():
 api=w._API();h=api.k.CreateFileW(str(p),0x80,0,None,3,0,None)
 assert h not in (None,w.C.c_void_p(-1).value)
 try:
  try:
   with w.inspect_path(str(p)):pass
   return {'second_metadata_open':'allowed','exclusive_lock_proven':False}
  except w.NativeInspectionError as e:
   assert e.code=='node_open_failed' and e.winerror==32,(e.code,e.winerror)
   return {'second_metadata_open':'refused','winerror':e.winerror,'exclusive_lock_proven':False}
 finally:api.k.CloseHandle(h)
check('metadata_share_zero_observation',metadata_sharing)
check('data_read_share_zero_conflict',lambda:sharing(0x80000000,0,True))
check('data_read_shared_control',lambda:sharing(0x80000000,3,False))
def junction(ancestor=False,inject=False):
 link=a/'junction';target=a/'target';target.mkdir();(target/'inside.txt').write_text('synthetic')
 try:
  cp=subprocess.run([r'C:\Windows\System32\cmd.exe','/d','/c','mklink','/J',str(link),str(target)],capture_output=True,timeout=10)
  assert cp.returncode==0,('junction_creation_unavailable',cp.returncode)
  if inject:raise RuntimeError('synthetic junction body failure')
  return expect_refused(link/'inside.txt' if ancestor else link)
 finally:
  # Also handle a timed-out mklink that created the junction before raising.
  if os.path.lexists(link):link.rmdir()
  assert not os.path.lexists(link),'junction cleanup failed'
  assert (target/'inside.txt').read_text()=='synthetic','cleanup touched target'
def junction_cleanup():
 try:junction(inject=True)
 except RuntimeError as e:assert str(e)=='synthetic junction body failure';return {'removed':True,'target_preserved':True}
 raise AssertionError('injected failure did not execute')
check('junction_leaf_refused',junction)
check('junction_ancestor_refused',lambda:junction(ancestor=True))
check('junction_exception_cleanup',junction_cleanup)
for bad in ('D:relative',r'\\server\share',r'D:\bad:ads',r'D:\NUL.txt'):
 def syntax(bad=bad):
  try:w.path_chain(bad)
  except w.NativeInspectionError as e:return e.code
  raise AssertionError('unsafe syntax admitted')
 check('syntax_refused_'+str(len(out['checks'])),syntax)
out['not_covered']=['ACL write/restore or access-denied DACL injection','case-sensitive directory enabled by system change','atomic relative-handle walk','production lifecycle']
out['finished']=time.time()
with evidence.open('x',encoding='utf-8') as stream:json.dump(out,stream,ensure_ascii=False,indent=2)
print(json.dumps({'checks':[(x['name'],x['status']) for x in out['checks']]}))
sys.exit(1 if any(x['status']=='failed' for x in out['checks']) else 0)
