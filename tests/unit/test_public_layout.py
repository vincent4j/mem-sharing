"""0.1.3 public-memory-layout migration: old modules build the real baseline.

Baselines are installed with the ACTUAL old kernels exported byte-exact from
Git history (0.1.1=04c32e2, 0.1.2=0f690ef), so old user entries/public layout
are genuinely old-shaped; the current kernel only drives the upgrade and the
public_layout migration. The 0.1.3 target is the current worktree payload —
release freezing replaces it with committed identities. Synthetic
HOME/detection only; no real HOME, client or Context Keeper is touched.
"""
import copy
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import approved  # noqa: E402
from agm_core import detect, legacy_import as legacy, paths, public_layout, registry, upgrade  # noqa: E402
from agm_core import user_install as install, user_entries  # noqa: E402
from agm_core.entries import sha256  # noqa: E402

spec = importlib.util.spec_from_file_location('layout013_cli', REPO / 'scripts/install.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

PREDECESSORS = {
    '0.1.1': {'commit': '04c32e24b9ab9504514908f2368cddca4356e478',
              'tree_sha256': '15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179'},
    '0.1.2': {'commit': '0f690ef7aabf747a23bacc7662c19bee34c4bf52',
              'tree_sha256': '1fb1e199c992e07747bbf031fcb83cd74d2b85b5c9c491cda7d2836fca1dd353'},
}
URL = 'https://github.com/vincent4j/mem-sharing'
LEGACY_SHIPPED_011 = ('SKILL.md', 'README.md', 'INSTALL.md', 'llms.txt')  # 0.1.1 manifest rule


def _git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True).stdout


def _manifest_rule(version):
    if version == '0.1.1':
        def rule(name):
            if name in LEGACY_SHIPPED_011 or name.startswith('scripts/'):
                return name != 'scripts/registry.json' and not name.startswith(
                    ('scripts/backups/', 'scripts/.agm.lock/'))
            return False
        return rule
    return cli._managed_source


def _export_release(root, commit, version):
    rule = _manifest_rule(version)
    files = {}
    for record in _git('ls-tree', '-rz', commit).decode().split('\0'):
        if not record:
            continue
        meta, path = record.split('\t', 1)
        mode, kind, blob = meta.split()
        if kind != 'blob' or not rule(path):
            continue
        raw = _git('cat-file', 'blob', blob)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if mode == '100755' else 0o644)
        files[path] = legacy.digest(raw)
    return files


def _load_old_kernel(root):
    """Load the exported release as an isolated package; submodules on demand."""
    name = 'agm_old_' + uuid.uuid4().hex
    init = root / 'scripts/agm_core/__init__.py'
    pkg_spec = importlib.util.spec_from_file_location(
        name, init, submodule_search_locations=[str(root / 'scripts/agm_core')])
    package = importlib.util.module_from_spec(pkg_spec)
    sys.modules[name] = package
    pkg_spec.loader.exec_module(package)
    return name, package


def _export_target(root):
    files = {}
    for path in sorted(REPO.rglob('*')):
        if not path.is_file() or path.is_symlink() or '.git' in path.parts:
            continue
        if '__pycache__' in path.parts or path.name == '.DS_Store':
            continue
        rel = str(path.relative_to(REPO))
        if cli._managed_source(rel):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(path.read_bytes())
            (root / rel).chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
            files[rel] = legacy.digest(path.read_bytes())
    return files


class PublicLayoutMigrationFixture(unittest.TestCase):
    """0.1.x baseline via the real old kernel; 0.1.3 target is the worktree."""

    VERSION = '0.1.1'
    CONNECTED = ('codex', 'claude', 'workbuddy')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / 'home'
        self.home.mkdir()
        self.runtime = install._runtime({'home': str(self.home)})
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')

        identity = PREDECESSORS[self.VERSION]
        self.prev_root = self.area / ('release-' + self.VERSION.replace('.', ''))
        self.prev_files = _export_release(self.prev_root, identity['commit'], self.VERSION)
        self._old_name, _package = _load_old_kernel(self.prev_root)
        self.old_install = importlib.import_module(self._old_name + '.user_install')
        old_detect = importlib.import_module(self._old_name + '.detect')
        old_paths = importlib.import_module(self._old_name + '.paths')
        old_config = old_paths.select_platform(old_paths.load_agents_table(), 'darwin')

        self.bin_dir = self.area / 'bin'
        self.bin_dir.mkdir()
        package = self.area / 'npm'
        (package / 'bin').mkdir(parents=True)
        exe = package / 'bin/codex'
        exe.write_text('#!/bin/sh\n')
        exe.chmod(0o755)
        (package / 'package.json').write_text(json.dumps(
            {'name': '@openai/codex', 'version': '1.0', 'bin': {'codex': 'bin/codex'}}))
        (self.bin_dir / 'codex').symlink_to(exe)
        facts = old_detect.detect_agents(old_config, None, home=str(self.home),
                                         search_paths=[str(self.bin_dir)], app_directories=[])
        for agent in ('workbuddy', 'claude'):
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        self.addCleanup(patch.stopall)
        patch.object(old_detect, 'detect_agents', return_value=facts).start()

        self.req_old = {'home': str(self.home), 'platform_config': old_config,
                        'agents': list(self.CONNECTED), 'search_paths': [str(self.bin_dir)],
                        'app_directories': [],
                        'operation_id': 'install-' + self.VERSION.replace('.', ''),
                        'source': {'root': str(self.prev_root), 'url': URL,
                                   'commit': identity['commit'], 'version': self.VERSION,
                                   'files': self.prev_files}}
        self.private_wb = (b'private WB rules\r\n'
                           b'<!-- context-keeper:workbuddy:start -->\nold CK block\n'
                           b'<!-- context-keeper:workbuddy:end -->\n')
        entry = self.home / '.workbuddy/MEMORY.md'
        entry.parent.mkdir(parents=True)
        entry.write_bytes(self.private_wb)
        plan = self.old_install.plan_install(self.req_old)
        done = self.old_install.execute_install(plan, approved(plan), request=self.req_old)
        self.assertEqual(done['status'], 'completed', done)
        self.baseline = self.snapshot()
        # 旧内核真实产出旧形态模板(旧常量与历史字节一致性交叉核验)。
        memory_index = self.runtime.root / 'memories/MEMORY.md'
        if 'codex' in self.CONNECTED:
            self.assertEqual(install._node(self.home / '.codex/AGENTS.md')['sha256'],
                             legacy.digest(public_layout.old_codex_block(memory_index, self.runtime.code)))
        if 'claude' in self.CONNECTED:
            self.assertEqual((self.home / '.claude/CLAUDE.md').read_bytes(),
                             ('@' + str(memory_index) + '\n').encode())
        self.assertEqual((self.runtime.root / 'memories/topics/使用约定.md').read_bytes(),
                         public_layout.old_topic(self.runtime.code))

        # 0.1.3 target: the current worktree payload (frozen at release).
        self.next_root = self.area / 'release-013'
        self.next_files = _export_target(self.next_root)
        self.assertIn('scripts/agm_core/public_layout.py', self.next_files)
        self.next_source = {'root': str(self.next_root), 'url': URL,
                            'commit': 'd' * 40, 'version': '0.1.3', 'files': self.next_files}
        self.old_product = json.loads(self.runtime.registry.read_bytes())['product']
        checked, _ = install._source(dict(source=self.next_source))
        self.req13 = {'home': str(self.home), 'platform_config': self.config, 'agents': None,
                      'search_paths': [str(self.bin_dir)], 'app_directories': [],
                      'operation_id': 'upgrade-013', 'source': self.next_source,
                      'conversions': [{'before': dict(
                          schema_version=3, product_structure_version=1,
                          product_code_version=self.VERSION, source=self.old_product['source']),
                          'after': dict(schema_version=3, product_structure_version=1,
                                        product_code_version='0.1.3',
                                        source={k: checked[k] for k in ('url', 'commit', 'tree_sha256')}),
                          'direction': 'upgrade',
                          'entries': {'type': public_layout.HANDLER_TYPE}}]}

    # ---- helpers ------------------------------------------------------------

    def snapshot(self):
        return {str(p.relative_to(self.home)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in [self.home, *self.home.rglob('*')]}

    def plan(self, **overrides):
        request = dict(self.req13, **overrides)
        return cli.plan_machine(request), request

    def apply(self, plan, request, **kwargs):
        return cli.execute_machine(plan, approved(plan), request=request, **kwargs)

    def migrate_selected_connected_agents(self):
        """Keep no-Codex matrices explicit under the new full machine default."""
        facts = detect.detect_agents(self.config, None, home=str(self.home),
                                     search_paths=[str(self.bin_dir)], app_directories=[])
        for agent in self.CONNECTED:
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        with patch.object(detect, 'detect_agents', return_value=facts):
            plan, request = self.plan(agents=list(self.CONNECTED))
            done = self.apply(plan, request)
        return plan, request, done

    def index_bytes(self):
        return (self.runtime.root / 'memories/MEMORY.md').read_bytes()

    def topic_bytes(self):
        return (self.runtime.root / 'memories/topics/使用约定.md').read_bytes()

    def ledger(self):
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        return registry.load_registry(self.runtime.registry, allowed_user_paths=allowed)

    def make_variant(self, **attrs):
        variant = self.__class__('test_upgrade_runs_migration_to_v2_and_preserves_private_bytes')
        for key, value in attrs.items():
            setattr(variant, key, value)
        variant.setUp()
        self.addCleanup(variant.doCleanups)
        return variant

    # ---- happy path ----------------------------------------------------------

    def test_upgrade_runs_migration_to_v2_and_preserves_private_bytes(self):
        plan, request = self.plan()
        self.assertIsNotNone(plan['plan']['migration_plan'])
        migration = plan['plan']['migration_plan']
        kinds = sorted(t['kind'] for t in migration['targets'])
        self.assertEqual(kinds, ['claude_fallback', 'guide_topic', 'managed_block',
                                 'managed_block', 'public_index'])
        done = self.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(done['result']['migration']['migration_phase'], 'committed')
        self.assertFalse(os.path.lexists(migration['guard']))
        codex = (self.home / '.codex/AGENTS.md').read_bytes()
        self.assertIn(public_layout.new_codex_block(self.runtime.root / 'memories/MEMORY.md'), codex)
        self.assertNotIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), codex)
        wb = (self.home / '.workbuddy/MEMORY.md').read_bytes()
        self.assertTrue(wb.startswith(self.private_wb))
        self.assertIn(public_layout.new_workbuddy_block(self.runtime.root / 'memories/MEMORY.md'), wb)
        claude = (self.home / '.claude/CLAUDE.md').read_bytes()
        self.assertTrue(claude.startswith(
            ('@' + str(self.runtime.root / 'memories/MEMORY.md') + '\n').encode()))
        self.assertIn(public_layout.new_claude_fallback_block(), claude)
        self.assertIn(public_layout.new_contract_bytes(), self.index_bytes())
        self.assertNotIn(public_layout._OLD_GOVERNANCE.encode(), self.index_bytes())
        self.assertEqual(self.topic_bytes(), public_layout.new_topic_bytes(self.runtime.code))
        data = self.ledger()
        self.assertEqual(data['product']['product_code_version'], '0.1.3')
        claude_path = str(self.home / '.claude/CLAUDE.md')
        self.assertEqual(data['machine']['objects'][claude_path + '#claude-fallback']['marker'],
                         user_entries.CLAUDE_FALLBACK_MARKER)
        self.assertEqual(data['machine']['objects'][claude_path + '#import']['fingerprint']['value'],
                         sha256(claude))
        self.assertIn(b'old CK block', wb)
        self.assertIn('Context Keeper'.encode(), self.index_bytes())
        status = user_entries.connection_status(self.runtime, self.config, data,
                                                list(self.CONNECTED))
        self.assertEqual({a: status[a]['status'] for a in self.CONNECTED},
                         {a: 'connected' for a in self.CONNECTED})
        stable = self.snapshot()
        again, request2 = self.plan(operation_id='upgrade-013-replay')
        self.assertTrue(again['plan']['noop'])
        self.assertIsNone(again['plan']['migration_plan'])
        self.assertEqual(self.apply(again, request2)['status'], 'completed')
        self.assertEqual(self.snapshot(), stable)

    def test_migration_index_tail_preserved_byte_exact(self):
        index = self.runtime.root / 'memories/MEMORY.md'
        user_line = '- 用户主题：手写结论。 [x](topics/user.md)\n'.encode()
        index.write_bytes(index.read_bytes() + user_line)
        plan, request = self.plan()
        self.apply(plan, request)
        self.assertTrue(self.index_bytes().endswith(user_line))
        self.assertNotIn('[目录](topics/)'.encode(), self.index_bytes())

    def test_shared_convention_keeps_oid_scope_ownership_consumers(self):
        data = self.ledger()
        oid = str(self.home / '.workbuddy/MEMORY.md') + '#convention'
        obj = data['machine']['objects'].pop(oid)
        obj.update(scope='user', ownership='reused', original_existed=True,
                   backup_manifest=None, consumers=[])
        data['shared_objects'][oid] = obj
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(
            registry.serialize_registry(data, allowed_user_paths=allowed))
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        self.assertTrue(any(t['kind'] == 'managed_block' and t['path'] == obj['path']
                            for t in migration['targets']))
        self.apply(plan, request)
        after = self.ledger()['shared_objects'][oid]
        self.assertEqual(after['scope'], 'user')
        self.assertEqual(after['ownership'], 'reused')
        self.assertEqual(after['consumers'], [])
        block = public_layout.new_workbuddy_block(self.runtime.root / 'memories/MEMORY.md')
        self.assertEqual(after['fingerprint']['value'], sha256(block))

    def test_no_codex_matrix_migrates_claude_and_workbuddy_only(self):
        variant = self.make_variant(CONNECTED=('claude', 'workbuddy'))
        plan, request, done = variant.migrate_selected_connected_agents()
        migration = plan['plan']['migration_plan']
        self.assertFalse(any(t['path'].startswith(str(variant.home / '.codex'))
                             for t in migration['targets']))
        self.assertEqual(done['status'], 'completed', done)
        self.assertFalse((variant.home / '.codex').exists())
        data = variant.ledger()
        status = user_entries.connection_status(variant.runtime, variant.config, data,
                                                ['claude', 'workbuddy'])
        self.assertEqual({a: status[a]['status'] for a in ('claude', 'workbuddy')},
                         {'claude': 'connected', 'workbuddy': 'connected'})

    def test_registered_new_native_entries_remain_byte_identical_during_migration(self):
        facts = detect.detect_agents(self.config, None, home=str(self.home),
            search_paths=[str(self.bin_dir)], app_directories=[])
        for agent in ('dsh', 'zcode'):
            facts['agents'][agent] = copy.deepcopy(facts['agents']['codex'])
        request = dict(self.req13, agents=['dsh', 'zcode'])
        with patch.dict(os.environ, DSH_HOME=''), patch.object(detect, 'detect_agents', return_value=facts):
            preview = user_entries.run_user_entries(request)
            self.assertEqual(preview['status'], 'approval_required', preview)
            approval = json.loads(preview['next_action'])
            request['approval'] = approved({k:v for k,v in approval.items() if k not in ('confirmed_at','reference')})
            self.assertEqual(user_entries.run_user_entries(request)['status'], 'completed')
        private = {a: (self.home/('.'+a)/'AGENTS.md').read_bytes() for a in ('dsh', 'zcode')}
        plan, request = self.plan()
        done = self.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        for a, raw in private.items():
            self.assertEqual((self.home/('.'+a)/'AGENTS.md').read_bytes(), raw)
        status = user_entries.connection_status(self.runtime, self.config, self.ledger(), ['dsh','zcode'])
        self.assertEqual([status[a]['status'] for a in ('dsh', 'zcode')], ['connected', 'connected'])

    def test_new_desktop_readers_are_scanned_and_private_files_preserved(self):
        for agent in ('dsh', 'zcode'):
            with self.subTest(agent=agent):
                entry = self.home/('.'+agent)/'AGENTS.md'
                entry.parent.mkdir()
                private = b'private desktop rules\xff\r\n'
                entry.write_bytes(private)
                before = self.snapshot()
                plan, request = self.plan()
                self.assertEqual(self.snapshot(), before)
                migration = plan['plan']['migration_plan']
                self.assertIn(str(entry), migration['observations'])
                self.assertFalse(any(t['path'] == str(entry) for t in migration['targets']))
                entry.write_bytes(private + user_entries.native_public_source_block(
                    agent, self.runtime.root/'memories/MEMORY.md'))
                before = self.snapshot()
                with self.assertRaises(ValueError) as stopped: self.plan()
                self.assertIn('unregistered_public_reader', str(stopped.exception))
                self.assertEqual(self.snapshot(), before)
                entry.write_bytes(private)
        plan, request = self.plan()
        done = self.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        for agent in ('dsh', 'zcode'):
            self.assertEqual((self.home/('.'+agent)/'AGENTS.md').read_bytes(), private)

    def test_unregistered_public_reader_blocks_before_code_upgrade(self):
        variant = self.make_variant(CONNECTED=('codex', 'workbuddy'))
        claude = variant.home / '.claude/CLAUDE.md'
        claude.parent.mkdir()
        claude.write_bytes(
            ('@' + str(variant.runtime.root / 'memories/MEMORY.md') + '\n').encode())
        before = variant.snapshot()
        with self.assertRaises(ValueError) as ctx:
            cli.plan_machine(variant.req13)
        self.assertIn('unregistered_public_reader', str(ctx.exception))
        self.assertEqual(variant.snapshot(), before)

    def test_manual_edit_and_wrong_approval_reject_zero_write(self):
        entry = self.home / '.codex/AGENTS.md'
        original = entry.read_bytes()
        entry.write_bytes(original.replace(b'AGENTS.md', b'CHANGED.md', 1))
        with self.assertRaises(ValueError):
            cli.plan_machine(self.req13)
        entry.write_bytes(original)
        plan, request = self.plan()
        before = self.snapshot()
        bad = approved(plan)
        bad['plan']['migration_plan']['targets'] = []
        with self.assertRaises(ValueError):
            cli.execute_machine(plan, bad, request=request)
        self.assertEqual(self.snapshot(), before)

    def test_interrupt_before_public_index_rolls_back_then_fresh_preview(self):
        # fallback 未齐不动公共:公共索引写入前中断,事务自动回滚,公共保持旧布局。
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        old_index = self.index_bytes()
        old_topic = self.topic_bytes()

        def hook(event, path):
            if event == 'before_write' and str(path) == migration['public']['index']:
                raise RuntimeError('interrupted before public index')
        result = self.apply(plan, request, hook=hook)
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        self.assertEqual(result['errors'][0]['code'], 'migration_recovery_required')
        self.assertIn('V=V1', result['errors'][0]['message'])
        self.assertEqual(self.index_bytes(), old_index)
        self.assertEqual(self.topic_bytes(), old_topic)
        self.assertTrue(os.path.lexists(migration['guard']))
        # V1(代码已升、迁移回滚)只允许 rollback;finish/redo 须新预览批准。
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='finish')
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertEqual(done['status'], 'rolled_back')
        self.assertFalse(os.path.lexists(migration['guard']))
        # 同版代码 noop 但旧布局仍生成迁移;重预览获新计划并完成。
        again, request2 = self.plan(operation_id='upgrade-013-fresh')
        self.assertTrue(again['plan']['noop'])
        self.assertIsNotNone(again['plan']['migration_plan'])
        result = self.apply(again, request2)
        self.assertEqual(result['status'], 'completed', result)
        self.assertIn(public_layout.new_contract_bytes(), self.index_bytes())
        self.assertEqual(self.topic_bytes(), public_layout.new_topic_bytes(self.runtime.code))

    def test_v2_committed_is_finish_only(self):
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        seen = []

        def hook(event, path):
            if event == 'after_write' and str(path) == str(self.runtime.registry):
                seen.append(path)
                raise RuntimeError('post-commit interrupt')
        result = self.apply(plan, request, hook=hook)
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        self.assertTrue(seen)
        self.assertTrue(os.path.lexists(migration['guard']))
        # V2 authoritative:rollback 拒绝;finish 收尾去 guard。
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        recovery = public_layout.plan_recovery(migration['journal'], action='finish')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'])
        self.assertFalse(os.path.lexists(migration['guard']))
        stable = self.snapshot()
        again, request2 = self.plan(operation_id='upgrade-013-after-finish')
        self.assertTrue(again['plan']['noop'])
        self.assertIsNone(again['plan']['migration_plan'])
        self.assertEqual(self.apply(again, request2)['status'], 'completed')
        self.assertEqual(self.snapshot(), stable)

    def test_third_state_output_rejects_recovery(self):
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']

        def hook(event, path):
            if event == 'after_write' and str(path) == str(self.runtime.registry):
                raise RuntimeError('post-commit interrupt')
        self.apply(plan, request, hook=hook)
        self.assertTrue(os.path.lexists(migration['guard']))
        index = self.runtime.root / 'memories/MEMORY.md'
        index.write_bytes(b'third party edit')
        for action in ('rollback', 'finish'):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    public_layout.plan_recovery(migration['journal'], action=action)


class PublicLayout012BaselineTests(PublicLayoutMigrationFixture):
    VERSION = '0.1.2'


class PublicLayoutHardeningTests(PublicLayoutMigrationFixture):
    """P1/R 批次与门禁回归:只跑 0.1.1 前身,聚焦迁移自身行为。"""

    VERSION = '0.1.1'

    def test_private_only_claude_file_is_observed_never_touched(self):
        # P1-1:无登记依赖的私文不被隐式接入——零 target/零对象,字节不变。
        variant = self.make_variant(CONNECTED=('codex', 'workbuddy'))
        claude = variant.home / '.claude/CLAUDE.md'
        claude.parent.mkdir()
        claude.write_bytes(b'# my private claude\n')
        plan, request = variant.plan()
        migration = plan['plan']['migration_plan']
        self.assertFalse(any(t['path'] == str(claude) for t in migration['targets']))
        before = claude.read_bytes()
        done = variant.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(claude.read_bytes(), before)
        self.assertNotIn(str(claude) + '#claude-fallback', variant.ledger()['machine']['objects'])
        self.assertNotIn(str(claude) + '#import', variant.ledger()['machine']['objects'])

    def test_registered_but_missing_entry_rejects_whole_order(self):
        entry = self.home / '.workbuddy/MEMORY.md'
        entry.unlink()
        before = self.snapshot()
        with self.assertRaises(ValueError) as ctx:
            cli.plan_machine(self.req13)
        self.assertIn('已登记依赖的入口缺失', str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_existing_fallback_without_slot_registers_reused_not_created(self):
        # P1-2:兜底字节既存而无登记 → reused,不追认删除权。
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        # 预置:claude 入口已含正确兜底字节(模拟中断后重放前的现场),
        # 台账 import 指纹按无兜底旧字节。
        claude = self.home / '.claude/CLAUDE.md'
        old_bytes = claude.read_bytes()
        fallback = public_layout.new_claude_fallback_block()
        claude.write_bytes(old_bytes + fallback)
        plan2, request2 = self.plan(operation_id='upgrade-013-reused')
        migration2 = plan2['plan']['migration_plan']
        target = [t for t in migration2['targets'] if t['path'] == str(claude)]
        self.assertFalse(target)  # 字节已就位,不再写文件
        variant_done = self.apply(plan2, request2)
        self.assertEqual(variant_done['status'], 'completed', variant_done)
        obj = self.ledger()['machine']['objects'][str(claude) + '#claude-fallback']
        self.assertEqual(obj['ownership'], 'reused')
        self.assertIsNone(obj['backup_manifest'])
        self.assertTrue(obj['original_existed'])

    def test_direct_api_from_old_version_is_refused(self):
        # P1-4:0.1.1 机器直连(无 code_plan)预览/伪造执行都被拒,零写。
        before = self.snapshot()
        with self.assertRaises(ValueError) as ctx:
            public_layout.plan_migration(dict(self.req13))
        self.assertIn('仅可经外层升级转换', str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_conversion_schema_rejections_are_zero_write(self):
        # fix-2:额外键/错前身/错目标版本/错方向/preserve 全部严格拒绝。
        import copy as _copy
        cases = []
        extra = _copy.deepcopy(self.req13)
        extra['conversions'][0]['entries'] = {'type': public_layout.HANDLER_TYPE, 'extra': 1}
        cases.append(extra)
        wrong_pred = _copy.deepcopy(self.req13)
        wrong_pred['conversions'][0]['before']['source'] = dict(
            self.old_product['source'], commit='e' * 40)
        cases.append(wrong_pred)
        wrong_version = _copy.deepcopy(self.req13)
        wrong_version['source']['version'] = '0.1.4'
        wrong_version['conversions'][0]['after']['product_code_version'] = '0.1.4'
        cases.append(wrong_version)
        wrong_direction = _copy.deepcopy(self.req13)
        wrong_direction['direction'] = 'rollback'
        wrong_direction['conversions'][0]['direction'] = 'rollback'
        cases.append(wrong_direction)
        preserve = _copy.deepcopy(self.req13)
        preserve['conversions'][0]['entries'] = 'preserve'
        cases.append(preserve)
        before = self.snapshot()
        for request in cases:
            with self.subTest(entries=request['conversions'][0]['entries']):
                with self.assertRaises(ValueError):
                    cli.plan_machine(request)
                self.assertEqual(self.snapshot(), before)

    def test_wrong_target_module_is_rejected_by_frozen_contract(self):
        # 目标模块漂移(错 public_layout.py)不能借固定合同放行。
        import copy as _copy
        drift_root = self.area / 'release-013-drift'
        drift_files = dict(self.next_files)
        for rel in self.next_files:
            path = drift_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.next_root / rel).read_bytes())
            path.chmod(0o755 if (self.next_root / rel).stat().st_mode & 0o111 else 0o644)
        drifted = drift_root / 'scripts/agm_core/public_layout.py'
        drifted.write_bytes(drifted.read_bytes() + b'# drift\n')
        drift_files['scripts/agm_core/public_layout.py'] = sha256(drifted.read_bytes())
        req = _copy.deepcopy(self.req13)
        req['source'] = dict(self.next_source, root=str(drift_root), files=drift_files)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            cli.plan_machine(req)
        self.assertEqual(self.snapshot(), before)

    def test_v0_imported_index_placeholder_line_deleted_tail_preserved(self):
        # fix-5/主审缺项:旧 v0 导入索引的占位主题目录行整行删除(仅固定旧行),
        # 其余尾字节(用户行/legacy 原文行)顺序全等,并补使用约定真实可达链接。
        import copy as _copy
        variant = self.make_variant(CONNECTED=('codex', 'workbuddy'))
        old_kernel = variant.old_install
        # 在 0.1.1 基线上重放 v0 导入形态:直接改写公共索引为 v0 导入模板形状。
        index = variant.runtime.root / 'memories/MEMORY.md'
        code = variant.runtime.code
        contract = public_layout._old_contract_text(code)
        v0_line = '- v0 原文：历史字节已保存在只读阅读包，按需深读。 [v0 原始记忆](legacy-v0-op1/memories/MEMORY.md)\n'
        placeholder = '- 主题目录：新增主题按需维护，当前请先查看既有原文。[目录](topics/)\n'
        user_line = '- 用户自留主题：结论。 [z](topics/z.md)\n'
        index.write_bytes(('# 公共记忆\n\n' + contract + v0_line + placeholder + user_line).encode())
        plan, request = variant.plan()
        done = variant.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        migrated = variant.index_bytes().decode('utf-8')
        self.assertNotIn('[目录](topics/)', migrated)
        self.assertNotIn('主题目录', migrated)
        self.assertIn(v0_line, migrated)
        self.assertIn(user_line, migrated)
        usage = '使用约定：操作指南与维护规则。[概要与全文](topics/使用约定.md)\n'
        self.assertIn(usage, migrated)
        # 原顺序全等保留(v0 行→用户行),使用约定真实可达链接补在尾部。
        self.assertLess(migrated.index(v0_line), migrated.index(user_line))
        self.assertLess(migrated.index(user_line), migrated.index(usage))
        self.assertTrue(migrated.endswith(usage))

    def test_only_workbuddy_real_assembly_without_codex_or_claude(self):
        # fix-6/用户关键场景:仅 WorkBuddy 也能独立完成入口与共享基座装配。
        variant = self.make_variant(CONNECTED=('workbuddy',))
        plan, request, done = variant.migrate_selected_connected_agents()
        self.assertEqual(done['status'], 'completed', done)
        self.assertFalse((variant.home / '.codex').exists())
        self.assertFalse((variant.home / '.claude').exists())
        wb = (variant.home / '.workbuddy/MEMORY.md').read_bytes()
        self.assertIn(public_layout.new_workbuddy_block(
            variant.runtime.root / 'memories/MEMORY.md'), wb)
        self.assertTrue((variant.runtime.root / 'memories/MEMORY.md').is_file())
        self.assertEqual(variant.topic_bytes(), public_layout.new_topic_bytes(variant.runtime.code))
        status = user_entries.connection_status(variant.runtime, variant.config,
                                                variant.ledger(), ['workbuddy'])
        self.assertEqual(status['workbuddy']['status'], 'connected')
        # 项目接入:--agent workbuddy 在无 Codex 机器上装配共享 AGENTS 基座。
        project = self._git_project()
        from agm_core import enable
        from agm_core import detect
        facts = detect.detect_agents(variant.config, None, home=str(variant.home),
                                     search_paths=[str(variant.bin_dir)], app_directories=[])
        facts['agents']['workbuddy'] = copy.deepcopy(facts['agents']['codex'])
        facts['agents']['claude'] = copy.deepcopy(facts['agents']['codex'])
        with patch.object(detect, 'detect_agents', return_value=facts):
            result = enable.run({'home': str(variant.home), 'platform_config': variant.config,
                             'project': str(project), 'agents': ['workbuddy'],
                             'memory_choice': 'follow_ck', 'interactive': True,
                             'confirm': lambda prompt: True, 'app_directories': [], 'search_paths': []})
        self.assertEqual(result['status'], 'completed', result)
        self.assertTrue((project / 'AGENTS.md').is_file())
        self.assertFalse((project / 'CLAUDE.md').exists())

    def test_only_claude_real_assembly_without_codex_or_workbuddy(self):
        variant = self.make_variant(CONNECTED=('claude',))
        plan, request, done = variant.migrate_selected_connected_agents()
        self.assertEqual(done['status'], 'completed', done)
        self.assertFalse((variant.home / '.codex').exists())
        # 私文 .workbuddy/MEMORY.md(夹具预置)被观察保全,不新增任何受管痕迹。
        wb_entry = variant.home / '.workbuddy/MEMORY.md'
        self.assertEqual(wb_entry.read_bytes(), variant.private_wb)
        self.assertNotIn(user_entries.BASE_MARKER['start'].encode(), wb_entry.read_bytes())
        claude = (variant.home / '.claude/CLAUDE.md').read_bytes()
        self.assertIn(public_layout.new_claude_fallback_block(), claude)
        status = user_entries.connection_status(variant.runtime, variant.config,
                                                variant.ledger(), ['claude'])
        self.assertEqual(status['claude']['status'], 'connected')
        project = self._git_project()
        from agm_core import enable
        from agm_core import detect
        facts = detect.detect_agents(variant.config, None, home=str(variant.home),
                                     search_paths=[str(variant.bin_dir)], app_directories=[])
        facts['agents']['workbuddy'] = copy.deepcopy(facts['agents']['codex'])
        facts['agents']['claude'] = copy.deepcopy(facts['agents']['codex'])
        with patch.object(detect, 'detect_agents', return_value=facts):
            result = enable.run({'home': str(variant.home), 'platform_config': variant.config,
                             'project': str(project), 'agents': ['claude'],
                             'memory_choice': 'follow_ck', 'interactive': True,
                             'confirm': lambda prompt: True, 'app_directories': [], 'search_paths': []})
        self.assertEqual(result['status'], 'completed', result)
        self.assertTrue((project / 'AGENTS.md').is_file())
        self.assertIn('@AGENTS.md'.encode(), (project / 'CLAUDE.md').read_bytes())

    def _git_project(self):
        project = self.area / ('project-' + uuid.uuid4().hex[:6])
        project.mkdir()
        subprocess.run(['git', '-C', str(project), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(project), 'commit', '--allow-empty', '-m', 'init',
                        '-q'], check=True)
        return project

    # ---- R 批次六组 -------------------------------------------------------

    def _interrupted_v1_scene(self):
        """公共索引写入前中断(V1,可回滚),返回 (migration, journal 快照)。"""
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']

        def hook(event, path):
            if event == 'before_write' and str(path) == migration['public']['index']:
                raise RuntimeError('stop before index')
        result = self.apply(plan, request, hook=hook)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        return migration

    def test_r1_manifest_tamper_and_injection_reject_recovery(self):
        migration = self._interrupted_v1_scene()
        manifest_path = Path(migration['manifest_path'])
        manifest = json.loads(manifest_path.read_bytes())
        # 注入 allowed 但非 target 的用户路径。
        manifest['entries'].insert(0, dict(manifest['entries'][0],
                                           path=str(self.home / '.codex/AGENTS.md')))
        manifest_path.write_bytes(json.dumps(manifest, ensure_ascii=False).encode())
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        # 篡改 before 指纹(与 backup 改成一致也拦:集合/前后像与计划比对)。
        manifest = json.loads(manifest_path.read_bytes())
        manifest['entries'] = manifest['entries'][1:]
        manifest['entries'][0]['before']['fingerprint'] = 'f' * 64
        manifest_path.write_bytes(json.dumps(manifest, ensure_ascii=False).encode())
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')

    def test_r1_last_backup_corrupt_is_zero_write(self):
        migration = self._interrupted_v1_scene()
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        manifest_path = Path(migration['manifest_path'])
        manifest = json.loads(manifest_path.read_bytes())
        backups = [e['before']['backup'] for e in manifest['entries'] if e['before']['backup']]
        (manifest_path.parent / backups[-1]).write_bytes(b'corrupt last backup')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            public_layout.recover_migration(recovery, approved(recovery))
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        self.assertEqual(before, self.snapshot())

    def test_r2_crash_after_guard_without_manifest_recovers_cleanly(self):
        from agm_core import registry as registry_module
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        with patch.object(registry_module, 'commit_registry',
                          side_effect=RuntimeError('crash before transaction')):
            result = self.apply(plan, request)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        self.assertTrue(os.path.lexists(migration['guard']))
        # guard 后无 manifest(未写任何输出):精确批准仅结束 journal/清 guard。
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done.get('finalized_only'))
        self.assertFalse(os.path.lexists(migration['guard']))
        # 同 op 材料已存在时不得覆盖重放。
        plan2, request2 = self.plan(operation_id='upgrade-013-replay-guard')
        self.assertTrue(plan2['plan']['noop'])

    def test_r2_same_operation_material_refuses_overwrite(self):
        migration = self._interrupted_v1_scene()
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertEqual(done['status'], 'rolled_back')
        with self.assertRaises(ValueError):
            public_layout.execute_migration(
                json.loads(Path(migration['journal']).read_bytes())['plan'],
                approved(json.loads(Path(migration['journal']).read_bytes())['plan']),
                request=self.req13)

    def test_r3_dynamic_reader_mode_kind_and_topic_changes_reject(self):
        # 动态新增读者:计划后写入未登记公共指针 → 执行拒绝零写。
        plan, request = self.plan()
        claude = self.home / '.claude/CLAUDE.md'
        variant_claude = claude.read_bytes()
        request = dict(request)
        plan_copy = json.loads(json.dumps(plan))
        claude.write_bytes(b'# private\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            cli.execute_machine(plan_copy, approved(plan_copy), request=request)
        self.assertEqual(self.snapshot(), before)
        claude.write_bytes(variant_claude)
        # mode-only 与 kind-only 变化在观察核验下拒绝。
        entry = self.home / '.codex/AGENTS.md'
        original_mode = entry.stat().st_mode
        entry.chmod(0o640)
        with self.assertRaises(ValueError):
            cli.execute_machine(plan, approved(plan), request=request)
        entry.chmod(original_mode & 0o777)
        # 无 target 的指南主题被外部改动 → 新预览拒绝(既非旧模板也非新目标)。
        topic = self.runtime.root / 'memories/topics/使用约定.md'
        topic.write_bytes(b'user rewrite\n')
        with self.assertRaises(ValueError):
            cli.plan_machine(dict(self.req13, operation_id='upgrade-013-topic'))

    def test_r4_fixed_toolkit_tamper_blocks_recovery_intact_toolkit_works(self):
        migration = self._interrupted_v1_scene()
        tool = Path(migration['backup_scope']) / 'tools/agm_core/public_layout.py'
        original = tool.read_bytes()
        tool.write_bytes(original + b'# tampered\n')
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        tool.write_bytes(original)
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertEqual(done['status'], 'rolled_back')

    def test_r5_v2_foreign_edits_never_rollback_registry(self):
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']
        v2_hash = None

        def hook(event, path):
            nonlocal v2_hash
            if event == 'after_write' and str(path) == str(self.runtime.registry):
                v2_hash = self.runtime.registry.read_bytes()
                # V 落盘后、收尾前,外部改入口与公共文件(制造第三态)。
                (self.home / '.codex/AGENTS.md').write_bytes(b'foreign edit\n')
                raise RuntimeError('post-commit foreign state')
        result = self.apply(plan, request, hook=hook)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        # V2 不倒退;入口第三态保全;恢复对 rollback/finish 均拒绝。
        self.assertEqual(self.runtime.registry.read_bytes(), v2_hash)
        self.assertEqual((self.home / '.codex/AGENTS.md').read_bytes(), b'foreign edit\n')
        for action in ('rollback', 'finish'):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    public_layout.plan_recovery(migration['journal'], action=action)

    def test_r6_fake_rolled_back_with_mixed_outputs_rejected(self):
        migration = self._interrupted_v1_scene()
        # The in-process exception restored all outputs. Put one approved after
        # state back, while leaving the rolled_back manifest: that is mixed.
        target = next(t for t in migration['targets'] if t['kind'] == 'guide_topic')
        Path(target['path']).write_bytes(public_layout.new_topic_bytes(self.runtime.code))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        self.assertEqual(before, self.snapshot())

    def test_r6_v2_finish_syncs_both_manifests_and_repeats_refuse(self):
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']

        def hook(event, path):
            if event == 'after_write' and str(path) == str(self.runtime.registry):
                raise RuntimeError('post-commit')
        result = self.apply(plan, request, hook=hook)
        self.assertEqual(result['migration_phase'], 'recovery_required')
        recovery = public_layout.plan_recovery(migration['journal'], action='finish')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'])
        manifest = json.loads(Path(migration['manifest_path']).read_bytes())
        journal = json.loads(Path(migration['journal']).read_bytes())
        self.assertEqual(manifest['status'], 'committed')
        self.assertEqual(journal['status'], 'committed')
        self.assertFalse(os.path.lexists(migration['guard']))
        for action in ('rollback', 'finish'):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    public_layout.plan_recovery(migration['journal'], action=action)

    def _crash_migration_process(self, migration, request, event, path):
        payload = self.area / 'crash-input.json'
        payload.write_text(json.dumps({'plan': migration, 'approval': approved(migration),
                                       'request': request, 'event': event, 'path': str(path)}))
        code = """import json,os,sys
sys.path.insert(0,sys.argv[1])
from agm_core import public_layout
x=json.load(open(sys.argv[2]))
def hook(event,path):
    if event==x['event'] and str(path)==x['path']: os._exit(73)
public_layout.execute_migration(x['plan'],x['approval'],request=x['request'],hook=hook)
"""
        done = subprocess.run([sys.executable, '-B', '-c', code, str(REPO/'scripts'), str(payload)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 73, done.stdout + done.stderr)
        # This child is confirmed dead. Only its two empty synthetic lock dirs
        # are removed, exactly as explicit stale-lock handling requires.
        if self.runtime.transaction_lock.exists():
            self.runtime.transaction_lock.rmdir()
        self.runtime.lock.rmdir()

    def test_real_process_crash_before_v_and_fixed_launcher_rollback(self):
        plan, request = self.plan()
        inner = plan['plan']
        upgrade.execute_upgrade(inner, approved(inner), request=request)
        migration = inner['migration_plan']
        self._crash_migration_process(migration, request, 'before_write', self.runtime.registry)
        self.assertEqual(sha256(self.runtime.registry.read_bytes()), migration['v1_registry_sha256'])
        launcher = Path(migration['backup_scope'])/'recover.py'
        preview = subprocess.run([sys.executable, '-B', str(launcher), 'preview',
                                  migration['journal'], 'rollback'], capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        recovery = json.loads(preview.stdout)
        approval_path = self.area/'recovery-approval.json'
        approval_path.write_text(json.dumps(approved(recovery)))
        applied = subprocess.run([sys.executable, '-B', str(launcher), 'apply', str(approval_path)],
                                 capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual(json.loads(applied.stdout)['status'], 'rolled_back')
        self.assertNotIn(public_layout.new_contract_bytes(), self.index_bytes())
        self.assertFalse(Path(migration['guard']).exists())

    def test_real_process_crash_after_v_fixed_tools_survive_active_code_change(self):
        plan, request = self.plan()
        inner = plan['plan']
        code_result = upgrade.execute_upgrade(inner, approved(inner), request=request)
        self.assertEqual(code_result['scope'], 'product_code')
        self.assertEqual(code_result['entry_phase'], 'migration_pending')
        migration = inner['migration_plan']
        self._crash_migration_process(migration, request, 'after_write', self.runtime.registry)
        # Activity in C must not affect the frozen recovery interpreter/imports.
        (self.runtime.code/'scripts/agm_core/public_layout.py').write_bytes(b'raise RuntimeError("changed active C")')
        launcher = Path(migration['backup_scope'])/'recover.py'
        preview = subprocess.run([sys.executable, '-B', str(launcher), 'preview',
                                  migration['journal'], 'continue'], capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        recovery = json.loads(preview.stdout)
        approval_path = self.area/'finish-approval.json'
        approval_path.write_text(json.dumps(approved(recovery)))
        applied = subprocess.run([sys.executable, '-B', str(launcher), 'apply', str(approval_path)],
                                 capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertTrue(json.loads(applied.stdout)['finalized_only'])
        self.assertEqual(sha256(self.runtime.registry.read_bytes()), migration['final_registry_sha256'])
        self.assertFalse(Path(migration['guard']).exists())

    def test_code_plan_cannot_be_supplied_directly(self):
        old = self.runtime.registry.read_bytes()
        with self.assertRaises(public_layout.MigrationError) as caught:
            public_layout.plan_migration(self.req13, code_plan={'after_registry_hex': old.hex()})
        self.assertEqual(caught.exception.code, 'installer_context_required')
        self.assertEqual(old, self.runtime.registry.read_bytes())

    def test_dynamic_untouched_reader_after_hook_blocks_public_removal(self):
        variant = self.make_variant(CONNECTED=('workbuddy',))
        plan, request = variant.plan()
        migration = plan['plan']['migration_plan']
        claude = variant.home/'.claude/CLAUDE.md'
        old_index = variant.index_bytes()
        def hook(event, path):
            if event == 'before_write' and str(path) == migration['public']['index']:
                claude.parent.mkdir(parents=True, exist_ok=True)
                claude.write_bytes(('@'+migration['public']['index']+'\n').encode())
        result = variant.apply(plan, request, hook=hook)
        self.assertEqual(result['status'], 'partial', result)
        self.assertEqual(variant.index_bytes(), old_index)
        stable = variant.snapshot()
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        self.assertEqual(stable, variant.snapshot())

    def test_registry_mode_only_recovery_change_is_rejected(self):
        migration = self._interrupted_v1_scene()
        self.runtime.registry.chmod(0o640)
        stable = self.snapshot()
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        self.assertEqual(stable, self.snapshot())

    def test_recovery_rechecks_material_after_machine_lock_acquisition(self):
        from contextlib import contextmanager
        migration = self._interrupted_v1_scene()
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        original_lock = public_layout.write_lock
        manifest = Path(migration['manifest_path'])
        @contextmanager
        def changed_lock(path):
            with original_lock(path):
                manifest.write_bytes(manifest.read_bytes()+b' ')
                yield
        with patch.object(public_layout, 'write_lock', changed_lock):
            with self.assertRaises(ValueError):
                public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(Path(migration['guard']).exists())

    def _equal_v_fixture(self):
        plan, request = self.plan()
        done = self.apply(plan, request)
        self.assertEqual(done['status'], 'completed', done)
        # A legitimate public-only continuation: the installed registered agent
        # entries are already current. Preserve the complete main operation.
        main_id = self.ledger()['product']['last_operation_id']
        main_journal = self.home/('.mem-sharing-install-'+main_id)/'journal.json'
        main_bytes = main_journal.read_bytes()
        index = self.runtime.root/'memories/MEMORY.md'
        index.write_bytes(public_layout._INDEX_PREFIX +
                          public_layout._old_contract_text(self.runtime.code).encode() + b'- custom tail\n')
        request = dict(self.req13, operation_id='public-only-continuation')
        migration = public_layout.plan_migration(request)
        self.assertEqual(migration['v1_registry_sha256'], migration['final_registry_sha256'])
        return migration, request, main_id, main_journal, main_bytes

    def test_equal_v_real_crash_before_manifest_commit_can_rollback(self):
        migration, request, main_id, main_journal, main_bytes = self._equal_v_fixture()
        self._crash_migration_process(migration, request, 'after_write', migration['public']['index'])
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='finish')
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertEqual(done['status'], 'rolled_back')
        self.assertEqual(main_journal.read_bytes(), main_bytes)
        self.assertEqual(self.ledger()['product']['last_operation_id'], main_id)

    def test_equal_v_real_crash_after_manifest_commit_finish_and_context_keeper_source(self):
        from agm_core import ck_install
        migration, request, main_id, main_journal, main_bytes = self._equal_v_fixture()
        self._crash_migration_process(migration, request, 'after_commit', migration['manifest_path'])
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        recovery = public_layout.plan_recovery(migration['journal'], action='finish')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'])
        self.assertEqual(main_journal.read_bytes(), main_bytes)
        self.assertEqual(self.ledger()['product']['last_operation_id'], main_id)
        # Read-only Context Keeper acceptance gate; no upstream installer runs.
        runtime, ledger, agents = ck_install._scene(request, main_id)
        self.assertEqual(runtime, self.runtime)
        self.assertEqual(set(agents), set(self.CONNECTED))
        for action in ('finish', 'rollback'):
            with self.assertRaises(ValueError):
                public_layout.plan_recovery(migration['journal'], action=action)

    def test_equal_v_committed_third_state_and_invalid_manifest_refuse(self):
        migration, request, _, _, _ = self._equal_v_fixture()
        self._crash_migration_process(migration, request, 'after_commit', migration['manifest_path'])
        index = Path(migration['public']['index'])
        current = index.read_bytes()
        index.write_bytes(b'foreign third state')
        stable = self.snapshot()
        for action in ('finish', 'rollback'):
            with self.assertRaises(ValueError):
                public_layout.plan_recovery(migration['journal'], action=action)
        self.assertEqual(stable, self.snapshot())
        index.write_bytes(current)
        manifest_path = Path(migration['manifest_path'])
        original = manifest_path.read_bytes()
        manifest = json.loads(original)
        manifest['entries'][0]['before']['mode'] = 0o777
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='finish')
        manifest_path.unlink()
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='finish')
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')

    def test_pre_guard_journal_failure_does_not_activate_guard(self):
        plan, request = self.plan()
        inner = plan['plan']
        upgrade.execute_upgrade(inner, approved(inner), request=request)
        migration = inner['migration_plan']
        original = public_layout._apply
        def fail_journal(path, *args, **kwargs):
            if str(path) == migration['journal']:
                raise OSError('synthetic prepared journal failure')
            return original(path, *args, **kwargs)
        index = self.index_bytes()
        with patch.object(public_layout, '_apply', fail_journal):
            with self.assertRaises(OSError):
                public_layout.execute_migration(migration, approved(migration), request=request)
        self.assertFalse(Path(migration['guard']).exists())
        self.assertEqual(self.index_bytes(), index)
        self.assertEqual(sha256(self.runtime.registry.read_bytes()), migration['v1_registry_sha256'])

    def test_foreign_guard_race_is_never_overwritten(self):
        plan, request = self.plan()
        inner = plan['plan']
        upgrade.execute_upgrade(inner, approved(inner), request=request)
        migration = inner['migration_plan']
        foreign = b'other operation guard'
        def hook(event, path):
            if event == 'before_guard':
                Path(path).write_bytes(foreign)
        with self.assertRaises(ValueError):
            public_layout.execute_migration(migration, approved(migration), request=request, hook=hook)
        self.assertEqual(Path(migration['guard']).read_bytes(), foreign)
        self.assertEqual(sha256(self.runtime.registry.read_bytes()), migration['v1_registry_sha256'])

    def test_crash_immediately_after_guard_is_recoverable(self):
        plan, request = self.plan()
        inner = plan['plan']
        upgrade.execute_upgrade(inner, approved(inner), request=request)
        migration = inner['migration_plan']
        self._crash_migration_process(migration, request, 'after_guard', migration['guard'])
        self.assertFalse(Path(migration['manifest_path']).exists())
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'])
        self.assertFalse(Path(migration['guard']).exists())

    def test_existing_claude_fallback_keeps_trailing_private_context_keeper_bytes(self):
        entry = self.home/'.claude/CLAUDE.md'
        private = (b'\n<!-- context-keeper:start -->\nprivate synthetic rule\r\n'
                   b'<!-- context-keeper:end -->\n')
        raw = entry.read_bytes()+public_layout.new_claude_fallback_block()+private
        entry.write_bytes(raw)
        data = self.ledger()
        data['machine']['objects'][str(entry)+'#import']['fingerprint']['value'] = sha256(raw)
        self.runtime.registry.write_bytes(registry.serialize_registry(
            data, allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home))))
        plan, request = self.plan()
        result = self.apply(plan, request)
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(entry.read_bytes(), raw)
        obj = self.ledger()['machine']['objects'][str(entry)+'#claude-fallback']
        self.assertEqual(obj['ownership'], 'reused')
        self.assertIsNone(obj['backup_manifest'])

    def test_equal_v_post_commit_exception_preserves_durable_commit_fact(self):
        migration, request, _, _, _ = self._equal_v_fixture()
        def hook(event, path):
            if event == 'after_commit':
                raise RuntimeError('post durable equal-V commit')
        with self.assertRaises(public_layout.MigrationError) as caught:
            public_layout.execute_migration(migration, approved(migration), request=request, hook=hook)
        self.assertIn('V2已提交,仅finish', str(caught.exception))
        manifest = json.loads(Path(migration['manifest_path']).read_bytes())
        self.assertEqual(manifest['status'], 'committed')
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='rollback')
        recovery = public_layout.plan_recovery(migration['journal'], action='finish')
        public_layout.recover_migration(recovery, approved(recovery))
        self.assertFalse(Path(migration['guard']).exists())

    def test_unknown_symlink_reader_and_damaged_public_marker_fail_closed(self):
        variant = self.make_variant(CONNECTED=('workbuddy',))
        claude = variant.home/'.claude/CLAUDE.md'
        claude.parent.mkdir()
        claude.symlink_to(variant.runtime.root/'memories/MEMORY.md')
        stable = variant.snapshot()
        with self.assertRaises(public_layout.MigrationError):
            variant.plan()
        self.assertEqual(stable, variant.snapshot())
        claude.unlink()
        codex = variant.home/'.codex/AGENTS.md'
        codex.parent.mkdir()
        codex.write_bytes(user_entries.BASE_MARKER['start'].encode()+b'\n'+
                          public_layout._old_read_text(variant.runtime.root/'memories/MEMORY.md').encode())
        stable = variant.snapshot()
        with self.assertRaises(public_layout.MigrationError):
            variant.plan()
        self.assertEqual(stable, variant.snapshot())

    def test_equal_v_precommit_error_reports_rollback(self):
        migration, request, _, _, _ = self._equal_v_fixture()
        def hook(event, path):
            if event == 'after_write' and str(path) == migration['public']['index']:
                raise RuntimeError('before equal-V durable commit')
        with self.assertRaises(public_layout.MigrationError) as caught:
            public_layout.execute_migration(migration, approved(migration), request=request, hook=hook)
        self.assertIn('V1,可rollback', str(caught.exception))
        self.assertNotIn('V2已提交', str(caught.exception))
        with self.assertRaises(ValueError):
            public_layout.plan_recovery(migration['journal'], action='finish')
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        public_layout.recover_migration(recovery, approved(recovery))

    def test_second_backup_failure_full_manifest_prewrite_cleanup(self):
        from agm_core import transaction
        plan, request = self.plan()
        inner = plan['plan']
        upgrade.execute_upgrade(inner, approved(inner), request=request)
        migration = inner['migration_plan']
        original = transaction._atomic_file
        hits = []
        def fail_second(path, *args, **kwargs):
            if Path(path).name == '1.before':
                hits.append(path)
                raise OSError('synthetic second backup write failed')
            return original(path, *args, **kwargs)
        before = {raw: public_layout._observe(Path(raw)) for raw in migration['observations']}
        with patch.object(transaction, '_atomic_file', fail_second):
            with self.assertRaises(public_layout.MigrationError):
                public_layout.execute_migration(migration, approved(migration), request=request)
        self.assertEqual(len(hits), 1)
        manifest = json.loads(Path(migration['manifest_path']).read_bytes())
        self.assertEqual([e['path'] for e in manifest['entries']], migration['order'])
        self.assertTrue(all(not e['attempted'] for e in manifest['entries']))
        self.assertEqual(before, {raw: public_layout._observe(Path(raw)) for raw in before})
        recovery = public_layout.plan_recovery(migration['journal'], action='rollback')
        self.assertIn({'kind': 'absent'}, recovery['evidence']['backups'].values())
        done = public_layout.recover_migration(recovery, approved(recovery))
        self.assertTrue(done['finalized_only'])
        self.assertFalse(Path(migration['guard']).exists())
        self.assertEqual(before, {raw: public_layout._observe(Path(raw)) for raw in before})

    def test_same_version_other_release_does_not_dispatch_layout_migration(self):
        plan, request = self.plan()
        self.assertEqual(self.apply(plan, request)['status'], 'completed')
        data = self.ledger()
        data['product']['product_code_version'] = '0.4.1'
        self.runtime.registry.write_bytes(registry.serialize_registry(
            data, allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home))))
        other_source = dict(self.next_source, version='0.4.1')
        request = dict(self.req13, source=other_source, operation_id='other-same-version')
        before = self.snapshot()
        with patch.object(public_layout, 'plan_migration', side_effect=AssertionError('wrong migration route')):
            same = upgrade.plan_upgrade(request)
            self.assertTrue(same['noop'])
            self.assertIsNone(same['migration_plan'])
            self.assertTrue(upgrade.execute_upgrade(same, request=request)['noop'])
        self.assertEqual(before, self.snapshot())

    def test_cli_recover_maps_continue_to_finish(self):
        # 标准 --recover 统一入口分派迁移 journal,continue→finish,rollback→rollback。
        plan, request = self.plan()
        migration = plan['plan']['migration_plan']

        def hook(event, path):
            if event == 'after_write' and str(path) == str(self.runtime.registry):
                raise RuntimeError('post-commit')
        self.apply(plan, request, hook=hook)
        self.assertTrue(os.path.lexists(migration['guard']))
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        argv = ['--recover', migration['journal'], '--action', 'continue']
        with patch.dict(os.environ, HOME=str(self.home)), redirect_stdout(out):
            code = cli.main(argv)
        self.assertEqual(code, 5, out.getvalue())
        preview = json.loads(out.getvalue())['approval_plan']
        self.assertEqual(preview['command'], 'recover-public-layout')
        self.assertEqual(preview['action'], 'finish')
        approval = self.area / 'recover-approval.json'
        approval.write_text(json.dumps(approved(preview)))
        out = io.StringIO()
        with patch.dict(os.environ, HOME=str(self.home)), redirect_stdout(out):
            code = cli.main(['--recover', migration['journal'], '--action', 'continue',
                             '--approval-file', str(approval)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertFalse(os.path.lexists(migration['guard']))

    def test_frozen_target_contract_matches_running_kernel(self):
        # 冻结完整性:目标合同字面量 == 当前内核摘要;模块再修改必须显式重冻结。
        frozen = upgrade.PUBLIC_LAYOUT_TARGET_CONTRACT
        self.assertEqual(frozen['scripts/agents.json'],
                         sha256((REPO / 'scripts/agents.json').read_bytes()))
        self.assertEqual(frozen['scripts/agm_core/user_entries.py'],
                         sha256(Path(user_entries.__file__).read_bytes()))
        self.assertEqual(frozen['scripts/agm_core/public_layout.py'],
                         sha256(Path(public_layout.__file__).read_bytes()))


if __name__ == '__main__':
    unittest.main()
