import ctypes as C
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('cf_probe', Path(__file__).parents[1]/'integration/windows_cf_registration_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Runtime:
    def __init__(self, owned=True, interrupt=False, foreign=False, unregister_error=0, absent=True, attrs_drift=False):
        self.registered = False
        self.owned = owned
        self.interrupt = interrupt
        self.foreign = foreign
        self.unregister_error = unregister_error
        self.absent = absent
        self.unregister_count = 0
        self.ever_registered = False
        self.attrs_drift = attrs_drift
        self.after_called = False

    def preflight(self):
        self.created_root = dict(root=dict(identity='root-id',security_sha256='root-security',attributes=16,reparse_tag=0),entries=[],child=None)
        self.with_child = self.snapshot()
        return {'root_created_before_child':self.created_root,'baseline_with_child':self.with_child}
    def snapshot(self):
        return dict(root=dict(identity='root-id',security_sha256='root-security',attributes=48 if self.attrs_drift and self.ever_registered else 16,reparse_tag=0),entries=['known-child'],child={'identity':'child-id','sha256':'known-hash','attributes':32,'reparse_tag':0})
    def describe(self): return {'operation': 'unique-fixed-root', 'marker': 'random-marker'}
    def register(self):
        self.registered = True
        self.ever_registered = True
        if self.interrupt: raise KeyboardInterrupt('effect then interrupted')
        return 0
    def ownership(self): return {'owned': self.registered and self.owned}
    def verify_refusal(self): return [{'registered_cloud_root_refused': True}]
    def cleanup_guard(self):
        if self.foreign: raise RuntimeError('foreign child; do not traverse')
    def unregister(self):
        self.unregister_count += 1
        if not self.unregister_error: self.registered = False
        return self.unregister_error
    def after(self):
        self.after_called = True
        after=self.snapshot(); after['entries']=[]; after['child']=None
        return {'dimensions':probe.compare_dimensions(self.created_root,after),'query_classification':'inferred_not_root' if self.absent else 'unknown'}


class CloudFixtureTests(unittest.TestCase):
    def run_probe(self, runtime, fail=None):
        self.receipts = []
        def save(name, value):
            if name == fail: raise OSError('durable intent failed')
            self.receipts.append((name, dict(value)))
        return probe.exercise(runtime, save)

    def test_intent_failure_never_registers(self):
        r = Runtime(); result = self.run_probe(r, 'intent')
        self.assertFalse(result['register_attempted'])
        self.assertFalse(r.registered)
        self.assertEqual(r.unregister_count, 0)

    def test_positive_then_exact_owned_cleanup(self):
        r = Runtime(); result = self.run_probe(r)
        self.assertEqual(result['status'], 'observed_positive')
        self.assertTrue(result['fixture_cleanup_complete'])
        self.assertEqual(r.unregister_count, 1)
        self.assertFalse(result['r2_admission_satisfied'])

    def test_interrupted_effect_is_not_lost(self):
        r = Runtime(interrupt=True); result = self.run_probe(r)
        self.assertTrue(result['register_attempted'])
        self.assertTrue(result['fixture_cleanup_complete'])
        self.assertFalse(r.registered)
        self.assertNotEqual(result['status'], 'observed_positive')

    def test_unknown_owner_or_foreign_tree_never_unregisters(self):
        for options in [{'owned': False}, {'foreign': True}]:
            with self.subTest(options=options):
                r = Runtime(**options); result = self.run_probe(r)
                self.assertEqual(result['status'], 'needs_inspection')
                self.assertEqual(r.unregister_count, 0)
                self.assertTrue(r.registered)

    def test_unregister_intent_failure_preserves_registration(self):
        r = Runtime(); result = self.run_probe(r, 'unregister-intent')
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertEqual(r.unregister_count, 0)
        self.assertTrue(r.registered)

    def test_unregister_failure_never_retries(self):
        r = Runtime(unregister_error=0x80070001); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertEqual(r.unregister_count, 1)
        self.assertFalse(result['fixture_cleanup_complete'])

    def test_unknown_postquery_stays_separate_from_physical_cleanup(self):
        r = Runtime(absent=False); result = self.run_probe(r)
        self.assertEqual(result['status'], 'observed_positive')
        self.assertTrue(result['fixture_cleanup_complete'])
        self.assertEqual(result['after']['query_classification'], 'unknown')
        self.assertTrue(result['unregister_succeeded'])
        self.assertFalse(result['full_cf_gate_verified'])
        self.assertFalse(result['r2_admission_satisfied'])

    def test_foreign_child_hash_or_placeholder_retains_tree(self):
        for reason in ['content hash drift', 'placeholder state', 'foreign tree entry']:
            class Refuse(Runtime):
                def cleanup_guard(self): raise RuntimeError(reason)
            with self.subTest(reason=reason):
                r = Refuse(); result = self.run_probe(r)
                self.assertEqual(result['status'], 'needs_inspection')
                self.assertEqual(r.unregister_count, 0)
                self.assertTrue(r.registered)

    def test_child_changed_during_unregister_never_claims_tree_restored(self):
        class Changed(Runtime):
            def after(self): raise RuntimeError('child id/hash mismatch; preserve')
        r = Changed(); result = self.run_probe(r)
        self.assertTrue(result['unregister_succeeded'])
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertFalse(result.get('fixture_cleanup_complete', False))

    def test_partial_effect_with_unknown_owner_never_unregisters(self):
        r = Runtime(owned=False, interrupt=True); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertEqual(r.unregister_count, 0)
        self.assertTrue(r.registered)

    def test_baseline_persist_failure_never_registers(self):
        r=Runtime(); result=self.run_probe(r,'baseline-before-register')
        self.assertFalse(result['register_attempted'])
        self.assertEqual(r.unregister_count,0)
        self.assertFalse(r.registered)

    def test_before_unregister_snapshot_persist_failure_preserves(self):
        r=Runtime(); result=self.run_probe(r,'before-unregister')
        self.assertEqual(result['status'],'needs_inspection')
        self.assertEqual(r.unregister_count,0)
        self.assertTrue(r.registered)

    def test_each_stage_snapshot_is_saved_without_losing_api_results(self):
        r=Runtime(); result=self.run_probe(r)
        names=[name for name,_ in self.receipts]
        self.assertEqual(names,['baseline-before-register','intent','after-register','before-unregister','unregister-intent','after-unregister-before-delete','result'])
        self.assertEqual(result['register_hresult'],0)
        self.assertEqual(result['unregister_hresult'],0)
        self.assertEqual(result['after_register']['entries'],['known-child'])
        self.assertEqual(result['after_unregister_before_delete']['child']['sha256'],'known-hash')

    def test_attribute_delta_is_not_masked_by_other_true_dimensions(self):
        r=Runtime(attrs_drift=True); result=self.run_probe(r)
        self.assertEqual(result['status'],'needs_inspection')
        self.assertTrue(result['unregister_succeeded'])
        self.assertFalse(result['dimensions']['attrs_equal'])
        self.assertTrue(result['dimensions']['tree_empty'])
        self.assertTrue(result['dimensions']['identity_equal'])
        self.assertTrue(result['dimensions']['security_equal'])
        self.assertFalse(result['fixture_cleanup_complete'])

    def test_after_unregister_snapshot_save_failure_keeps_child_cleanup_unstarted(self):
        r=Runtime(); result=self.run_probe(r,'after-unregister-before-delete')
        self.assertTrue(result['unregister_succeeded'])
        self.assertEqual(result['status'],'needs_inspection')
        self.assertFalse(r.after_called)
        self.assertEqual(r.unregister_count,1)
        self.assertFalse(result['fixture_cleanup_complete'])

    def test_standard_identity_abi_and_bounds(self):
        self.assertEqual(C.sizeof(probe.Policies), 24)
        self.assertEqual(C.sizeof(probe.Registration), 72)
        self.assertEqual(C.sizeof(probe.Standard), 1064)
        self.assertEqual(probe.Standard.identity.offset, 1056)
        buf = C.create_string_buffer(8192)
        h = probe.Standard.from_buffer(buf)
        h.name[0] = ord('N'); h.version[0] = ord('V'); h.identity_length = 32
        marker = b'x'*32
        C.memmove(C.addressof(buf)+1056, marker, len(marker))
        decoded = probe.decode_standard(buf.raw, 1088, marker, 'N', 'V')
        self.assertTrue(decoded['owned'])
        self.assertFalse(probe.decode_standard(buf.raw, 1088, b'y'*32, 'N', 'V')['owned'])
        for bad in [0, 1055, 1087, 8193]:
            with self.subTest(length=bad), self.assertRaises(RuntimeError):
                probe.decode_standard(buf.raw, bad, marker, 'N', 'V')


if __name__ == '__main__': unittest.main()
