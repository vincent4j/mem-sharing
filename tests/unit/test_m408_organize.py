"""Optional organization: synthetic HOME only, no mutation of existing modules."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from agm_core import paths, registry, entries, user_rules_organize as org
from agm_core.transaction import TransactionError
from runtime_fixture import seed_runtime


class OrganizeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name).resolve();self.home=self.area/'home';self.home.mkdir()
        self.runtime=seed_runtime(self.home)
        self.memories=self.runtime.root/'memories';self.memories.mkdir()
        (self.memories/'MEMORY.md').write_text('# 公共记忆\n\n- 沟通：回答应简洁明确。[沟通](communication.md)\n')
        (self.memories/'communication.md').write_text('# 沟通\n\n## L1 概要\n\n回答应简洁明确。\n\n## L2 原文\n\n- 回答应简洁明确。\n')
        self.config=paths.select_platform(paths.load_agents_table(),'darwin')
        self.request={'home':str(self.home),'platform_config':self.config,'date':'2026-10-30'}
        self.files={};self.managed={};self.unique={}
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md'),('workbuddy','MEMORY.md')]:
            p=self.home/('.'+agent)/name;p.parent.mkdir()
            block=('<!-- agent-group-memory:rules:start -->\r\n'
                   '只读公共记忆：这行有公共规则关键词但不得整理。\r\n'
                   '<!-- agent-group-memory:rules:end -->').encode()
            self.managed[agent]=block
            special=('- '+agent+' 专属：使用专用执行器路径。\r\n').encode()
            self.unique[agent]=special
            p.write_bytes(b'# User rules\r\n\r\n'+block+b'\r\n\r\n'
                          +'- 提交信息请使用简体中文。\r\n'.encode()+special
                          +'- 回答应简洁明确。\r\n'.encode())
            self.files[agent]=p
        self.vbefore=self.runtime.registry.read_bytes()

    def preview(self,request=None):
        result=org.plan_organize(request or self.request)
        self.assertEqual(result['status'],'approval_required',result)
        return result['approval_plan']

    def approve(self,plan):
        return dict(plan,confirmed_at='2026-10-30T00:00:00Z',reference='explicit synthetic central user confirmation')

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,
                p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in [self.home,*self.home.rglob('*')]}

    def test_scan_three_mixed_entries_is_read_only_and_exact_byte_spans(self):
        before=self.snapshot();plan=self.preview()
        self.assertEqual(before,self.snapshot());self.assertEqual(len(plan['items']),9)
        for agent in self.files:
            items=[i for i in plan['items'] if i['agent']==agent]
            self.assertEqual([i['classification'] for i in items],['公共','独有','疑似冗余'])
            self.assertEqual([i['action'] for i in items],['move','keep','delete'])
            for item in items:
                raw=self.files[agent].read_bytes()[item['start']:item['end']]
                self.assertEqual(raw.decode(),item['text']);self.assertEqual(entries.sha256(raw),item['sha256'])
            duplicate=items[2];self.assertIn('回答应简洁明确',duplicate['comparison']['text'])
            self.assertTrue(duplicate['comparison']['path'].startswith(str(self.memories)))
        self.assertEqual(len(plan['protected_units']),3)
        self.assertIn('建议',plan['items'][0]['reason'])

    def test_execute_one_transaction_preserves_unique_and_blocks_V_unchanged(self):
        plan=self.preview();result=org.execute_organize(plan,self.approve(plan))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.runtime.registry.read_bytes(),self.vbefore)
        manifest=json.loads(Path(result['manifest']).read_bytes())
        self.assertEqual(manifest['status'],'committed');self.assertEqual(len(manifest['entries']),5)
        self.assertNotIn(str(self.runtime.registry),[e['path'] for e in manifest['entries']])
        for agent,path in self.files.items():
            self.assertIn(self.unique[agent],path.read_bytes());self.assertIn(self.managed[agent],path.read_bytes())
            self.assertNotIn('提交信息'.encode(),path.read_bytes());self.assertNotIn('回答应简洁明确'.encode(),path.read_bytes())
        topic=(self.memories/'user-rules.md').read_text()
        self.assertLess(topic.index('## L1'),topic.index('## L2'))
        self.assertIn('当前有效结论',topic);self.assertIn('待办',topic)
        for agent in self.files:self.assertIn('> 迁自 ~/.'+agent+'/',topic)
        self.assertIn('(2026-10-30, 原段 sha256 ',topic)
        index=(self.memories/'MEMORY.md').read_text()
        self.assertIn('用户公共规则：通用约定已按集中批准计划归位',index);self.assertIn('(user-rules.md)',index)
        self.assertEqual({p.suffix for p in self.memories.rglob('*') if p.is_file()},{'.md'})
        before=self.snapshot();again=org.plan_organize(self.request)
        self.assertEqual(again['status'],'completed',again);self.assertEqual(again['approval_plan']['changes'],[])
        self.assertEqual(before,self.snapshot())

    def test_central_approval_binds_every_item_and_rejects_old_confirmation_field(self):
        plan=self.preview();approval=self.approve(plan);before=self.snapshot()
        self.assertEqual(set(approval)-set(plan),{'confirmed_at','reference'})
        approval['items']=[i for i in approval['items'] if i['action']!='delete']
        result=org.execute_organize(plan,approval)
        self.assertEqual(result['errors'][0]['code'],'approval_mismatch');self.assertEqual(before,self.snapshot())
        approval=self.approve(plan);approval['item_confirmations']=[]
        self.assertEqual(org.execute_organize(plan,approval)['status'],'failed');self.assertEqual(before,self.snapshot())

    def test_decision_keep_redundant_and_modify_requires_exact_new_preview(self):
        original=self.preview();decisions={i['item_id']:{'action':'keep'} for i in original['items'] if i['classification']=='疑似冗余'}
        item=next(i for i in original['items'] if i['classification']=='公共')
        decisions[item['item_id']]={'action':'modify','replacement':'- 提交说明遵循已确认的项目语言。'}
        request=dict(self.request,decisions=decisions);plan=self.preview(request)
        self.assertEqual(org.execute_organize(plan,self.approve(original),request=request)['status'],'failed')
        done=org.execute_organize(plan,self.approve(plan),request=request)
        self.assertEqual(done['status'],'completed',done)
        for agent,path in self.files.items():
            self.assertIn('回答应简洁明确'.encode(),path.read_bytes());self.assertIn(self.unique[agent],path.read_bytes())
        self.assertIn('提交说明遵循已确认的项目语言。\r\n'.encode(),self.files[item['agent']].read_bytes())

    def test_exclusive_cannot_be_moved_or_deleted_even_with_decision(self):
        plan=self.preview();item=next(i for i in plan['items'] if i['classification']=='独有')
        before=self.snapshot()
        for action in ('move','delete','modify'):
            result=org.plan_organize(dict(self.request,decisions={item['item_id']:{'action':action,'replacement':'changed'} if action=='modify' else {'action':action}}))
            self.assertEqual(result['errors'][0]['code'],'exclusive_rule_protected')
        self.assertEqual(before,self.snapshot())

    def test_preview_source_public_or_registry_drift_stops_without_more_writes(self):
        for path in (self.files['codex'],self.memories/'communication.md',self.runtime.registry):
            with self.subTest(path=path):
                plan=self.preview();old=path.read_bytes();path.write_bytes(old+b'\n')
                before=self.snapshot();result=org.execute_organize(plan,self.approve(plan))
                self.assertEqual(result['status'],'failed',result);self.assertEqual(before,self.snapshot())
                path.write_bytes(old)
        plan=self.preview();new=self.memories/'new.md';new.write_text('new public rule')
        before=self.snapshot();result=org.execute_organize(plan,self.approve(plan))
        self.assertEqual(result['errors'][0]['code'],'drift');self.assertEqual(before,self.snapshot())

    def test_symlink_incomplete_markers_bad_encoding_and_target_escape_reject(self):
        plan=self.preview();self.files['codex'].write_bytes(b'<!-- agent-group-memory:rules:start -->\nuser')
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'entry_conflict')
        self.files['codex'].write_bytes(b'\xff')
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'encoding_conflict')
        self.files['codex'].unlink();self.files['codex'].symlink_to(self.files['claude'])
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'path_conflict')
        for topic in ('../escape.md','MEMORY.md','nested/topic.md'):
            self.assertEqual(org.plan_organize(dict(self.request,topic=topic))['errors'][0]['code'],'invalid_request')

    def test_old_wholefile_owned_entry_listed_and_edit_blocked(self):
        data=registry.load_registry(self.runtime.registry,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home)))
        data['machine']['agents']['codex']={'installation':{'status':'installed','observed_at':'2026-10-30T00:00:00Z','evidence':'fixture'},
            'static':registry.unknown_fact(),'runtime_acceptance':{'status':'pending','evidence_path':None}}
        data['machine']['objects']['old-import']={'kind':'import','path':str(self.files['codex']),'scope':'machine',
            'agents':['codex'],'ownership':'reused','marker':None,'fingerprint':{'algorithm':'sha256','basis':'file_bytes',
            'value':entries.sha256(self.files['codex'].read_bytes())},'original_existed':True,'link_target':None,'backup_manifest':None,'consumers':[]}
        self.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        plan=self.preview();blocked=plan['blocked_entries'];self.assertEqual(len(blocked),1)
        self.assertEqual(blocked[0]['path'],str(self.files['codex']));self.assertEqual(blocked[0]['record_types'],['import'])
        self.assertIn('生命周期',blocked[0]['conversion']);before=self.snapshot()
        result=org.execute_organize(plan,self.approve(plan))
        self.assertEqual(result['errors'][0]['code'],'ownership_conflict');self.assertEqual(result['blocked_entries'],blocked)
        self.assertEqual(before,self.snapshot())

    def test_managed_reference_line_paragraph_and_lists_protected(self):
        p=self.files['claude'];reference=('@'+str(self.memories/'MEMORY.md')+'\n').encode()
        p.write_bytes(reference+b'\n'+p.read_bytes())
        plan=self.preview();self.assertFalse(any(i['text'].startswith('@') for i in plan['items']))
        self.assertEqual(org.execute_organize(plan,self.approve(plan))['status'],'completed')
        self.assertTrue(p.read_bytes().startswith(reference))

    def test_fenced_tool_commands_are_exclusive_and_multiline_paragraph_exact(self):
        p=self.files['codex'];p.write_bytes('偏好使用简体中文，\n长段落保持原来的字节。\n\n```sh\ngit status\n```\n'.encode())
        plan=self.preview();items=[i for i in plan['items'] if i['agent']=='codex']
        self.assertEqual(len(items),2);self.assertEqual(items[0]['classification'],'公共')
        self.assertEqual(items[1]['classification'],'独有');self.assertIn('\n长段落',items[0]['text'])

    def test_public_symlink_and_different_index_link_conflict(self):
        link=self.memories/'external.md';link.symlink_to(self.files['codex'])
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'path_conflict');link.unlink()
        with (self.memories/'MEMORY.md').open('ab') as stream:stream.write(b'- existing [x](user-rules.md)\n')
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'content_conflict')

    def test_transaction_failure_rolls_back_entries_content_and_registry_unchanged(self):
        plan=self.preview();before={str(p):p.read_bytes() for p in [*self.files.values(),self.memories/'MEMORY.md',self.runtime.registry]}
        count=[]
        def fault(event,path):
            if event=='after_write':
                count.append(path)
                if len(count)==2:raise TransactionError('synthetic write failure')
        result=org.execute_organize(plan,self.approve(plan),hook=fault)
        self.assertEqual(result['status'],'failed',result)
        for path,raw in before.items():self.assertEqual(Path(path).read_bytes(),raw)
        self.assertFalse((self.memories/'user-rules.md').exists())

    def test_request_result_interface_missing_approval_and_execution(self):
        preview=org.run(self.request);self.assertEqual(preview['status'],'approval_required')
        self.assertEqual(set(json.loads(preview['next_action']))-set(preview['approval_plan']),{'confirmed_at','reference'})
        result=org.run(dict(self.request,approval=self.approve(preview['approval_plan'])))
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(org.run(dict(self.request,approval=[]))['status'],'failed')

    def test_unknown_item_and_invalid_confirmation_stop(self):
        self.assertEqual(org.plan_organize(dict(self.request,decisions={'not-an-item':{'action':'keep'}}))['errors'][0]['code'],'stale_decision')
        plan=self.preview();approval=self.approve(plan);approval['reference']=''
        before=self.snapshot();self.assertEqual(org.execute_organize(plan,approval)['status'],'failed')
        self.assertEqual(before,self.snapshot())

    def test_empty_entries_are_noop_without_lock_or_backup(self):
        for p in self.files.values():p.write_bytes(b'# Personal\n')
        before=self.snapshot();result=org.run(self.request)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['approval_plan']['changes'],[])
        self.assertEqual(before,self.snapshot())

    def test_nested_executor_specific_list_keeps_entire_parent(self):
        self.files['codex'].write_text('- 通用提交偏好：\n  - Codex 专属约束保持在这里。\n- 提交信息使用简体中文。\n')
        plan=self.preview();items=[i for i in plan['items'] if i['agent']=='codex']
        self.assertEqual(len(items),2);self.assertEqual(items[0]['classification'],'独有')
        self.assertIn('  - Codex',items[0]['text']);self.assertEqual(items[1]['action'],'move')

    def test_inflight_public_addition_stops_and_preserves_foreign_new_file(self):
        plan=self.preview();before={str(p):p.read_bytes() for p in self.files.values()};injected=[]
        foreign=self.memories/'late.md'
        def hook(event,path):
            if event=='after_write' and not injected:
                injected.append(True);foreign.write_text('foreign change')
        result=org.execute_organize(plan,self.approve(plan),hook=hook)
        self.assertEqual(result['status'],'failed',result);self.assertEqual(foreign.read_text(),'foreign change')
        for name,raw in before.items():self.assertEqual(Path(name).read_bytes(),raw)
        self.assertEqual(self.runtime.registry.read_bytes(),self.vbefore)

    def test_home_with_symlink_ancestor_is_canonicalized_not_rejected(self):
        # Mirrors macOS mktemp HOME under /var -> /private/var. Only the
        # environment anchor is aliased; managed components remain real.
        alias=self.area/'environment-alias';alias.symlink_to(self.area,target_is_directory=True)
        request=dict(self.request,home=str(alias/'home'))
        plan=self.preview(request);self.assertEqual(plan['layout']['root'],str(self.runtime.root))
        self.assertEqual(org.execute_organize(plan,self.approve(plan),request=request)['status'],'completed')
