from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import windows_native as w


def node(identity, volume=1):
    return dict(volume_id=volume, file_id=identity)


def candidate(identity, ancestors=('drive', 'scope'), volume=1):
    return dict(node(identity, volume), path_checks_passed=True,
                chain=[node(i, volume) for i in (*ancestors, identity)])


class CandidateSetTests(unittest.TestCase):
    def refused(self, code, values):
        with self.assertRaises(w.NativeInspectionError) as caught:
            w.validate_candidate_set(values)
        self.assertEqual(caught.exception.code, code)

    def test_disjoint_set_retains_count_and_no_write_authority(self):
        result = w.validate_candidate_set([candidate('first'), candidate('second')])
        self.assertEqual(result['candidate_count'], 2)
        self.assertTrue(result['overlap_checks_passed'])
        self.assertIs(result['production_write_authorized'], False)
        self.assertIs(result['race_free'], False)

    def test_duplicate_physical_node_rejected(self):
        self.refused('candidate_overlap', [candidate('same'), candidate('same')])

    def test_mapped_name_same_leaf_identity_rejected(self):
        self.refused('candidate_overlap', [candidate('same'), candidate('same', ('other-drive-name', 'scope'))])

    def test_ancestor_descendant_rejected_in_both_orders(self):
        values = [candidate('folder'), candidate('leaf', ('drive', 'scope', 'folder'))]
        for pair in (values, values[::-1]):
            self.refused('candidate_overlap', pair)

    def test_file_id_equal_across_volumes_is_not_same_object(self):
        result = w.validate_candidate_set([candidate('same', volume=1), candidate('same', volume=2)])
        self.assertTrue(result['overlap_checks_passed'])

    def test_unchecked_candidate_rejected(self):
        value = candidate('leaf')
        value['path_checks_passed'] = False
        self.refused('candidate_unchecked', [value])

    def test_inconsistent_leaf_identity_rejected(self):
        value = candidate('leaf')
        value['chain'][-1]['file_id'] = 'different'
        self.refused('candidate_identity_unknown', [value])

    def test_cloud_checks_are_reported_separately_from_overlap(self):
        values = [candidate('first'), candidate('second')]
        self.assertIs(w.validate_candidate_set(values)['registered_cloud_roots_checked'], False)
        for value in values:
            value['registered_cloud_root_checked'] = True
        self.assertIs(w.validate_candidate_set(values)['registered_cloud_roots_checked'], True)

    def test_empty_or_oversize_rejected(self):
        self.refused('candidate_set_size', [])
        self.refused('candidate_set_size', [candidate(str(i)) for i in range(257)])


class RegisteredCloudResultTests(unittest.TestCase):
    def test_only_exact_non_root_error_is_narrow_absence_observation(self):
        for value in (0x80070186, -2147024506):
            with self.subTest(value=value):
                result = w.classify_registered_cloud_result(value, 0)
                self.assertTrue(result['registered_cloud_root_checked'])
                self.assertFalse(result['registered_cloud_root_present'])
                self.assertTrue(result['cloud_hresult_mapping_inferred'])
                self.assertNotIn('production_write_authorized', result)

    def test_success_means_registered_root_refused(self):
        with self.assertRaises(w.NativeInspectionError) as caught:
            w.classify_registered_cloud_result(0, 8)
        self.assertEqual(caught.exception.code, 'registered_cloud_root_refused')

    def test_unknown_error_and_short_success_refused(self):
        for status, size in ((0x80070005, 0), (0x80004001, 0), (1, 8), (0, 0), (0, 7)):
            with self.subTest(status=status, size=size), self.assertRaises(w.NativeInspectionError) as caught:
                w.classify_registered_cloud_result(status, size)
            self.assertEqual(caught.exception.code, 'cloud_query_unverified')
