from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from agm_core import windows_native as w


def observed():
    return dict(volume_id=1,file_id='file',chain=[dict(volume_id=1,file_id='root'),dict(volume_id=1,file_id='file')],
                path_checks_passed=True,registered_cloud_root_checked=True,
                registered_cloud_root_present=False,cloud_hresult_mapping_inferred=False,
                storage_provider_verified=True)


class R2AdmissionTests(unittest.TestCase):
    def refused(self, value, code):
        with self.assertRaises(w.NativeInspectionError) as caught:
            w.validate_r2_admission([value])
        self.assertEqual(caught.exception.code,code)

    def test_synthetic_complete_evidence_still_never_authorizes_write(self):
        # Synthetic complete observations exercise combination only, not a
        # claim that any real provider has been verified on Windows.
        result=w.validate_r2_admission([observed()])
        self.assertTrue(result['r2_conditions_satisfied'])
        self.assertFalse(result['production_write_authorized'])
        self.assertFalse(result['race_free'])

    def test_cloud_disabled_or_missing_not_admitted(self):
        for value in (False,None):
            item=observed();item['registered_cloud_root_checked']=value
            self.refused(item,'cloud_check_required')

    def test_cloud_present_or_unknown_refused(self):
        for value in (True,None):
            item=observed();item['registered_cloud_root_present']=value
            self.refused(item,'cloud_root_or_unknown')

    def test_inferred_or_unclassified_mapping_refused(self):
        for value in (True,None):
            item=observed();item['cloud_hresult_mapping_inferred']=value
            self.refused(item,'cloud_evidence_inferred')

    def test_unknown_provider_refused(self):
        item=observed();item['storage_provider_verified']=False
        self.refused(item,'storage_provider_unverified')

    def test_overlap_cannot_be_promoted(self):
        with self.assertRaises(w.NativeInspectionError) as caught:
            w.validate_r2_admission([observed(),observed()])
        self.assertEqual(caught.exception.code,'candidate_overlap')

    def test_unchecked_path_cannot_be_promoted(self):
        item=observed();item['path_checks_passed']=False
        self.refused(item,'candidate_unchecked')
