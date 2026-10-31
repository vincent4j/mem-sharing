"""One release-bound WB conversion; isolated HOME, no real installation writes."""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from agm_core import detect, legacy_import as legacy, upgrade, user_entries, user_install, versions

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('wb_release_cli', REPO/'scripts/install.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)


class WorkBuddyContractUpgradeTests(InstallFixture):
    def setUp(self):
        super().setUp()
        # Synthetic predecessor content; only pin constants are substituted.
        # All source validation, transactions, private bytes and recovery are real.
        (self.source/'scripts/agents.json').write_bytes((REPO/'scripts/agents.json').read_bytes())
        (self.source/'scripts/agm_core/user_entries.py').write_text('# synthetic old WB entry contract\n')
        self.request['source'].update(version='0.1.0', files=self.files(self.source))
        self.codex(); self.execute()
        self.old_product = json.loads(self.runtime.registry.read_bytes())['product']
        self.target = self.area/'release'
        shutil.copytree(self.source, self.target)
        (self.target/'scripts/agm_core/user_entries.py').write_bytes(Path(user_entries.__file__).read_bytes())
        self.target_source = dict(self.request['source'], root=str(self.target), version='0.1.1',
                                  commit='b'*40, files=self.files(self.target))
        self.policy = copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION)
        self.policy['before_contract']['scripts/agm_core/user_entries.py'] = self.request['source']['files']['scripts/agm_core/user_entries.py']
        # 机制测试:前后合同摘要随场景/当前内核动态替换,不冒充固定历史哈希;
        # 010→011 真实历史链不在本文件锁定,生产常量门禁由
        # WorkBuddyFixedGateTests 不打补丁回归覆盖。
        self.policy['after_contract']['scripts/agm_core/user_entries.py'] = legacy.digest(Path(user_entries.__file__).read_bytes())
        self.addCleanup(patch.stopall)
        patch.object(upgrade, 'WORKBUDDY_PREDECESSOR', self.old_product['source']).start()
        patch.object(upgrade, 'WORKBUDDY_ENTRY_CONVERSION', self.policy).start()
        self.req = dict(self.request, source=self.target_source, operation_id='wb-contract-release', agents=['workbuddy'])
        source, _ = user_install._source(self.req)
        self.conversion = {
            'before': dict(schema_version=3, product_structure_version=1, product_code_version='0.1.0', source=self.old_product['source']),
            'after': dict(schema_version=3, product_structure_version=1, product_code_version='0.1.1',
                          source={k:source[k] for k in ('url','commit','tree_sha256')}),
            'direction': 'upgrade', 'entries': self.policy,
        }
        self.req['conversions'] = [self.conversion]
        facts = detect.detect_agents(self.config, None, home=str(self.home), search_paths=self.request['search_paths'], app_directories=[])
        facts['agents']['workbuddy'] = copy.deepcopy(facts['agents']['codex'])
        patch.object(detect, 'detect_agents', return_value=facts).start()
        self.entry = self.home/'.workbuddy/MEMORY.md'; self.entry.parent.mkdir()
        self.private = b'private WB rules\r\n<!-- context-keeper:workbuddy:start -->\nprivate CK block\n<!-- context-keeper:workbuddy:end -->\n'
        self.entry.write_bytes(self.private)

    def files(self, root):
        return {str(p.relative_to(root)):legacy.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode,p.lstat().st_mtime_ns,p.read_bytes() if p.is_file() else None)
                for p in self.home.rglob('*') if not p.is_symlink()}

    def apply(self, plan=None):
        plan = plan or cli.plan_machine(self.req)
        return cli.execute_machine(plan, approved(plan), request=self.req)

    def test_exact_conversion_and_entry_plan_are_bound_and_private_bytes_preserved(self):
        before = self.snapshot(); plan = cli.plan_machine(self.req)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(plan['entry_plan']['effective'], ['workbuddy'])
        self.assertEqual(plan['entry_plan']['changes'][0]['before_fingerprint'], legacy.digest(self.private))
        bad = approved(plan); bad['entry_plan'] = None
        with self.assertRaises(ValueError): self.apply_bad(plan, bad)
        self.assertEqual(before, self.snapshot())
        done = self.apply(plan)
        self.assertEqual(done['status'], 'completed', done)
        self.assertEqual(done['agents']['connected'], ['workbuddy'])
        self.assertEqual(done['entry_status']['workbuddy']['runtime_acceptance'], 'pending')
        self.assertTrue(self.entry.read_bytes().startswith(self.private))
        self.assertIn(str(self.runtime.root/'memories/MEMORY.md').encode(), self.entry.read_bytes())
        self.assertFalse((self.area/'.workbuddy/memory').exists())
        stable = self.snapshot(); same = cli.plan_machine(self.req)
        self.assertTrue(same['plan']['noop']); self.assertIsNone(same['entry_plan'])
        self.assertEqual(self.apply(same)['status'], 'completed')
        self.assertEqual(stable, self.snapshot())
        with self.assertRaises(ValueError):
            upgrade.plan_recovery(plan['plan']['journal'], action='rollback')

    def apply_bad(self, plan, evidence):
        return cli.execute_machine(plan, evidence, request=self.req)

    def test_unknown_before_target_identity_agent_version_and_preserve_cannot_bypass(self):
        requests = []
        for agents in (None, [], ['codex'], ['codex','workbuddy']):
            requests.append(dict(self.req, agents=agents))
        for path, value in ((('before','source','commit'),'f'*40), (('after','source','commit'),'f'*40),
                            (('after','source','tree_sha256'),'f'*64), (('after','product_code_version'),'0.1.2'),
                            (('entries',),'preserve')):
            req = copy.deepcopy(self.req); at = req['conversions'][0]
            for k in path[:-1]: at = at[k]
            at[path[-1]] = value; requests.append(req)
        req = copy.deepcopy(self.req)
        req['source']['version'] = '0.1.2'
        req['conversions'][0]['after']['product_code_version'] = '0.1.2'
        requests.append(req)
        before = self.snapshot()
        for request in requests:
            with self.subTest(request=request), self.assertRaises(ValueError): cli.plan_machine(request)
            self.assertEqual(before, self.snapshot())
        # A caller-updated manifest and matching target identity still cannot
        # turn a changed agents table into an allowed entry transition.
        (self.target/'scripts/agents.json').write_bytes(b'{}\n')
        req = copy.deepcopy(self.req); req['source']['files'] = self.files(self.target)
        source, _ = user_install._source(req)
        req['conversions'][0]['after']['source'] = {k:source[k] for k in ('url','commit','tree_sha256')}
        with self.assertRaises(ValueError): cli.plan_machine(req)
        self.assertEqual(before, self.snapshot())

    def test_changed_private_bytes_after_preview_invalidate_outer_approval(self):
        plan = cli.plan_machine(self.req)
        self.entry.write_bytes(self.private+b'user edit\n'); before = self.snapshot()
        with self.assertRaises(ValueError): self.apply(plan)
        self.assertEqual(before, self.snapshot())

    def test_entry_failure_after_code_commit_is_partial_and_explicit_retry_is_idempotent(self):
        plan = cli.plan_machine(self.req)
        original = user_entries.run_user_entries
        def fail_only_apply(request):
            if request.get('approval'):
                return {'status':'failed', 'errors':[{'code':'synthetic_entry_failure'}]}
            return original(request)
        with patch.object(user_entries, 'run_user_entries', side_effect=fail_only_apply):
            done = self.apply(plan)
        self.assertEqual(done['status'], 'partial', done)
        self.assertEqual(done['agents']['connected'], [])
        self.assertEqual(self.entry.read_bytes(), self.private)
        self.assertEqual(json.loads(self.runtime.registry.read_bytes())['product']['product_code_version'], '0.1.1')
        # The prior approval is stale after code commit; do not replay it.
        with self.assertRaises(ValueError): self.apply(plan)
        retry = cli.plan_machine(self.req)
        self.assertTrue(retry['plan']['noop']); self.assertTrue(retry['entry_plan'])
        self.assertEqual(self.apply(retry)['status'], 'completed')
        self.assertEqual(self.entry.read_bytes().count(user_entries.BASE_MARKER['start'].encode()), 1)

    def test_external_entry_edit_during_code_upgrade_is_not_overwritten(self):
        plan = cli.plan_machine(self.req); original = upgrade.execute_upgrade
        def execute(*args, **kwargs):
            result = original(*args, **kwargs)
            self.entry.write_bytes(self.private+b'external edit\n')
            return result
        with patch.object(upgrade, 'execute_upgrade', side_effect=execute): done = self.apply(plan)
        self.assertEqual(done['status'], 'partial', done)
        self.assertEqual(done['entries']['status'], 'approval_required')
        self.assertEqual(self.entry.read_bytes(), self.private+b'external edit\n')

    def _interrupt_code(self):
        plan = cli.plan_machine(self.req)
        def hook(event, path):
            if event == 'after_code_replace': raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError):
            upgrade.execute_upgrade(plan['plan'], approved(plan['plan']), request=self.req, hook=hook)
        self.assertEqual(self.entry.read_bytes(), self.private)
        return plan['plan']

    def test_fixed_toolkit_rollback_preserves_private_entry(self):
        plan = self._interrupt_code()
        launcher = Path(plan['bootstrap'])/'recover.py'
        result = subprocess.run([sys.executable,'-B',str(launcher),'preview',plan['journal'],'rollback'],capture_output=True,text=True,check=True)
        recovery = json.loads(result.stdout)
        approval = self.area/'rollback.json'; approval.write_text(json.dumps(approved(recovery)))
        done = subprocess.run([sys.executable,'-B',str(launcher),'apply',str(approval)],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(done.stdout)['status'], 'rolled_back')
        self.assertEqual(self.entry.read_bytes(), self.private)
        self.assertEqual(json.loads(self.runtime.registry.read_bytes())['product']['product_code_version'], '0.1.0')
        user_install._code_matches(self.runtime, self.old_product)

    def test_continue_is_code_only_then_requires_fresh_entry_approval(self):
        plan = self._interrupt_code()
        launcher = Path(plan['bootstrap'])/'recover.py'
        result = subprocess.run([sys.executable,'-B',str(launcher),'preview',plan['journal'],'continue'],capture_output=True,text=True,check=True)
        recovery = json.loads(result.stdout)
        approval = self.area/'continue.json'; approval.write_text(json.dumps(approved(recovery)))
        result = subprocess.run([sys.executable,'-B',str(launcher),'apply',str(approval)],capture_output=True,text=True,check=True)
        done = json.loads(result.stdout)
        self.assertEqual(done['scope'], 'product_code')
        self.assertEqual(done['entry_phase'], 'not_run_by_upgrade_core')
        self.assertEqual(self.entry.read_bytes(), self.private)
        retry = cli.plan_machine(self.req)
        self.assertTrue(retry['plan']['noop']); self.assertTrue(retry['entry_plan'])
        self.assertEqual(self.apply(retry)['status'], 'completed')


def _git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True).stdout


class WorkBuddyFixedGateTests(InstallFixture):
    """不打补丁的固定门禁回归:生产常量保持精确历史哈希,当前新合同放行不了。

    010→011 的 WORKBUDDY 前后合同哈希必须仍是旧值(155e…→eda7…),且换成当前
    user_entries.py 的目标既不能借旧 handler 也不能借 preserve 通过合同门禁。
    """

    OLD_USER_ENTRIES_SHA = '155eba8df9b14ccb96e017bc19e3975930be544019fdb1d3aaa17f3aa563be44'
    OLD_PREDECESSOR_COMMIT = '4cfe7bedfde695b0bd4085ccc453afd3ef161711'

    def test_production_contract_hashes_stay_pinned_to_history(self):
        contract = upgrade.WORKBUDDY_ENTRY_CONVERSION
        self.assertEqual(contract['before_contract']['scripts/agm_core/user_entries.py'],
                         self.OLD_USER_ENTRIES_SHA)
        self.assertEqual(contract['after_contract']['scripts/agm_core/user_entries.py'],
                         'eda73b02e99d8092f6f587d786d163efd4d8bbc72340e79de0ad1ffabd25c85a')
        self.assertEqual(upgrade.WORKBUDDY_PREDECESSOR['commit'], self.OLD_PREDECESSOR_COMMIT)
        # 当前内核的入口合同已不同于历史 0.1.1 合同,不能与固定常量混同。
        current = legacy.digest(Path(user_entries.__file__).read_bytes())
        self.assertNotEqual(current, contract['after_contract']['scripts/agm_core/user_entries.py'])

    def test_current_contract_cannot_pass_via_old_handler_or_preserve(self):
        # 前身侧安装真实的 010 合同字节(从 Git 历史导出),目标侧换成当前内核字节。
        old_bytes = _git('cat-file', 'blob', self.OLD_PREDECESSOR_COMMIT +
                         ':scripts/agm_core/user_entries.py')
        self.assertEqual(legacy.digest(old_bytes), self.OLD_USER_ENTRIES_SHA)
        (self.source/'scripts/agm_core/user_entries.py').write_bytes(old_bytes)
        (self.source/'scripts/agents.json').write_bytes(_git(
            'cat-file', 'blob', self.OLD_PREDECESSOR_COMMIT + ':scripts/agents.json'))
        self.request['source'].update(version='0.1.0', files=self._files(self.source))
        self.execute()
        old_product = json.loads(self.runtime.registry.read_bytes())['product']

        target = self.area/'release-current'
        shutil.copytree(self.source, target)
        (target/'scripts/agm_core/user_entries.py').write_bytes(Path(user_entries.__file__).read_bytes())
        target_source = dict(self.request['source'], root=str(target), version='0.1.1',
                             commit='c'*40, files=self._files(target))
        before = {str(p.relative_to(self.home)): p.read_bytes() if p.is_file() else None
                  for p in self.home.rglob('*') if not p.is_symlink()}
        for entries in ('preserve', copy.deepcopy(upgrade.WORKBUDDY_ENTRY_CONVERSION)):
            with self.subTest(entries=entries if isinstance(entries, str) else entries['type']):
                req = dict(self.request, source=target_source, operation_id='gate-%s' % (
                    'preserve' if isinstance(entries, str) else 'handler'))
                source, _ = user_install._source(req)
                req['conversions'] = [{'before': dict(schema_version=3, product_structure_version=1,
                                                      product_code_version='0.1.0', source=old_product['source']),
                                       'after': dict(schema_version=3, product_structure_version=1,
                                                     product_code_version='0.1.1',
                                                     source={k: source[k] for k in ('url', 'commit', 'tree_sha256')}),
                                       'direction': 'upgrade', 'entries': entries}]
                with self.assertRaises(ValueError):
                    cli.plan_machine(req)
                after = {str(p.relative_to(self.home)): p.read_bytes() if p.is_file() else None
                         for p in self.home.rglob('*') if not p.is_symlink()}
                self.assertEqual(after, before)

    def _files(self, root):
        return {str(p.relative_to(root)): legacy.digest(p.read_bytes())
                for p in root.rglob('*') if p.is_file()}
