"""0.1.1 -> 0.1.2 candidate upgrade: entries='preserve', contract unchanged.

The 0.1.1 predecessor and the 0.1.2 target are both real release identities,
rebuilt byte-exact from read-only Git history (ls-tree/cat-file, no invented
identity and never the evolving worktree). The 0.1.2 target is the committed
candidate 0f690ef with its real commit SHA and tree hash. The install/upgrade
kernel is real throughout; only executor detection uses synthetic facts, and
no real HOME, client or CK is touched.

Both historical source and producer/target kernels are isolated fixed exports.
The moving new-layout candidate is never used as an old release payload.
"""
import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from agm_core import detect, legacy_import as legacy, registry, upgrade
from agm_core import user_install as install, user_entries, versions

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release012_cli', REPO/'scripts/install.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)

PREDECESSOR = {
    'url': 'https://github.com/vincent4j/mem-sharing',
    'commit': '04c32e24b9ab9504514908f2368cddca4356e478',
    'tree_sha256': '15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179',
}
# Frozen 0.1.2 candidate payload: committed 0f690ef with its real SHA/tree,
# never the working tree.
TARGET_012 = {
    'commit': '0f690ef7aabf747a23bacc7662c19bee34c4bf52',
    'tree_sha256': '1fb1e199c992e07747bbf031fcb83cd74d2b85b5c9c491cda7d2836fca1dd353',
}
LEGACY_SHIPPED = ('SKILL.md', 'README.md', 'INSTALL.md', 'llms.txt')  # 0.1.1 manifest rule


def _legacy_manifest_rule(name):
    if name in LEGACY_SHIPPED or name.startswith('scripts/'):
        return name != 'scripts/registry.json' and not name.startswith(('scripts/backups/', 'scripts/.agm.lock/'))
    return False


def _git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True).stdout


def _export(root, entries):
    """entries: [(git_mode, path, blob)] -> byte-exact export preserving mode."""
    files = {}
    for mode, rel, blob in entries:
        raw = _git('cat-file', 'blob', blob)
        path = root/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o755 if mode == '100755' else 0o644)
        files[rel] = legacy.digest(raw)
    return files


class Release012UpgradeTests(InstallFixture):
    def setUp(self):
        super().setUp()
        # 0.1.1 predecessor: the real 27-file release, byte-exact from history.
        records = []
        for record in _git('ls-tree', '-rz', PREDECESSOR['commit']).decode().split('\0'):
            if record:
                meta, path = record.split('\t', 1)
                mode, kind, blob = meta.split()
                if kind == 'blob' and _legacy_manifest_rule(path):
                    records.append((mode, path, blob))
        self.assertEqual(len(records), 27)
        self.prev_root = self.area/'release-011'
        self.prev_files = _export(self.prev_root, records)
        source11 = {'root': str(self.prev_root), 'url': PREDECESSOR['url'],
                    'commit': PREDECESSOR['commit'], 'version': '0.1.1', 'files': self.prev_files}

        # Synthetic WB entry analogous to the real-machine 0.1.1 baseline shape
        # (private own text plus a CK block predating the machine product).
        # The CK block bytes here are synthetic test data, not a real CK block.
        self.private_wb = (b'private WB rules\r\n'
                           b'<!-- context-keeper:workbuddy:start -->\nprivate CK block\n'
                           b'<!-- context-keeper:workbuddy:end -->\n')
        entry = self.home/'.workbuddy/MEMORY.md'
        entry.parent.mkdir(parents=True)
        entry.write_bytes(self.private_wb)

        # Synthetic detection facts only; install/upgrade kernels stay real.
        self.codex()
        facts = detect.detect_agents(self.config, None, home=str(self.home),
                                     search_paths=self.request['search_paths'], app_directories=[])
        facts['agents']['workbuddy'] = copy.deepcopy(facts['agents']['codex'])
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', return_value=facts).start()

        self.req11 = dict(self.request, source=source11, agents=['codex', 'workbuddy'],
                          operation_id='install-011')
        from frozen_kernel_fixture import Kernel
        predecessor_kernel = Kernel(self.prev_root)
        predecessor_install = predecessor_kernel.module('user_install')
        predecessor_detect = predecessor_kernel.module('detect')
        patch.object(predecessor_detect, 'detect_agents', return_value=facts).start()
        done = predecessor_install.execute_install(predecessor_install.plan_install(self.req11), approved(
            predecessor_install.plan_install(self.req11)), request=self.req11)
        self.assertEqual(done['status'], 'completed', done)
        self.user_entries_before = {
            '.workbuddy/MEMORY.md': (self.home/'.workbuddy/MEMORY.md').read_bytes(),
            '.codex/AGENTS.md': (self.home/'.codex/AGENTS.md').read_bytes(),
            'memories/MEMORY.md': (self.runtime.root/'memories/MEMORY.md').read_bytes(),
        }

        # 0.1.2 target: byte-exact export of the committed 0.1.2 candidate
        # (30 files from 0f690ef), frozen so later worktree edits cannot
        # masquerade as the historical 0.1.2 release payload.
        records = []
        for record in _git('ls-tree', '-rz', TARGET_012['commit']).decode().split('\0'):
            if record:
                meta, path = record.split('\t', 1)
                mode, kind, blob = meta.split()
                if kind == 'blob' and cli._managed_source(path):
                    records.append((mode, path, blob))
        self.assertEqual(len(records), 30)
        self.next_root = self.area/'release-012'
        self.next_files = _export(self.next_root, records)
        from frozen_kernel_fixture import bind
        bind(self, globals(), self.next_root)
        self.next_source = {'root': str(self.next_root), 'url': PREDECESSOR['url'],
                            'commit': TARGET_012['commit'], 'version': '0.1.2',
                            'files': self.next_files}
        checked, _ = install._source(dict(source=self.next_source))
        self.target_tree = checked['tree_sha256']
        self.assertEqual(self.target_tree, TARGET_012['tree_sha256'])
        self.before = {'schema_version': 3, 'product_structure_version': 1,
                       'product_code_version': '0.1.1', 'source': dict(PREDECESSOR)}
        self.after = {'schema_version': 3, 'product_structure_version': 1,
                      'product_code_version': '0.1.2',
                      'source': {'url': PREDECESSOR['url'], 'commit': TARGET_012['commit'],
                                 'tree_sha256': self.target_tree}}
        self.req12 = dict(self.request, source=self.next_source, agents=None,
                          operation_id='upgrade-012',
                          conversions=[{'before': self.before, 'after': self.after,
                                        'direction': 'upgrade', 'entries': 'preserve'}])

    def product(self):
        return json.loads(self.runtime.registry.read_bytes())['product']

    def code_manifest(self):
        return json.loads((self.runtime.code/'.agm-code-manifest.json').read_bytes())

    def snapshot(self, root=None):
        root = root or self.home
        return {str(p.relative_to(root)): (p.lstat().st_mode, p.read_bytes() if p.is_file() else None)
                for p in [root, *root.rglob('*')] if not p.is_symlink()}

    def assert_user_bytes_untouched(self):
        after = {'.workbuddy/MEMORY.md': (self.home/'.workbuddy/MEMORY.md').read_bytes(),
                 '.codex/AGENTS.md': (self.home/'.codex/AGENTS.md').read_bytes(),
                 'memories/MEMORY.md': (self.runtime.root/'memories/MEMORY.md').read_bytes()}
        self.assertEqual(after, self.user_entries_before)

    def test_predecessor_identity_and_contract_chain_bind(self):
        # The 27-file export reproduces the real machine 0.1.1 source identity.
        source, _ = install._source(dict(source={'root': str(self.prev_root), 'url': PREDECESSOR['url'],
                                                 'commit': PREDECESSOR['commit'], 'version': '0.1.1',
                                                 'files': self.prev_files}))
        self.assertEqual(source['tree_sha256'], PREDECESSOR['tree_sha256'])
        self.assertEqual(self.product()['source'], {k: PREDECESSOR[k] for k in ('url', 'commit', 'tree_sha256')})
        # 0.1.1 sits exactly on the reviewed contract chain's after side...
        self.assertEqual(self.prev_files['scripts/agents.json'],
                         upgrade.WORKBUDDY_ENTRY_CONVERSION['after_contract']['scripts/agents.json'])
        self.assertEqual(self.prev_files['scripts/agm_core/user_entries.py'],
                         upgrade.WORKBUDDY_ENTRY_CONVERSION['after_contract']['scripts/agm_core/user_entries.py'])
        # ...and 0.1.2 keeps both contract bytes identical, so preserve is the only route.
        for name in upgrade._ENTRY_CONTRACT_NAMES:
            self.assertEqual(self.next_files[name], self.prev_files[name], name)

    def test_preserve_upgrade_assembles_docs_and_preserves_user_bytes(self):
        preview_before = self.snapshot()
        plan = cli.plan_machine(self.req12)
        # Existing connected agents have no entry difference; default still scans all installed agents.
        self.assertIsNone(plan['entry_plan'])
        # Historical .1.2 producer has no current default entry stage on preserve.
        self.assertFalse(plan['entry_requested'])
        self.assertEqual(plan['channel'], 'upgrade')
        # The frozen .1.2 CLI defaulted to Codex; current all-installed routing
        # remains covered by current-kernel installer/layout tests.
        self.assertEqual(plan['effective_agents'], ['codex'])
        self.assertEqual(preview_before, self.snapshot())  # preview is read-only

        done = cli.execute_machine(plan, approved(plan), request=self.req12)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(done['versions']['product_code_version'], '0.1.2')
        for rel in ('DESIGN.md', 'docs/architecture.md', 'docs/operations.md'):
            self.assertEqual((self.runtime.code/rel).read_bytes(), (self.next_root/rel).read_bytes(), rel)
        self.assertEqual(self.product()['product_code_version'], '0.1.2')
        self.assertEqual(self.product()['product_structure_version'], 1)
        self.assertEqual(self.product()['source']['tree_sha256'], self.target_tree)
        self.assertEqual(self.code_manifest()['source']['tree_sha256'], self.target_tree)
        self.assertEqual(len(self.code_manifest()['files']), 30)
        # The code manifest carries source/files only; the version lives in V and
        # in the version store's release.json.
        release = json.loads((self.runtime.code.parent/'mem-sharing-versions/0.1.2'/
                              self.target_tree/'release.json').read_bytes())
        self.assertEqual(release['versions']['product_code_version'], '0.1.2')
        self.assert_user_bytes_untouched()

        # Same-version replay is a read-only noop that still cannot touch entries.
        stable = self.snapshot()
        same = cli.plan_machine(self.req12)
        self.assertTrue(same['plan']['noop'])
        self.assertIsNone(same['entry_plan'])
        self.assertEqual(cli.execute_machine(same, approved(same), request=self.req12)['status'], 'completed')
        self.assertEqual(stable, self.snapshot())
        self.assert_user_bytes_untouched()

    def test_conversion_gate_rejects_drift_without_writes(self):
        def rejected(req, message=None):
            before = self.snapshot()
            with self.assertRaises(ValueError) as ctx:
                cli.plan_machine(req)
            if message:
                self.assertIn(message, str(ctx.exception))
            self.assertEqual(before, self.snapshot())

        rejected(dict(self.req12, conversions=[]))
        for path, value in ((('conversions', 0, 'before', 'source', 'commit'), 'e'*40),
                            (('conversions', 0, 'before', 'product_code_version'), '0.1.0'),
                            (('conversions', 0, 'after', 'source', 'tree_sha256'), 'e'*64),
                            (('conversions', 0, 'after', 'product_code_version'), '0.1.3'),
                            (('conversions', 0, 'direction'), 'rollback')):
            req = copy.deepcopy(self.req12)
            at = req
            for key in path[:-1]:
                at = at[key]
            at[path[-1]] = value
            rejected(req)
        doubled = copy.deepcopy(self.req12)
        doubled['conversions'].append(copy.deepcopy(doubled['conversions'][0]))
        rejected(doubled)

        # A changed target contract is not a preserve release even if asked to be.
        drift_root = self.area/'release-012-drift'
        drift_files = dict(self.next_files)
        for rel, digest in self.next_files.items():
            path = drift_root/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.next_root/rel).read_bytes())
            path.chmod(0o755 if (self.next_root/rel).stat().st_mode & 0o111 else 0o644)
        drifted = (drift_root/'scripts/agm_core/user_entries.py')
        drifted.write_bytes(drifted.read_bytes() + b'# drift\n')
        drift_files['scripts/agm_core/user_entries.py'] = legacy.digest(drifted.read_bytes())
        drift_source = dict(self.next_source, root=str(drift_root), files=drift_files)
        checked, _ = install._source(dict(source=drift_source))
        req = dict(self.req12, source=drift_source)
        req['conversions'] = [dict(self.req12['conversions'][0],
                                   after=dict(self.after, source={'url': PREDECESSOR['url'],
                                                                  'commit': TARGET_012['commit'],
                                                                  'tree_sha256': checked['tree_sha256']}))]
        rejected(req, 'no handler for changed entry contract')

        # Exact approval tampering stays a zero-write rejection.
        plan = cli.plan_machine(self.req12)
        before = self.snapshot()
        for bad in ({}, dict(approved(plan), extra=True), dict(approved(plan), operation_id='other')):
            with self.assertRaises(ValueError):
                cli.execute_machine(plan, bad, request=self.req12)
            self.assertEqual(before, self.snapshot())

    def test_interrupted_upgrade_continue_rollback_and_finish_state(self):
        plan = cli.plan_machine(self.req12)
        inner = plan['plan']

        # Interrupt before the code phase: pending work refuses new plans.
        def halt(event, path):
            if event == 'before_phase:code':
                raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(inner, approved(inner), request=self.req12, hook=halt)
        with self.assertRaises(ValueError):
            cli.plan_machine(self.req12)
        self.assert_user_bytes_untouched()

        # Continue finishes the approved operation to the same end state.
        recovery = upgrade.plan_recovery(inner['journal'], action='continue')
        done = upgrade.recover_upgrade(recovery, approved(recovery))
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(self.product()['product_code_version'], '0.1.2')
        for rel in ('DESIGN.md', 'docs/architecture.md', 'docs/operations.md'):
            self.assertTrue((self.runtime.code/rel).is_file(), rel)
        self.assert_user_bytes_untouched()
        # finish-only: a committed journal is closed to every recovery action.
        with self.assertRaises(ValueError):
            upgrade.plan_recovery(inner['journal'], action='rollback')
        same = cli.plan_machine(self.req12)
        self.assertTrue(same['plan']['noop'])

    def test_interrupted_upgrade_rollback_restores_011(self):
        plan = cli.plan_machine(self.req12)
        inner = plan['plan']

        # Halt after the code phase: the three new docs are already assembled.
        def halt(event, path):
            if event == 'after_phase:code':
                raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(inner, approved(inner), request=self.req12, hook=halt)
        for rel in ('DESIGN.md', 'docs/architecture.md', 'docs/operations.md'):
            self.assertTrue((self.runtime.code/rel).is_file(), rel)

        recovery = upgrade.plan_recovery(inner['journal'], action='rollback')
        done = upgrade.recover_upgrade(recovery, approved(recovery))
        self.assertEqual(done['status'], 'rolled_back', done)
        self.assertEqual(self.product()['product_code_version'], '0.1.1')
        self.assertEqual(self.product()['source'], {k: PREDECESSOR[k] for k in ('url', 'commit', 'tree_sha256')})
        self.assertEqual(len(self.code_manifest()['files']), 27)
        for rel in ('DESIGN.md', 'docs/architecture.md', 'docs/operations.md'):
            self.assertFalse((self.runtime.code/rel).exists(), rel)
        for rel, digest in self.prev_files.items():
            self.assertEqual(legacy.digest((self.runtime.code/rel).read_bytes()), digest, rel)
        self.assert_user_bytes_untouched()
        # The finished operation's bootstrap blocks the same operation id; a fresh
        # operation upgrades cleanly again.
        with self.assertRaises(ValueError):
            cli.plan_machine(self.req12)
        retry = cli.plan_machine(dict(self.req12, operation_id='upgrade-012-retry'))
        self.assertFalse(retry['plan']['noop'])
        self.assertEqual(cli.execute_machine(retry, approved(retry),
                                             request=dict(self.req12, operation_id='upgrade-012-retry'))['status'],
                         'completed')

    def test_committed_v_is_authoritative_finish_only(self):
        plan = cli.plan_machine(self.req12)
        inner = plan['plan']

        # Halt right after V is committed, before finalization.
        def halt(event, path):
            if event == 'after_registry_commit':
                raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(inner, approved(inner), request=self.req12, hook=halt)
        self.assertEqual(self.product()['product_code_version'], '0.1.2')

        # A committed V refuses rollback: finish only, then a separately
        # approved release rollback.
        with self.assertRaises(ValueError) as ctx:
            upgrade.plan_recovery(inner['journal'], action='rollback')
        self.assertIn('Committed V is authoritative', str(ctx.exception))
        self.assertEqual(self.product()['product_code_version'], '0.1.2')

        recovery = upgrade.plan_recovery(inner['journal'], action='continue')
        done = upgrade.recover_upgrade(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'], done)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(self.product()['product_code_version'], '0.1.2')
        self.assertFalse(upgrade.marker(self.runtime).exists())
        for rel in ('DESIGN.md', 'docs/architecture.md', 'docs/operations.md'):
            self.assertTrue((self.runtime.code/rel).is_file(), rel)
        self.assert_user_bytes_untouched()
        same = cli.plan_machine(self.req12)
        self.assertTrue(same['plan']['noop'])

    def test_third_party_edit_blocks_recovery_and_preserves_scene(self):
        plan = cli.plan_machine(self.req12)
        inner = plan['plan']

        def halt(event, path):
            if event == 'after_phase:code':
                raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(inner, approved(inner), request=self.req12, hook=halt)

        # A third-party byte edit inside the staged code tree must stop recovery
        # and stay untouched: no silent rollback, no silent overwrite.
        design = self.runtime.code/'DESIGN.md'
        self.assertTrue(design.is_file())
        third_party = b'third party edit\n'
        design.write_bytes(design.read_bytes() + third_party)
        with self.assertRaises(ValueError):
            upgrade.plan_recovery(inner['journal'], action='continue')
        self.assertIn(third_party, design.read_bytes())
        self.assertEqual(self.product()['product_code_version'], '0.1.1')
        self.assert_user_bytes_untouched()


if __name__ == '__main__':
    unittest.main()
