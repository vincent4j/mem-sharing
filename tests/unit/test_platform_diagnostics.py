import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import platform_diagnostics as pd
from agm_core import paths, user_install, upgrade


class PlatformDiagnosticsTests(unittest.TestCase):
    def test_windows_syntax_preserves_unicode_spaces(self):
        for path in ('C:\\', 'C:\\Users\\测试 用户\\项目\\AGENTS.md', 'd:/中文/规则.md'):
            with self.subTest(path=path):
                self.assertIsNone(pd.windows_path_issue(path))

    def test_ambiguous_or_unsafe_windows_paths(self):
        for path in ('', 'C:relative', '\\rooted', '\\\\server\\share',
                     '\\\\?\\C:\\a', '\\\\.\\NUL', 'C:\\a:stream', 'C:\\a.',
                     'C:\\a ', 'C:\\..\\a', 'C:\\.\\a', 'C:\\a\\\\b',
                     'C:\\CON.txt', 'C:\\LPT¹.txt', 'C:\\COM9', 'C:\\a?b',
                     'C:\\a\x00b', 'C:\\a\nb'):
            with self.subTest(path=path):
                self.assertIsNotNone(pd.windows_path_issue(path))

    def test_reparse_takes_precedence_over_regular_type(self):
        for mode in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK):
            with patch.object(os, 'lstat', return_value=SimpleNamespace(
                    st_mode=mode, st_file_attributes=0x400)):
                self.assertEqual(pd.classify_node('unused'), 'reparse')

    def test_metadata_only_and_errors(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / '合成.txt'
            path.write_bytes(b'\xef\xbb\xbfsynthetic\r\n')
            before = path.read_bytes()
            self.assertEqual(pd.classify_node(root), 'directory')
            self.assertEqual(pd.classify_node(path), 'file')
            self.assertEqual(path.read_bytes(), before)
        with patch.object(os, 'lstat', side_effect=FileNotFoundError):
            self.assertEqual(pd.classify_node('unused'), 'absent')
        with patch.object(os, 'lstat', side_effect=PermissionError):
            self.assertEqual(pd.classify_node('unused'), 'unreadable')
        with patch.object(os, 'lstat', side_effect=NotADirectoryError):
            self.assertEqual(pd.classify_node('unused'), 'unreadable')

    def test_syntax_never_authorizes_writes_or_admits_agents(self):
        result = pd.diagnose(windows_paths=['C:\\safe'])
        self.assertFalse(result['windows']['production_write_enabled'])
        self.assertEqual(set(result['windows']['agents']), set(paths.AGENT_ORDER))
        self.assertEqual(set(result['windows']['agents'].values()), {'not_admitted'})
        self.assertFalse(result['windows']['path_checks'][0]['write_authorized'])
        self.assertEqual(result['changes'], [])

    def test_existing_production_guards_still_reject_windows(self):
        with patch.object(sys, 'platform', 'win32'):
            with self.assertRaises(ValueError):
                user_install.plan_install({})
            with self.assertRaises(ValueError):
                upgrade._plan({})
        with self.assertRaises(paths.PathsError):
            paths.select_platform(paths.load_agents_table(), 'windows')


if __name__ == '__main__':
    unittest.main()
