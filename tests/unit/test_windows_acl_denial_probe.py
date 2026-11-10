import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('acl_probe', Path(__file__).parents[1]/'integration/windows_acl_denial_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Runtime:
    def __init__(self, fail_set=False, interrupt=False, fail_restore=False, mismatch=False):
        self.denied = False
        self.fail_set = fail_set
        self.interrupt = interrupt
        self.fail_restore = fail_restore
        self.mismatch = mismatch
        self.restored = 0
        self.handle = object()
        self.original = {'descriptor': 'owner-group-dacl-control-original'}

    def snapshot(self):
        if self.denied: return {'descriptor': 'deny'}
        if self.mismatch and self.restored: return {'descriptor': 'drift'}
        return dict(self.original)
    def prepare(self): pass
    def deny(self):
        self.denied = True
        if self.fail_set: raise OSError('effect then failure')
        if self.interrupt: raise KeyboardInterrupt('effect then interrupt')
    def verify_denied(self):
        if not self.denied: raise RuntimeError('new open admitted')
        return [{'name': 'denied', 'winerror': 5}]
    def restore(self, original):
        # Simulates restoration using already-held authority, no new read-open.
        current = self.snapshot()  # Production restore queries before touching the DACL.
        if current['descriptor'] not in ('deny', self.original['descriptor']):
            raise RuntimeError('foreign DACL; preserve')
        if self.fail_restore: raise OSError('restore failed; retain fixture')
        self.restored += 1
        self.denied = False
    def verify_readable(self):
        if self.denied: raise RuntimeError('still denied')


class AclDenialCleanupTests(unittest.TestCase):
    def run_probe(self, runtime, fail_save=None):
        self.receipts = []
        def save(name, value):
            if name == fail_save: raise OSError('save failed')
            self.receipts.append((name, dict(value)))
        return probe.exercise(runtime, save)

    def test_held_handle_restores_before_new_read(self):
        r = Runtime(); result = self.run_probe(r)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['restore_complete'])
        self.assertEqual(r.restored, 1)

    def test_backup_and_intent_failure_never_sets(self):
        for name in ['backup', 'intent']:
            with self.subTest(name=name):
                r = Runtime(); result = self.run_probe(r, name)
                self.assertFalse(result['set_attempted'])
                self.assertFalse(r.denied)
                self.assertEqual(r.restored, 0)

    def test_set_failure_or_interrupt_still_restores(self):
        for options in [{'fail_set': True}, {'interrupt': True}]:
            with self.subTest(options=options):
                r = Runtime(**options); result = self.run_probe(r)
                self.assertNotEqual(result['status'], 'passed')
                self.assertTrue(result['restore_complete'])
                self.assertEqual(r.restored, 1)

    def test_restoration_failure_preserves_unknown(self):
        r = Runtime(fail_restore=True); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertFalse(result['restore_complete'])
        self.assertTrue(r.denied)

    def test_readback_mismatch_never_claims_restored(self):
        r = Runtime(mismatch=True); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertFalse(result['restore_complete'])

    def test_one_post_deny_query_failure_can_restore(self):
        class Once(Runtime):
            failed = False
            def snapshot(self):
                if self.denied and not self.failed:
                    self.failed = True
                    raise OSError('one failed post-deny query')
                return super().snapshot()
        r = Once(); result = self.run_probe(r)
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['restore_complete'])
        self.assertEqual(r.restored, 1)

    def test_persistent_query_failure_preserves_unrestored_fixture(self):
        class Persistent(Runtime):
            def snapshot(self):
                if self.denied: raise OSError('query remains unavailable')
                return super().snapshot()
        r = Persistent(); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertFalse(result['restore_complete'])
        self.assertTrue(r.denied)
        self.assertEqual(r.restored, 0)


if __name__ == '__main__': unittest.main()
