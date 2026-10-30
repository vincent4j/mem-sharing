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

INSTALL_STUB = r'''import json, sys, traceback
from pathlib import Path
BRIDGE_START = "<!-- context-keeper:start -->"
BRIDGE_END = "<!-- context-keeper:end -->"
BRIDGE = f"{BRIDGE_START}\nKeeper rules\n{BRIDGE_END}\n"
WORKBUDDY_BRIDGE_START = "<!-- context-keeper:workbuddy:start -->"
WORKBUDDY_BRIDGE_END = "<!-- context-keeper:workbuddy:end -->"
WORKBUDDY_BRIDGE = f"{WORKBUDDY_BRIDGE_START}\nUpstream WorkBuddy rules\n{WORKBUDDY_BRIDGE_END}\n"
SKILLS = {"codex": (".agents/skills", ".codex/skills"), "claude": (".claude/skills",), "workbuddy": (".workbuddy/skills",)}

def main():
    args = sys.argv[1:]
    def value(name): return args[args.index(name)+1]
    source = Path(__file__).resolve().parents[1]
    if "--ensure-bridge" in args:
        root = Path(value("--root"))
        bridge = root / (".workbuddy/memory/MEMORY.md" if "--workbuddy" in args else "AGENTS.md" if "--codex" in args else "CLAUDE.md")
        assert (WORKBUDDY_BRIDGE if "--workbuddy" in args else BRIDGE).rstrip() in bridge.read_text()
        print(json.dumps(dict(scope="project", bridge=str(bridge), action="unchanged")))
        sys.exit(0)
    root = Path(value("--project"))
    links, rules = [], []
    for agent, bases in SKILLS.items():
        if "--" + agent not in args: continue
        links += [str(root / base / "context-keeper") for base in bases]
        rules.append(str(root / (".workbuddy/memory/MEMORY.md" if agent == "workbuddy" else "AGENTS.md" if agent == "codex" else "CLAUDE.md")))
    if "--approved" not in args:
        print(json.dumps(dict(approval_required=True, skill_entries=links, rule_files=rules)))
        sys.exit(0)
    for link in links:
        assert Path(link).is_symlink() and Path(link).resolve() == source
    for rule in rules:
        assert (WORKBUDDY_BRIDGE if Path(rule).name == "MEMORY.md" else BRIDGE).rstrip() in Path(rule).read_text()
    print(json.dumps(dict(scope="project", project=str(root))))

try:
    main()
except SystemExit:
    raise
except BaseException:
    (Path(__file__).resolve().parents[1] / "trace.log").open("a").write(
        repr(sys.argv) + "\n" + traceback.format_exc() + "\n")
    raise
'''

PROBE_STUB = r'''import sys, traceback
from pathlib import Path

def main():
    args = sys.argv[1:]
    def value(name): return args[args.index(name)+1]
    root, store = Path(value("--root")), Path(value("--store-dir"))
    mode = (Path(__file__).resolve().parents[1] / "mode")
    mode = mode.read_text() if mode.exists() else ""
    if mode == "migration": sys.exit(3)
    complete = (store / "memory-keeper.md").is_file() and all(
        (store / name).is_dir() for name in ("plans", "worklogs", "evolution"))
    if "--approved" not in args:
        sys.exit(0 if complete else 5)
    if not complete:  # 幂等 init:已有完整库时不改写任何字节
        store.mkdir(parents=True, exist_ok=True)
        (store / "memory-keeper.md").write_text("# keeper store\n")
        if mode == "partial": sys.exit(2)
        for name in ("plans", "worklogs", "evolution"):
            (store / name).mkdir(exist_ok=True)
        if store != root / "docs/context-keeper":
            (root / "context-keeper.json").write_text('{"directory": "%s"}' % str(store))
    print("store ready")

try:
    main()
except SystemExit:
    raise
except BaseException:
    (Path(__file__).resolve().parents[1] / "trace.log").open("a").write(
        repr(sys.argv) + "\n" + traceback.format_exc() + "\n")
    raise
'''


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
        project = json.loads(self.registry.read_text())["projects"][str(self.root)]
        assembly = project["checkouts"][str(self.root)]
        common = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--git-common-dir"],
                                check=True, capture_output=True, text=True).stdout.strip()
        approval = {
            "schema_version": 1, "command": "remove-memory",
            "main_checkout": str(self.root), "checkout": str(self.root),
            "git_common_dir": str((self.root / common).resolve()),
            "agents": assembly["agents"], "memory_authorization": None,
            "store_path": assembly["store"]["path"], "provider_source": project["provider_source"],
            "provider_fingerprints": [],
            "changes": [{"path": c["path"], "operation": c["operation"],
                         "before_fingerprint": c["before_fingerprint"],
                         "after_fingerprint": c["after_fingerprint"]}
                        for c in envelope["changes"]],
            "confirmed_at": "2026-10-29T00:00:00Z", "reference": "m2-07 removal approval",
        }
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
        return self.approve(["enable-memory", "--project", str(self.root), "--memory"], edit=edit)

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
    def test_second_enable_changes_no_byte_or_mtime(self):
        rc, _ = self.enable_memory()
        self.assertEqual(rc, 0)
        before = self.outputs_snapshot()
        rc, envelope = self.cli(["enable-memory", "--project", str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual(envelope["changes"], [], envelope)
        self.assertEqual(self.outputs_snapshot(), before,
                         "二次 enable 不得改变任何输出字节或 mtime(registry 证据时间戳与备份除外)")

    def test_cleared_bridge_check_only_reports_then_enable_repairs(self):
        _, _ = self.enable_memory()
        path = self.root / "AGENTS.md"
        original = path.read_bytes()
        start = b"<!-- context-keeper:start -->"
        end = b"<!-- context-keeper:end -->"
        left, right = original.index(start), original.index(end) + len(end)
        cleared = original[:left] + original[right:]
        path.write_bytes(cleared)
        watched = [self.root / ".git"]
        before = self.snapshot(self.root, self.home, self.install.parent, exclude=watched)

        rc, envelope = self.check()
        self.assertEqual(rc, 1, envelope)
        codes = {gap["code"] for gap in envelope["projects"][0]["gaps"]}
        self.assertIn("object_missing", codes)
        self.assertEqual(self.snapshot(self.root, self.home, self.install.parent, exclude=watched),
                         before, "check 只报告不修复,任何文件字节/mtime 不得变化")

        rc, envelope = self.cli(["enable-memory", "--project", str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual(path.read_bytes(), original,
                         "幂等补装必须精确恢复被清空的桥接块,其余字节原样")


class InstallOrderTests(CliHarness):
    def test_group_first_then_keeper(self):
        rc, envelope = self.approve(["enable-memory", "--project", str(self.root), "--no-memory"])
        self.assertEqual(rc, 0, envelope)
        self.assertTrue((self.root / "AGENTS.md").read_bytes()
                        .startswith(b"# " + self.root.name.encode()))
        self.assertFalse((self.root / "docs/context-keeper").exists())

        rc, envelope = self.enable_memory()
        self.assertEqual(rc, 0, envelope)
        states = envelope["projects"][0]["states"]
        self.assertEqual(states["store_authorized_ready"]["status"], "ready")
        self.assertTrue(all(f["status"] == "ready" for f in states["skill_installed"].values()))
        self.assertTrue(all(f["status"] == "ready" for f in states["bridge_assembled"].values()))
        self.assertIn(b"Keeper rules", (self.root / "AGENTS.md").read_bytes())
        ledger = json.loads(self.registry.read_text())
        assembly = ledger["projects"][str(self.root)]["checkouts"][str(self.root)]
        # §8.1: free rules carry no managed base ownership.
        self.assertNotIn(str(self.root / "AGENTS.md") + "#base", assembly["objects"])
        alias = assembly["objects"][str(self.root / ".agents/skills/context-keeper")]
        self.assertEqual(alias["ownership"], "reused", "先置链接由 AGM 接管为 reused,不改写")

    def test_keeper_first_adoption_preserves_user_bytes(self):
        bridge = b"<!-- context-keeper:start -->\nKeeper rules\n<!-- context-keeper:end -->"
        prefix = b"legacy project rules\r\n"
        (self.root / "AGENTS.md").write_bytes(prefix + bridge + b"\r\nuser tail\n")
        (self.root / "CLAUDE.md").write_bytes(b"@AGENTS.md\n" + bridge + b"\n")
        for base in (".agents/skills", ".codex/skills", ".claude/skills", ".workbuddy/skills"):
            target = self.root / base / "context-keeper"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(self.keeper, target_is_directory=True)

        # §8.2: fixture represents a native WorkBuddy-opened project.
        (self.root / ".workbuddy/memory").mkdir(parents=True, exist_ok=True)
        rc, envelope = self.approve(["enable-memory", "--project", str(self.root), "--memory"])
        self.assertEqual(rc, 0, envelope)
        data = (self.root / "AGENTS.md").read_bytes()
        self.assertTrue(data.startswith(prefix), "既有 Keeper 装配被接管时用户前缀必须原样")
        self.assertTrue(data.endswith(b"\r\nuser tail\n"))
        self.assertEqual(data.count(bridge), 1)
        ledger = json.loads(self.registry.read_text())
        objects = ledger["projects"][str(self.root)]["checkouts"][str(self.root)]["objects"]
        self.assertEqual(objects[str(self.root / "AGENTS.md") + "#keeper"]["ownership"], "reused")
        self.assertNotIn(str(self.root / "AGENTS.md") + "#base", objects,
                         "§8.1: AGENTS 非桥接正文为自由规则,不登记整文件基线")


class BoundaryTests(CliHarness):
    def test_no_memory_persisted_check_gap_and_no_silent_flip(self):
        rc, _ = self.approve(["enable-memory", "--project", str(self.root), "--no-memory"])
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "docs/context-keeper").exists())

        rc, envelope = self.check()
        self.assertEqual(rc, 1, envelope)
        gaps = envelope["projects"][0]["gaps"]
        self.assertIn("memory_not_enabled", [g["code"] for g in gaps])

        rc, envelope = self.cli(["enable-memory", "--project", str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual(envelope["changes"], [])
        ledger = json.loads(self.registry.read_text())
        self.assertEqual(ledger["projects"][str(self.root)]["memory_authorization"], "no",
                         "重复 enable 不得把拒绝过的记忆选择翻转成 yes")
        self.assertFalse((self.root / "docs/context-keeper").exists())

    def test_custom_store_location_via_approval(self):
        custom = self.area / "custom-store"
        rc, _ = self.enable_memory(edit=lambda plan: plan.update(store_path=str(custom)))
        self.assertEqual(rc, 0)
        self.assertTrue((custom / "memory-keeper.md").is_file())
        config = json.loads((self.root / "context-keeper.json").read_text())
        self.assertEqual(config["directory"], str(custom))
        ledger = json.loads(self.registry.read_text())
        store = ledger["projects"][str(self.root)]["checkouts"][str(self.root)]["store"]
        self.assertEqual(store["path"], str(custom))
        self.assertFalse((self.root / "docs/context-keeper").exists())

        rc, envelope = self.cli(["enable-memory", "--project", str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertTrue((custom / "memory-keeper.md").is_file())
        self.assertEqual(json.loads((self.root / "context-keeper.json").read_text())["directory"],
                         str(custom), "幂等重装不得移动已获批库位置")

    def test_approved_store_conflicting_with_local_config_rejected(self):
        """现场 context-keeper.json 已指向别处时,批准的库位置不得改写现场配置。"""
        self.link_alias()
        elsewhere = self.area / "elsewhere-store"
        (self.root / "context-keeper.json").write_text('{"directory": "%s"}' % str(elsewhere))
        rc, envelope = self.approve(
            ["enable-memory", "--project", str(self.root), "--memory"],
            edit=lambda plan: plan.update(store_path=str(self.area / "approved-store")))
        self.assertEqual(rc, 2, envelope)
        self.assertEqual(envelope["errors"][0]["code"], "approval_mismatch")
        self.assertFalse((self.area / "approved-store").exists(),
                         "位置冲突被拒时不得创建或移动任何库")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(json.loads((self.root / "context-keeper.json").read_text())["directory"],
                         str(elsewhere))

    def test_skill_copy_directory_conflict_rejected_untouched(self):
        # 复制目录放 .codex 根(坏落点),好链接放 .agents 根保住源发现,让冲突真正进入计划。
        self.link_alias()
        copy = self.root / ".codex/skills/context-keeper"
        copy.mkdir(parents=True)
        (copy / "SKILL.md").write_text("copied skill\n")
        before = self.snapshot(self.root, exclude=[self.root / ".git"])
        rc, envelope = self.cli(["enable-memory", "--project", str(self.root), "--memory"])
        self.assertEqual(rc, 2, envelope)
        self.assertEqual(envelope["errors"][0]["code"], "path_conflict")
        self.assertEqual(self.snapshot(self.root, exclude=[self.root / ".git"]), before,
                         "复制目录冲突时现场字节不得被改动")
        self.assertEqual(json.loads(self.registry.read_bytes())["projects"], {})
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_corrupt_registry_conservative_across_cli_commands(self):
        rc, _ = self.approve(["enable-memory", "--project", str(self.root), "--no-memory"])
        self.assertEqual(rc, 0)
        healthy = self.registry.read_bytes()
        corrupt = b"{corrupt registry"
        self.registry.write_bytes(corrupt)

        rc, envelope = self.check()
        self.assertEqual(rc, 1, envelope)
        self.assertTrue(any("registry" in w for w in envelope["warnings"]))
        self.assertEqual(self.registry.read_bytes(), corrupt, "check 不得重写损坏 registry")

        common = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--git-common-dir"],
                                check=True, capture_output=True, text=True).stdout.strip()
        approval = {"schema_version": 1, "command": "remove-memory",
                    "main_checkout": str(self.root), "checkout": str(self.root),
                    "git_common_dir": str((self.root / common).resolve()),
                    "agents": ["codex", "claude", "workbuddy"], "memory_authorization": None,
                    "store_path": None, "provider_source": None, "provider_fingerprints": [],
                    "changes": [], "confirmed_at": "2026-10-29T00:00:00Z",
                    "reference": "corrupt registry removal attempt"}
        path = self.area / "remove-approval.json"
        path.write_text(json.dumps(approval), encoding="utf-8")
        rc, envelope = self.cli(["remove-memory", "--project", str(self.root),
                                 "--approval-file", str(path)])
        self.assertEqual(rc, 2, envelope)
        self.assertEqual(envelope["errors"][0]["code"], "registry_invalid")
        self.assertEqual(self.registry.read_bytes(), corrupt)
        self.assertTrue((self.root / "AGENTS.md").exists(), "损坏登记下 remove 不得删除任何输出")

        rc, envelope = self.cli(["enable-memory", "--project", str(self.root), "--no-memory"])
        self.assertEqual(rc, 2, envelope)
        self.assertEqual(envelope["errors"][0]["code"], "registry_invalid")
        self.assertEqual(self.registry.read_bytes(), corrupt)
        self.assertFalse(self.runtime.lock.exists())

    def test_remove_twice_then_reenable_full_cycle(self):
        rc, _ = self.enable_memory()
        self.assertEqual(rc, 0)
        store_marker = (self.root / "docs/context-keeper/memory-keeper.md").read_bytes()

        rc, envelope = self.approve_remove()
        self.assertEqual(rc, 0, envelope)
        agents_left = (self.root / "AGENTS.md").read_bytes()
        self.assertNotIn(b"mem-sharing:rules", agents_left)
        self.assertNotIn(b"context-keeper:start", agents_left,
                         "AGM 创建的受管块应被摘除(块间残余字节按字节精确保留)")
        self.assertFalse((self.root / "CLAUDE.md").exists(),
                         "§8.1: 新 v2 纯入口有独立创建证据,可删除空薄壳")
        self.assertEqual((self.root / "docs/context-keeper/memory-keeper.md").read_bytes(),
                         store_marker, "记录库资产在 remove 后必须原样保留")
        for base in (".codex", ".claude", ".workbuddy"):
            self.assertFalse((self.root / base / "skills/context-keeper").exists(),
                             "%s Skill 链接(AGM created)应被移除" % base)
        self.assertTrue((self.root / ".agents/skills/context-keeper").is_symlink(),
                        "用户预置的 .agents 链接(reused)必须保留,不改写不删除")

        rc, envelope = self.cli_tty(["remove-memory", "--project", str(self.root)])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual(envelope["changes"], [], "二次 remove 必须零变更完成")
        rc, envelope = self.cli(["remove-memory", "--project", str(self.root)])
        self.assertEqual(rc, 5, envelope)

        rc, envelope = self.check()
        self.assertEqual(rc, 1, envelope)

        rc, envelope = self.enable_memory()
        self.assertEqual(rc, 0, envelope)
        states = envelope["projects"][0]["states"]
        self.assertEqual(states["store_authorized_ready"]["status"], "ready")
        self.assertIn(b"Keeper rules", (self.root / "AGENTS.md").read_bytes())

    def test_check_all_two_projects_zero_write(self):
        rc, _ = self.enable_memory()
        self.assertEqual(rc, 0)
        second = self.area / "second"
        second.mkdir()
        self.git("init", "-q", str(second))
        alias = second / ".agents/skills/context-keeper"
        alias.parent.mkdir(parents=True)
        alias.symlink_to(self.keeper, target_is_directory=True)
        # §8.2: native-ready fixture; AGM must not manufacture this directory.
        (second / ".workbuddy/memory").mkdir(parents=True)
        rc, envelope = self.approve(["enable-memory", "--project", str(second), "--memory"])
        self.assertEqual(rc, 0, envelope)

        before = self.snapshot(self.root, second, self.home, self.install.parent,
                               exclude=[self.root / ".git", second / ".git"])
        rc, envelope = self.cli(["check-memory", "--all"])
        self.assertEqual(rc, 0, envelope)
        self.assertEqual([p["checkout"] for p in envelope["projects"]],
                         [str(self.root), str(second)])
        self.assertEqual(self.snapshot(self.root, second, self.home, self.install.parent,
                                       exclude=[self.root / ".git", second / ".git"]), before,
                         "check --all 对全部已登记项目零写入")

        path = second / "AGENTS.md"
        data = path.read_bytes()
        # §8.1: free project rules do not drift; the actual bridge still does.
        path.write_bytes(data + b"\nFree user rules\n")
        rc, envelope = self.cli(["check-memory", "--all"])
        self.assertEqual(rc, 0, envelope)
        path.write_bytes(path.read_bytes().replace(b"Keeper rules", b"edited bridge"))
        rc, envelope = self.cli(["check-memory", "--all"])
        self.assertEqual(rc, 1, envelope)
        by_project = {p["checkout"]: p for p in envelope["projects"]}
        self.assertFalse(by_project[str(self.root)]["gaps"])
        self.assertTrue(by_project[str(second)]["gaps"])

    def test_partial_init_failure_keeps_prior_state_and_store_assets(self):
        rc, _ = self.approve(["enable-memory", "--project", str(self.root), "--no-memory"])
        self.assertEqual(rc, 0)
        registry_before = self.registry.read_bytes()
        agents_before = (self.root / "AGENTS.md").read_bytes()

        (self.keeper / "mode").write_text("partial")
        rc, envelope = self.enable_memory()
        self.assertEqual(rc, 2, envelope)
        self.assertEqual(envelope["errors"][0]["code"], "keeper_failed")
        self.assertEqual(self.registry.read_bytes(), registry_before,
                         "Provider init 部分失败时旧 registry 必须原样保留")
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), agents_before,
                         "已提交配置不得因记忆档失败而漂移")
        self.assertTrue((self.root / "docs/context-keeper/memory-keeper.md").exists(),
                        "部分写入的库资产必须保留现场")
        self.assertFalse((self.root / "docs/context-keeper/plans").exists())

        (self.keeper / "mode").unlink()
        rc, envelope = self.enable_memory()
        self.assertEqual(rc, 0, envelope)
        self.assertTrue((self.root / "docs/context-keeper/plans").is_dir())

    def test_no_pycache_or_lock_residue(self):
        rc, _ = self.enable_memory()
        self.assertEqual(rc, 0)
        rc, _ = self.check()
        self.assertEqual(rc, 0)
        rc, _ = self.approve_remove()
        self.assertEqual(rc, 0)
        residues = [p for p in self.area.rglob("__pycache__")]
        self.assertEqual(residues, [], "CLI 冷启动与全周期不得留下字节码缓存")
        self.assertFalse((self.runtime.lock).exists(), "锁必须正常释放")


if __name__ == "__main__":
    unittest.main()
