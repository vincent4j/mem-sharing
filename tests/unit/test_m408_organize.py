"""Optional organization: synthetic HOME only, no mutation of existing modules."""
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
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
            block=('<!-- mem-sharing:rules:start -->\r\n'
                   '只读公共记忆：这行有公共规则关键词但不得整理。\r\n'
                   '<!-- mem-sharing:rules:end -->').encode()
            self.managed[agent]=block
            special=('- '+agent+' 专属：使用专用执行器路径。\r\n').encode()
            self.unique[agent]=special
            p.write_bytes(b'# User rules\r\n\r\n'+block+b'\r\n\r\n'
                          +'- 提交信息请使用简体中文。\r\n'.encode()+special
                          +'- 回答应简洁明确。\r\n'.encode())
            self.files[agent]=p
        self.vbefore=self.runtime.registry.read_bytes()
        # Unit fixtures isolate installation/entry validation, covered end-to-end
        # with real synthetic detection and installer in test_memory_fusion.
        participants=patch.object(org,'_participants',side_effect=lambda req,*args:(paths.resolve_agents(req.get('agents')), {'fixture':'stable'}))
        participants.start();self.addCleanup(participants.stop)
        readers=patch.object(org.user_entries,'connection_status',return_value={a:{'status':'connected'} for a in paths.AGENT_ORDER})
        readers.start();self.addCleanup(readers.stop)


    def preview(self,request=None):
        req=request if request is not None else self.request
        result=org.plan_organize(req)
        # Single-file/partial content needs an explicit choice under the new PRD.
        if result['status']=='completed' and result['approval_plan']['items']:
            req['selection']='、'.join(str(g['number']) for g in result['approval_plan']['groups'])
            result=org.plan_organize(req)
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
        self.assertEqual(before,self.snapshot());self.assertEqual(len(plan['items']),6)
        self.assertEqual(len(plan['default_numbers']),2)
        for agent in self.files:
            items=[i for i in plan['items'] if agent in i['agents']]
            self.assertEqual(len(items),2)
            for item in items:
                raw=self.files[agent].read_bytes()[item['start']:item['end']]
                self.assertEqual(raw.decode(),item['text']);self.assertEqual(entries.sha256(raw),item['sha256'])
            self.assertFalse(any('专属' in i['text'] for i in items))
        self.assertEqual(len(plan['protected_units']),3)

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
        self.assertIn('- 提交信息请使用简体中文。',topic)
        self.assertIn('# User rules',topic)
        self.assertEqual({i['source'] for i in plan['items']},{str(p) for p in self.files.values()})
        index=(self.memories/'MEMORY.md').read_text()
        self.assertIn('用户记忆：',index);self.assertIn('(user-rules.md)',index)
        self.assertEqual({p.suffix for p in self.memories.rglob('*') if p.is_file()},{'.md'})
        before=self.snapshot();again=org.plan_organize(self.request)
        self.assertEqual(again['status'],'completed',again);self.assertEqual(again['approval_plan']['changes'],[])
        self.assertEqual(before,self.snapshot())

    def test_central_approval_binds_every_item_and_rejects_old_confirmation_field(self):
        plan=self.preview();approval=self.approve(plan);before=self.snapshot()
        self.assertEqual(set(approval)-set(plan),{'confirmed_at','reference'})
        approval['items']=approval['items'][:-1]
        result=org.execute_organize(plan,approval)
        self.assertEqual(result['errors'][0]['code'],'approval_mismatch');self.assertEqual(before,self.snapshot())
        approval=self.approve(plan);approval['item_confirmations']=[]
        self.assertEqual(org.execute_organize(plan,approval)['status'],'failed');self.assertEqual(before,self.snapshot())

    def test_decision_keep_redundant_and_modify_requires_exact_new_preview(self):
        original=self.preview()
        request=dict(self.request,decisions={'old':{'action':'modify','replacement':'changed'}})
        self.assertEqual(org.plan_organize(request)['errors'][0]['code'],'invalid_request')
        number=next(g['number'] for g in original['groups'] if '回答应简洁明确' in g['summary'])
        request=dict(self.request,selection='不共享 '+str(number));plan=self.preview(request)
        self.assertEqual(org.execute_organize(plan,self.approve(original),request=request)['status'],'failed')
        done=org.execute_organize(plan,self.approve(plan),request=request)
        self.assertEqual(done['status'],'completed',done)
        for agent,path in self.files.items():
            self.assertIn('回答应简洁明确'.encode(),path.read_bytes());self.assertIn(self.unique[agent],path.read_bytes())

    def test_exclusive_cannot_be_moved_or_deleted_even_with_decision(self):
        plan=self.preview();before=self.snapshot()
        self.assertFalse(any('专属' in i['text'] for i in plan['items']))
        for action in ('move','delete','modify'):
            result=org.plan_organize(dict(self.request,decisions={'exclusive':{'action':action}}))
            self.assertEqual(result['errors'][0]['code'],'invalid_request')
        self.assertEqual(before,self.snapshot())
        done=org.execute_organize(plan,self.approve(plan));self.assertEqual(done['status'],'completed',done)
        for agent,path in self.files.items():self.assertIn(self.unique[agent],path.read_bytes())

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
        plan=self.preview();self.files['codex'].write_bytes(b'<!-- mem-sharing:rules:start -->\nuser')
        self.assertEqual(org.plan_organize(self.request)['errors'][0]['code'],'entry_conflict')
        self.files['codex'].write_bytes(b'\xff')
        self.assertTrue(org.plan_organize(self.request)['approval_plan']['unknown_sources'])
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
        preview=org.plan_organize(self.request);self.assertEqual(preview['status'],'failed',preview)
        plan=preview['approval_plan'];blocked=plan['blocked_entries'];self.assertEqual(len(blocked),1)
        self.assertEqual(blocked[0]['path'],str(self.files['codex']));self.assertIn('受管入口',blocked[0]['reason']);before=self.snapshot()
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
        plan=self.preview();items=[i for i in plan['items'] if 'codex' in i['agents']]
        self.assertEqual(len(items),1);self.assertIn('\n长段落',items[0]['text'])
        self.assertFalse(any('git status' in i['text'] for i in plan['items']))
        done=org.execute_organize(plan,self.approve(plan));self.assertEqual(done['status'],'completed',done)
        self.assertIn(b'```sh\ngit status\n```',p.read_bytes())

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
        self.assertEqual(org.plan_organize(dict(self.request,decisions={'not-an-item':{'action':'keep'}}))['errors'][0]['code'],'invalid_request')
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
        plan=self.preview();items=[i for i in plan['items'] if 'codex' in i['agents']]
        self.assertEqual(len(items),1);self.assertNotIn('  - Codex',items[0]['text'])
        done=org.execute_organize(plan,self.approve(plan));self.assertEqual(done['status'],'completed',done)
        self.assertIn('- 通用提交偏好：\n  - Codex 专属约束保持在这里。',self.files['codex'].read_text())

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


class CKProtectionTests(unittest.TestCase):
    """CK owns both marker variants in every executor's entry, never AGM."""

    def scene(self, agent, raw):
        fixture = OrganizeTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        path = Path(paths.expand_path(fixture.config[agent]['user_entry'], home=str(fixture.home)))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        fixture.request['agents'] = [agent]
        return fixture, path

    def test_complete_variants_are_opaque_with_legal_rules_before_and_after(self):
        for agent in paths.AGENT_ORDER:
            for suffix in ('', ':workbuddy'):
                for newline in ('\n', '\r\n'):
                    with self.subTest(agent=agent, suffix=suffix, newline=repr(newline)):
                        start = '<!-- context-keeper'+suffix+':start -->'
                        end = '<!-- context-keeper'+suffix+':end -->'
                        ck = newline.join((start, '## Context Keeper', '',
                            '- 使用简体中文，提交前测试。', '- 回答应简洁明确。', '',
                            '保存前核验证据。', 'CK_PRIVATE_SENTINEL', end)).encode()
                        before = ('- 提交信息请使用简体中文。'+newline+newline).encode()
                        after = (newline+newline+'- 测试完成后核验证据。'+newline).encode()
                        # Also preserve existing AGM blocks and both native imports.
                        agm = b'<!-- mem-sharing:rules:start -->\nAGM opaque\n<!-- mem-sharing:rules:end -->'
                        imports = b'@AGENTS.md\n'
                        fixture, path = self.scene(agent, before+agm+b'\n'+imports+ck+after)
                        public_import = ('@'+str(fixture.memories/'MEMORY.md')+'\r\n').encode()
                        path.write_bytes(public_import+path.read_bytes())
                        initial = path.read_bytes(); snapshot = fixture.snapshot()
                        plan = fixture.preview()
                        self.assertEqual(fixture.snapshot(), snapshot)
                        self.assertEqual(len(plan['items']), 2)
                        self.assertEqual(len(plan['selected_numbers']),2)  # explicit single-source selection
                        self.assertFalse(any('CK_PRIVATE_SENTINEL' in i['text'] or 'context-keeper' in i['text'] for i in plan['items']))
                        self.assertTrue(any(initial[u['start']:u['end']] == ck for u in plan['protected_units']))
                        result = org.execute_organize(plan, fixture.approve(plan))
                        self.assertEqual(result['status'], 'completed', result)
                        expected = initial
                        for item in sorted(plan['items'], key=lambda i:i['start'], reverse=True):
                            expected = expected[:item['start']]+expected[item['end']:]
                        self.assertEqual(path.read_bytes(), expected)
                        self.assertIn(ck, expected); self.assertIn(agm, expected)
                        self.assertIn(imports, expected); self.assertIn(public_import, expected)
                        self.assertEqual(fixture.runtime.registry.read_bytes(), fixture.vbefore)
                        topic = (fixture.memories/'user-rules.md').read_bytes()
                        self.assertNotIn(ck, topic); self.assertNotIn(b'CK_PRIVATE_SENTINEL', topic)
                        self.assertNotIn(b'context-keeper', topic)

    def test_two_complete_ck_variants_coexist_without_becoming_candidates(self):
        for agent in paths.AGENT_ORDER:
            with self.subTest(agent=agent):
                blocks = [b'<!-- context-keeper'+suffix+b':start -->\n- '+
                          '测试使用简体中文。'.encode()+b'\n<!-- context-keeper'+suffix+b':end -->'
                          for suffix in (b'', b':workbuddy')]
                raw = b'\r\n\r\n'.join(blocks)
                fixture, path = self.scene(agent, raw)
                before = fixture.snapshot()
                result = org.run(fixture.request)
                self.assertEqual(result['status'], 'completed', result)
                self.assertEqual(result['approval_plan']['items'], [])
                self.assertEqual(fixture.snapshot(), before)
                self.assertEqual(path.read_bytes(), raw)

    def test_damaged_ck_markers_refuse_preview_and_approved_execution_zero_write(self):
        for agent in paths.AGENT_ORDER:
            for suffix in (b'', b':workbuddy'):
                start = b'<!-- context-keeper'+suffix+b':start -->'
                end = b'<!-- context-keeper'+suffix+b':end -->'
                other_suffix = b':workbuddy' if not suffix else b''
                other_start = b'<!-- context-keeper'+other_suffix+b':start -->'
                other_end = b'<!-- context-keeper'+other_suffix+b':end -->'
                agm_start = b'<!-- mem-sharing:rules:start -->'
                agm_end = b'<!-- mem-sharing:rules:end -->'
                shapes = {
                    'start_only': [start], 'end_only': [end],
                    'duplicate_start': [start, start, end],
                    'duplicate_end': [start, end, end],
                    'duplicate_pair': [start, end, start, end],
                    'reverse': [end, start],
                    'ck_cross': [start, other_start, end, other_end],
                    'ck_agm_cross': [start, agm_start, end, agm_end],
                    'agm_ck_cross': [agm_start, start, agm_end, end],
                }
                for name, markers in shapes.items():
                    with self.subTest(agent=agent, suffix=suffix, shape=name):
                        fixture, path = self.scene(agent, '- 提交前测试。\n'.encode())
                        good_plan = fixture.preview()
                        # A formerly valid exact approval must not override malformed CK.
                        path.write_bytes(b'\r\n\r\n'.join(markers)+'\r\n- 提交前测试。\r\n'.encode())
                        before = fixture.snapshot()
                        result = org.plan_organize(fixture.request)
                        self.assertEqual(result['status'], 'failed', result)
                        self.assertEqual(result['errors'][0]['code'], 'entry_conflict')
                        self.assertEqual(fixture.snapshot(), before)
                        result = org.run(dict(fixture.request, approval=fixture.approve(good_plan)))
                        self.assertEqual(result['status'], 'failed', result)
                        self.assertEqual(result['errors'][0]['code'], 'entry_conflict')
                        self.assertEqual(fixture.snapshot(), before)
