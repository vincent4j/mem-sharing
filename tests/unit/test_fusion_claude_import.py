"""Fresh Claude producer through fusion and subsequent checks, temporary HOME."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_m404_install as fixture_module
from runtime_fixture import seed_project_executors
from agm_core import user_rules_organize as fusion, user_entries, registry, paths, check, enable

class ClaudeFusionTests(unittest.TestCase):
    def setUp(self):
        f=fixture_module.InstallFixture();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        f.request.update(seed_project_executors(f.home));f.request['agents']=['codex','claude']
        self.original={}
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md')]:
            p=f.home/('.'+agent)/name;p.parent.mkdir(exist_ok=True)
            raw=('# 约定\n\n- 提交信息使用中文。\n\n'+agent+' 专属完整原文保留。\n').encode()
            p.write_bytes(raw);self.original[agent]=raw
        self.assertEqual(f.execute()['status'],'completed')
        self.req={k:v for k,v in f.request.items() if k in ('home','platform_config','agents','search_paths','app_directories','detect_runner')}
        self.claude=f.home/'.claude/CLAUDE.md'
        self.ledger=json.loads(f.runtime.registry.read_text())
        self.import_id=next(k for k,v in self.ledger['machine']['objects'].items() if v['kind']=='import')

    def approval(self,plan):return fixture_module.approved(plan)

    def test_fresh_installer_import_is_not_legacy_and_fusion_keeps_connection(self):
        self.assertEqual(self.ledger['machine']['objects'][self.import_id]['fingerprint']['basis'],'file_bytes')
        self.assertEqual(self.ledger['machine']['objects'][self.import_id]['ownership'],'reused')
        before=self.f.runtime.registry.read_bytes()
        r=fusion.plan_organize(self.req)
        self.assertEqual(r['blocked_entries'],[],r)
        self.assertEqual(r['status'],'approval_required',r)
        plan=r['approval_plan'];original=self.claude.read_bytes()
        done=fusion.execute_organize(plan,self.approval(plan),request=self.req)
        self.assertEqual(done['status'],'completed',done)
        self.assertIn(b'claude ',self.claude.read_bytes())
        self.assertNotIn('- 提交信息使用中文。'.encode(),self.claude.read_bytes())
        updated=json.loads(self.f.runtime.registry.read_bytes())
        expected=copy.deepcopy(self.ledger)
        expected['machine']['objects'][self.import_id]['fingerprint']['value']=fusion.entries.sha256(self.claude.read_bytes())
        self.assertEqual(updated,expected)
        self.assertTrue(plan['reference_rebindings'])
        self.assertEqual(plan['changes'][-1]['path'],str(self.f.runtime.registry))
        after_v=self.f.runtime.registry.read_bytes()
        data=registry.load_registry(self.f.runtime.registry,allowed_user_paths=paths.allowed_user_paths(self.f.config,None,home=str(self.f.home)))
        states=user_entries.connection_status(self.f.runtime,self.f.config,data,['codex','claude'])
        self.assertTrue(all(v['status']=='connected' for v in states.values()),states)
        user_entries._preflight_machine_units(data)
        again=fusion.plan_organize(self.req);self.assertNotEqual(again['status'],'failed',again)
        self.assertEqual(again['approval_plan']['changes'],[])
        follow=user_entries.run_user_entries(self.req)
        self.assertEqual(follow['status'],'completed',follow)
        # A reused import's whole-file hash is observation, never deletion authority.
        self.assertEqual(follow['errors'],[])
        self.assertEqual(self.f.runtime.registry.read_bytes(),after_v)

    def test_registry_write_failures_restore_body_and_observation_together(self):
        from agm_core.transaction import TransactionError
        before={p:p.read_bytes() for p in (self.claude,self.f.home/'.codex/AGENTS.md',self.f.runtime.registry)}
        for stage in ('before_write','after_write'):
            plan=fusion.plan_organize(self.req)['approval_plan']
            def fault(event,path):
                if event==stage and path==self.f.runtime.registry:raise TransactionError('synthetic registry write interruption')
            done=fusion.execute_organize(plan,self.approval(plan),request=self.req,hook=fault)
            self.assertEqual(done['status'],'failed',done)
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_registry_restore_failure_uses_restricted_original_transaction_recovery(self):
        from agm_core import fusion_recovery
        from agm_core.transaction import TransactionError
        before={p:p.read_bytes() for p in (self.claude,self.f.home/'.codex/AGENTS.md',self.f.runtime.registry)}
        plan=fusion.plan_organize(self.req)['approval_plan']
        def fault(event,path):
            if event=='after_write' and path==self.f.runtime.registry:raise TransactionError('synthetic V interruption')
            if event=='before_restore':raise TransactionError('synthetic restore unavailable')
        done=fusion.execute_organize(plan,self.approval(plan),request=self.req,hook=fault)
        self.assertEqual(done['status'],'recovery_required',done)
        manifest=done['errors'][0]['manifest']
        req={'home':str(self.f.home),'manifest':manifest}
        preview=fusion_recovery.run(req);self.assertEqual(preview['status'],'approval_required',preview)
        restored=fusion_recovery.run(dict(req,approval=self.approval(preview['approval_plan'])))
        self.assertEqual(restored['status'],'completed',restored)
        self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_terminal_history_recognizes_only_exact_reference_rebinding_transaction(self):
        from datetime import datetime,timezone
        from agm_core import staging_retirement
        plan=fusion.plan_organize(self.req)['approval_plan']
        approved=dict(plan,confirmed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),reference='Synthetic producer approval')
        done=fusion.execute_organize(plan,approved,request=self.req)
        self.assertEqual(done['status'],'completed',done)
        proof=staging_retirement._fusion_history(approved,self.f.runtime)
        self.assertIn(done['manifest'],proof)

    def test_prompt_includes_both_blocks_empty_text_and_all_choice_forms(self):
        r=fusion.plan_organize(self.req);prompt=r['prompt']
        for text in ('默认共享','由你选择是否共享','暂无','3、4','不共享 2','按默认方案','查看 3','本次融合尚未修改记忆内容'):
            self.assertIn(text,prompt)

    def test_presentation_projection_keeps_plan_and_full_sources_unchanged(self):
        plan=fusion.plan_organize(self.req)['approval_plan']
        before=copy.deepcopy(plan)
        number=plan['default_numbers'][0]
        prompt=fusion.present(plan)
        self.assertIn('记忆条目 %d' % number,prompt)
        self.assertIn('Claude Code',prompt);self.assertIn('Codex',prompt)
        self.assertNotIn(str(self.f.home),prompt)
        semantic=fusion.present(plan,summaries={number:'提交信息使用中文。'})
        self.assertIn('提交信息使用中文。',semantic)
        for text in ('默认共享','由你选择是否共享','暂无','3、4','不共享 2','查看 3','确认后才执行'):
            self.assertIn(text,semantic)
        self.assertEqual(plan,before)
        self.assertTrue(all('source' in i and 'text' in i for i in plan['items']))

    def test_unknown_whole_file_records_block_during_preview_not_final_execute(self):
        data=copy.deepcopy(self.ledger);obj=data['machine']['objects'][self.import_id]
        obj['kind']='file'
        self.f.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=paths.allowed_user_paths(self.f.config,None,home=str(self.f.home))))
        before=self.claude.read_bytes()
        stage=fusion.continuation(self.req)
        self.assertEqual(stage['status'],'blocked',stage)
        self.assertFalse(stage['automatic_continue']);self.assertTrue(stage['can_decline'])
        self.assertEqual(stage['preview']['errors'][0]['code'],'ownership_conflict')
        self.assertTrue(stage['preview']['next_action'])
        self.assertEqual(self.claude.read_bytes(),before)
        declined=fusion.plan_organize(dict(self.req,selection='暂不整理'))
        self.assertEqual(declined['fusion_status'],'declined')

if __name__=='__main__':unittest.main()
