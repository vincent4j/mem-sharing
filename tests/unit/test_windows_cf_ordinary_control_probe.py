import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('ordinary_control', Path(__file__).parents[1]/'integration/windows_cf_ordinary_control_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Runtime:
    def __init__(self, changed_attr=False, foreign=False):
        self.child = False
        self.created = False
        self.deleted = False
        self.changed_attr = changed_attr
        self.foreign = foreign
    def snapshot(self):
        if self.foreign and self.created: raise RuntimeError('foreign entry; preserve')
        return dict(identity='fixed-id', security_sha256='fixed-security', reparse_tag=0,
                    attributes=48 if self.changed_attr and self.created else 16,
                    entries=['own-child'] if self.child else [])
    def describe(self): return {'child':'fixed-child','hash':'fixed-hash'}
    def create_child(self): self.child=True; self.created=True
    def remove_child(self): self.snapshot(); self.child=False; self.deleted=True


class OrdinaryControlTests(unittest.TestCase):
    def run_probe(self, runtime, fail=None):
        self.receipts=[]
        def save(name,value):
            if name==fail: raise OSError('snapshot evidence unavailable')
            self.receipts.append((name,dict(value)))
        return probe.exercise(runtime,save)

    def test_normal_sequence_persists_all_three_snapshots(self):
        r=Runtime(); result=self.run_probe(r)
        self.assertEqual(result['status'],'observed')
        self.assertTrue(all(result['dimensions'].values()))
        self.assertEqual([name for name,_ in self.receipts],['root-created','create-intent','after-child-create','delete-intent','after-child-delete','result'])

    def test_attribute_difference_is_observed_not_repaired(self):
        r=Runtime(changed_attr=True); result=self.run_probe(r)
        self.assertFalse(result['dimensions']['attrs_equal'])
        self.assertTrue(result['dimensions']['tree_empty'])
        self.assertFalse(result['attribute_repair_attempted'])
        self.assertFalse(result['cf_calls_attempted'])

    def test_before_create_evidence_failure_zero_file_creation(self):
        for fail in ('root-created','create-intent'):
            with self.subTest(fail=fail):
                r=Runtime(); result=self.run_probe(r,fail)
                self.assertEqual(result['status'],'needs_inspection')
                self.assertFalse(r.created)

    def test_foreign_or_evidence_failure_preserves_own_child(self):
        for options,fail in (({'foreign':True},None),({},'after-child-create'),({},'delete-intent')):
            with self.subTest(options=options,fail=fail):
                r=Runtime(**options); result=self.run_probe(r,fail)
                self.assertEqual(result['status'],'needs_inspection')
                self.assertTrue(r.child)
                self.assertFalse(r.deleted)

    def test_dimensions_remain_separate(self):
        before=dict(identity='a',security_sha256='s',attributes=16,reparse_tag=0)
        after=dict(identity='b',security_sha256='t',attributes=48,reparse_tag=0,entries=[])
        result=probe.compare_root(before,after)
        self.assertEqual(result,dict(tree_empty=True,identity_equal=False,security_equal=False,attrs_equal=False,tag_equal=True))


if __name__=='__main__': unittest.main()
