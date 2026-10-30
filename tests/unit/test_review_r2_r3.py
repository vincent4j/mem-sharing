"""R2/R3: isolated global-impact approval and last-moment foreign-edit guards."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m204_enable import EnableFixture
from agm_core import enable, registry
from agm_core.transaction import Change, Transaction, TransactionError, read_snapshot, recover_manifest

STAMP = "2026-10-30T00:00:00Z"


class RebuildTests(EnableFixture):
    def two_projects(self):
        self.apply()
        first = str(self.root)
        self.root = self.area / 'second-project'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.request.update(project=str(self.root), approval=None)
        self.apply()
        self.request['approval'] = None
        return first

    def corrupt_first(self):
        first = self.two_projects()
        path = self.runtime.registry
        raw = json.loads(path.read_bytes())
        raw['projects'][first]['checkouts'][first]['states']['source_available']['status'] = 'INVALID'
        path.write_text(json.dumps(raw))
        return first, path

    def approved_rebuild(self, result):
        approval = json.loads(result['next_action'])
        approval.update(confirmed_at=STAMP, reference='separate project assembly confirmation')
        approval['rebuild_confirmation'].update(confirmed_at=STAMP, reference='explicit global index reset confirmation')
        return approval

    def test_multi_project_corruption_requires_separate_exact_global_authorization(self):
        first, path = self.corrupt_first()
        before = path.read_bytes()
        machine = json.loads(before)
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'approval_required', result)
        plan = json.loads(result['next_action'])
        self.assertEqual(plan['rebuild']['project_count'], 2)
        self.assertEqual({p['main_checkout'] for p in plan['rebuild']['removed_projects']}, {first, str(self.root)})
        self.assertEqual(plan['rebuild']['classification'], 'registry_project_corrupt')
        self.assertEqual(path.read_bytes(), before)
        approval = self.approved_rebuild(result)
        missing = dict(approval)
        del missing['rebuild_confirmation']
        self.request['approval'] = missing
        declined = enable.run(self.request)
        self.assertEqual(declined['status'], 'approval_required', declined)
        self.assertEqual(path.read_bytes(), before)
        self.request['approval'] = approval
        completed = enable.run(self.request)
        self.assertEqual(completed['status'], 'completed', completed)
        after = self.load()
        self.assertEqual(set(after['projects']), {str(self.root)})
        for field in ('product', 'machine', 'migration', 'legacy_import'):
            self.assertEqual(after[field], machine[field])
        backups = list(self.runtime.backups.glob('*/0.before'))
        self.assertTrue(any(p.read_bytes() == before for p in backups))
        print('REBUILD', json.dumps({'projects_before': 2, 'preview_rebuild': plan['rebuild'],
            'without_separate_approval': declined['status'], 'result': completed['status'], 'projects_after': len(after['projects'])}))

    def test_missing_created_manifest_is_evidence_unavailable_not_empty_registry(self):
        first = self.two_projects()
        path = self.runtime.registry
        raw = json.loads(path.read_bytes())
        obj = next(iter(raw['projects'][first]['checkouts'][first]['objects'].values()))
        Path(obj['backup_manifest']).unlink()
        before = path.read_bytes()
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'approval_required', result)
        plan = json.loads(result['next_action'])
        self.assertEqual(plan['rebuild']['classification'], 'registry_evidence_unavailable')
        self.assertEqual(plan['rebuild']['project_count'], 2)
        self.assertEqual(path.read_bytes(), before)
        self.request['approval'] = self.approved_rebuild(result)
        self.assertEqual(enable.run(self.request)['status'], 'completed')

    def test_registry_drift_after_preview_invalidates_both_approvals(self):
        _, path = self.corrupt_first()
        result = enable.run(self.request)
        self.request['approval'] = self.approved_rebuild(result)
        path.write_bytes(path.read_bytes() + b'\n')
        changed = path.read_bytes()
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'approval_required', result)
        self.assertEqual(result['errors'][0]['code'], 'approval_mismatch')
        self.assertEqual(path.read_bytes(), changed)

    def test_unknown_schema_unparseable_and_machine_damage_stop_without_rebuild(self):
        self.apply()
        path = self.runtime.registry
        valid = path.read_bytes()
        for kind in ('unknown_schema', 'unparseable', 'unknown_field', 'machine_damage', 'unidentifiable_project'):
            with self.subTest(kind=kind):
                raw = json.loads(valid)
                if kind == 'unknown_schema': raw['schema_version'] = 999
                if kind == 'unknown_field': raw['extra'] = True
                if kind == 'machine_damage': raw['product']['installation_status'] = 'BOGUS'
                if kind == 'unidentifiable_project': raw['projects'][str(self.root)]['main_checkout'] = '/different'
                path.write_bytes(b'{broken' if kind == 'unparseable' else json.dumps(raw).encode())
                before = path.read_bytes()
                self.request['approval'] = None
                result = enable.run(self.request)
                self.assertEqual(result['status'], 'failed', result)
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse(self.runtime.lock.exists())

    def test_enable_registry_provider_hook_edit_is_preserved(self):
        approval = self.preview('yes', True)
        self.request['approval'] = approval
        def hook(event, path):
            if event == 'before_write' and path == self.runtime.registry:
                path.write_bytes(b'external registry edit')
        self.request['transaction_hook'] = hook
        result = enable.run(self.request)
        self.assertEqual(result['status'], 'recovery_required', result)
        self.assertEqual(self.runtime.registry.read_bytes(), b'external registry edit')


class WriteWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.path = self.area / 'output'
        self.path.write_bytes(b'original')
        self.lock = self.area / 'lock'

    def tx(self, hook=None):
        return Transaction(lock_path=self.lock, backup_root=self.area / 'backups', allowed_roots=[self.area], hook=hook)

    def test_before_write_external_edit_is_never_silently_overwritten(self):
        def hook(event, path):
            if event == 'before_write': path.write_bytes(b'external edit')
        tx = self.tx(hook)
        with self.assertRaises(TransactionError) as caught:
            tx.run([Change.file(self.path, b'planned', expected=read_snapshot(self.path))])
        self.assertEqual(caught.exception.code, 'recovery_required')
        self.assertEqual(self.path.read_bytes(), b'external edit')
        print('RACE', caught.exception.code, self.path.read_text())

    def test_staging_window_forward_and_rollback_preserve_external_edit(self):
        for phase in ('forward', 'rollback'):
            with self.subTest(phase=phase):
                self.path.write_bytes(b'original')
                def hook(event, path):
                    if phase == 'rollback' and event == 'after_write': raise RuntimeError('force rollback')
                tx = self.tx(hook)
                chmod = os.chmod
                def edit_during_staging(path, mode):
                    if Path(path).parent == self.area and Path(path).read_bytes() == (b'planned' if phase == 'forward' else b'original'):
                        self.path.write_bytes(b'external staging edit')
                    return chmod(path, mode)
                with patch('agm_core.transaction.os.chmod', side_effect=edit_during_staging):
                    with self.assertRaises(TransactionError):
                        tx.run([Change.file(self.path, b'planned', expected=read_snapshot(self.path))])
                self.assertEqual(self.path.read_bytes(), b'external staging edit')

    def pending_recovery(self):
        def hook(event, path):
            if event in ('after_write', 'before_restore'): raise RuntimeError('interrupt')
        tx = self.tx(hook)
        with self.assertRaises(TransactionError):
            tx.run([Change.file(self.path, b'planned', expected=read_snapshot(self.path))])
        self.assertEqual(self.path.read_bytes(), b'planned')
        return tx.manifest_path

    def test_recovery_rechecks_after_hook_and_inside_staging(self):
        for phase in ('hook', 'staging'):
            with self.subTest(phase=phase):
                self.path.write_bytes(b'original')
                manifest = self.pending_recovery()
                def hook(event, path):
                    if phase == 'hook' and event == 'before_restore': path.write_bytes(b'external recovery edit')
                chmod = os.chmod
                def edit_during_staging(path, mode):
                    if phase == 'staging' and Path(path).parent == self.area:
                        self.path.write_bytes(b'external recovery edit')
                    return chmod(path, mode)
                with patch('agm_core.transaction.os.chmod', side_effect=edit_during_staging):
                    with self.assertRaises(TransactionError):
                        recover_manifest(manifest, lock_path=self.lock, allowed_roots=[self.area], hook=hook)
                self.assertEqual(self.path.read_bytes(), b'external recovery edit')
