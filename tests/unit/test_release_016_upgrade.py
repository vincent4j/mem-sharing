"""Fixed .5 producer -> unissued .6 fixture; entirely synthetic HOME.

No moving HEAD predecessor: immutable R/S and actual historical installers.
The approved .6 source commit/tree will only exist after root freezes S.
"""
import copy
import importlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import test_legacy_import_reconcile as historical
approval, snapshot = historical.approval, historical.snapshot
from test_public_layout import _export_target
from test_release_014_upgrade import _export, _load_old_kernel, PREDECESSOR_014
from test_m404_install import approved
from agm_core import upgrade, user_install, policy_migration, legacy_reconcile, versions

R015 = '417e1637e7ff172eb5651cd0cdd360559341b8db'
S015 = '542f248f35e9de8fb2e7566b6312e6f13d26cd41'
TREE015 = '023bbaa275cd1290450ee7ac707f0b58d341d3e6064a09a6c24bfd6245f0d2e5'


class HistoryReady(Exception):
    pass


class Release016Tests(unittest.TestCase):
    def setUp(self):
        # Stop only the existing TEST fixture's later synthetic-C staging;
        # its actual .1.2 installer + ea553738 .1.3 producer run unchanged.
        self.seed = historical.ReconcileTests('test_real_producer_chain_preview_execute_policy_and_noop')
        self.addCleanup(self.seed.doCleanups)
        with patch('test_legacy_import_reconcile._export_target', side_effect=HistoryReady):
            with self.assertRaises(HistoryReady):
                self.seed.setUp()
        self.home, self.runtime, self.area = self.seed.home, self.seed.runtime, self.seed.area
        self.baseline = self.seed.path.read_bytes()
        root14=self.area/'fixed014';files14=_export(root14,PREDECESSOR_014['commit'])
        source14=dict(root=str(root14),url=PREDECESSOR_014['url'],commit=PREDECESSOR_014['commit'],version='0.1.4',files=files14)
        module14=importlib.import_module(_load_old_kernel(root14)+'.upgrade')
        self.apply(module14,source14,'history-to-014','preserve')
        repo=Path(__file__).resolve().parents[2]
        manifest=json.loads(subprocess.check_output(['git','show',R015+':release/core-release.json'],cwd=repo))
        self.assertEqual(manifest['source']['commit'],S015)
        self.assertEqual(manifest['source']['tree_sha256'],TREE015)
        root15=self.area/'fixed015';files15=_export(root15,S015)
        self.source15=dict(root=str(root15),url=manifest['source']['url'],commit=S015,version='0.1.5',files=files15)
        checked,_=user_install._source({'source':self.source15})
        self.assertEqual(checked['tree_sha256'],TREE015)
        self.assertEqual(len(files15),35)
        module15=importlib.import_module(_load_old_kernel(root15)+'.upgrade')
        self.apply(module15,self.source15,'fixed-to-015',module15.NATIVE_ENTRY_CONVERSION)
        self.assertEqual(self.product()['source'],{k:manifest['source'][k] for k in ('url','commit','tree_sha256')})
        self.assertEqual(self.seed.path.read_bytes(),self.baseline)
        # Existing independent CK-only drift is already present on .5.
        self.seed.path.write_bytes(self.baseline.replace(self.seed.ckold,self.seed.cknew))
        self.entry_before=self.seed.path.read_bytes()
        config=policy_migration.config()
        from agm_core import paths
        names=paths.allowed_user_paths(config,None,home=str(self.home))+[str(self.runtime.root/'memories/MEMORY.md'),str(self.runtime.root/'memories/topics/使用约定.md')]
        self.entry_set={name:(Path(name).read_bytes(),Path(name).stat().st_mode) if Path(name).is_file() else None for name in names}
        ledger=json.loads(self.runtime.registry.read_bytes())
        self.object_set=copy.deepcopy((ledger['machine']['objects'],ledger['shared_objects']))
        from frozen_kernel_fixture import export, bind, FROZEN_016
        target=self.area/'candidate016';files16=export(target,FROZEN_016)
        bind(self, globals(), target)
        self.source16=dict(root=str(target),url='fixture://unissued-016',commit='6'*40,
                           version='0.1.6',files=files16)
        for name in ('scripts/agents.json','scripts/agm_core/user_entries.py'):
            self.assertEqual(files15[name],files16[name])
        self.req=self.request(self.source16,'candidate-to-016','preserve')

    def assert_entries_preserved(self):
        actual={name:(Path(name).read_bytes(),Path(name).stat().st_mode) if Path(name).is_file() else None for name in self.entry_set}
        self.assertEqual(actual,self.entry_set)
        ledger=json.loads(self.runtime.registry.read_bytes())
        self.assertEqual((ledger['machine']['objects'],ledger['shared_objects']),self.object_set)

    def product(self):
        return json.loads(self.runtime.registry.read_bytes())['product']

    def request(self,source,op,entries,direction='upgrade'):
        checked,_=user_install._source({'source':source})
        before=self.product()
        conversion=dict(before=dict(schema_version=3,product_structure_version=1,
                            product_code_version=before['product_code_version'],source=before['source']),
                        after=dict(schema_version=3,product_structure_version=1,
                            product_code_version=checked['version'],source={k:checked[k] for k in ('url','commit','tree_sha256')}),
                        direction=direction,entries=entries)
        return dict(home=str(self.home),platform_config=policy_migration.config(),agents=None,source=source,operation_id=op,direction=direction,
                    conversions=[conversion],search_paths=[str(self.seed.bin)],app_directories=[])

    def apply(self,module,source,op,entries):
        req=self.request(source,op,entries)
        req['platform_config']=module.paths.select_platform(module.paths.load_agents_table(Path(module.__file__).parent.parent/'agents.json'),'darwin')
        plan=module.plan_upgrade(req)
        done=module.execute_upgrade(plan,approved(plan),request=req)
        self.assertEqual(done['status'],'completed')
        return plan,done

    def test_fixed_015_preserve_upgrade_inventory_rollback_and_reconcile(self):
        before=snapshot(self.home);plan=upgrade.plan_upgrade(self.req)
        self.assertEqual(before,snapshot(self.home))
        self.assertEqual(plan['conversion']['entries'],'preserve')
        done=upgrade.execute_upgrade(plan,approved(plan),request=self.req)
        self.assertEqual(done['status'],'completed')
        self.assertEqual(self.product()['product_code_version'],'0.1.6')
        self.assertEqual(self.seed.path.read_bytes(),self.entry_before)
        self.assert_entries_preserved()
        user_install._code_matches(self.runtime,self.product())
        for item in (plan['before_inventory'],plan['target_inventory']):versions.verify(self.runtime,item)
        reverse=self.request(self.source15,'rollback-to-fixed015','preserve','rollback')
        reverse['rollback_target']=dict(version='0.1.5',tree_sha256=TREE015);reverse.pop('source')
        back=upgrade.plan_upgrade(reverse)
        self.assertEqual(upgrade.execute_upgrade(back,approved(back),request=reverse)['status'],'completed')
        self.assertEqual(self.product()['source']['commit'],S015)
        self.assertEqual(self.seed.path.read_bytes(),self.entry_before)
        self.assert_entries_preserved()
        self.apply(upgrade,self.source16,'forward-again-016','preserve')
        self.assert_entries_preserved()
        with self.assertRaisesRegex(ValueError,'Native import baseline drift'):
            policy_migration.preview(home=self.home)
        reconcile=legacy_reconcile.preview(home=self.home)
        self.assertEqual(legacy_reconcile.execute(approval(reconcile),home=self.home)['status'],'completed')
        self.assertIn(self.seed.cknew,self.seed.path.read_bytes())
        self.assertIn(self.seed.private,self.seed.path.read_bytes())
        self.assertTrue(legacy_reconcile.preview(home=self.home)['noop'])
        policy_migration.preview(home=self.home)  # no policy execution

    def test_missing_wrong_source_same_version_and_contract_drift_rejected(self):
        before=snapshot(self.home)
        missing=copy.deepcopy(self.req);missing['conversions']=[]
        wrong=copy.deepcopy(self.req);wrong['conversions'][0]['before']['source']['commit']='0'*40
        same=copy.deepcopy(self.req);same['source']['version']='0.1.5';same['conversions'][0]['after']['product_code_version']='0.1.5'
        for request in (missing,wrong,same):
            with self.assertRaises(ValueError):upgrade.plan_upgrade(request)
            self.assertEqual(before,snapshot(self.home))
        changed=copy.deepcopy(self.req);file=Path(changed['source']['root'])/'scripts/agm_core/user_entries.py'
        file.write_bytes(file.read_bytes()+b'\n# altered entry contract\n')
        from agm_core import legacy_import as legacy
        changed['source']['files']['scripts/agm_core/user_entries.py']=legacy.digest(file.read_bytes())
        checked,_=user_install._source(changed)
        changed['conversions'][0]['after']['source']['tree_sha256']=checked['tree_sha256']
        with self.assertRaisesRegex(ValueError,'no handler'):
            upgrade.plan_upgrade(changed)
        self.assertEqual(before,snapshot(self.home))
