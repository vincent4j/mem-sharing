"""Selected native Skill distribution and six-source dedup; isolated HOME only."""
import json
from pathlib import Path
from unittest.mock import patch
from test_m404_install import InstallFixture, approved
from test_m408_installer import cli
from runtime_fixture import seed_project_executors
from agm_core import detect, paths, user_rules_organize as fusion, memory_share as share
from agm_core import uninstall, uninstall_recovery as recovery
from test_uninstall import approval


class InstallCleanupTests(InstallFixture):
    def tree(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def test_monday_codex_wednesday_claude_and_repeat(self):
        self.request.update(seed_project_executors(self.home))
        self.request['agents'] = ['codex']
        first = cli.plan_machine(self.request)
        self.assertEqual(cli.execute_machine(first, approved(first), request=self.request)['status'], 'completed')
        codex_skill = self.home/'.codex/skills/mem-sharing/SKILL.md'
        claude_skill = self.home/'.claude/skills/mem-sharing/SKILL.md'
        self.assertTrue(codex_skill.is_file()); self.assertFalse(claude_skill.exists())
        claude = self.home/'.claude/CLAUDE.md'
        claude.parent.mkdir(exist_ok=True)
        private = '# 约定\n\n- 新的共享偏好。\n\nClaude 专属内容保留。\n'
        claude.write_text(private)
        before = self.tree(self.runtime.root/'memories')
        self.request['agents'] = ['claude']
        plan = cli.plan_machine(self.request)
        self.assertTrue(plan['plan']['noop'])
        done = cli.execute_machine(plan, approved(plan), request=self.request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(self.tree(self.runtime.root/'memories'), before)
        self.assertTrue(claude_skill.is_file())
        for p in (codex_skill, claude_skill):
            self.assertIn('name: mem-sharing', p.read_text())
            self.assertIn(str(self.runtime.code/'SKILL.md'), p.read_text())
            self.assertNotIn(str(self.source), p.read_text())
        self.assertIn(private, claude.read_text())
        self.assertEqual(done['fusion']['status'], 'pending_selection')
        all_before = self.tree(self.home)
        again = cli.plan_machine(self.request)
        result = cli.execute_machine(again, approved(again), request=self.request)
        self.assertEqual(result['message'], '已安装，已接入。')
        self.assertIsNone(result['fusion']);self.assertEqual(result['changes'], [])
        self.assertEqual(self.tree(self.home), all_before)
        # User-owned native Skill conflicts fail closed, never adopted by filename.
        claude_skill.write_text('user custom')
        with self.assertRaises(ValueError): cli.plan_machine(self.request)
        self.assertEqual(claude_skill.read_text(), 'user custom')

    def test_six_identical_sources_incremental_and_exact_return(self):
        original = {}
        common = '- 相同用户规则。\n'
        for agent, cfg in self.config.items():
            p=Path(paths.expand_path(cfg['user_entry'],home=str(self.home)))
            p.parent.mkdir(parents=True,exist_ok=True)
            original[agent]=(p, '# 约定\n\n'+common+common+'\n'+agent+' 专属正文。\n')
            p.write_text(original[agent][1])
        real=detect.detect_agents
        def installed(*args, **kwargs):
            data=real(*args, **kwargs)
            for row in data['agents'].values(): row['status']='installed'
            return data
        with patch.object(detect,'detect_agents',side_effect=installed):
            self.execute()
            req={k:v for k,v in self.request.items() if k in ('home','platform_config','agents','search_paths','app_directories')}
            plan=fusion.plan_organize(req)['approval_plan']
            done=fusion.execute_organize(plan,approved(plan),request=req)
            self.assertEqual(done['status'],'completed',done)
            topic=self.runtime.root/'memories/user-rules.md'
            self.assertEqual(topic.read_text().count(common),1)
            records=json.loads(Path(done['manifest']).read_text())['operation_metadata']['share_user_memory']['migrations']
            self.assertEqual(len(records),12)
            self.assertEqual(len({r['public_offset'] for r in records}),1)
            for r in records:
                self.assertEqual(topic.read_bytes()[r['public_offset']:r['public_end']],bytes.fromhex(r['text_hex']))
            # New source copy of an already shared rule is removed only after exact approval; public bytes stay unchanged.
            native=original['codex'][0];native.write_bytes(native.read_bytes()+common.encode())
            before=topic.read_bytes()
            inc=fusion.plan_organize(dict(req,agents=['codex']))['approval_plan']
            self.assertEqual(len(inc['selected_numbers']),1, inc['groups'])
            migrated=fusion.execute_organize(inc,approved(inc),request=dict(req,agents=['codex']))
            self.assertEqual(migrated['status'],'completed',migrated)
            self.assertEqual(topic.read_bytes(),before)
            # Existing native return consumer accepts every source reference, including duplicate positions.
            available=share._available_migrations(self.runtime)
            self.assertEqual(len(available),13)
            items=[]
            for (ref,position),r in available.items():
                items.append({'ref':ref,'migration':position,
                    'public_span':{'start':r['public_offset'],'end':r['public_end'],'text_hex':r['text_hex']},
                    'target':{'path':r['path'],'mode':'insert_at','insert_at':len(Path(r['path']).read_bytes())}})
            rp={'schema_version':1,'basis':{str(topic):share.entries.sha256(topic.read_bytes())},'items':items}
            return_req=dict(req, agents=list(self.config))
            preview=share.run_return(dict(return_req,return_plan=rp))
            self.assertEqual(preview['status'],'approval_required',preview)
            before_return=self.tree(self.home)
            def fail_registry(event,path):
                if event=='before_write' and path==self.runtime.registry:
                    raise share.TransactionError('synthetic registry failure')
            failed=share.run_return(dict(return_req,return_plan=rp,approval=approved(preview['approval_plan']),hook=fail_registry))
            self.assertEqual(failed['status'],'failed',failed)
            for path,(raw,_) in before_return.items():
                self.assertEqual((self.home/path).read_bytes(),raw)
            def break_restore(event,path):
                if (event=='before_write' and path==self.runtime.registry) or event=='before_restore':
                    raise share.TransactionError('synthetic recovery interruption')
            broken=share.run_return(dict(return_req,return_plan=rp,approval=approved(preview['approval_plan']),hook=break_restore))
            self.assertEqual(broken['status'],'recovery_required',broken)
            recovery_request={'home':str(self.home),'manifest':broken['errors'][0]['manifest']}
            recovery_preview=share.run_recover(recovery_request)
            self.assertEqual(recovery_preview['status'],'approval_required',recovery_preview)
            recovered=share.run_recover(dict(recovery_request,approval=approved(recovery_preview['approval_plan'])))
            self.assertEqual(recovered['status'],'completed',recovered)
            returned=share.run_return(dict(return_req,return_plan=rp,approval=approved(preview['approval_plan'])))
            self.assertEqual(returned['status'],'completed',returned)
            for agent,(p,_) in original.items():
                self.assertEqual(p.read_text().count(common),3 if agent=='codex' else 2)
            # The legal V rebinding makes a later global uninstall usable too.
            backup=self.area/'after-exact-return'
            up=uninstall.preview(home=self.home,backup_dir=backup)
            self.assertEqual(uninstall.execute(approval(recovery.summary(up)),home=self.home,backup_dir=backup)['status'],'completed')


    def test_scope_siblings_and_duplicate_heading_context(self):
        from agm_core.memory_share import _heading_context
        raw=b'# A\n## X\nfirst\n## Y\nsecond\n## X\nthird\n'
        titles,ctx=_heading_context(raw,raw.index(b'second'),[])
        self.assertEqual(titles,['A','Y'])
        self.assertEqual(_heading_context(raw,raw.index(b'third'),[])[0],['A','X'])
        self.assertNotEqual(_heading_context(raw,raw.index(b'first'),[])[1],_heading_context(raw,raw.index(b'third'),[])[1])

    def test_direct_fused_uninstall_preserves_source_counts_then_fresh(self):
        self.request.update(seed_project_executors(self.home))
        self.request['agents']=['codex','claude']
        common='- 同一原文。\n'
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md')]:
            p=self.home/('.'+agent)/name;p.parent.mkdir(exist_ok=True)
            p.write_text('# 规则\n\n'+common+common+'\n'+agent+' 私有原文。\n')
        self.execute()
        self.assertFalse((self.runtime.root/'memories/topics/使用约定.md').exists())
        self.assertNotIn('user-rules.md](', (self.runtime.root/'memories/MEMORY.md').read_text())
        req={k:v for k,v in self.request.items() if k in ('home','platform_config','agents','search_paths','app_directories','detect_runner')}
        fp=fusion.plan_organize(req)['approval_plan']
        self.assertEqual(fusion.execute_organize(fp,approved(fp),request=req)['status'],'completed')
        self.assertEqual((self.runtime.root/'memories/user-rules.md').read_text().count(common),1)
        # Refuse private drift without editing it; the same plan then succeeds after exact restoration.
        codex=self.home/'.codex/AGENTS.md';saved=codex.read_bytes()
        codex.write_bytes(b'private changed prefix\n'+saved)
        before=self.tree(self.home)
        with self.assertRaisesRegex(ValueError,'Native source drift'):
            uninstall.preview(home=self.home,backup_dir=self.area/'drift-backup')
        self.assertEqual(self.tree(self.home),before)
        codex.write_bytes(saved)
        backup=self.area/'external-backup'
        up=uninstall.preview(home=self.home,backup_dir=backup)
        result=uninstall.execute(approval(recovery.summary(up)),home=self.home,backup_dir=backup)
        self.assertEqual(result['status'],'completed',result)
        for agent,name in [('codex','AGENTS.md'),('claude','CLAUDE.md')]:
            self.assertFalse((self.home/('.'+agent)/'skills/mem-sharing/SKILL.md').exists())
            body=(self.home/('.'+agent)/name).read_text()
            self.assertIn(agent+' 私有原文。',body)
            self.assertEqual(body.count(common),2)
        self.request['operation_id']='fresh-after-uninstall'
        fresh=self.plan();self.assertEqual(fresh['channel'],'fresh')
        self.assertEqual(self.execute(fresh)['status'],'completed')

    def test_new_claude_incremental_reuses_public_and_global_uninstall(self):
        self.request.update(seed_project_executors(self.home))
        self.request['agents']=['codex']
        common='- 已有公共偏好。\n';new='- 新增获准偏好。\n'
        codex=self.home/'.codex/AGENTS.md';codex.parent.mkdir(exist_ok=True)
        codex.write_text('# 约定\n\n'+common+'\ncodex 专属保留。\n')
        self.execute()
        req={k:v for k,v in self.request.items() if k in ('home','platform_config','agents','search_paths','app_directories','detect_runner')}
        preview=fusion.plan_organize(req)['approval_plan']
        number=next(g['number'] for g in preview['groups'] if g['summary']==common.strip())
        req['selection']='共享 '+str(number)
        plan=fusion.plan_organize(req)['approval_plan']
        self.assertEqual(fusion.execute_organize(plan,approved(plan),request=req)['status'],'completed')
        topic=self.runtime.root/'memories/user-rules.md'
        claude=self.home/'.claude/CLAUDE.md';claude.parent.mkdir(exist_ok=True)
        claude.write_text('# 约定\n\n'+common+new+'\nclaude 专属保留。\n')
        self.request['agents']=['claude']
        before=self.tree(self.runtime.root/'memories')
        install=cli.plan_machine(self.request)
        done=cli.execute_machine(install,approved(install),request=self.request)
        self.assertEqual(done['status'],'completed',done)
        self.assertEqual(self.tree(self.runtime.root/'memories'),before)
        req=dict(req,agents=['claude']);req.pop('selection',None)
        plan=fusion.plan_organize(req)['approval_plan']
        self.assertTrue(plan['default_numbers'])
        number=next(g['number'] for g in plan['groups'] if g['summary']==new.strip())
        req['selection']='共享 '+str(number)
        plan=fusion.plan_organize(req)['approval_plan']
        self.assertEqual(fusion.execute_organize(plan,approved(plan),request=req)['status'],'completed')
        self.assertEqual(topic.read_text().count(common),1)
        self.assertEqual(topic.read_text().count(new),1)
        self.assertIn('claude 专属保留。',claude.read_text())
        repeat=cli.plan_machine(self.request)
        self.assertEqual(repeat['changes'],[])
        self.assertIsNone(cli.execute_machine(repeat,approved(repeat),request=self.request)['fusion'])
        backup=self.area/'incremental-global-uninstall'
        plan=uninstall.preview(home=self.home,backup_dir=backup)
        result=uninstall.execute(approval(recovery.summary(plan)),home=self.home,backup_dir=backup)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(codex.read_text().count(common),1)
        self.assertEqual(claude.read_text().count(common),1)
        self.assertEqual(claude.read_text().count(new),1)
        for agent in ('codex','claude'):
            self.assertFalse((self.home/('.'+agent)/'skills/mem-sharing/SKILL.md').exists())
