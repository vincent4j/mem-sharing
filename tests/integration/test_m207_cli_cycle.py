"""M2-07 集成回归:agm.py CLI 子进程级的装/补/查/拆全周期幂等与故障矩阵。

隔离:整体拷贝真实安装树(agm.py + agm_core + agents.json)到临时目录,
临时 HOME、临时项目仓库、Keeper 桩 checkout(真实子进程脚本);不触碰真实
registry/入口/记录库。所有断言基于真实文件字节/mtime 快照与 CLI JSON envelope,
不以 mock 成功替代文件行为。运行:仓库根目录 `python3 -m unittest discover -s tests/integration`。
"""

import hashlib
import itertools
import json
import os
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests/unit"))
from runtime_fixture import seed_runtime, seed_project_executors, CLI_DETECTION_BOOTSTRAP

INSTALL_STUB = "raise AssertionError('project enable must not invoke CK installer')\n"
PROBE_STUB = "raise AssertionError('project enable must not invoke CK probe')\n"


class CliHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.install = self.area / "agm" / "scripts"
        self.install.mkdir(parents=True)
        shutil.copy(REPO / "scripts/agm.py", self.install / "agm.py")
        shutil.copy(REPO / "scripts/agents.json", self.install / "agents.json")
        core = self.install / "agm_core"
        core.mkdir()
        for source in (REPO / "scripts/agm_core").glob("*.py"):
            shutil.copy(source, core / source.name)
        self.agm = self.install / "agm.py"
        self.registry = self.install / "registry.json"
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.registry = self.runtime.registry
        self.root = self.area / "project"
        self.root.mkdir()
        self.git("init", "-q", str(self.root))
        self.keeper = self.area / "keeper"
        (self.keeper / "scripts").mkdir(parents=True)
        self.git("init", "-q", str(self.keeper))
        (self.keeper / "SKILL.md").write_text("name: context-keeper\n")
        (self.keeper / "scripts/install.py").write_text(INSTALL_STUB)
        (self.keeper / "scripts/context_keeper_probe.py").write_text(PROBE_STUB)
        self._approvals = itertools.count()
        self.execution_signals=seed_project_executors(self.home)

    def git(self, *args):
        subprocess.run(["git", *args], check=True, capture_output=True)

    def cli(self, argv):
        env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1", PATH=self.execution_signals["search_paths"][0])
        result = subprocess.run([sys.executable,"-B","-c",CLI_DETECTION_BOOTSTRAP,str(self.agm),*argv], cwd=str(self.area),
                                capture_output=True, text=True, env=env)
        envelope = json.loads(result.stdout)
        return result.returncode, envelope

    def cli_tty(self, argv):
        """交互(PTY)路径:remove 的内核级预览仅在交互终端可达(非交互被外壳保守门拦截)。"""
        import pty
        master, slave = pty.openpty()
        env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1", PATH=self.execution_signals["search_paths"][0])
        proc = subprocess.Popen([sys.executable,"-B","-c",CLI_DETECTION_BOOTSTRAP,str(self.agm),*argv], stdin=slave,
                                stdout=slave, stderr=subprocess.PIPE, env=env,
                                cwd=str(self.area))
        os.close(slave)
        chunks = []
        while True:
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        os.close(master)
        proc.stderr.read()
        proc.stderr.close()
        proc.wait()
        text = b"".join(chunks).decode("utf-8", "replace")
        return proc.returncode, json.loads(text[text.index("{"):])

    def approve(self, argv, *, edit=None, expect=5):
        rc, envelope = self.cli(argv)
        self.assertEqual(rc, expect, envelope)
        plan = json.loads(envelope["next_action"])
        if edit:
            edit(plan)
        plan["confirmed_at"] = "2026-10-29T00:00:00Z"
        plan["reference"] = "m2-07 cli integration confirmation"
        path = self.area / ("approval-%d.json" % next(self._approvals))
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.cli(list(argv) + ["--approval-file", str(path)])

    def approve_remove(self):
        rc, envelope = self.cli_tty(["remove-memory", "--project", str(self.root)])
        self.assertEqual(rc, 5, envelope)
        approval=json.loads(envelope['next_action'])
        approval.update(confirmed_at='2026-10-30T00:00:00Z',reference='exact CLI removal confirmation')
        path = self.area / ("approval-%d.json" % next(self._approvals))
        path.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.cli(["remove-memory", "--project", str(self.root),
                         "--approval-file", str(path)])

    def link_alias(self):
        alias = self.root / ".agents/skills/context-keeper"
        alias.parent.mkdir(parents=True, exist_ok=True)
        if not alias.is_symlink():
            alias.symlink_to(self.keeper, target_is_directory=True)
        return alias

    def enable_memory(self, *, edit=None):
        """完整装配记忆档:先建项目 Skill 链接供源发现,再预览→批准→执行。"""
        (self.root/".workbuddy/memory").mkdir(parents=True,exist_ok=True)  # Native WorkBuddy-created fixture, §8.2.
        self.link_alias()
        return self.approve(["enable-memory", "--project", str(self.root), "--memory", "--agent", "codex", "claude", "workbuddy"], edit=edit)

    def check(self, *extra):
        return self.cli(["check-memory", "--project", str(self.root), *extra])

    def snapshot(self, *roots, exclude=()):
        """真实文件证据:文件/符号链接记(类型, 内容, mtime_ns);目录只记存在性——
        目录 mtime 会因被排除项(registry/备份/.git)的写入而联动,不属于输出字节证据。"""
        out = {}
        for root in roots:
            for path in sorted(root.rglob("*")):
                if any(str(path) == str(item) or Path(item) in path.parents for item in exclude):
                    continue
                info = path.lstat()
                if stat_module.S_ISLNK(info.st_mode):
                    out[str(path)] = ("symlink", os.readlink(path), info.st_mtime_ns)
                elif stat_module.S_ISDIR(info.st_mode):
                    out[str(path)] = ("dir", None, None)
                else:
                    out[str(path)] = ("file", hashlib.sha256(path.read_bytes()).hexdigest(),
                                      info.st_mtime_ns)
        return out

    def outputs_snapshot(self, exclude=()):
        """幂等断言口径:项目 + HOME + 安装树。排除设计上会刷新的 registry/备份,
        以及 git 自身会触碰 mtime 的 .git 元数据(非 AGM 输出)。"""
        return self.snapshot(self.root, self.home, self.install.parent,
                             exclude=[self.registry, self.runtime.backups,
                                      self.root / ".git", *exclude])


class IdempotencyTests(CliHarness):
    def test_default_cli_does_not_precreate_or_patch_installed_claude(self):
        for existing in (False,True):
            with self.subTest(existing=existing):
                root=self.area/('existing-claude' if existing else 'unused-claude');root.mkdir();self.git('init','-q',str(root))
                entry=root/'CLAUDE.md'
                if existing:entry.write_bytes(b'private rules\xff\r\n')
                before=(entry.read_bytes(),entry.stat().st_mtime_ns) if existing else None
                rc,result=self.approve(['enable-memory','--project',str(root)])
                self.assertEqual(rc,0,result)
                self.assertEqual(result['projects'][0]['agents'],['codex','claude','workbuddy'])
                if existing:self.assertEqual((entry.read_bytes(),entry.stat().st_mtime_ns),before)
                else:self.assertFalse(entry.exists())
                self.assertFalse((root/'.workbuddy').exists())
                rc,result=self.cli(['check-memory','--project',str(root)])
                self.assertEqual(rc,0,result)
                rc,result=self.approve(['enable-memory','--project',str(root),'--agent','claude'])
                self.assertEqual(rc,0,result);self.assertIn(b'@AGENTS.md',entry.read_bytes())
                if existing:self.assertTrue(entry.read_bytes().startswith(before[0]))

    def test_second_enable_changes_no_byte_or_mtime(self):
        rc,_=self.enable_memory();self.assertEqual(rc,0)
        before=self.outputs_snapshot();rc,result=self.cli(['enable-memory','--project',str(self.root)])
        self.assertEqual(rc,0,result);self.assertEqual(result['changes'],[]);self.assertEqual(self.outputs_snapshot(),before)

    def test_cleared_pointer_check_only_reports_then_enable_repairs(self):
        self.assertEqual(self.enable_memory()[0],0)
        path=self.root/'.workbuddy/memory/MEMORY.md';raw=path.read_bytes();path.unlink()
        before=self.outputs_snapshot();rc,result=self.check()
        self.assertEqual(rc,1,result);self.assertEqual(before,self.outputs_snapshot());self.assertFalse(path.exists())
        rc,result=self.cli(['enable-memory','--project',str(self.root)])
        self.assertEqual(rc,0,result);self.assertEqual(path.read_bytes(),raw)

    def test_no_ck_source_is_needed_and_no_store_initialized(self):
        shutil.rmtree(self.keeper)
        rc,result=self.approve(['enable-memory','--project',str(self.root)])
        self.assertEqual(rc,0,result);self.assertEqual(self.check()[0],0)
        self.assertFalse((self.root/'docs/context-keeper').exists())

    def test_legacy_keeper_block_requires_exact_review(self):
        old=b'<!-- context-keeper:start -->\nlegacy CK\n<!-- context-keeper:end -->'
        (self.root/'AGENTS.md').write_bytes(b'user rules\xff\r\n'+old)
        rc,result=self.cli(['enable-memory','--project',str(self.root)])
        self.assertEqual(rc,5,result);plan=json.loads(result['next_action'])
        self.assertEqual(bytes.fromhex(plan['legacy_bridge_transition'][0]['before_hex']),old)
        self.assertIn(old,(self.root/'AGENTS.md').read_bytes())
        self.assertEqual(self.approve(['enable-memory','--project',str(self.root)])[0],0)
        self.assertNotIn(old,(self.root/'AGENTS.md').read_bytes())
        self.assertTrue((self.root/'AGENTS.md').read_bytes().startswith(b'user rules\xff\r\n'))

    def test_disabled_persisted_healthy_and_no_silent_flip(self):
        argv=['enable-memory','--project',str(self.root),'--no-memory']
        self.assertEqual(self.approve(argv)[0],0)
        self.assertEqual(self.check()[0],0)
        self.assertEqual(self.cli(['enable-memory','--project',str(self.root)])[0],0)
        self.assertEqual(json.loads(self.registry.read_bytes())['projects'][str(self.root)]['memory_policy'],'disabled')
        self.assertEqual(self.cli(['enable-memory','--project',str(self.root),'--memory'])[0],5)
        self.assertEqual(self.approve(['enable-memory','--project',str(self.root),'--memory'])[0],0)

    def test_invalid_legacy_approval_fields_rejected(self):
        def edit(plan):plan['provider_source']=str(self.keeper)
        rc,result=self.approve(['enable-memory','--project',str(self.root)],edit=edit)
        self.assertEqual(rc,2,result);self.assertFalse((self.root/'AGENTS.md').exists())

    def test_foreign_skill_copy_untouched(self):
        path=self.root/'.codex/skills/context-keeper';path.mkdir(parents=True);(path/'local').write_bytes(b'private')
        self.assertEqual(self.enable_memory()[0],0);self.assertEqual((path/'local').read_bytes(),b'private')

    def test_corrupt_registry_conservative_all_commands(self):
        self.assertEqual(self.enable_memory()[0],0);self.registry.write_bytes(b'{broken')
        before=self.outputs_snapshot()
        rc,result=self.cli(['enable-memory','--project',str(self.root)]);self.assertEqual(rc,2,result)
        self.assertEqual(self.check()[0],1)
        self.assertEqual(self.cli_tty(['remove-memory','--project',str(self.root)])[0],2)
        self.assertEqual(self.registry.read_bytes(),b'{broken');self.assertEqual(before,self.outputs_snapshot())

    def test_remove_twice_then_explicit_reenable_cycle(self):
        self.assertEqual(self.enable_memory()[0],0)
        rc,result=self.approve_remove();self.assertEqual(rc,0,result)
        self.assertNotIn(b'mem-sharing:project-experience',(self.root/'AGENTS.md').read_bytes())
        self.assertIn(b'mem-sharing:memory-denied',(self.root/'AGENTS.md').read_bytes())
        self.assertEqual(self.cli_tty(['remove-memory','--project',str(self.root)])[0],0)
        self.assertEqual(self.check()[0],0)
        self.assertEqual(self.approve(['enable-memory','--project',str(self.root),'--memory'])[0],0)
        self.assertEqual(self.check()[0],0)

    def test_check_all_two_projects_zero_write(self):
        self.assertEqual(self.enable_memory()[0],0)
        other=self.area/'second';other.mkdir();self.git('init','-q',str(other))
        self.assertEqual(self.approve(['enable-memory','--project',str(other),'--agent','codex'])[0],0)
        before=self.snapshot(self.area,exclude=[self.root/'.git',other/'.git'])
        rc,result=self.cli(['check-memory','--all'])
        self.assertEqual(rc,1,result)  # Matrix reports Claude/WB not yet assembled in second project.
        self.assertEqual(len(result['projects']),2)
        self.assertEqual(before,self.snapshot(self.area,exclude=[self.root/'.git',other/'.git']))

    def test_noninteractive_remove_never_consumes_stdin_as_approval(self):
        self.assertEqual(self.enable_memory()[0],0);before=self.outputs_snapshot()
        rc,result=self.cli(['remove-memory','--project',str(self.root)])
        self.assertEqual(rc,5,result);self.assertEqual(before,self.outputs_snapshot())

    def test_no_pycache_or_lock_residue(self):
        self.assertEqual(self.enable_memory()[0],0);self.assertEqual(self.check()[0],0)
        self.assertFalse(list(self.install.rglob('__pycache__')))
        self.assertFalse(self.runtime.lock.exists());self.assertFalse(self.runtime.transaction_lock.exists())
