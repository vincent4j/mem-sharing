"""Four-agent slice: WorkBuddy/DSH/ZCode/OpenCode on temporary HOME trees.

Extends the frozen two-agent chain evidence to the remaining four agents with
their real native user files from agents.json: normal plain-CLI share and
return, single public copy with every source recorded, native entry blocks per
agent, protection of CK/unique/unrelated bytes, environment redirect rejection
(DSH_HOME/OpenCode config) without echoing values, non-blocking variables
(DSH_AGENTS_HOME, ZCODE_HOME), parity with the frozen user_entries boundary
helpers, and rollback when a hook fails at the source-deletion stage.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import memory_share as ms
from agm_core import paths

SHARED = '- 提交信息使用中文。\n'
WORKBUDDY_TEXT = ('# 约定\n\n' + SHARED + '- 表达简洁，先给结论。\n\n'
                  '<!-- context-keeper:workbuddy:start -->\n私有经历，不参与共享。\n'
                  '<!-- context-keeper:workbuddy:end -->\n')
DSH_TEXT = '# 约定\n\n' + SHARED + '- 只走海运。\n'
ZCODE_TEXT = '# 约定\n\n' + SHARED + '- 只走空运。\n'
OLD_BLOCK = ('<!-- mem-sharing:public-source:start -->\n'
             '开始任务前读取并遵守 /old/public/MEMORY.md;读不到就说明。\n'
             '<!-- mem-sharing:public-source:end -->\n')
OPENCODE_TEXT = '# 约定\n\n' + SHARED + '- 新增依赖前先确认。\n\n' + OLD_BLOCK
NATIVE = {'workbuddy': '.workbuddy/MEMORY.md', 'dsh': '.dsh/AGENTS.md',
          'zcode': '.zcode/AGENTS.md', 'opencode': '.config/opencode/AGENTS.md'}
TEXTS = {'workbuddy': WORKBUDDY_TEXT, 'dsh': DSH_TEXT,
         'zcode': ZCODE_TEXT, 'opencode': OPENCODE_TEXT}
AGENTS = list(NATIVE)
ENV_VARS = ('DSH_HOME', 'DSH_AGENTS_HOME', 'ZCODE_HOME', 'XDG_CONFIG_HOME',
            'OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG')


class FourAgentChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # 隔离宿主环境：清空四家相关重定向变量，进程内 API 调用不继承真实配置，
        # 合成测试保持确定；子进程已在 cli_call 单独清洗。
        self.env_backup = {name: os.environ.get(name) for name in ENV_VARS}
        for name in ENV_VARS:
            os.environ.pop(name, None)
        self.addCleanup(self._restore_env)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.home.mkdir()
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')
        self.files = {}
        for agent, rel in NATIVE.items():
            target = self.home / rel
            target.parent.mkdir(parents=True)
            target.write_text(TEXTS[agent])
            self.files[agent] = target
        self.req = {'home': str(self.home), 'platform_config': self.config,
                    'agents': AGENTS}
        self.memories = self.home / '.mem-sharing' / 'memories'
        self.topic = self.memories / 'user-rules.md'
        self.originals = {a: p.read_bytes() for a, p in self.files.items()}

    def _restore_env(self):
        for name, value in self.env_backup.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def cli_call(self, *args, env_extra=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ('DSH_HOME', 'DSH_AGENTS_HOME', 'ZCODE_HOME',
                            'XDG_CONFIG_HOME', 'OPENCODE_CONFIG_DIR',
                            'OPENCODE_CONFIG')}
        if env_extra:
            env.update(env_extra)
        command = [sys.executable, '-B', str(Path(__file__).resolve().parents[2]
                   / 'scripts' / 'memory_share.py'), *args, '--home', str(self.home)]
        done = subprocess.run(command, capture_output=True, text=True, env=env)
        return done, json.loads(done.stdout or 'null')

    def proposal(self):
        preview = ms.plan_share(dict(self.req))
        self.assertEqual(preview['status'], 'completed', preview)
        items = []
        for agent in AGENTS:
            match = [s for s in preview['segments']
                     if s['agent'] == agent and s['text'] == SHARED]
            self.assertTrue(match, agent)
            items.append({'agent': agent, 'start': match[0]['start'],
                          'end': match[0]['end']})
        return {'schema_version': 1, 'basis': preview['basis'],
                'groups': [{'summary': '四家都要求中文提交信息',
                            'same_content': True, 'items': items}]}

    def do_share(self, hook=None):
        result = ms.plan_share(dict(self.req, proposal=self.proposal(),
                                    selection='按默认方案'))
        self.assertEqual(result['status'], 'approval_required', result)
        plan = result['approval_plan']
        approval = dict(plan, confirmed_at='2026-11-03T14:20:00Z',
                        reference='synthetic four-agent confirmation')
        outcome = ms.execute_share(plan, approval, request=self.req, hook=hook)
        self.assertEqual(outcome['status'], 'completed', outcome)
        return outcome

    def migrations(self, manifest_path):
        data = json.loads(Path(manifest_path).read_text())
        return data['operation_metadata']['share_user_memory']['migrations']

    # ---- normal chain ------------------------------------------------------

    def test_cli_share_single_copy_all_sources_and_native_entries(self):
        proposal_file = Path(self.tmp.name) / 'proposal.json'
        approval_file = Path(self.tmp.name) / 'approval.json'
        proposal_file.write_text(json.dumps(self.proposal(), ensure_ascii=False))
        argv = ['share-user-memory'] + sum((['--agent', a] for a in AGENTS), [])
        done, preview = self.cli_call(*argv, '--proposal-file', str(proposal_file))
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        plan = preview['approval_plan']
        self.assertEqual(plan['selected_numbers'], [1])
        approval_file.write_text(json.dumps(dict(
            plan, confirmed_at='2026-11-03T14:21:00Z',
            reference='synthetic CLI four-agent confirmation'), ensure_ascii=False))
        done, shared = self.cli_call('share-user-memory', '--approval-file',
                                     str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        records = self.migrations(shared['manifest'])
        # 完全同字节公共只此一份；四处来源逐处记录。
        self.assertEqual(len(records), 4)
        self.assertEqual({r['agent'] for r in records}, set(AGENTS))
        topic_bytes = self.topic.read_bytes()
        self.assertEqual(topic_bytes, '# 用户记忆\n\n- 提交信息使用中文。\n'.encode())
        self.assertEqual({(r['public_offset'], r['public_end']) for r in records},
                         {(topic_bytes.index(SHARED.encode()), len(topic_bytes))})
        runtime = ms._runtime(self.req)
        created = {c['agent']: c for c in json.loads(
            Path(shared['manifest']).read_text())['operation_metadata']
            ['share_user_memory']['entries_created']}
        self.assertEqual(set(created), set(AGENTS))
        for agent, path in self.files.items():
            data = path.read_bytes()
            self.assertEqual(ms._entry_state(agent, data, runtime), 1, agent)
            self.assertEqual(created[agent]['kind'], 'memory_index_block')
            # 独有内容保留；共享行精确删除；CK/旧兼容受管块逐字节保全。
            self.assertNotIn(SHARED.encode(), data)
            for unique in ('- 表达简洁，先给结论。', '- 只走海运。', '- 只走空运。',
                           '- 新增依赖前先确认。'):
                if unique in TEXTS[agent]:
                    self.assertIn(unique.encode(), data)
            if agent == 'workbuddy':
                self.assertIn(b'<!-- context-keeper:workbuddy:start -->', data)
            if agent == 'opencode':
                self.assertIn(OLD_BLOCK.encode(), data)
            expected = self.originals[agent].replace(SHARED.encode(), b'', 1)
            self.assertTrue(data.startswith(expected.rstrip(b'\n')))
        return shared

    def test_cli_full_return_restores_bytes_and_strips_entries(self):
        shared = self.do_share()
        records = self.migrations(shared['manifest'])
        current = self.topic.read_bytes()
        agent_plan = {'schema_version': 1,
                      'basis': {str(self.topic): ms.entries.sha256(current)},
                      'items': [{'ref': Path(shared['manifest']).parent.name,
                                 'migration': i,
                                 'public_span': {'start': r['public_offset'],
                                                 'end': r['public_end'],
                                                 'text_hex': r['text_hex']},
                                 'target': {'path': r['path'], 'mode': 'in_place'}}
                                for i, r in enumerate(records)],
                      'remove_entries': True}
        return_file = Path(self.tmp.name) / 'return.json'
        return_file.write_text(json.dumps(agent_plan, ensure_ascii=False))
        argv = ['return-user-memory'] + sum((['--agent', a] for a in AGENTS), [])
        done, preview = self.cli_call(*argv, '--return-plan-file', str(return_file))
        self.assertEqual(done.returncode, 5, done.stdout + done.stderr)
        approval_file = Path(self.tmp.name) / 'return-approval.json'
        approval_file.write_text(json.dumps(dict(
            preview['approval_plan'], confirmed_at='2026-11-03T14:22:00Z',
            reference='synthetic CLI four-agent return'), ensure_ascii=False))
        done, returned = self.cli_call('return-user-memory', '--return-plan-file',
                                       str(return_file), '--approval-file',
                                       str(approval_file))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        runtime = ms._runtime(dict(self.req))
        for agent, path in self.files.items():
            data = path.read_bytes()
            # 原文完整回到原位，只保留入口补齐时的分隔换行；入口已剥离。
            self.assertEqual(data, self.originals[agent] + b'\n', agent)
            self.assertEqual(ms._entry_state(agent, data, runtime), 0, agent)
        self.assertEqual(self.topic.read_bytes(), '# 用户记忆\n\n'.encode())

    # ---- protection and unknown -------------------------------------------

    def test_unknown_source_reported_and_blocks_execution(self):
        self.files['zcode'].unlink()
        self.files['zcode'].mkdir()  # 非普通文件：未知，不算无内容
        preview = ms.plan_share(dict(self.req))
        self.assertEqual(preview['status'], 'completed', preview)
        self.assertEqual(preview['participants'][str(self.files['zcode'])]['status'],
                         'unknown')
        items = []
        for agent in ('workbuddy', 'dsh', 'opencode'):
            match = [s for s in preview['segments']
                     if s['agent'] == agent and s['text'] == SHARED]
            items.append({'agent': agent, 'start': match[0]['start'],
                          'end': match[0]['end']})
        proposal = {'schema_version': 1, 'basis': preview['basis'],
                    'groups': [{'summary': '三家可读的同文偏好', 'same_content': True,
                                'items': items}]}
        result = ms.plan_share(dict(self.req, proposal=proposal, selection='共享 1'))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'unknown_source')

    # ---- environment boundaries -------------------------------------------

    def env_case(self, extra, agents=None):
        old = os.environ.copy()
        os.environ.update(extra)
        try:
            return ms.plan_share(dict(self.req, agents=agents or AGENTS))
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_redirects_rejected_without_value_echo_and_allies_allowed(self):
        elsewhere = str(Path(self.tmp.name) / 'elsewhere')
        # 重定向拒绝：DSH_HOME 与 OpenCode 配置根，均不回显原值。
        for extra, code in (({'DSH_HOME': elsewhere}, 'dsh_home_redirected'),
                            ({'XDG_CONFIG_HOME': str(Path(self.tmp.name) / 'xdg')},
                             'opencode_config_redirected'),
                            ({'OPENCODE_CONFIG': 'anything'}, 'opencode_config_redirected')):
            result = self.env_case(extra)
            self.assertEqual(result['status'], 'failed', (extra, result))
            self.assertEqual(result['errors'][0]['code'], code)
            for value in extra.values():
                self.assertNotIn(value, result['errors'][0]['message'])
        # ~/ 与 ~\ 前缀展开后等于默认根：不算重定向。
        for value in ('~/.dsh', '~\\.dsh'):
            result = self.env_case({'DSH_HOME': value})
            self.assertEqual(result['status'], 'completed', (value, result))
        # DSH_AGENTS_HOME 只影响 Skill 根，不得阻断仍有效用户入口；
        # ZCODE_HOME 不是规则根，不据此寻址也不据此阻断。
        for extra in ({'DSH_AGENTS_HOME': elsewhere}, {'ZCODE_HOME': elsewhere},
                      {'DSH_HOME': '   '}):
            result = self.env_case(extra)
            self.assertEqual(result['status'], 'completed', (extra, result))
        preview = self.env_case({'ZCODE_HOME': elsewhere})
        self.assertEqual(preview['participants'][str(self.files['zcode'])]['status'],
                         'ok')

    def test_boundary_helpers_match_frozen_user_entries_contract(self):
        from agm_core import user_entries
        matrix = [None, '', '   ', '~/.dsh', '~\\.dsh', '~', str(self.home / '.dsh'),
                  str(self.home / '.dsh/'), '/somewhere/else', 'relative/.dsh',
                  '~/../.dsh']
        for value in matrix:
            for env in ({}, {'DSH_HOME': value}, {'DSH_HOME': value, 'DSH_AGENTS_HOME': '/x'}):
                clean = {k: v for k, v in env.items() if v is not None}
                with unittest.mock.patch.dict(os.environ, clean, clear=True):
                    self.assertEqual(ms._dsh_home_redirected(self.home),
                                     user_entries.dsh_home_redirected(self.home), env)
        oc_matrix = [None, '', '  ', str(self.home / '.config'),
                     str(self.home / '.config/opencode'), '/elsewhere', 'relative']
        for value in oc_matrix:
            for name in ('XDG_CONFIG_HOME', 'OPENCODE_CONFIG_DIR'):
                clean = {name: value} if value is not None else {}
                with unittest.mock.patch.dict(os.environ, clean, clear=True):
                    self.assertEqual(ms._opencode_config_redirected(self.home),
                                     user_entries.opencode_config_redirected(self.home),
                                     (name, value))
            with unittest.mock.patch.dict(os.environ, {'OPENCODE_CONFIG': value or ''},
                                          clear=True):
                self.assertEqual(ms._opencode_config_redirected(self.home),
                                 user_entries.opencode_config_redirected(self.home))

    # ---- rollback ----------------------------------------------------------

    def test_hook_failure_at_deletion_rolls_back_everything(self):
        natives = {str(p) for p in self.files.values()}

        def fault(event, path):
            if event != 'after_write' or str(path) not in natives:
                return
            if SHARED.encode() not in Path(path).read_bytes():
                raise ms.TransactionError('synthetic failure at source deletion')
        result = ms.plan_share(dict(self.req, proposal=self.proposal(),
                                    selection='按默认方案'))
        outcome = ms.execute_share(result['approval_plan'],
                                   dict(result['approval_plan'],
                                        confirmed_at='2026-11-03T14:23:00Z',
                                        reference='synthetic user confirmation'),
                                   request=self.req, hook=fault)
        self.assertEqual(outcome['status'], 'failed', outcome)
        self.assertEqual(outcome['errors'][0]['code'], 'transaction_failed')
        self.assertTrue(outcome['errors'][0]['manifest'])
        for agent, path in self.files.items():
            self.assertEqual(path.read_bytes(), self.originals[agent], agent)
        self.assertFalse(self.topic.exists())
        self.assertFalse((self.memories / 'MEMORY.md').exists())


if __name__ == '__main__':
    unittest.main()
