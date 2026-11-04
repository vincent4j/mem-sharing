"""项目共享硬崩溃/恢复与旧安装兼容的合成运行时验收。

合同（SKILL.md 项目记忆行 + docs/acceptance/skill-first-project-chain.md）：
子进程硬退出（os._exit，非异常回滚）后，事务清单持久于
<项目>/.mem-sharing/backups/，陈旧两层锁不被抢占；操作员核实进程结束后处置
锁，先只读核验再按批准回滚，三个项目文件逐字节回到共享前原文；旧安装登记
按 registry.py 真实布局构造（schema_version 3，projects.<main> 记录含
main_checkout/memory_policy/checkouts），旧入口保全/冲突依 _entry_state 合同。
全部使用合成临时 Git 主 checkout 与临时 HOME，不接触真实环境。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agm_core import project_share as ps
from project_share_crash_fixture import (AGENTS_TEXT, CLAUDE_TEXT, TESTS,
                                         WB_TEXT, ZH)

FIXTURE = Path(__file__).resolve().parent / 'project_share_crash_fixture.py'


def git(repo, *args):
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                          text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


class RuntimeFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.home.mkdir()
        self.repo = Path(self.tmp.name).resolve() / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init')
        git(self.repo, 'config', 'user.email', 't@t')
        git(self.repo, 'config', 'user.name', 't')
        self.agents = self.repo / 'AGENTS.md'
        self.claude = self.repo / 'CLAUDE.md'
        self.wb = self.repo / '.workbuddy' / 'memory' / 'MEMORY.md'
        self.wb.parent.mkdir(parents=True)
        for path, text in ((self.agents, AGENTS_TEXT), (self.claude, CLAUDE_TEXT),
                           (self.wb, WB_TEXT)):
            path.write_text(text)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-m', 'init')
        self.req = {'home': str(self.home), 'project': str(self.repo)}
        self.originals = {p: p.read_bytes() for p in (self.agents, self.claude, self.wb)}
        self.lock = self.repo / '.mem-sharing' / 'var' / '.agm.lock'
        self.tx_lock = self.lock / 'transaction'
        self.backups = self.repo / '.mem-sharing' / 'backups'

    def old_registry(self, policy):
        """真实旧安装登记布局（registry.py:163/180/500）：v3 + 完整项目记录。"""
        main = str(self.repo)
        registry = self.home / '.mem-sharing' / 'var' / 'registry.json'
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({
            'schema_version': 3,
            'projects': {main: {'main_checkout': main, 'memory_policy': policy,
                                'checkouts': []}},
            'shared_objects': {}}, ensure_ascii=False))

    def do_share(self):
        from project_share_crash_fixture import build_proposal
        result = ps.plan_share(dict(self.req, proposal=build_proposal(self.req),
                                    selection='共享 1、2'))
        self.assertEqual(result['status'], 'approval_required', result)
        plan = result['approval_plan']
        return ps.execute_share(
            plan, dict(plan, confirmed_at='2026-11-03T15:41:00Z',
                       reference='synthetic runtime confirmation'), request=self.req)


class HardCrashRecoveryTests(RuntimeFixture):
    """子进程硬退出（退出码 9，无异常回滚）后按合同恢复。"""

    def crash(self, event, suffix, occurrence=1):
        spec = Path(self.tmp.name) / 'crash-spec.json'
        spec.write_text(json.dumps({'home': str(self.home), 'project': str(self.repo),
                                    'event': event, 'path_suffix': suffix,
                                    'occurrence': occurrence, 'exit_code': 9}))
        done = subprocess.run([sys.executable, '-B', str(FIXTURE), str(spec)],
                              capture_output=True, text=True)
        # 硬退出合同：精确退出码 9（非信号、非 0/2/5），无 JSON 输出、无回滚。
        self.assertEqual(done.returncode, 9, done.stdout + done.stderr)
        self.assertEqual(done.stdout, '')
        return done

    def recover(self):
        """操作员恢复流程：核实硬退出 → 陈旧锁 fail closed → 处置锁 → 核验 → 批准回滚。"""
        manifests = sorted(self.backups.glob('*/manifest.json'))
        self.assertEqual(len(manifests), 1, '崩溃后必须恰有一份事务清单')
        manifest = manifests[0]
        self.assertEqual(json.loads(manifest.read_text())['status'], 'applying')
        # 崩溃遗留两层陈旧锁：新共享被未闭合事务阻断（code=recovery_required）。
        self.assertTrue(self.lock.is_dir() and self.tx_lock.is_dir())
        blocked = ps.plan_share(dict(self.req))
        self.assertEqual(blocked['errors'][0]['code'], 'recovery_required', blocked)
        # 陈旧锁永不抢占（write_lock 原语合同，SKILL：陈旧锁不会自动抢占）。
        with self.assertRaises(ps.TransactionError) as caught:
            with ps.write_lock(self.lock):
                pass
        self.assertEqual(caught.exception.code, 'lock_conflict')
        # 恢复在陈旧锁现场必须拒绝完成且零写。
        before = {p: p.read_bytes() for p in self.originals}
        request = dict(self.req, manifest=str(manifest))
        refused = ps.run_recover(dict(request))
        self.assertNotEqual(refused['status'], 'completed', refused)
        self.assertEqual({p: p.read_bytes() for p in self.originals}, before)
        # 操作员核实进程已结束（子进程已返回 9）后处置两层陈旧锁。
        self.tx_lock.rmdir()
        self.lock.rmdir()
        preview = ps.run_recover(dict(request))
        self.assertEqual(preview['status'], 'approval_required', preview)
        self.assertEqual({p: p.read_bytes() for p in self.originals}, before,
                         '只读核验必须零写')
        result = ps.run_recover(dict(request, approval=dict(
            preview['approval_plan'], confirmed_at='2026-11-03T15:42:00Z',
            reference='synthetic crash recovery approval')))
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['recovery_status'], 'rolled_back')
        # 逐字节回到共享前原文；锁释放；未闭合事务清零，可重新共享。
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original, str(path))
        self.assertFalse(self.lock.exists())
        self.assertEqual(json.loads(manifest.read_text())['status'], 'rolled_back')
        self.assertEqual(ps.plan_share(dict(self.req))['status'], 'completed')

    FINAL_CLAUDE = '# 约定\n\n- 表达简洁，先给结论。\n\n@AGENTS.md\n'
    FINAL_WB_PREFIX = '# 约定\n\n- 只走海运。\n\n'

    def crash_scene_bytes(self, agents_changed, claude_stage, wb_stage):
        """按文件实际阶段断言：stage ∈ original / entry（原文前缀完整+入口1个）
        / deleted（删源后终态，原文已不在）。不弱化原文与入口完整性。"""
        agents = self.agents.read_bytes()
        if agents_changed:
            self.assertEqual(agents, AGENTS_TEXT.encode() + b'\n' + TESTS.encode())
        else:
            self.assertEqual(agents, AGENTS_TEXT.encode())
        stages = {'claude': (self.claude, CLAUDE_TEXT, b'@AGENTS.md\n',
                            self.FINAL_CLAUDE),
                  'wb': (self.wb, WB_TEXT, ps.WORKBUDDY_BLOCK, None)}
        for name, stage in (('claude', claude_stage), ('wb', wb_stage)):
            path, base, entry, final = stages[name]
            data = path.read_bytes()
            if stage == 'original':
                self.assertEqual(data, base.encode(), name)
            elif stage == 'entry':
                self.assertTrue(data.startswith(base.encode()),
                                '入口只追加，原文前缀必须完整：' + name)
                self.assertEqual(data.count(entry), 1, name)
            elif stage == 'deleted':
                if final is not None:
                    self.assertEqual(data, final.encode(), name)
                else:
                    self.assertEqual(data, self.FINAL_WB_PREFIX.encode()
                                     + ps.WORKBUDDY_BLOCK, name)
                self.assertNotIn(ZH.encode(), data, '删源后原文必须确实移除')
                self.assertNotIn(base.encode(), data, name)

    def test_crash_before_public_write(self):
        self.crash('before_write', 'AGENTS.md')
        self.crash_scene_bytes(False, 'original', 'original')
        self.recover()

    def test_crash_after_public_write(self):
        self.crash('after_write', 'AGENTS.md')
        self.crash_scene_bytes(True, 'original', 'original')
        self.recover()

    def test_crash_after_first_entry_write(self):
        # 首个入口写入是 WB 桥块（.workbuddy 路径排序在前）。
        self.crash('after_write', 'MEMORY.md', occurrence=1)
        self.crash_scene_bytes(True, 'original', 'entry')
        self.recover()

    def test_crash_after_second_entry_write(self):
        self.crash('after_write', 'CLAUDE.md', occurrence=1)
        self.crash_scene_bytes(True, 'entry', 'entry')
        self.recover()

    def test_crash_before_first_source_deletion(self):
        # 写入按路径排序：.workbuddy 在 CLAUDE 前，首处删源是 WB 删源
        # （MEMORY.md 第 2 次 before_write；第 1 次是入口安装）。
        self.crash('before_write', 'MEMORY.md', occurrence=2)
        self.crash_scene_bytes(True, 'entry', 'entry')
        self.recover()

    def test_crash_after_first_source_deletion(self):
        # WB 删源写入已落盘：已删内容确实消失；CLAUDE 仍在原文+入口态。
        self.crash('after_write', 'MEMORY.md', occurrence=2)
        self.crash_scene_bytes(True, 'entry', 'deleted')
        self.assertIn(ZH.encode(), self.claude.read_bytes())
        self.recover()

    def test_crash_after_last_source_deletion(self):
        # 最后一次写入（CLAUDE 删源）落盘后、提交前硬退出：全链终态仍须可恢复。
        self.crash('after_write', 'CLAUDE.md', occurrence=2)
        self.crash_scene_bytes(True, 'deleted', 'deleted')
        self.recover()


class OldInstallCompatTests(RuntimeFixture):
    """旧安装登记与旧入口：真实 v3 registry 布局 + _entry_state 入口合同。"""

    def test_old_enabled_registry_and_existing_entries_preserved(self):
        self.old_registry('follow_ck')
        # 旧入口已存在：CLAUDE 已有 @ 导入行、WorkBuddy 已有受管桥块。
        self.claude.write_text(CLAUDE_TEXT + '\n@AGENTS.md\n')
        self.wb.write_bytes(WB_TEXT.encode() + b'\n' + ps.WORKBUDDY_BLOCK)
        outcome = self.do_share()
        self.assertEqual(outcome['status'], 'completed', outcome)
        # 旧入口原样保全，不重复添加；共享仍完成内容迁移与删源。
        self.assertEqual(self.claude.read_bytes().count(b'@AGENTS.md\n'), 1)
        self.assertEqual(self.wb.read_bytes().count(ps.WORKBUDDY_BLOCK), 1)
        self.assertNotIn(ZH.encode(), self.claude.read_bytes())
        self.assertIn(TESTS.encode(), self.agents.read_bytes())

    def test_old_disabled_registry_blocks_share(self):
        self.old_registry('disabled')
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'project_disabled')
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original, '拒绝必须零写')

    def test_old_corrupt_registry_fails_closed(self):
        registry = self.home / '.mem-sharing' / 'var' / 'registry.json'
        registry.parent.mkdir(parents=True)
        registry.write_text('{corrupt old install registry')
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'disabled_unknown')
        # 旧登记缺 memory_policy 键（仅 main_checkout/checkouts）同样 fail closed。
        main = str(self.repo)
        registry.write_text(json.dumps({'schema_version': 3, 'projects': {
            main: {'main_checkout': main, 'checkouts': []}}, 'shared_objects': {}}))
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['errors'][0]['code'], 'disabled_unknown')

    def test_drifted_old_workbuddy_block_fails_closed(self):
        self.wb.write_bytes(WB_TEXT.encode() + b'\n'
                            + b'<!-- mem-sharing:project-rules:start -->\n'
                            + b'<!-- mem-sharing:project-rules:end -->\n'
                            + b'<!-- mem-sharing:project-rules:start -->\n'
                            + b'<!-- mem-sharing:project-rules:end -->')
        result = ps.plan_share(dict(self.req))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['errors'][0]['code'], 'entry_conflict')

    def test_duplicate_old_claude_import_lines_fail_closed_at_execution(self):
        # 现行合同：@ 导入行计数非 0 即不新增入口；计数 2 在删源守卫处 fail
        # closed（入口未就绪），事务回滚、原文保全，不产生无入口删源。
        self.claude.write_text(CLAUDE_TEXT + '\n@AGENTS.md\n\n@AGENTS.md\n')
        outcome = self.do_share()
        self.assertIn(outcome['status'], ('failed', 'recovery_required'), outcome)
        self.assertIn(outcome['errors'][0]['code'],
                      ('transaction_failed', 'entry_conflict'), outcome)
        self.assertIn('未就绪', outcome['errors'][0]['message'])
        self.assertEqual(self.claude.read_bytes(),
                         (CLAUDE_TEXT + '\n@AGENTS.md\n\n@AGENTS.md\n').encode())
        self.assertEqual(self.agents.read_bytes(), self.originals[self.agents])


if __name__ == '__main__':
    unittest.main()
