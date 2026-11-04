"""Fusion safety and selection, entirely synthetic HOME/project trees."""
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import paths, registry, entries, user_rules_organize as org
from agm_core.transaction import TransactionError, recover_manifest, write_lock
from runtime_fixture import seed_runtime
REAL_PARTICIPANTS = org._participants

class FusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()/'home'; self.home.mkdir()
        self.rt = seed_runtime(self.home)
        self.mem = self.rt.root/'memories'; self.mem.mkdir()
        (self.mem/'MEMORY.md').write_text('# 用户记忆\n')
        self.config = paths.select_platform(paths.load_agents_table(),'darwin')
        self.req = dict(home=str(self.home), platform_config=self.config)
        self.agents = ['codex','claude','workbuddy']
        self.files = []
        for agent in self.agents:
            p = Path(paths.expand_path(self.config[agent]['user_entry'],home=str(self.home)))
            p.parent.mkdir(parents=True); p.write_text('# 约定\n\n- 提交信息使用中文。\n')
            self.files.append(p)
        self.participants = patch.object(org, '_participants', side_effect=lambda *a:(self.agents.copy(), {'fixture':'stable'}))
        self.participants.start(); self.addCleanup(self.participants.stop)

    def plan(self, **kw):
        result = org.plan_organize(dict(self.req, **kw))
        self.assertNotEqual(result['status'],'failed',result)
        return result['approval_plan']

    def approve(self, plan):
        return dict(plan,confirmed_at='2026-11-03T06:00:00Z',reference='synthetic user confirmation')

    def execute(self, plan, hook=None, readers=True):
        # Group/transaction tests isolate the pre-existing user-entry validator.
        with patch.object(org.user_entries,'connection_status',return_value={a:{'status':'connected' if readers else 'pending'} for a in self.agents}):
            return org.execute_organize(plan,self.approve(plan),hook=hook)

    def test_three_all_default_subset_optional_and_single_not_default(self):
        self.files[0].write_text(self.files[0].read_text()+'- 修改后运行相关测试。\n- 单家记录。\n')
        self.files[1].write_text(self.files[1].read_text()+'- 修改后运行相关测试。\n')
        p = self.plan()
        self.assertEqual((len(p['default_numbers']),len(p['optional_numbers']),len(p['single_numbers'])),(1,1,1))
        self.assertEqual([g['number'] for g in p['groups']],[1,2,3])
        chosen=self.plan(selection='2')
        self.assertEqual(chosen['selected_numbers'],[1,2])
        self.assertEqual(p['groups'],chosen['groups'])
        self.assertEqual(self.plan(selection='共享 2，不共享 1')['selected_numbers'],[2])

    def test_n_one_never_default_missing_and_unknown_not_coverage(self):
        self.agents[:]=['codex']
        self.assertEqual(self.plan()['default_numbers'],[])
        self.agents[:]=['codex','claude','workbuddy']
        self.files[2].unlink()
        self.assertEqual(self.plan()['optional_numbers'],[1])
        self.files[2].write_bytes(b'\xff')
        p=self.plan(); self.assertTrue(p['unknown_sources']);self.assertEqual(p['default_numbers'],[])

    def test_single_items_visible_under_pending_with_stable_numbers_and_view_zero_write(self):
        self.agents[:] = ['codex']
        self.files[0].write_text('# 约定\n\n- 忠实的单家偏好。\n')
        plan = self.plan()
        text = org.present(plan)
        self.assertIn('由你选择是否共享\n1.', text)
        self.assertIn('原文摘录：- 忠实的单家偏好。', text)
        self.assertIn('单家内容，默认不共享', text)
        self.assertEqual(plan['selected_numbers'], [])
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob('*') if p.is_file()}
        viewed = org.plan_organize(dict(self.req, selection='查看 1'))
        self.assertEqual(viewed['status'], 'viewed')
        self.assertEqual(viewed['changes'], [])
        self.assertEqual(viewed['approval_plan']['groups'], plan['groups'])
        self.assertEqual({str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob('*') if p.is_file()}, before)

    def test_scope_punctuation_and_exclusive_protection(self):
        self.files[1].write_text('# 不同范围\n- 提交信息使用中文。\n')
        self.files[2].write_text('# 约定\n- 提交信息不使用中文。\n')
        self.assertEqual(self.plan()['default_numbers'],[])
        for p in self.files:
            p.write_text(p.read_text()+'\n## Codex 专属\n- 提交前确认。\n')
        self.assertFalse(any('提交前确认' in i['text'] for i in self.plan()['items']))

    def test_view_decline_read_only_and_approval_binding(self):
        before=[p.read_bytes() for p in self.files]
        p=self.plan(selection='查看 1');self.assertEqual(p['changes'],[])
        self.assertEqual([p.read_bytes() for p in self.files],before)
        self.assertEqual(org.plan_organize(dict(self.req,selection='暂不整理'))['fusion_status'],'declined')
        p=self.plan(); approval=self.approve(p); approval['selected_numbers']=[]
        self.assertEqual(org.execute_organize(p,approval)['errors'][0]['code'],'approval_mismatch')
        self.assertEqual(self.execute(self.plan(selection='查看 1'))['errors'][0]['code'],'view_only')

    def test_complete_copy_before_exact_delete_preserves_protocol_and_unique(self):
        raw=b'<!-- context-keeper:start -->\nprivate\n<!-- context-keeper:end -->\n'
        self.files[0].write_bytes(self.files[0].read_bytes()+raw+'\n- 单家独有。\n'.encode())
        plan=self.plan(); order=[]
        def hook(event,path):
            if event=='before_write' and path in self.files:
                topic=self.mem/'user-rules.md'
                self.assertIn('- 提交信息使用中文。\n',topic.read_text())
            if event=='after_write':order.append(str(path))
        r=self.execute(plan,hook);self.assertEqual(r['status'],'completed',r)
        self.assertEqual(order[0],str(self.mem/'user-rules.md'))
        self.assertEqual(order[1],str(self.mem/'MEMORY.md'))
        self.assertIn(raw,self.files[0].read_bytes());self.assertIn('单家独有',self.files[0].read_text())
        for p in self.files:self.assertNotIn('提交信息使用中文',p.read_text())
        self.assertEqual(self.plan()['changes'],[])

    def test_drift_entry_failure_and_transaction_failure_preserve_sources(self):
        p=self.plan();self.files[0].write_bytes(self.files[0].read_bytes()+b'\n')
        self.assertEqual(self.execute(p)['errors'][0]['code'],'drift')
        before=[p.read_bytes() for p in self.files]
        r=self.execute(self.plan(),readers=False);self.assertEqual(r['status'],'failed',r)
        self.assertEqual([p.read_bytes() for p in self.files],before)
        count=[]
        def fault(event,path):
            if event=='after_write':
                count.append(path)
                if len(count)==3:raise TransactionError('synthetic failure after first delete')
        r=self.execute(self.plan(),fault);self.assertEqual(r['status'],'failed',r)
        self.assertEqual([p.read_bytes() for p in self.files],before)
        self.assertFalse((self.mem/'user-rules.md').exists())

    def test_project_dedup_public_not_optional_and_exclusion_asks_location(self):
        root=self.home/'project';root.mkdir();subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'AGENTS.md').write_text('# 约定\n- 公共项。\n')
        (root/'CLAUDE.md').write_text('@AGENTS.md\n\n# 约定\n- 待选项。\n')
        wb=root/'.workbuddy/memory/MEMORY.md';wb.parent.mkdir(parents=True)
        wb.write_text('<!-- mem-sharing:project-rules:start -->\n读取 AGENTS.md\n<!-- mem-sharing:project-rules:end -->\n\n# 约定\n- 待选项。\n')
        p=self.plan(scope='project',project=str(root))
        self.assertEqual(p['default_numbers'],[1]);self.assertEqual(p['optional_numbers'],[2])
        self.assertTrue(p['groups'][0]['existing_public'])
        r=org.plan_organize(dict(self.req,scope='project',project=str(root),selection='不共享 1'))
        self.assertEqual(r['errors'][0]['code'],'retention_location_required')
        p=self.plan(scope='project',project=str(root),selection='2')
        r=org.execute_organize(p,self.approve(p));self.assertEqual(r['status'],'completed',r)
        self.assertIn('- 待选项。',(root/'AGENTS.md').read_text())
        self.assertNotIn('- 待选项。',(root/'CLAUDE.md').read_text());self.assertIn('@AGENTS.md',(root/'CLAUDE.md').read_text())

    def test_existing_public_exclusion_copies_before_removal(self):
        root=self.home/'project';root.mkdir();subprocess.run(['git','init','-q',str(root)],check=True)
        (root/'AGENTS.md').write_text('# 约定\n- 公共项。\n')
        (root/'CLAUDE.md').write_text('@AGENTS.md\n')
        req=dict(self.req,scope='project',project=str(root),selection='不共享 1',retentions={'1':'CLAUDE.md'})
        result=org.plan_organize(req);self.assertNotEqual(result['status'],'failed',result)
        plan=result['approval_plan'];self.assertEqual(plan['changes'][0]['path'],str(root/'CLAUDE.md'))
        done=org.execute_organize(plan,self.approve(plan));self.assertEqual(done['status'],'completed',done)
        self.assertNotIn('- 公共项。',(root/'AGENTS.md').read_text())
        self.assertIn('- 公共项。',(root/'CLAUDE.md').read_text())

    def test_legacy_decision_cannot_reach_keyword_migration(self):
        r=org.plan_organize(dict(self.req,decisions={'old':{'action':'delete'}}))
        self.assertEqual(r['errors'][0]['code'],'invalid_request')

    def test_crash_reuses_existing_manifest_recovery(self):
        before=[p.read_bytes() for p in self.files]
        def crash(event,path):
            if event=='after_write' and path in self.files:raise TransactionError('synthetic interruption')
            if event=='before_restore':raise TransactionError('synthetic recovery unavailable')
        result=self.execute(self.plan(),crash)
        self.assertEqual(result['status'],'recovery_required',result)
        manifests=list(self.rt.backups.glob('*/manifest.json'))
        self.assertEqual(len(manifests),1)
        with write_lock(self.rt.lock):
            recover_manifest(manifests[0],lock_path=self.rt.transaction_lock,allowed_roots=[self.home,self.rt.root])
        self.assertEqual([p.read_bytes() for p in self.files],before)
        self.assertFalse((self.mem/'user-rules.md').exists())

    def test_cli_routes_selection_and_legacy_alias(self):
        import agm
        for command in ('organize-user-memory','organize-user-rules'):
            out=io.StringIO()
            rc=agm.main([command,'--selection','查看 1'],home=str(self.home),stdout=out,stderr=io.StringIO())
            self.assertEqual(rc,0,out.getvalue());self.assertEqual(json.loads(out.getvalue())['status'],'viewed')
        out=io.StringIO()
        self.assertEqual(agm.main(['organize-user-memory','--decline'],home=str(self.home),stdout=out,stderr=io.StringIO()),0)
        self.assertEqual(json.loads(out.getvalue())['fusion_status'],'declined')

    def test_real_entry_installer_detection_and_reader_gate_in_temporary_home(self):
        from test_m405_user_entries import UserEntryFixture
        f=UserEntryFixture();f.setUp();self.addCleanup(f.doCleanups)
        f.seed_codex_package()
        installed=f.execute(agents=['codex'])
        self.assertEqual(installed['status'],'completed',installed)
        f.memory_index.parent.mkdir(parents=True,exist_ok=True)
        f.memory_index.write_text('# 用户记忆\n')
        source=f.home/'.codex/AGENTS.md'
        source.write_bytes(source.read_bytes()+'\n# 自定义\n- 迁移完整原文。\n'.encode())
        req=f.request(agents=['codex'])
        with patch.object(org,'_participants',REAL_PARTICIPANTS):
            preview=org.plan_organize(req)
            self.assertNotEqual(preview['status'],'failed',preview)
            plan=preview['approval_plan'];self.assertEqual(plan['agents'],['codex'])
            self.assertEqual(plan['default_numbers'],[])
            num=next(g['number'] for g in plan['groups'] if '迁移完整原文' in g['summary'])
            req['selection']=str(num)
            p=org.plan_organize(req)['approval_plan']
            result=org.execute_organize(p,self.approve(p),request=req)
            self.assertEqual(result['status'],'completed',result)
            self.assertNotIn('- 迁移完整原文。',source.read_text())
            self.assertIn('- 迁移完整原文。',(f.runtime.root/'memories/user-rules.md').read_text())

    def test_untrusted_platform_config_rejected_core_and_cli_zero_write(self):
        import agm
        before=[p.read_bytes() for p in self.files]
        config=copy.deepcopy(self.config); config['claude']['project_rule_entry']='{project}/ordinary-notes.txt'
        r=org.plan_organize(dict(self.req,platform_config=config))
        self.assertEqual(r['errors'][0]['code'],'untrusted_platform_config')
        plan=self.plan(); approval=self.approve(plan)
        approval['request']['platform_config']=config
        f=self.home/'forged.json';f.write_text(json.dumps(approval))
        out=io.StringIO()
        self.assertEqual(agm.main(['organize-user-memory','--approval-file',str(f)],home=str(self.home),stdout=out,stderr=io.StringIO()),2)
        self.assertEqual(json.loads(out.getvalue())['errors'][0]['code'],'untrusted_platform_config')
        self.assertEqual([p.read_bytes() for p in self.files],before)

    def test_stage_machine_readable_and_decline(self):
        follow=org.continuation(self.req)
        self.assertEqual(follow['status'],'pending_selection'); self.assertTrue(follow['automatic_continue'])
        self.assertIn('默认共享',follow['preview']['prompt']); self.assertTrue(follow['can_decline'])

if __name__=='__main__':unittest.main()
