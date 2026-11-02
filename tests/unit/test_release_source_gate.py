"""Source-stage gate: stale generated release artifacts must not pose as clean S.

The dev sync test tolerates a non-empty identity while it matches an existing
generated manifest, so the source gate itself must reject an old release
descriptor, an old Paseo payload tree and any non-sentinel identity. The
release stage keeps the opposite real-identity checks (separate contrast
tests); synthetic Git only, no node run, no host, no network.
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

_spec = importlib.util.spec_from_file_location('release_gate_cli', REPO/'tools/plugin-release/check.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

from agm_core import plugin_release as release  # noqa: E402
from test_plugin_release import ReleaseFixture  # noqa: E402


class SourceGateFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()/'repo'; self.repo.mkdir(parents=True)
        self.git('init', '-q'); self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.identity = self.repo/release.IDENTITY
        self.identity.parent.mkdir(parents=True, exist_ok=True)
        self.identity.write_bytes(release._identity_bytes(''))
        self.head = self.commit('clean source S')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True,
                              check=True, env={'GIT_CONFIG_NOSYSTEM': '1', 'PATH': '/usr/bin:/bin'}).stdout.decode().strip()

    def commit(self, message):
        self.git('add', '.'); self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def rewrite_identity(self, digest):
        self.identity.write_bytes(release._identity_bytes(digest))
        return self.commit('identity ' + (digest or 'sentinel'))


class CleanSourceGateTests(SourceGateFixture):
    def test_clean_s_with_sentinel_passes(self):
        gate._verify_clean_source(self.repo, self.head)

    def test_old_root_manifest_is_rejected(self):
        manifest = self.repo/release.ROOT_MANIFEST; manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(b'{}')
        commit = self.commit('old release descriptor')
        with self.assertRaisesRegex(ValueError, 'release/core-release.json'):
            gate._verify_clean_source(self.repo, commit)

    def test_old_paseo_payload_files_are_rejected(self):
        payload = self.repo/release.PAYLOAD/'core/README.md'
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(b'stale payload bytes')
        commit = self.commit('old payload tree')
        with self.assertRaisesRegex(ValueError, 'plugins/paseo/payload'):
            gate._verify_clean_source(self.repo, commit)

    def test_nonempty_identity_is_rejected_even_when_manifest_backed(self):
        # The dev sync test accepts a real digest matching an old manifest; the
        # source gate must not: any non-sentinel identity is R-only.
        commit = self.rewrite_identity('d5eb5f65f9c0f0e08ae08b272be5872cd11f2f6a2538ee515ad80d725a8270fe')
        with self.assertRaisesRegex(ValueError, 'empty dev sentinel'):
            gate._verify_clean_source(self.repo, commit)

    def test_missing_identity_is_rejected(self):
        self.identity.unlink()
        commit = self.commit('identity removed')
        with self.assertRaisesRegex(ValueError, 'empty dev sentinel'):
            gate._verify_clean_source(self.repo, commit)

    def test_identity_hidden_worktree_drift_is_rejected(self):
        # A non-sentinel working-tree identity hidden behind assume-unchanged
        # keeps git status clean; the gate must compare against the pinned blob.
        self.git('update-index', '--assume-unchanged', release.IDENTITY)
        self.identity.write_bytes(release._identity_bytes('f'*64))
        with self.assertRaisesRegex(ValueError, 'empty dev sentinel'):
            gate._verify_clean_source(self.repo, self.head)

    def _ignore(self, *patterns):
        exclude = self.repo/'.git/info/exclude'
        exclude.write_text(exclude.read_text() + '\n' + '\n'.join(patterns) + '\n')

    def _assert_git_clean(self):
        self.assertEqual(subprocess.run(
            ['git', '-C', str(self.repo), 'status', '--porcelain', '--untracked-files=all'],
            capture_output=True, text=True, check=True,
            env={'GIT_CONFIG_NOSYSTEM': '1', 'PATH': '/usr/bin:/bin'}).stdout, '')

    def test_ignored_root_manifest_is_rejected_despite_clean_status(self):
        self._ignore('/release/core-release.json')
        manifest = self.repo/release.ROOT_MANIFEST
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(b'{"stale":true}\n')
        self._assert_git_clean()
        with self.assertRaisesRegex(ValueError, 'ignored or untracked.*release/core-release.json'):
            gate._verify_clean_source(self.repo, self.head)

    def test_ignored_payload_files_are_rejected_despite_clean_status(self):
        self._ignore('/plugins/paseo/payload/')
        payload = self.repo/release.PAYLOAD/'core/stray.py'
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(b'# ignored stale payload\n')
        self._assert_git_clean()
        with self.assertRaisesRegex(ValueError, 'ignored or untracked.*plugins/paseo/payload'):
            gate._verify_clean_source(self.repo, self.head)

    def test_ignored_empty_payload_directory_is_rejected(self):
        self._ignore('/plugins/paseo/payload/')
        (self.repo/release.PAYLOAD).mkdir(parents=True)
        self._assert_git_clean()
        with self.assertRaisesRegex(ValueError, 'plugins/paseo/payload'):
            gate._verify_clean_source(self.repo, self.head)

    def test_ignored_payload_symlink_and_dangling_link_are_rejected(self):
        real_dir = self.repo.parent/'external-payload'
        real_dir.mkdir()
        self.addCleanup(lambda: real_dir.rmdir())
        # No-slash pattern also ignores non-directory nodes (links); the
        # directory pattern alone would leave a dangling link visible.
        self._ignore('/plugins/paseo/payload/', '/plugins/paseo/payload')
        payload = self.repo/release.PAYLOAD
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.symlink_to(real_dir)
        self._assert_git_clean()
        with self.assertRaisesRegex(ValueError, 'plugins/paseo/payload'):
            gate._verify_clean_source(self.repo, self.head)
        payload.unlink()
        payload.symlink_to(self.repo.parent/'absent-target')  # dangling link
        self._assert_git_clean()
        with self.assertRaisesRegex(ValueError, 'plugins/paseo/payload'):
            gate._verify_clean_source(self.repo, self.head)


class SourceReleaseStageContrastTests(ReleaseFixture):
    """Source tightening must not weaken the release stage's real identity."""

    def test_old_artifacts_fail_source_gate_but_release_delivery_still_passes(self):
        # Synthetic R carries manifest + payload + concrete identity exactly
        # like the ca26e66 baseline: source gate rejects, R verifier accepts.
        with self.assertRaisesRegex(ValueError, 'old generated release artifacts'):
            gate._verify_clean_source(self.repo, self.r)
        self.assertEqual(self.delivery()['commit'], self.r)
        self.assertEqual(self.identity_digest(), self.generated['manifest_sha256'])

    def test_cleaned_source_tree_passes_source_gate_but_not_release_stage(self):
        self.git('rm', '-q', release.ROOT_MANIFEST)
        self.git('rm', '-q', '-r', release.PAYLOAD)
        identity = self.repo/release.IDENTITY
        identity.write_bytes(release._identity_bytes(''))
        clean = self.commit('restore clean source state')
        gate._verify_clean_source(self.repo, clean)
        with self.assertRaisesRegex(ValueError, 'release descriptor'):
            release.checkout_delivery(self.repo, clean)

    def identity_digest(self):
        import re
        text = (self.repo/release.IDENTITY).read_text()
        return re.search(r"SHA256 = '([^']*)'", text).group(1)
