import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('dos_probe', Path(__file__).parents[1]/'integration/windows_dosdevice_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Runtime:
    def __init__(self, after=None, fail_verify=False, fail_remove=False):
        self.mapping = []
        self.after = after
        self.fail_verify = fail_verify
        self.fail_remove = fail_remove
        self.removed = []
        self.defined = False

    def preimage(self): return {'old': []}
    def select(self, pre): return 'Z:', 'exact-own-target'
    def recheck(self, letter): pass
    def define(self, letter, target):
        self.defined = True
        self.mapping = list(self.after) if self.after is not None else [target]
    def query(self, letter): return list(self.mapping)
    def remove_exact(self, letter, target):
        self.removed.append((letter, target))
        if self.fail_remove: raise RuntimeError('remove failed')
        self.mapping.remove(target)
    def verify(self, letter):
        if self.fail_verify: raise RuntimeError('verification failed')
        return [{'name': 'same_identity_refused', 'status': 'passed'}]
    def verify_restored(self, pre):
        if self.mapping: raise RuntimeError('not restored')


class DosDeviceCleanupTests(unittest.TestCase):
    def run_probe(self, runtime, fail_intent=False):
        self.receipts = []
        def save(name, value):
            if name == 'intent' and fail_intent: raise OSError('intent unavailable')
            self.receipts.append((name, dict(value)))
        return probe.exercise(runtime, save)

    def test_success_restores_preimage(self):
        r = Runtime(); result = self.run_probe(r)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(r.removed, [('Z:', 'exact-own-target')])

    def test_intent_failure_never_defines(self):
        r = Runtime(); result = self.run_probe(r, True)
        self.assertFalse(r.defined)
        self.assertEqual(result['status'], 'failed')

    def test_verification_failure_still_removes_exact(self):
        r = Runtime(fail_verify=True); result = self.run_probe(r)
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['cleanup_complete'])

    def test_foreign_definition_never_removed(self):
        r = Runtime(after=['foreign', 'exact-own-target']); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertEqual(r.mapping, ['foreign'])
        self.assertEqual(r.removed, [('Z:', 'exact-own-target')])

    def test_missing_or_duplicate_own_target_retains(self):
        for values in (['foreign'], ['exact-own-target', 'exact-own-target']):
            with self.subTest(values=values):
                r = Runtime(after=values); result = self.run_probe(r)
                self.assertEqual(result['status'], 'needs_inspection')
                self.assertFalse(r.removed)

    def test_api_effect_then_interrupt_is_exactly_cleaned(self):
        class Interrupted(Runtime):
            def define(self, letter, target):
                super().define(letter, target)
                raise KeyboardInterrupt('after external effect')
        r = Interrupted(); result = self.run_probe(r)
        self.assertTrue(result['define_attempted'])
        self.assertFalse(result['created'])
        self.assertTrue(result['definition_observed'])
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(r.mapping, [])
        self.assertEqual(result['error']['type'], 'KeyboardInterrupt')
        self.assertEqual([name for name, _ in self.receipts], ['intent', 'define-intent', 'result'])

    def test_api_interrupt_before_effect_checks_preimage(self):
        class Interrupted(Runtime):
            def define(self, letter, target): raise KeyboardInterrupt('before effect')
        r = Interrupted(); result = self.run_probe(r)
        self.assertTrue(result['cleanup_complete'])
        self.assertFalse(result['definition_observed'])
        self.assertEqual(r.removed, [])

    def test_removal_failure_reports_unrestored(self):
        r = Runtime(fail_remove=True); result = self.run_probe(r)
        self.assertEqual(result['status'], 'needs_inspection')
        self.assertFalse(result['cleanup_complete'])
        self.assertEqual(r.mapping, ['exact-own-target'])


if __name__ == '__main__': unittest.main()
