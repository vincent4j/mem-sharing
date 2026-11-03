import sys,json,tempfile,collections,unittest
from pathlib import Path
from unittest.mock import patch
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'scripts'));sys.path.insert(0,str(repo/'tests/unit'))
from test_m404_install import InstallFixture,approved
from agm_core import detect,paths,user_rules_organize as fusion,uninstall,uninstall_memory as memory

class ScopedProductionTests(unittest.TestCase):
 def test_six_groups_six_sources_return_has_no_added_nonempty_lines(self):
  f=InstallFixture();f.setUp()
  try:
   rule='- 用简体中文；明确目标与范围，做必要改动，以证据报告结果、风险和未验证项，不把配置或静态检查当作实际成功。'
   pref='# 内容处理偏好';rules='## 规则'
   original={}
   for agent,config in f.config.items():
    p=Path(paths.expand_path(config['user_entry'],home=str(f.home)));p.parent.mkdir(parents=True,exist_ok=True)
    raw=(pref+'\n\n'+rules+'\n\n- A 合成条款完整保留。\n\n# 按需操作参考\n## 临时交接\n\n- B 合成条款完整保留。\n\n- C 合成条款完整保留。\n\n- D 合成条款完整保留。\n\n- E 合成条款完整保留。\n\n'+rule+'\n\n'+agent+' 专属合成内容保留。\n').encode()
    p.write_bytes(raw);original[agent]=(p,raw)
   real=detect.detect_agents
   def installed(*args,**kwargs):
    result=real(*args,**kwargs)
    for row in result['agents'].values():row.update(status='installed',summary='synthetic evidence')
    return result
   with patch.object(detect,'detect_agents',side_effect=installed):
    assert f.execute()['status']=='completed'
    request={k:v for k,v in f.request.items() if k in ('home','platform_config','agents','search_paths','app_directories')}
    preview=fusion.plan_organize(request);assert preview['status']=='approval_required',preview['status']
    plan=preview['approval_plan'];done=fusion.execute_organize(plan,approved(plan),request=request);assert done['status']=='completed',done['status']
    extra=f.runtime.root/'memories/unlinked-heading.md'
    extra.write_bytes(b'# Standalone user heading\n')
    result=uninstall.preview(home=f.home,backup_dir=f.area/'future-backup')
    body=memory.public_body(f.runtime,memory.public_sources(f.runtime))
    report={'synthetic_only':True,'groups':[{'number':g['number'],'sources':len(g['sources']),'scopes':[x['scope'] for x in g['sources']],'trailing_LF':[len(x['text'])-len(x['text'].rstrip('\n')) for x in g['sources']]} for g in plan['groups']],'public_unlinked_case':True,'public_paths':[str(p.relative_to(f.runtime.root)) for p in (f.runtime.root/'memories').rglob('*') if p.is_file()],'native_deltas':{}}
    for agent,(p,before) in original.items():
     after=bytes.fromhex(next(c['after']['hex'] for c in result['changes'] if c['path']==str(p)))
     count=lambda raw:collections.Counter(line for line in raw.decode().splitlines() if line.strip())
     assert after.count(b'# Standalone user heading')==1
     after=after.replace(b'# Standalone user heading\n',b'')
     assert count(after)==count(before), (agent,count(after)-count(before),count(before)-count(after))
     delta=count(after)-count(before)
     report['native_deltas'][agent]=dict(delta)
    out=Path(tempfile.mkdtemp(prefix='memsharing-scope-duplicate-readonly-')).resolve()
    (out/'base-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (out/'synthetic-public-body.txt').write_bytes(body)
    assert all(not delta for delta in report['native_deltas'].values()), report['native_deltas']
  finally:f.doCleanups()

class ScopedBoundaryTests(unittest.TestCase):
 def test_same_text_different_scope_and_original_duplicates_preserved(self):
  raw=b'# A\n\n- same\n\n- same\n\n# B\n\n'
  result=memory.merge_native(raw,b'# A\n\n- same\n\n# B\n\n- same\n',scoped=True)
  self.assertEqual(result.count(b'- same'),3)
  self.assertIn(b'# A\n\n- same\n\n- same\n\n',result)
  sections,items,_=memory._scoped_layout(result)
  self.assertEqual(sum(scope==(b'B',) and b'- same' in item for scope,item,_ in items),1)
 def test_bom_crlf_native_bytes_and_ck_remain_opaque(self):
  ck=b'<!-- context-keeper:start -->\r\n# Fake scope\r\nprivate CK\r\n<!-- context-keeper:end -->'
  raw=b'\xef\xbb\xbf# A\r\n\r\n- original\r\n\r\n'+ck+b'\r\n'
  result=memory.merge_native(raw,b'# A\n\n- original\n\n- new full text\n\n'+ck,scoped=True)
  self.assertTrue(result.startswith(raw));self.assertEqual(result.count(b'- original'),1)
  self.assertEqual(result.count(ck),1);self.assertIn(b'- new full text\n',result)
 def test_code_fence_headings_do_not_change_scope(self):
  raw=b'# A\n\n```text\n# Fake\n```\n\n'
  result=memory.merge_native(raw,b'# A\n\n- new\n',scoped=True)
  self.assertIn(raw,result);self.assertNotIn(b'# A\n\n# A',result)
  _,items,_=memory._scoped_layout(result)
  self.assertTrue(any(scope==(b'A',) and text.startswith(b'- new') for scope,text,_ in items))
 def test_repeated_native_scope_missing_item_rejects(self):
  raw=b'# A\n\nold one\n\n# A\n\nold two\n'
  with self.assertRaisesRegex(ValueError,'Ambiguous'):memory.merge_native(raw,b'# A\n\n- new\n',scoped=True)

 def test_heading_only_preserved_and_unclassified_indented_heading_rejected(self):
  raw=b'# User heading\n'
  self.assertIn(raw,memory.merge_native(b'',raw,scoped=True))
  for prefix in (b' ',b'  ',b'   '):
   with self.assertRaisesRegex(ValueError,'Unclassified'):memory.merge_native(b'',prefix+raw,scoped=True)

class EmptyHierarchyTests(unittest.TestCase):
 def test_parent_child_and_siblings_empty_preserve_one_prefix(self):
  for raw in (b'# A\n## B\n',b'# A\n## B\n## C\n',b'# A\r\n## B\r\n### C\r\n## D\r\n',b'\xef\xbb\xbf# A\r\n## B\r\n'):
   result=memory.merge_native(b'',raw,scoped=True)
   self.assertEqual([line for line in result.splitlines() if line.strip()],raw.splitlines())
   self.assertEqual(result.count(b'# A'),1)
 def test_mixed_parent_body_child_empty_sibling_body_source_order(self):
  raw=b'# A\n\nparent original\n\n## B\n## C\n\nchild original\n'
  result=memory.merge_native(b'',raw,scoped=True)
  self.assertEqual([line for line in result.splitlines() if line.strip()],[line for line in raw.splitlines() if line.strip()])
  self.assertEqual(result.count(b'# A'),1)
 def test_reuse_existing_parent_when_new_empty_child_inserted(self):
  native=b'# A\n\noriginal parent\n\n# Z\n\noriginal tail\n'
  result=memory.merge_native(native,b'# A\n## B\n## C\n',scoped=True)
  self.assertEqual(result.count(b'# A'),1);self.assertEqual(result.count(b'## B'),1);self.assertEqual(result.count(b'## C'),1)
  self.assertLess(result.index(b'## C'),result.index(b'# Z'))
  _,items,_=memory._scoped_layout(result)
  self.assertIn(((b'Z',),b'original tail\n'),[(scope,text) for scope,text,_ in items])

 def test_incompatible_existing_parent_depth_refuses_instead_of_rewriting(self):
  with self.assertRaisesRegex(ValueError,'hierarchy'):memory.merge_native(b'## A\n',b'# A\n## B\n',scoped=True)
