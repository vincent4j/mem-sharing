"""Old disabled controls retire only with provenance and exact approval."""
import copy
from pathlib import Path
import test_m204_enable
from test_m204_enable import EnableFixture
from test_uninstall import approval
from agm_core import policy_migration as migration, uninstall_recovery as recovery
from unittest.mock import patch
from agm_core import user_entries
from agm_core import registry, paths, entries
import test_uninstall as fixtures
import unittest


class PolicyMigrationTests(EnableFixture):
    def seed_compatible_runtime(self, home):
        # A generated route must point to a real compatible installed executor,
        # not the old project-only seed_runtime (which has no C at all).
        from test_m404_install import InstallFixture
        from agm_core import plugin_release, legacy_import
        from agm_core.layout import resolve_layout
        f=InstallFixture('runTest');self.addCleanup(f.doCleanups);f.setUp()
        repo=Path(__file__).resolve().parents[2]
        for source in (repo/'scripts').rglob('*'):
            if source.is_file() and source.suffix in ('.py','.json'):
                target=f.source/source.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.read_bytes())
        for rel in plugin_release.SHIPPED_DOCS:
            target=f.source/rel;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((repo/rel).read_bytes())
        f.home=Path(home);f.runtime=resolve_layout(home)
        f.request['home']=str(home)
        f.request['source']['files']={str(p.relative_to(f.source)):legacy_import.digest(p.read_bytes())
            for p in f.source.rglob('*') if p.is_file()}
        f.execute()
        return f.runtime

    def setUp(self):
        with patch.object(test_m204_enable,'seed_runtime',side_effect=self.seed_compatible_runtime):
            super().setUp()
        self.apply()
        # Freeze the historical schema3 denied fixture rather than calling the
        # retired --no-memory API (current enable deliberately never emits it).
        self.entry = self.root/'AGENTS.md'
        denied = (migration.DENIED['start']+'\n本项目已撤销自动记忆授权。\n'+migration.DENIED['end']+'\n').encode()
        self.entry.write_bytes(self.entry.read_bytes()+denied)
        ledger=self.load();record=ledger['projects'][str(self.root)]
        record['memory_policy']='disabled'
        record['checkouts'][str(self.root)]['objects']['historical-denied']={
            'kind':'block','path':str(self.entry),'scope':'project','agents':['codex'],
            'ownership':'created','marker':migration.DENIED,
            'fingerprint':{'algorithm':'sha256','basis':'block_bytes','value':entries.block_fingerprint(denied,**migration.DENIED)},
            'original_existed':False,'link_target':None,'backup_manifest':str(next(self.runtime.backups.glob('*/manifest.json'))),'consumers':[str(self.root)]}
        self.runtime.registry.write_bytes(registry.serialize_registry(ledger,allowed_user_paths=paths.allowed_user_paths(self.config,None,home=str(self.home))))
        self.entry.write_bytes(b'private user limit\r\n'+self.entry.read_bytes()+b'\nprivate tail\xff')
        self.store = self.root/'docs/context-keeper/memory-keeper.md'
        self.store.parent.mkdir(parents=True)
        self.store.write_bytes(b'untouched history\x00')
        (self.runtime.root/'memories/topics').mkdir(parents=True,exist_ok=True)
        (self.runtime.root/'memories/MEMORY.md').write_bytes(b'# public\n'+migration.legacy('contract',self.runtime)+b'\nprivate topic')
        (self.runtime.root/'memories/topics/使用约定.md').write_bytes(migration.legacy('topic',self.runtime))

    def test_preview_zero_write_and_approved_retirement(self):
        before = recovery.tree(self.root)
        plan = migration.preview(home=self.home)
        self.assertEqual(recovery.tree(self.root),before)
        result = migration.execute(approval(migration.view(plan)),home=self.home)
        self.assertEqual(result['status'],'completed')
        self.assertTrue(self.entry.read_bytes().startswith(b'private user limit\r\n'))
        self.assertTrue(self.entry.read_bytes().endswith(b'private tail\xff'))
        self.assertNotIn(b'memory-denied',self.entry.read_bytes())
        self.assertNotIn('重新授权'.encode(),self.entry.read_bytes())
        self.assertEqual(self.store.read_bytes(),b'untouched history\x00')
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')
        again = migration.preview(home=self.home)
        self.assertEqual(again['files'],{})
        self.assertEqual(migration.execute(approval(migration.view(again)),home=self.home)['changes'],[])

    def test_bad_approval_and_drift_stop_without_rewriting(self):
        plan = migration.preview(home=self.home)
        self.entry.write_bytes(self.entry.read_bytes().replace('本项目已撤销'.encode(),'私自修改'.encode()))
        before = self.entry.read_bytes()
        with self.assertRaises(ValueError):
            migration.execute(approval(migration.view(plan)),home=self.home)
        self.assertEqual(self.entry.read_bytes(),before)

    def test_unknown_or_private_ownership_rejected(self):
        ledger = self.load()
        for assembly in ledger['projects'][str(self.root)]['checkouts'].values():
            for obj in assembly['objects'].values():
                if obj.get('marker')==migration.DENIED:obj['ownership']='unknown'
        with self.assertRaises(ValueError):migration.retire_controls(ledger)
        ledger = self.load()
        for assembly in ledger['projects'][str(self.root)]['checkouts'].values():
            assembly['objects']={k:o for k,o in assembly['objects'].items() if o.get('marker')!=migration.DENIED}
        with self.assertRaises(ValueError):migration.retire_controls(ledger)

    def test_generated_public_controls_change_to_current_template(self):
        # The implementation worktree still has old generators. Explicitly
        # substitute a retired-control-free target, never count old→old as proof.
        with patch.object(user_entries,'GOVERNANCE_RULES_TEXT','公共用户记忆共享；Context Keeper 独立管理经历。'), \
             patch.object(user_entries,'usage_convention_topic_text',return_value='# 使用约定\n项目规则接入；经历由 Context Keeper 管理。\n'):
            plan=migration.preview(home=self.home)
            text='\n'.join(bytes.fromhex(raw).decode(errors='replace') for raw in plan['files'].values())
            self.assertNotIn('--no-memory',text)
            self.assertNotIn('remove-memory',text)
            self.assertNotIn('解除 disabled',text)
            migration.execute(approval(migration.view(plan)),home=self.home)
        raw=(self.runtime.root/'memories/MEMORY.md').read_bytes()
        self.assertIn(b'private topic',raw)
        self.assertNotIn('已有 Context Keeper 自动规则也不能覆盖'.encode(),raw)

    def test_explicit_invalid_project_zero_write_and_global_scope_visible(self):
        before=recovery.tree(self.home)
        for project in ('relative',str(self.area/'not-registered'),str(self.root/'..'/'project with spaces')):
            with self.assertRaises(ValueError) as raised:migration.preview(home=self.home,project=project)
            self.assertEqual(raised.exception.code,'invalid_target')
            self.assertEqual(recovery.tree(self.home),before)
        view=migration.view(migration.preview(home=self.home,project=str(self.root)))
        self.assertIn('machine-wide',view['scope'])

    def test_post_approval_transaction_construction_drift_cannot_be_adopted(self):
        for kind in ('content','mode','registry'):
            with self.subTest(kind=kind):
                fixture=PolicyMigrationTests();fixture.setUp()
                try:
                    plan=migration.preview(home=fixture.home)
                    index=fixture.runtime.root/'memories/MEMORY.md';original=index.read_bytes()
                    constructor=migration.Transaction;changed={}
                    def transaction(**kwargs):
                        instance=constructor(**kwargs)
                        target=fixture.runtime.registry if kind=='registry' else fixture.entry
                        if kind=='mode':target.chmod(0o640)
                        else:target.write_bytes(target.read_bytes()+b'\n')
                        changed['path']=target;changed['state']=recovery.snapshot(target)
                        return instance
                    with patch.object(migration,'Transaction',side_effect=transaction):
                        with self.assertRaisesRegex(ValueError,'drift'):
                            migration.execute(approval(migration.view(plan)),home=fixture.home)
                    self.assertEqual(recovery.snapshot(changed['path']),changed['state'])
                    self.assertEqual(index.read_bytes(),original)
                    self.assertFalse(fixture.runtime.lock.exists())
                finally:fixture.doCleanups()


class GeneratedTemplateMigrationTests(unittest.TestCase):
    def test_actual_frozen_old_to_current_six_agent_templates(self):
        from test_natural_uninstall_route import NaturalUninstallRouteTests
        fixture=NaturalUninstallRouteTests();fixture.setUp();fixture.install_agents()
        self.addCleanup(fixture.doCleanups)
        allowed=paths.allowed_user_paths(fixture.config,None,home=str(fixture.home))
        data=registry.load_registry(fixture.runtime.registry,allowed_user_paths=allowed)
        for obj in data['machine']['objects'].values():
            if not obj.get('marker'):continue
            agent=obj['agents'][0]
            name='claude' if obj['marker']==user_entries.CLAUDE_FALLBACK_MARKER else agent
            raw=Path(obj['path']).read_bytes();span=entries.managed_span(raw,**obj['marker'])
            old=migration.legacy(name,fixture.runtime)
            Path(obj['path']).write_bytes(raw[:span[0]]+old+raw[span[1]:])
            obj['fingerprint']['value']=recovery.digest(old)
        for obj in data['machine']['objects'].values():
            if obj['kind']=='import':obj['fingerprint']['value']=recovery.digest(Path(obj['path']).read_bytes())
        fixture.runtime.registry.write_bytes(registry.serialize_registry(data,allowed_user_paths=allowed))
        index=fixture.runtime.root/'memories/MEMORY.md'
        index.write_bytes(b'# public\n'+migration.legacy('contract',fixture.runtime)+b'\nprivate tail\xff')
        topic=fixture.runtime.root/'memories/topics/使用约定.md';topic.parent.mkdir(parents=True,exist_ok=True);topic.write_bytes(migration.legacy('topic',fixture.runtime))
        plan=migration.preview(home=fixture.home)
        self.assertGreaterEqual(len(plan['files']),8)
        migration.execute(fixtures.approval(migration.view(plan)),home=fixture.home)
        for obj in data['machine']['objects'].values():
            text=Path(obj['path']).read_bytes().decode(errors='replace')
            self.assertNotIn('--no-memory',text)
            self.assertNotIn('remove-memory',text)
            self.assertNotIn('已有 Context Keeper 自动规则也不能覆盖',text)
        self.assertIn(user_entries.public_memory_contract_text().encode(),index.read_bytes())
        self.assertTrue(index.read_bytes().endswith(b'private tail\xff'))
        self.assertEqual(topic.read_text(),user_entries.usage_convention_topic_text(fixture.runtime.code))
        self.assertEqual(migration.preview(home=fixture.home)['files'],{})
