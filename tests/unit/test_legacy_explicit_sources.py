"""Current legal install fixture; explicit spans never widen default scanning."""
import copy,json,os,sys,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import test_thin_context_equivalence as thin
from test_thin_context_equivalence import RULES,AGENTS,approved
from test_m404_install import InstallFixture
from agm_core import detect,user_rules_organize as org,memory_share as ms
from agm_core.layout import resolve_layout
from agm_core.uninstall_recovery import tree

class LegacyExplicitSourceTests(unittest.TestCase):
 def setUp(self):
  self.t=thin.ThinContextTests();self.t.setUp();self.addCleanup(self.t.doCleanups);self.f=InstallFixture();self.f.setUp();self.addCleanup(self.f.doCleanups)
  f=self.f;t=self.t;f.home=t.home;f.runtime=resolve_layout(t.home);f.request['home']=str(t.home);f.request['agents']=AGENTS
  original=detect.detect_agents
  def installed(*a,**kw):
   kw.update(search_paths=[],app_directories=[]);facts=original(*a,**kw)
   for row in facts['agents'].values():row['status']='installed'
   return facts
  mock=patch.object(detect,'detect_agents',side_effect=installed);mock.start();self.addCleanup(mock.stop)
  self.assertEqual(f.execute()['status'],'completed')
  self.req=dict(t.req,scope='user',search_paths=[],app_directories=[])
 def proof(self,agents=None):
  _,proposal=self.t.proposal(agents);return proposal['equivalent_sources']
 def plan(self,request):
  result=org.plan_organize(request);self.assertNotEqual(result['status'],'failed',result);return result['approval_plan']
 def execute(self,request):
  plan=self.plan(request);result=org.execute_organize(plan,approved(plan),request=request);self.assertEqual(result['status'],'completed',result);return result
 def test_default_missing_WB_explicit_six_by_six_and_original_contexts(self):
  baseline=self.plan(self.req);self.assertFalse(any('workbuddy' in item['agents'] for item in baseline['items']))
  request=dict(self.req,equivalent_sources=self.proof());plan=self.plan(request)
  self.assertEqual(len(plan['groups']),6);self.assertEqual([len(g['sources']) for g in plan['groups']],[6]*6)
  expected={(i['source'],i['start'],i['end']):i['context'] for proof in request['equivalent_sources'] for i in proof['sources']}
  self.execute(request);self.assertEqual([self.t.topic.read_bytes().count(rule) for rule in RULES],[1]*6)
  records=list(ms._available_migrations(self.f.runtime).values());self.assertEqual(len(records),36)
  for record in records:self.assertEqual(record['context'],expected[(record['path'],record['start'],record['end'])])
  self.assertFalse(any('workbuddy' in item['agents'] for item in baseline['items']))
 def test_invalid_and_protected_proofs_view_decline_zero_write(self):
  request=dict(self.req,equivalent_sources=self.proof());before=tree(self.t.home)
  for selection in ('查看 1','暂不整理'):
   result=self.plan(dict(request,selection=selection));self.assertEqual(result['changes'],[]);self.assertEqual(tree(self.t.home),before)
  for mode in ('partial','basis','context','hash','overlap','source','unknown','canonical'):
   bad=copy.deepcopy(request);group=bad['equivalent_sources'][0]
   if mode=='partial':group['sources'].pop()
   elif mode=='overlap':group['sources'].append(copy.deepcopy(group['sources'][0]))
   elif mode=='canonical':group['canonical_context']=[[1,'invented',1]]
   elif mode=='unknown':group['sources'][0]['unexpected']='reject'
   else:group['sources'][0][{'basis':'basis','context':'context','hash':'text_sha256','source':'source'}[mode]]=[] if mode=='context' else '0'*64
   result=org.plan_organize(bad);self.assertEqual(result['status'],'failed',(mode,result));self.assertEqual(tree(self.t.home),before)
  # A declaration cannot wash a protected marker into an ordinary candidate.
  wb=self.t.native['workbuddy'];wb.write_bytes(wb.read_bytes()+b'<!-- context-keeper:start -->\nprivate block\n<!-- context-keeper:end -->\n');request=dict(self.req,equivalent_sources=self.proof());bad=copy.deepcopy(request);row=next(r for r in bad['equivalent_sources'][0]['sources'] if r['source']==str(wb));raw=wb.read_bytes();left=raw.index(b'private block');row.update(start=left,end=left+len(b'private block\n'),text_sha256=ms.entries.sha256(b'private block\n'))
  before=tree(self.t.home);result=org.plan_organize(bad);self.assertEqual(result['status'],'failed');self.assertIn('受保护',result['errors'][0]['message']);self.assertEqual(tree(self.t.home),before)
 def test_five_then_OpenCode_reuses_public_metadata_and_return_keeps_alias(self):
  first=dict(self.req,agents=AGENTS[:-1],equivalent_sources=self.proof(AGENTS[:-1]));self.execute(first)
  topic=self.t.topic;public=topic.read_bytes();metadata=(topic.stat().st_mode,topic.stat().st_mtime_ns,topic.stat().st_ino)
  scan=ms.plan_share(dict(self.t.req,agents=['opencode']));records=list(ms._available_migrations(self.f.runtime).values());proof=[]
  for item in scan['segments']:
   target=next((r for r in records if bytes.fromhex(r['text_hex'])==item['text'].encode()),None)
   if target:proof.append({'source':item['source'],'start':item['start'],'end':item['end'],'source_context':item['context'],'source_basis':scan['basis'][item['source']],'public_basis':ms.entries.sha256(public),'public_start':target['public_offset'],'public_end':target['public_end'],'public_context':target['context'],'text_sha256':item['sha256'],'equivalent':True,'reason':'Full original contexts compared by the Agent.'})
  self.assertEqual(len(proof),6);request=dict(self.req,agents=['opencode'],public_reuse=proof);plan=self.plan(request);self.assertFalse(any(c['path']==str(topic) for c in plan['changes']));self.execute(request)
  self.assertEqual(topic.read_bytes(),public);self.assertEqual((topic.stat().st_mode,topic.stat().st_mtime_ns,topic.stat().st_ino),metadata);available=ms._available_migrations(self.f.runtime);self.assertEqual(len(available),36)
  native=self.t.native['opencode'];rp={'schema_version':1,'basis':{str(topic):ms.entries.sha256(public),str(native):ms.entries.sha256(native.read_bytes())},'items':[]}
  for ref,r in available.items():
   if r['agent']=='opencode':rp['items'].append({'ref':ref[0],'migration':ref[1],'public_span':{'start':r['public_offset'],'end':r['public_end'],'text_hex':public[r['public_offset']:r['public_end']].hex()},'target':{'path':str(native),'mode':'insert_at','insert_at':len(native.read_bytes())}})
  req=dict(self.t.req,agents=['opencode'],return_plan=rp);plan=ms.build_return_plan(req,rp);result=ms.run_return(dict(req,approval=approved(plan)));self.assertEqual(result['status'],'completed',result);self.assertEqual(topic.read_bytes(),public)
 def test_actual_legacy_CLI_selection_uninstall_and_external_recovery(self):
  f=self.f;t=self.t;proof=self.proof();file=t.area/'equivalence.json';file.write_text(json.dumps(proof));kernel=f.runtime.code/'scripts/agm.py'
  # Only installation facts are synthetic. The actual installed CLI and all
  # plan/proof/transaction paths execute unmodified copied product bytes.
  bootstrap="import runpy,sys;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));from agm_core import detect;original=detect.detect_agents;exec(\"def installed(*a,**kw):\\n kw.update(search_paths=[],app_directories=[]);r=original(*a,**kw)\\n for row in r['agents'].values():row['status']='installed'\\n return r\");detect.detect_agents=installed;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
  env=dict(os.environ,HOME=str(t.home),PYTHONDONTWRITEBYTECODE='1')
  def cli(args):
   p=subprocess.run([sys.executable,'-B','-c',bootstrap,str(kernel),*args],capture_output=True,text=True,env=env);self.assertTrue(p.stdout.strip(),p.stderr);return p.returncode,json.loads(p.stdout)
  flags=[]
  for agent in AGENTS:flags+=['--agent',agent]
  argv=['organize-user-memory',*flags,'--equivalent-sources-file',str(file)]
  rc,view=cli(argv);self.assertEqual(rc,5,view);self.assertEqual([len(g['sources']) for g in view['approval_plan']['groups']],[6]*6)
  shown=t.area/'shown.json';shown.write_text(json.dumps(view['approval_plan']));before=tree(t.home)
  for args in (['--selection','查看 1'],['--decline']):
   rc,result=cli(argv+args);self.assertEqual(rc,0,result);self.assertEqual(tree(t.home),before)
  rc,result=cli(argv+['--selection','按默认方案','--selection-plan-file',str(shown),'--selection-reference','synthetic actual legacy selection']);self.assertEqual(rc,0,result);self.assertEqual([t.topic.read_bytes().count(rule) for rule in RULES],[1]*6);self.assertEqual(len(ms._available_migrations(f.runtime)),36)
  backup=t.area/'exit';before=tree(t.home);rc,result=cli(['uninstall-machine','--backup-dir',str(backup)]);self.assertEqual(rc,5,result);self.assertEqual(tree(t.home),before)
  approval=t.area/'approval.json';approval.write_text(json.dumps({'plan':result['plan'],'confirmed_at':'2026-11-06T05:10:00Z','reference':'synthetic legacy formal exit approval'}));rc,result=cli(['uninstall-machine','--backup-dir',str(backup),'--approval-file',str(approval)]);self.assertEqual(rc,0,result)
  for native in t.native.values():self.assertEqual([native.read_bytes().count(rule) for rule in RULES],[1]*6)
  argv=[sys.executable,'-I','-S','-B',str(backup/'recover.py'),'--manifest',str(backup/'manifest.json'),'--action','restore'];p=subprocess.run(argv,capture_output=True,text=True,env=env);self.assertEqual(p.returncode,5,p.stdout);approval.write_text(json.dumps({'plan':json.loads(p.stdout)['plan'],'confirmed_at':'2026-11-06T05:10:00Z','reference':'synthetic external recovery approval'}));p=subprocess.run(argv+['--approval-file',str(approval)],capture_output=True,text=True,env=env);self.assertEqual(p.returncode,0,p.stdout);self.assertEqual(tree(t.home),before)
