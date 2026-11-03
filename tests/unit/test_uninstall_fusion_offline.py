"""Pinned old fusion -> old uninstall -> entirely offline correction, synthetic only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_uninstall_fusion_generated import FusionReturnTests
from test_m404_install import InstallFixture
from test_uninstall import approval
from agm_core import legacy_import as legacy, uninstall, uninstall_recovery as recovery
from agm_core import uninstall_fusion_repair as offline

REPO=Path(__file__).resolve().parents[2]


class OfflineFusionTests(unittest.TestCase):
    def setUp(self):
        f=FusionReturnTests();self.addCleanup(f.doCleanups);self.fixture=f
        original_execute=InstallFixture.execute
        old_code=subprocess.check_output(['git','-C',str(REPO),'show','HEAD:scripts/agm_core/uninstall_memory.py'])
        self.assertNotIn(b'def fusion_generated_units',old_code)
        def pinned_execute(inner,*args,**kwargs):
            (inner.source/'scripts/agm_core/uninstall_memory.py').write_bytes(old_code)
            original_org=inner.source/'scripts/agm_core/user_rules_organize.py'
            original_org.write_bytes(original_org.read_bytes()+b'\n# Original presentation revision; not a replay dependency.\n')
            def git(*args):
                return subprocess.check_output(['git','-C',str(inner.source),*args],env=dict(os.environ,HOME='/nonexistent',GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1'),stderr=subprocess.PIPE).decode().strip()
            git('init','-q');git('add','.')
            git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','old synthetic producer')
            self.pin=git('rev-parse','HEAD');self.repo=inner.source
            inner.request['source']['commit']=self.pin
            inner.request['source']['files']['scripts/agm_core/uninstall_memory.py']=legacy.digest(old_code)
            inner.request['source']['files']['scripts/agm_core/user_rules_organize.py']=legacy.digest(original_org.read_bytes())
            return original_execute(inner,*args,**kwargs)
        with patch.object(InstallFixture,'execute',new=pinned_execute):f.setUp()
        old=types.ModuleType('agm_core._test_original_memory');old.__package__='agm_core'
        exec(compile(old_code,'<old pinned fixture>','exec'),old.__dict__)
        self.backup=f.f.area/'external-old-uninstall'
        with patch.object(uninstall,'uninstall_memory',old):
            plan=uninstall.preview(home=f.f.home,backup_dir=self.backup)
            result=uninstall.execute(approval(recovery.summary(plan)),home=f.f.home,backup_dir=self.backup)
        self.assertEqual(result['status'],'completed')
        self.manifest=self.backup/'manifest.json'
        self.digest=recovery.digest(self.manifest.read_bytes())
        self.home=f.f.home
        self.before={str(p):p.read_bytes() for p,_ in f.private.values()}
        self.assertTrue(all('以下记忆经完整清单确认后共享'.encode() in v for v in self.before.values()))

    def invoke(self):
        return offline.plan_repair(self.manifest,manifest_sha256=self.digest,source_repo=self.repo,source_commit=self.pin)

    def test_old_producer_offline_plan_six_files_no_home_reads_or_writes(self):
        active=[True];events=[]
        def audit(event,args):
            if not active[0] or event not in ('open','os.scandir','os.listdir'):return
            if not args or not isinstance(args[0],(str,bytes,os.PathLike)):return
            path=Path(os.fsdecode(args[0]))
            if path.is_absolute() and path.is_relative_to(self.home):
                events.append(event);raise AssertionError('offline tool accessed original HOME')
        sys.addaudithook(audit)
        try:result=self.invoke()
        finally:active[0]=False
        self.assertEqual(events,[]);self.assertEqual(result['status'],'plan_only')
        self.assertFalse(result['execution_supported']);self.assertEqual(len(result['changes']),6)
        for row in result['changes']:
            self.assertEqual(bytes.fromhex(row['before']['hex']),self.before[row['path']])
            corrected=bytes.fromhex(row['after']['hex'])
            self.assertIn(self.fixture.common,corrected);self.assertIn(self.fixture.ck,corrected)
            self.assertNotIn('以下记忆经完整清单确认后共享'.encode(),corrected)
            self.assertNotIn('- 用户记忆：user-rules.md'.encode(),corrected)
            self.assertEqual(row['before']['mode'],row['after']['mode'])
        self.assertEqual({str(p):p.read_bytes() for p,_ in self.fixture.private.values()},self.before)
        output=self.backup.parent/'private-repair-plan.json'
        process=subprocess.run([sys.executable,'-B',str(REPO/'scripts/plan_fusion_return_repair.py'),
            '--manifest',str(self.manifest),'--manifest-sha256',self.digest,'--source-repo',str(self.repo),
            '--source-commit',self.pin,'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr+process.stdout)
        summary=json.loads(process.stdout);self.assertEqual(summary['changes'],6)
        self.assertNotIn('完整用户原文',process.stdout);self.assertEqual(output.stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads(output.read_bytes())['plan_sha256'],result['plan_sha256'])

    def test_manifest_or_source_pin_mismatch_rejects(self):
        with self.assertRaises(ValueError):offline.plan_repair(self.manifest,manifest_sha256='0'*64,source_repo=self.repo,source_commit=self.pin)
        with self.assertRaises(ValueError):offline.plan_repair(self.manifest,manifest_sha256=self.digest,source_repo=self.repo,source_commit='f'*40)
        original=json.loads(self.manifest.read_bytes())
        def rewrite(envelope):
            recovery.seal(envelope['plan']);envelope['approval']['plan']=recovery.summary(envelope['plan'])
            self.manifest.write_text(json.dumps(envelope));self.digest=recovery.digest(self.manifest.read_bytes())
        # A re-sealed snapshot still needs the exact pinned C and transaction before bytes.
        for fault in ('code','transaction-backup','after'):
            with self.subTest(fault=fault):
                envelope=copy.deepcopy(original);plan=envelope['plan']
                if fault=='code':
                    row=next(c for c in plan['changes'] if c['path'].endswith('/scripts/agm_core/user_entries.py'))
                    row['before']['hex']+=b'foreign code'.hex()
                elif fault=='transaction-backup':
                    row=next(c for c in plan['changes'] if '/backups/' in c['path'] and c['path'].endswith('.before'))
                    row['before']['hex']+=b'foreign backup'.hex()
                else:
                    row=next(c for c in plan['changes'] if c['stage']=='detach' and c['after']['kind']=='file')
                    row['after']['hex']+=b'foreign modified output'.hex()
                rewrite(envelope)
                with self.assertRaises(ValueError):self.invoke()

class OfflineDeletionTraceTests(unittest.TestCase):
    def test_existing_final_user_paragraph_is_never_duplicated(self):
        from agm_core import uninstall_memory as memory
        native=b'Private\n\n## L2 '+ '原文与来源'.encode()+b'\nUSER LAST\n\nNative tail\n'
        label=b'- generated topic\n'
        body=label+memory.FUSION_GENERATED_PREFIX+b'USER LAST\n\nUSER FIRST\n'
        reproduced=memory.merge_native(native,body)
        spans=[(0,len(label)),(len(label),len(label)+len(memory.FUSION_GENERATED_PREFIX))]
        corrected=offline._delete_proven_additions(memory,native,body,reproduced,spans)
        self.assertEqual(reproduced.count(b'USER LAST'),1)
        self.assertEqual(corrected.count(b'USER LAST'),1)
        # The rejected new-merge strategy changes the leading paragraph and duplicates it.
        bad=memory.merge_native(native,b'USER LAST\n\nUSER FIRST\n')
        self.assertEqual(bad.count(b'USER LAST'),2)
        self.assertTrue(corrected.startswith(native))
        self.assertNotIn(memory.FUSION_GENERATED_PREFIX,corrected)

if __name__=='__main__':unittest.main()
