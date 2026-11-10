import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('attr_recovery',Path(__file__).parents[1]/'fixtures/windows_cf_attribute_recovery.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
PLAN=dict(identity='fixed-id',security_sha256='fixed-security',receipts={'bound-receipt':'hash'})


class Runtime:
    source_sha256='approved-source'
    def __init__(self,attrs=48,interrupt=False,error=False,effect=True,post_failure=False,time_change=False,drift=False):
        self.attrs=attrs;self.interrupt=interrupt;self.error=error;self.effect=effect
        self.post_failure=post_failure;self.time_change=time_change;self.drift=drift
        self.calls=0;self.snapshots=0
    def snapshot(self):
        self.snapshots+=1
        if self.post_failure and self.calls: raise OSError('post snapshot failed')
        attrs=self.attrs|1 if self.drift and self.snapshots==2 else self.attrs
        return dict(identity='fixed-id',named_identity='fixed-id',security_sha256='fixed-security',named_security_sha256='fixed-security',
                    attributes=attrs,named_attributes=attrs,reparse_tag=0,named_reparse_tag=0,entries=[],
                    basic=dict(creation_time=1,last_access_time=2,last_write_time=3,change_time=5 if self.time_change and self.calls else 4,attributes=attrs))
    def apply(self):
        self.calls+=1
        if self.effect:self.attrs=16
        if self.interrupt:raise KeyboardInterrupt('effect then interrupt')
        return dict(success=not self.error,winerror=87 if self.error else None)


class AttributeRecoveryTests(unittest.TestCase):
    def run_probe(self,runtime,fail=None):
        self.receipts=[]
        def save(name,value):
            if name==fail:raise OSError('evidence unavailable')
            self.receipts.append((name,dict(value)))
        return probe.exercise(runtime,save,PLAN)

    def test_single_effect_and_full_before_basic_persisted(self):
        r=Runtime();result=self.run_probe(r)
        self.assertEqual(result['status'],'applied');self.assertTrue(result['attributes_observed_restored'])
        self.assertEqual(r.calls,1)
        self.assertEqual([x for x,_ in self.receipts],['before','write-intent','immediate-before-write','result'])
        self.assertIn('change_time',self.receipts[0][1]['basic'])
        self.assertFalse(result['full_metadata_restored']);self.assertFalse(result['full_cf_gate_verified'])

    def test_extra_attribute_or_immediate_drift_zero_write(self):
        for options in ({'attrs':49},{'drift':True}):
            with self.subTest(options=options):
                r=Runtime(**options);result=self.run_probe(r)
                self.assertFalse(result['write_attempted']);self.assertEqual(r.calls,0)

    def test_each_prewrite_evidence_failure_zero_write(self):
        for name in ('before','write-intent','immediate-before-write'):
            with self.subTest(name=name):
                r=Runtime();result=self.run_probe(r,name)
                self.assertFalse(result['write_attempted']);self.assertEqual(r.calls,0)

    def test_interrupted_effect_observed_without_retry_or_fake_success(self):
        r=Runtime(interrupt=True);result=self.run_probe(r)
        self.assertEqual(result['status'],'failed');self.assertTrue(result['attributes_observed_restored'])
        self.assertEqual(r.calls,1);self.assertNotIn('call_result',result)
        self.assertEqual(result['error']['type'],'KeyboardInterrupt')

    def test_false_result_with_and_without_effect_preserves_both_facts(self):
        for effect in (False,True):
            with self.subTest(effect=effect):
                r=Runtime(error=True,effect=effect);result=self.run_probe(r)
                self.assertFalse(result['call_result']['success'])
                self.assertEqual(result['attributes_observed_restored'],effect)
                self.assertNotEqual(result['status'],'applied');self.assertEqual(r.calls,1)

    def test_readback_failure_is_unknown_not_retry(self):
        r=Runtime(post_failure=True);result=self.run_probe(r)
        self.assertEqual(result['status'],'needs_inspection');self.assertEqual(r.calls,1)
        self.assertFalse(result['attributes_observed_restored'])

    def test_timestamp_change_is_separate_from_attribute_goal(self):
        r=Runtime(time_change=True);result=self.run_probe(r)
        self.assertTrue(result['attributes_observed_restored'])
        self.assertFalse(result['timestamp_equal_to_before_setter']['change_time'])
        self.assertFalse(result['full_metadata_restored'])

    def test_identity_security_tree_tag_drift_rejected(self):
        base=Runtime().snapshot()
        for key,value in [('identity','foreign'),('named_identity','foreign'),('security_sha256','changed'),('entries',['foreign']),('reparse_tag',1)]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                probe.guard(dict(base,**{key:value}),PLAN,48)


if __name__=='__main__':unittest.main()
