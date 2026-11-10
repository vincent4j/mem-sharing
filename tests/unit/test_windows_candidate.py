"""Necessary candidate conditions; these do not admit production writes."""
import ctypes
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import windows_native as w


def node(identity, directory=True, volume=1):
    return dict(file_id=identity, volume_id=volume, directory=directory,
                case_sensitivity_checked=True, case_sensitive_directory=False,
                attributes=16 if directory else 32, delete_pending=False,
                number_of_links=1)


def snapshot(chain):
    return dict(chain[-1], chain=chain, filesystem='NTFS')


class CandidateConditionsTests(unittest.TestCase):
    def setUp(self):
        self.root = snapshot([node('drive'), node('allowed')])
        self.target = snapshot([node('drive'), node('allowed'), node('file', False)])

    def refused(self, code, root=None, target=None):
        with self.assertRaises(w.NativeInspectionError) as caught:
            w.validate_candidate_scope(root or self.root, target or self.target)
        self.assertEqual(caught.exception.code, code)

    def test_contained_file_remains_unauthorized(self):
        result = w.validate_candidate_scope(self.root, self.target)
        self.assertTrue(result['path_checks_passed'])
        for flag in ('race_free', 'production_write_authorized', 'storage_provider_verified'):
            self.assertIs(result[flag], False)

    def test_root_must_be_directory(self):
        self.root['directory'] = False
        self.refused('scope_root_not_directory')

    def test_ancestor_identity_not_string_prefix_binds_scope(self):
        self.target['chain'][1]['file_id'] = 'other-directory'
        self.refused('outside_allowed_root')

    def test_parent_of_allowed_root_refused(self):
        self.refused('outside_allowed_root', target=snapshot([node('drive')]))

    def test_cross_volume_refused(self):
        self.target['chain'][-1]['volume_id'] = 2
        self.refused('cross_volume_refused')

    def test_hardlinks_and_unknown_count_refused(self):
        for count in (0, 2, None):
            with self.subTest(count=count):
                self.target['chain'][-1]['number_of_links'] = count
                self.refused('hardlink_or_unknown_links_refused')

    def test_case_sensitive_or_unknown_ancestor_refused(self):
        self.target['chain'][0]['case_sensitive_directory'] = True
        self.refused('case_sensitive_directory_refused')
        self.target['chain'][0]['case_sensitive_directory'] = False
        del self.target['chain'][0]['case_sensitivity_checked']
        self.refused('case_sensitivity_unknown')

    def test_delete_pending_and_unknown_refused(self):
        for value in (True, None):
            with self.subTest(value=value):
                self.target['chain'][-1]['delete_pending'] = value
                self.refused('node_delete_state_unknown')

    def test_reparse_offline_and_recall_attributes_refused(self):
        for flag in (0x400, 0x1000, 0x40000, 0x400000):
            with self.subTest(flag=flag):
                self.target['chain'][-1]['attributes'] = flag
                self.refused('storage_attributes_refused')

    def test_non_ntfs_refused(self):
        self.target['filesystem'] = 'ReFS'
        self.refused('storage_refused')


class CandidateMetadataTests(unittest.TestCase):
    def test_windows_abi_has_byte_booleans(self):
        self.assertEqual(ctypes.sizeof(w.CaseSensitiveInfo), 4)
        self.assertEqual(ctypes.sizeof(w.StandardInfo), 24)
        self.assertEqual(w.StandardInfo.number_of_links.offset, 16)
        self.assertEqual(w.StandardInfo.delete_pending.offset, 20)
        self.assertEqual(w.StandardInfo.directory.offset, 21)

    def api(self, directory, flags=0):
        api = w._API.__new__(w._API)
        def info(handle, kind, value):
            if kind == 1:
                value.directory = directory
                value.number_of_links = 1
            else:
                self.assertEqual(kind, 23)
                value.flags = flags
            return value
        api.info = info
        return api

    def test_case_sensitive_flag_is_observed(self):
        metadata = self.api(True, 1).candidate_metadata(1, True)
        self.assertTrue(metadata['case_sensitive_directory'])

    def test_unknown_case_flags_fail_closed(self):
        with self.assertRaises(w.NativeInspectionError) as caught:
            self.api(True, 2).candidate_metadata(1, True)
        self.assertEqual(caught.exception.code, 'case_sensitivity_flags_unknown')

    def test_query_failure_is_not_replaced_with_false_flag(self):
        api = self.api(True)
        def fail(*args):
            raise w.NativeInspectionError('node_information_unavailable', 'synthetic failure', 5)
        api.info = fail
        with self.assertRaises(w.NativeInspectionError) as caught:
            api.candidate_metadata(1, True)
        self.assertEqual(caught.exception.winerror, 5)

    def test_node_type_drift_fails_closed(self):
        with self.assertRaises(w.NativeInspectionError) as caught:
            self.api(False).candidate_metadata(1, True)
        self.assertEqual(caught.exception.code, 'node_type_drift')
