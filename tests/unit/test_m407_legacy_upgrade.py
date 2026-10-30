"""M2/M3 migration plus code install share one V-last upgrade boundary."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_m403_migrate import MigrationFixture, OLD_COMMIT, approved
from agm_core import upgrade, registry, legacy_import as legacy, user_install as install


class LegacyUpgradeTests(MigrationFixture):
    def request(self):
        source=self.area/'new-product';(source/'scripts/agm_core').mkdir(parents=True)
        for rel,raw in {'SKILL.md':b'# product\n','scripts/agm.py':b'print("installed")\n','scripts/agm_core/__init__.py':b''}.items():
            (source/rel).write_bytes(raw)
        return {'home':str(self.home),'platform_config':self.config,'operation_id':'m407-legacy',
            'source':{'root':str(source),'url':'fixture://same-development','commit':'c'*40,'version':'0.4.1',
                      'files':{str(p.relative_to(source)):legacy.digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}},
            'legacy_registries':[str(self.old)],'legacy_source_commits':{str(self.old):OLD_COMMIT},
            'evidence_files':[str(self.evidence)]}

    def test_m2_schema1_to_target_commits_code_before_v_and_preserves_authorization(self):
        request=self.request();plan=upgrade.plan_upgrade(request)
        self.assertEqual(plan['conversion']['source_version'],'m2-schema1')
        observed=[]
        def hook(event,path):
            if event=='before_registry_commit':
                self.assertFalse(self.runtime.registry.exists())
                self.assertTrue((self.runtime.code/'SKILL.md').is_file());self.assertTrue(self.old.is_dir())
                observed.append(True)
        result=upgrade.execute_upgrade(plan,approved(plan),request=request,hook=hook)
        self.assertEqual(result['status'],'completed');self.assertTrue(observed)
        data=registry.require_installed(self.load())
        self.assertEqual(data['projects'][str(self.repo)]['memory_authorization'],self.original['projects'][str(self.repo)]['memory_authorization'])
        self.assertEqual(data['product']['product_code_version'],'0.4.1')
        install._code_matches(self.runtime,data['product'])
        self.assertEqual(data['migration']['reference_map'],plan['migration_plan']['reference_map'])
        self.assertEqual(install.inspect_machine(request)['scene'],'same')

    def test_legacy_half_upgrade_can_continue_or_restore_single_old_ledger(self):
        for action in ('continue','rollback'):
            with self.subTest(action=action):
                fixture=LegacyUpgradeTests();fixture.setUp()
                try:
                    request=fixture.request();plan=upgrade.plan_upgrade(request)
                    def hook(event,path):
                        if event=='after_phase:code':raise RuntimeError('fault')
                    with self.assertRaises(RuntimeError):upgrade.execute_upgrade(plan,approved(plan),request=request,hook=hook)
                    recovery=upgrade.plan_recovery(plan['journal'],action=action)
                    result=upgrade.recover_upgrade(recovery,approved(recovery))
                    if action=='continue':
                        self.assertEqual(result['status'],'completed');self.assertTrue(fixture.old.is_dir())
                        registry.require_installed(fixture.load())
                    else:
                        self.assertEqual(result['status'],'rolled_back');self.assertTrue(fixture.old.is_file())
                        self.assertEqual(fixture.old.read_bytes(),fixture.before_raw)
                        self.assertFalse(fixture.runtime.registry.exists());self.assertFalse(fixture.runtime.code.exists())
                finally:fixture.doCleanups()
