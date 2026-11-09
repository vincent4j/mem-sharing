import ctypes
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import windows_native as native


class WindowsNativePortableTests(unittest.TestCase):
    def test_abi_fixed_width_even_on_non_windows(self):
        self.assertEqual(ctypes.sizeof(native.DWORD), 4)
        self.assertEqual(ctypes.sizeof(native.BOOL), 4)
        self.assertEqual(ctypes.sizeof(native.AttributeTagInfo), 8)
        self.assertEqual(ctypes.sizeof(native.FileIdInfo), 24)
        self.assertEqual(native.FileIdInfo.file_id.offset, 8)

    def test_chain_preserves_unicode_case_and_drive_root(self):
        self.assertEqual(native.path_chain('D:/中文 空格/Leaf'),
                         ['D:\\', 'D:\\中文 空格', 'D:\\中文 空格\\Leaf'])
        self.assertEqual(native.path_chain('C:\\'), ['C:\\'])

    def test_unsafe_names_rejected_before_os(self):
        for name in ('C:relative', '\\\\server\\share', '\\\\?\\C:\\a', 'C:\\a:b', 'C:\\a\\..\\b', 'C:\\NUL.txt'):
            with self.subTest(name=name), self.assertRaises(native.NativeInspectionError):
                native.path_chain(name)

    def test_volume_and_file_id_both_required_for_alias(self):
        a={'volume_id':1,'file_id':'abcd'}
        self.assertTrue(native.same_node(a,dict(a)))
        self.assertFalse(native.same_node(a,{'volume_id':2,'file_id':'abcd'}))
        self.assertFalse(native.same_node(a,{'volume_id':1,'file_id':'efgh'}))

    @unittest.skipIf(sys.platform == 'win32', 'non-Windows refusal only')
    def test_non_windows_native_calls_rejected(self):
        with self.assertRaises(native.NativeInspectionError) as caught:
            with native.inspect_path('C:\\'):
                self.fail('Unsupported host admitted')
        self.assertEqual(caught.exception.code, 'platform_unsupported')
