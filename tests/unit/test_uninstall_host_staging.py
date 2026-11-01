"""Synthetic host receipt acceptance; no real host cleanup or private HOME."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

import test_uninstall as fixtures
from agm_core import uninstall,uninstall_recovery as recovery


class HostStagingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.UninstallTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.home=self.fixture.home;self.area=self.fixture.area
        self.root=self.fixture.runtime.code.parent/'mem-sharing-plugin-staging';self.root.mkdir(mode=0o700)
        self.external=self.area/'host-evidence';self.external.mkdir(mode=0o700)
        self.operation=self.external/'op-ABC';self.operation.mkdir(mode=0o700)
        self.stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        self.document={'id':'synthetic-op','flow':'enable','phase':'preview','journal':None,
                       'home':str(self.home),'host':socket.gethostname(),'state':'completed','started_at':self.stamp}
        self.write(self.operation/'operation.json',self.document)
        self.row={'dir':'op-ABC','record_state':'completed','in_memory_running':False,'journal_status':None,
                  'artifacts':[{'name':'operation.json','sha256':recovery.digest((self.operation/'operation.json').read_bytes())}]}
        self.receipt={'schema_version':1,'product_id':'mem-sharing','kind':'host-staging-retired',
                      'home':str(self.home),'host':socket.gethostname(),'staging_root':str(self.root),
                      'backup_root':str(self.external),'backup_tree_sha256':uninstall._runtime_digest(self.external),
                      'generated_at':self.stamp,'status':'completed',
                      'approval':{'digest':'a'*64,'confirmed_at':self.stamp,'reference':'separate synthetic host cleanup approval'},
                      'terminal_evidence':[self.row]}
        self.write(self.root/'host-receipt.json',self.receipt)

    def write(self,path,value):
        path.write_bytes(recovery.encoded(value));path.chmod(0o600)

    def save_receipt(self):self.write(self.root/'host-receipt.json',self.receipt)

    def plan(self):return uninstall.preview(home=self.home,backup_dir=self.fixture.backup)

    def test_exact_receipt_preview_and_removal_preserve_external_evidence(self):
        before=recovery.tree(self.home);external=recovery.tree(self.external)
        plan=self.plan()
        self.assertEqual(recovery.tree(self.home),before)
        self.assertEqual(plan['observation_trees'],[str(self.external)])
        changes=[c['path'] for c in plan['changes'] if Path(c['path']).is_relative_to(self.root)]
        self.assertEqual(set(changes),{str(self.root),str(self.root/'host-receipt.json')})
        self.assertFalse(any(Path(c['path']).is_relative_to(self.external) for c in plan['changes']))
        result=uninstall.execute(fixtures.approval(recovery.summary(plan)),home=self.home,backup_dir=self.fixture.backup)
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.root.exists())
        self.assertEqual(recovery.tree(self.external),external)

    def test_hash_unknown_children_activity_and_duplicate_keys_rejected_zero_write(self):
        baseline=self.receipt.copy()
        for update in ({'backup_tree_sha256':'0'*64},{'status':'running'},{'schema_version':True},
                       {'host':'another-host'},{'backup_root':str(self.fixture.runtime.root)}):
            with self.subTest(update=update):
                self.receipt=dict(baseline,**update);self.save_receipt();before=recovery.tree(self.home)
                with self.assertRaises(ValueError):self.plan()
                self.assertEqual(recovery.tree(self.home),before)
        self.receipt=baseline;self.row['in_memory_running']=True;self.save_receipt()
        with self.assertRaises(ValueError):self.plan()
        self.row['in_memory_running']=False;self.save_receipt()
        extra=self.external/'unexpected-private';extra.write_bytes(b'unknown artifact must not be adopted')
        with self.assertRaises(ValueError):self.plan()
        extra.unlink()
        marker=self.root/'host-receipt.json'
        marker.write_bytes(marker.read_bytes().replace(b'"schema_version": 1',b'"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(ValueError):self.plan()
        self.assertFalse(self.fixture.backup.exists())

    def test_terminal_operation_seven_key_compatibility_and_running_rejection(self):
        self.document.pop('journal');self.write(self.operation/'operation.json',self.document)
        self.row['artifacts'][0]['sha256']=recovery.digest((self.operation/'operation.json').read_bytes())
        self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external);self.save_receipt()
        self.plan()
        self.document['state']='running';self.row['record_state']='running'
        self.write(self.operation/'operation.json',self.document)
        self.row['artifacts'][0]['sha256']=recovery.digest((self.operation/'operation.json').read_bytes())
        self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external);self.save_receipt()
        with self.assertRaises(ValueError):self.plan()

    def test_original_running_record_recovers_only_from_verified_original_journal(self):
        # Use the actual kernel install journal produced by fixture installation.
        journal=next(self.home.glob('.mem-sharing-install-*/journal.json'))
        original=json.loads(journal.read_text())
        self.document.update(state='running',flow='machine',journal=str(journal))
        self.write(self.operation/'operation.json',self.document)
        self.row['artifacts'][0]['sha256']=recovery.digest((self.operation/'operation.json').read_bytes())
        self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external)
        self.row.update(record_state='recovered',journal_status='committed');self.save_receipt()
        for status in ('committed','rolled_back'):
            with self.subTest(status=status):
                current=dict(original,status=status);self.write(journal,current)
                self.row['journal_status']=status;self.save_receipt()
                before=recovery.tree(self.home)
                _,observed=uninstall._host_staging_receipt(self.fixture.runtime,self.root,self.fixture.backup)
                self.assertEqual(observed[str(journal)],recovery.snapshot(journal))
                self.assertEqual(recovery.tree(self.home),before)
                self.assertEqual(json.loads((self.operation/'operation.json').read_text())['state'],'running')
        for document,status in ((dict(original,status='prepare'),'committed'),
                                (dict(original,status='committed'),'rolled_back'),
                                (dict(original,status='unknown'),'committed')):
            with self.subTest(document_status=document['status'],claim=status):
                self.write(journal,document);self.row['journal_status']=status;self.save_receipt()
                before=recovery.tree(self.home)
                with self.assertRaises(ValueError):uninstall._host_staging_receipt(self.fixture.runtime,self.root,self.fixture.backup)
                self.assertEqual(recovery.tree(self.home),before)
        self.write(journal,original)
        # A non-owned JSON with a terminal claim cannot replace the real journal.
        private=self.area/'private-journal.json';self.write(private,original)
        self.document['journal']=str(private);self.write(self.operation/'operation.json',self.document)
        self.row['artifacts'][0]['sha256']=recovery.digest((self.operation/'operation.json').read_bytes())
        self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external);self.save_receipt()
        with self.assertRaisesRegex(ValueError,'Original host kernel journal missing/unsafe'):
            uninstall._host_staging_receipt(self.fixture.runtime,self.root,self.fixture.backup)

    def test_persisted_outcomes_are_phase_and_flow_scoped(self):
        cases=[('bootstrap','execute','acquired',True),('enable','execute','stale_plan',True),
               ('enable','execute','no_pending_plan',True),('bootstrap','preview','already_prepared',True),
               ('bootstrap','preview','identity_missing',True),('bootstrap','preview','payload_missing',True),
               ('enable','preview','acquired',False),('enable','execute','already_prepared',False),
               ('bootstrap','execute','identity_missing',False),('enable','execute','canceled',False),
               ('enable','execute','unknown',False)]
        for flow,phase,state,accepted in cases:
            with self.subTest(flow=flow,phase=phase,state=state):
                self.document.update(flow=flow,phase=phase,state=state)
                self.write(self.operation/'operation.json',self.document)
                self.row['record_state']=state
                self.row['artifacts'][0]['sha256']=recovery.digest((self.operation/'operation.json').read_bytes())
                self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external);self.save_receipt()
                before=recovery.tree(self.home)
                if accepted:uninstall._host_staging_receipt(self.fixture.runtime,self.root,self.fixture.backup)
                else:
                    with self.assertRaises(ValueError):uninstall._host_staging_receipt(self.fixture.runtime,self.root,self.fixture.backup)
                self.assertEqual(recovery.tree(self.home),before)

    def test_orphan_known_artifact_requires_preserved_expired_mtime(self):
        (self.operation/'operation.json').unlink()
        path=self.operation/'release-request.json';self.write(path,{'command':'prepare-release-source'})
        self.row.update(record_state='no_operation_record',artifacts=[{'name':path.name,'sha256':recovery.digest(path.read_bytes())}])
        self.receipt['backup_tree_sha256']=uninstall._runtime_digest(self.external);self.save_receipt()
        with self.assertRaises(ValueError):self.plan()
        old=datetime.fromisoformat(self.stamp[:-1]+'+00:00').timestamp()-601
        os.utime(path,(old,old));plan=self.plan()
        self.assertEqual(plan['evidence_mtime_ns'][str(path)],path.stat().st_mtime_ns)

    def test_approved_external_tree_or_mtime_drift_rejected_without_product_write(self):
        plan=self.plan();approved=fixtures.approval(recovery.summary(plan))
        (self.operation/'new-private.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):
            uninstall.execute(approved,home=self.home,backup_dir=self.fixture.backup)
        (self.operation/'new-private.json').unlink()
        before=recovery.tree(self.home)
        os.utime(self.operation/'operation.json',ns=(1,1))
        with self.assertRaises(ValueError):recovery.apply_plan(plan)
        self.assertEqual(recovery.tree(self.home),before)
        self.assertFalse(self.fixture.backup.exists())

    def test_same_plan_detects_new_external_child_before_deletion(self):
        plan=self.plan();before=recovery.tree(self.home)
        (self.external/'new-file').write_bytes(b'new evidence drift')
        with self.assertRaisesRegex(ValueError,'evidence tree drift'):recovery.apply_plan(plan)
        self.assertEqual(recovery.tree(self.home),before)
