"""0.1.4 -> 0.1.5 native-entry-refresh upgrade: real predecessor kernel.

The 0.1.4 predecessor is the real release identity d14a3c0d (32 managed files,
tree 5f65647a…, installed from the machine's local-checkout durable source).
The baseline HOME is installed by the ACTUAL 0.1.4 kernel exported byte-exact
from read-only Git history, so entries and the public layout are genuinely
0.1.4-shaped; the 0.1.5 target is the current worktree payload (release
freezing replaces it with committed identities). Entry/public template refresh
after the code upgrade goes through the existing entry assembly plus
migrate-policy with private bytes and fingerprints preserved. Synthetic
HOME/detection only; no real HOME, client or Context Keeper is touched.
"""
import copy
import importlib
import importlib.util
import json
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import approved  # noqa: E402
from test_uninstall import approval as migration_approval  # noqa: E402
from agm_core import detect, legacy_import as legacy, paths, policy_migration  # noqa: E402
from agm_core import upgrade, user_entries, user_install as install  # noqa: E402
from agm_core import versions  # noqa: E402

spec = importlib.util.spec_from_file_location('release014_cli', REPO/'scripts/install.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

PREDECESSOR_014 = {
    'url': 'local-checkout:file:///Users/vincent4j/.local/share/mem-sharing-upgrade-sources/d14a3c0d121576cc7dbcab0c55ef4a680985f84e',
    'commit': 'd14a3c0d121576cc7dbcab0c55ef4a680985f84e',
    'tree_sha256': '5f65647a0b496bed48feadae67107a968fc086173e9766db74dc5b01fe80dfca',
}
LEGACY_AGENTS = ('codex', 'claude', 'workbuddy', 'dsh', 'zcode')  # the real 0.1.4 registration surface


def _git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True).stdout


def _export(root, commit):
    files = {}
    for record in _git('ls-tree', '-rz', '--full-tree', commit).decode().split('\0'):
        if not record:
            continue
        meta, path = record.split('\t', 1)
        mode, kind, blob = meta.split()
        if kind != 'blob' or not cli._managed_source(path):
            continue
        raw = _git('cat-file', 'blob', blob)
        target = root/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if mode == '100755' else 0o644)
        files[path] = legacy.digest(raw)
    return files


def _export_target(root):
    files = {}
    for path in sorted(REPO.rglob('*')):
        if (not path.is_file() or path.is_symlink() or '.git' in path.parts
                or '__pycache__' in path.parts or path.name == '.DS_Store'):
            continue
        rel = str(path.relative_to(REPO))
        if not cli._managed_source(rel):
            continue
        (root/rel).parent.mkdir(parents=True, exist_ok=True)
        (root/rel).write_bytes(path.read_bytes())
        (root/rel).chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        files[rel] = legacy.digest(path.read_bytes())
    return files


def _load_old_kernel(root):
    name = 'agm_old_' + uuid.uuid4().hex
    init = root/'scripts/agm_core/__init__.py'
    pkg_spec = importlib.util.spec_from_file_location(
        name, init, submodule_search_locations=[str(root/'scripts/agm_core')])
    package = importlib.util.module_from_spec(pkg_spec)
    sys.modules[name] = package
    pkg_spec.loader.exec_module(package)
    return name


class Release014UpgradeTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        from frozen_kernel_fixture import export, bind, FROZEN_NATIVE
        self.fixed_kernel_root = self.area/'fixed-native-kernel'
        export(self.fixed_kernel_root, FROZEN_NATIVE)
        bind(self, globals(), self.fixed_kernel_root)
        self.home = self.area/'home'
        self.home.mkdir()
        self.runtime = install._runtime({'home': str(self.home)})
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')

        # Real 0.1.4 export; the managed set reproduces the machine's tree.
        self.prev_root = self.area/'release-014'
        self.prev_root.mkdir()
        self.prev_files = _export(self.prev_root, PREDECESSOR_014['commit'])
        self.assertEqual(len(self.prev_files), 32)
        checked, _ = install._source(dict(source=self._prev_source()))
        self.assertEqual(checked['tree_sha256'], PREDECESSOR_014['tree_sha256'])

        # Baseline HOME installed by the actual 0.1.4 kernel.
        self._old_name = _load_old_kernel(self.prev_root)
        old_install = importlib.import_module(self._old_name + '.user_install')
        old_detect = importlib.import_module(self._old_name + '.detect')
        old_paths = importlib.import_module(self._old_name + '.paths')
        old_config = old_paths.select_platform(old_paths.load_agents_table(), 'darwin')
        self.bin_dir = self.area/'bin'
        self.bin_dir.mkdir()
        package = self.area/'npm'
        (package/'bin').mkdir(parents=True)
        exe = package/'bin/codex'
        exe.write_text('#!/bin/sh\n')
        exe.chmod(0o755)
        (package/'package.json').write_text(json.dumps(
            {'name': '@openai/codex', 'version': '1.0', 'bin': {'codex': 'bin/codex'}}))
        (self.bin_dir/'codex').symlink_to(exe)
        facts = old_detect.detect_agents(old_config, None, home=str(self.home),
                                         search_paths=[str(self.bin_dir)], app_directories=[])
        for agent in LEGACY_AGENTS[1:]:
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        self.addCleanup(patch.stopall)
        patch.object(old_detect, 'detect_agents', return_value=facts).start()

        self.private_wb = (b'private WB rules\r\n'
                           b'<!-- context-keeper:workbuddy:start -->\nprivate CK block\n'
                           b'<!-- context-keeper:workbuddy:end -->\n')
        wb_entry = self.home/'.workbuddy/MEMORY.md'
        wb_entry.parent.mkdir()
        wb_entry.write_bytes(self.private_wb)
        req_old = {'home': str(self.home), 'platform_config': old_config,
                   'agents': list(LEGACY_AGENTS), 'search_paths': [str(self.bin_dir)],
                   'app_directories': [], 'operation_id': 'install-014',
                   'source': self._prev_source()}
        plan = old_install.plan_install(req_old)
        done = old_install.execute_install(plan, approved(plan), request=req_old)
        self.assertEqual(done['status'], 'completed', done)
        # Baseline shapes are genuinely 0.1.4 (frozen legacy templates).
        self.assertEqual(self.product()['source'], PREDECESSOR_014)
        self.assertEqual((self.home/'.codex/AGENTS.md').read_bytes(),
                         policy_migration.legacy('codex', self.runtime))
        index = (self.runtime.root/'memories/MEMORY.md').read_bytes()
        self.assertTrue(index.startswith('# 公共记忆\n\n'.encode()
                         + policy_migration.legacy('contract', self.runtime)))
        self.assertEqual((self.runtime.root/'memories/topics/使用约定.md').read_bytes(),
                         policy_migration.legacy('topic', self.runtime))

        # 0.1.5 target: current worktree payload; after identity comes only
        # from this external request (the frozen handler never pins it).
        self.next_root = self.area/'release-015'
        self.next_root.mkdir()
        self.next_files = export(self.next_root, FROZEN_NATIVE)
        self.assertIn('scripts/agm_core/policy_migration.py', self.next_files)
        self.assertIn('docs/uninstall-design.md', self.next_files)
        self.next_source = {'root': str(self.next_root), 'url': 'local-checkout:'+self.next_root.as_uri(),
                            'commit': FROZEN_NATIVE, 'version': '0.1.5', 'files': self.next_files}
        target_checked, _ = install._source(dict(source=self.next_source))
        self.target_tree = target_checked['tree_sha256']
        self.req = self.request()

        # Current-kernel detection mirrors the real machine: the legacy five
        # stay installed, OpenCode is newly installed, Claude detects unknown.
        real = detect.detect_agents
        def installed(*args, **kwargs):
            report = real(*args, **kwargs)
            for name in ('codex', 'workbuddy', 'dsh', 'zcode', 'opencode'):
                report['agents'][name].update(status='installed', summary='synthetic fixture')
            return report
        patch.object(detect, 'detect_agents', side_effect=installed).start()

    # ---- helpers ------------------------------------------------------------

    def _prev_source(self):
        return {'root': str(self.prev_root), 'url': PREDECESSOR_014['url'],
                'commit': PREDECESSOR_014['commit'], 'version': '0.1.4',
                'files': self.prev_files}

    def request(self, **overrides):
        base = {'home': str(self.home), 'platform_config': self.config, 'agents': None,
                'search_paths': [str(self.bin_dir)], 'app_directories': [],
                'operation_id': 'upgrade-015', 'source': self.next_source,
                'conversions': [self.conversion()]}
        base.update(overrides)
        return base

    def conversion(self):
        return {'before': dict(schema_version=3, product_structure_version=1,
                               product_code_version='0.1.4', source=dict(PREDECESSOR_014)),
                'after': dict(schema_version=3, product_structure_version=1,
                              product_code_version='0.1.5',
                              source={'url': self.next_source['url'], 'commit': self.next_source['commit'],
                                      'tree_sha256': self.target_tree}),
                'direction': 'upgrade', 'entries': upgrade.NATIVE_ENTRY_CONVERSION}

    def product(self):
        return json.loads(self.runtime.registry.read_bytes())['product']

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in [self.home, *self.home.rglob('*')]}

    def plan(self, **overrides):
        request = self.request(**overrides)
        return cli.plan_machine(request), request

    # ---- conversion chain ---------------------------------------------------

    def test_exact_conversion_upgrades_code_and_binds_entry_plan(self):
        before = self.snapshot()
        plan, request = self.plan()
        self.assertEqual(plan['channel'], 'upgrade')
        self.assertFalse(plan['plan']['noop'])
        self.assertEqual(plan['entry_plan']['effective'],
                         ['codex', 'workbuddy', 'dsh', 'zcode', 'opencode'])
        operations = {(c['path'], c['operation']) for c in plan['entry_plan']['changes']}
        self.assertIn((str(self.home/'.config/opencode/AGENTS.md'), 'create'), operations)
        self.assertIn((str(self.home/'.workbuddy/MEMORY.md'), 'update'), operations)
        self.assertEqual(before, self.snapshot())  # preview is read-only

        done = cli.execute_machine(plan, approved(plan), request=request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(done['agents']['connected'], ['codex', 'workbuddy', 'dsh', 'zcode', 'opencode'])
        self.assertEqual(done['agents']['unknown'], ['claude'])
        product = self.product()
        self.assertEqual(product['product_code_version'], '0.1.5')
        self.assertEqual(product['source']['tree_sha256'], self.target_tree)
        manifest = json.loads((self.runtime.code/'.agm-code-manifest.json').read_bytes())
        self.assertEqual(manifest['source']['tree_sha256'], self.target_tree)
        self.assertEqual(len(manifest['files']), len(self.next_files))
        release = json.loads((versions.root(self.runtime)/'0.1.5'/self.target_tree/'release.json').read_bytes())
        self.assertEqual(release['versions']['product_code_version'], '0.1.5')
        # New uninstall design ships with the upgrade; old five plus OpenCode.
        self.assertEqual((self.runtime.code/'docs/uninstall-design.md').read_bytes(),
                         (self.next_root/'docs/uninstall-design.md').read_bytes())
        opencode = (self.home/'.config/opencode/AGENTS.md').read_bytes()
        self.assertIn(str(self.runtime.root/'memories/MEMORY.md').encode(), opencode)
        # Entry assembly updated the workbuddy block only; native/claude blocks
        # stay at their registered 0.1.4 bytes for migrate-policy to refresh.
        wb = (self.home/'.workbuddy/MEMORY.md').read_bytes()
        self.assertTrue(wb.startswith(b'private WB rules\r\n'))
        self.assertIn(b'context-keeper:workbuddy', wb)
        self.assertEqual(wb.count(user_entries.WORKBUDDY_FALLBACK_TEXT.encode()), 1)
        self.assertEqual((self.home/'.codex/AGENTS.md').read_bytes(),
                         policy_migration.legacy('codex', self.runtime))
        result = done['result']
        self.assertEqual(result['entry_phase'], 'not_run_by_upgrade_core')
        self.assertIn('migrate-policy', result['entry_next_action'])

    def test_post_upgrade_migrate_policy_refreshes_templates_and_preserves_bytes(self):
        plan, request = self.plan()
        cli.execute_machine(plan, approved(plan), request=request)
        migration = policy_migration.preview(home=self.home)
        self.assertIn(str(self.home/'.claude/CLAUDE.md'), migration['files'])
        policy_migration.execute(migration_approval(policy_migration.view(migration)), home=self.home)
        index = (self.runtime.root/'memories/MEMORY.md').read_text()
        topic = (self.runtime.root/'memories/topics/使用约定.md').read_bytes()
        self.assertIn('卸载 memSharing', index)
        self.assertIn('自然语言卸载 memSharing', topic.decode())
        self.assertEqual(topic, user_entries.usage_convention_topic_text(self.runtime.code).encode())
        for agent in ('codex', 'dsh', 'zcode'):
            entry = self.home/paths.expand_path(self.config[agent]['user_entry'], home=str(self.home))
            self.assertIn(user_entries.native_public_source_block(agent, self.runtime.root/'memories/MEMORY.md'),
                          entry.read_bytes(), agent)
        claude = (self.home/'.claude/CLAUDE.md').read_bytes()
        self.assertIn(user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER,
                                               user_entries.CLAUDE_FALLBACK_TEXT), claude)
        wb = (self.home/'.workbuddy/MEMORY.md').read_bytes()
        self.assertTrue(wb.startswith(b'private WB rules\r\n'))
        self.assertIn(b'context-keeper:workbuddy', wb)
        self.assertEqual(policy_migration.preview(home=self.home)['files'], {})

    def test_replay_same_source_is_noop_and_same_version_other_source_rejected(self):
        plan, request = self.plan()
        cli.execute_machine(plan, approved(plan), request=request)
        stable = self.snapshot()
        same, _ = self.plan()
        self.assertTrue(same['plan']['noop'])
        self.assertIsNone(same['entry_plan'])
        self.assertEqual(cli.execute_machine(same, approved(same), request=self.request())['status'], 'completed')
        self.assertEqual(stable, self.snapshot())
        # Same version from a different source is not a legal upgrade.
        other = dict(self.next_source, commit='f'*40)
        other['files'] = {**self.next_files, 'README.md': legacy.digest(b'other bytes')}
        (self.next_root/'README.md').write_bytes(b'other bytes')
        req = self.request(source=other)
        req['conversions'][0]['after']['source']['commit'] = 'f'*40
        with self.assertRaisesRegex(ValueError, 'future|same-version'):
            cli.plan_machine(req)

    def test_gate_rejects_every_inexact_request_without_writes(self):
        def rejected(req, message=None):
            before = self.snapshot()
            with self.assertRaises(ValueError) as ctx:
                cli.plan_machine(req)
            if message:
                self.assertIn(message, str(ctx.exception))
            self.assertEqual(before, self.snapshot())

        rejected(self.request(conversions=[]))
        for path, value in ((('conversions', 0, 'before', 'source', 'commit'), 'f'*40),
                            (('conversions', 0, 'before', 'source', 'url'), 'local-checkout:file:///other'),
                            (('conversions', 0, 'before', 'source', 'tree_sha256'), 'f'*64),
                            (('conversions', 0, 'before', 'product_code_version'), '0.1.3'),
                            (('conversions', 0, 'after', 'source', 'tree_sha256'), 'f'*64),
                            (('conversions', 0, 'after', 'product_code_version'), '0.1.6'),
                            (('conversions', 0, 'direction'), 'rollback'),
                            (('conversions', 0, 'entries'), 'preserve'),
                            (('conversions', 0, 'entries'), {'type': 'public-memory-layout-v1'}),
                            (('conversions', 0, 'entries'), copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION))):
            req = self.request()
            at = req
            for key in path[:-1]:
                at = at[key]
            at[path[-1]] = value
            rejected(req)
        # A single-character contract edit inside the frozen entries dict.
        tampered = copy.deepcopy(upgrade.NATIVE_ENTRY_CONVERSION)
        tampered['after_contract']['scripts/agents.json'] = '0'*64
        req = self.request()
        req['conversions'][0]['entries'] = tampered
        rejected(req)
        doubled = self.request()
        doubled['conversions'].append(self.conversion())
        rejected(doubled)

    def test_drift_after_preview_invalidates_approval_without_extra_writes(self):
        plan, _ = self.plan()
        (self.home/'.workbuddy/MEMORY.md').write_bytes(self.private_wb + b'user edit\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            cli.execute_machine(plan, approved(plan), request=self.request())
        self.assertEqual(before, self.snapshot())

    def test_recovery_rollback_restores_014_and_continue_finishes_code_only(self):
        plan, request = self.plan()
        def interrupt(stage, path):
            if stage == 'after_code_replace':
                raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(plan['plan'], approved(plan['plan']), request=request, hook=interrupt)
        self.assertTrue((self.home/'.workbuddy/MEMORY.md').read_bytes().startswith(b'private WB rules\r\n'))
        launcher = Path(plan['plan']['bootstrap'])/'recover.py'
        result = subprocess.run([sys.executable, '-B', str(launcher), 'preview',
                                 plan['plan']['journal'], 'rollback'], capture_output=True, text=True, check=True)
        recovery = json.loads(result.stdout)
        approval_file = self.area/'rollback.json'
        approval_file.write_text(json.dumps(approved(recovery)))
        done = subprocess.run([sys.executable, '-B', str(launcher), 'apply', str(approval_file)],
                              capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(done.stdout)['status'], 'rolled_back')
        self.assertEqual(self.product()['product_code_version'], '0.1.4')
        self.assertEqual(self.product()['source'], PREDECESSOR_014)
        install._code_matches(self.runtime, self.product())
        # The rollback restores the full 0.1.4 baseline entry file: private
        # prefix plus its registered 0.1.4 managed block, byte for byte.
        self.assertTrue((self.home/'.workbuddy/MEMORY.md').read_bytes().startswith(self.private_wb))

        # Continue path commits code only; entry assembly needs a fresh approval.
        plan, request = self.plan(operation_id='upgrade-015-continue')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(plan['plan'], approved(plan['plan']), request=request, hook=interrupt)
        result = subprocess.run([sys.executable, '-B', str(launcher), 'preview',
                                 plan['plan']['journal'], 'continue'], capture_output=True, text=True, check=True)
        recovery = json.loads(result.stdout)
        approval_file = self.area/'continue.json'
        approval_file.write_text(json.dumps(approved(recovery)))
        done = subprocess.run([sys.executable, '-B', str(launcher), 'apply', str(approval_file)],
                              capture_output=True, text=True, check=True)
        finished = json.loads(done.stdout)
        self.assertEqual(finished['scope'], 'product_code')
        self.assertEqual(finished['entry_phase'], 'not_run_by_upgrade_core')
        self.assertEqual(self.product()['product_code_version'], '0.1.5')
        retry = cli.plan_machine(self.request())
        self.assertTrue(retry['plan']['noop'])
        self.assertTrue(retry['entry_plan'])
        self.assertEqual(cli.execute_machine(retry, approved(retry), request=self.request())['status'], 'completed')


class NativeEntryFixedGateTests(unittest.TestCase):
    """不打补丁的固定门禁回归:生产常量精确锚定真实前身/当前合同。"""

    def test_production_constants_pin_the_real_predecessor(self):
        self.assertEqual(upgrade.NATIVE_ENTRY_PREDECESSOR, PREDECESSOR_014)
        self.assertEqual(upgrade.NATIVE_ENTRY_TARGET_VERSION, '0.1.5')
        self.assertEqual(set(upgrade.NATIVE_ENTRY_CONVERSION),
                         {'type', 'before_contract', 'after_contract'})
        self.assertEqual(upgrade.NATIVE_ENTRY_CONVERSION['type'], 'native-entry-refresh-v1')
        for name in upgrade._ENTRY_CONTRACT_NAMES:
            blob = _git('cat-file', 'blob', PREDECESSOR_014['commit'] + ':' + name)
            self.assertEqual(upgrade.NATIVE_ENTRY_CONVERSION['before_contract'][name], legacy.digest(blob), name)
            self.assertEqual(upgrade.NATIVE_ENTRY_CONVERSION['after_contract'][name],
                             legacy.digest(_git('show', '542f248f35e9de8fb2e7566b6312e6f13d26cd41:'+name)), name)
        # The 0.1.5 entry contract is exactly the frozen 0.1.3-lineage target:
        # same agents table and user_entries bytes the reviewed chain ended on.
        self.assertEqual(upgrade.NATIVE_ENTRY_CONVERSION['after_contract']['scripts/agents.json'],
                         upgrade.PUBLIC_LAYOUT_TARGET_CONTRACT['scripts/agents.json'])
        self.assertEqual(upgrade.NATIVE_ENTRY_CONVERSION['after_contract']['scripts/agm_core/user_entries.py'],
                         legacy.digest(_git('show','542f248f35e9de8fb2e7566b6312e6f13d26cd41:scripts/agm_core/user_entries.py')))
        # Historical handlers stay pinned to their own predecessors; the real
        # 0.1.4 identity cannot ride them.
        for item in upgrade.PUBLIC_LAYOUT_PREDECESSORS:
            self.assertNotEqual(item['source'], PREDECESSOR_014)
        self.assertNotEqual(upgrade.WORKBUDDY_PREDECESSOR, PREDECESSOR_014)

    def test_current_worktree_contract_cannot_ride_old_handlers(self):
        self.assertFalse(upgrade._workbuddy_conversion(
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                 source=PREDECESSOR_014),
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.5'),
            'upgrade', copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION)))
        # And the dedicated handler refuses any drifted predecessor/target.
        checks = [
            (dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                  source=dict(PREDECESSOR_014, commit='f'*40)),
             '0.1.5', upgrade.NATIVE_ENTRY_CONVERSION),
            (dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                  source=PREDECESSOR_014), '0.1.4', upgrade.NATIVE_ENTRY_CONVERSION),
            (dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                  source=PREDECESSOR_014), '0.1.5', 'preserve'),
        ]
        for before_arg, version, entries in checks:
            self.assertFalse(upgrade._native_entry_conversion(
                before_arg, dict(schema_version=3, product_structure_version=1,
                                 product_code_version=version), 'upgrade', entries))
        self.assertFalse(upgrade._native_entry_conversion(
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                 source=PREDECESSOR_014),
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.5'),
            'rollback', upgrade.NATIVE_ENTRY_CONVERSION))
        # The real request shape is accepted (sanity for the gate itself).
        self.assertTrue(upgrade._native_entry_conversion(
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.4',
                 source=PREDECESSOR_014),
            dict(schema_version=3, product_structure_version=1, product_code_version='0.1.5'),
            'upgrade', upgrade.NATIVE_ENTRY_CONVERSION))


if __name__ == '__main__':
    unittest.main()
