"""M2-05 只读 check 与巡检矩阵单元测试。

运行:仓库根目录 `python3 -m unittest tests.unit.test_m205_check`(或 pytest)。
仅标准库;全部使用临时目录 fixture(临时 home/provider/agents.json/registry/项目仓库),
不触真实 registry、入口或记录库。零写入证明 = 前后文件集合/字节/mtime 快照一致
+ os/builtins 写调用拦截 + 子进程仅 git(不调用 Keeper 探针)+ 只读目录可执行。
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import agm  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from runtime_fixture import seed_runtime, installed_registry
from agm_core import check as check_mod  # noqa: E402
from agm_core import paths as agm_paths  # noqa: E402
from agm_core import registry as reg  # noqa: E402
from agm_core.entries import block_fingerprint, link_fingerprint, render_block, sha256  # noqa: E402

KS, KE = b"<!-- context-keeper:start -->", b"<!-- context-keeper:end -->"
WS, WE = b"<!-- context-keeper:workbuddy:start -->", b"<!-- context-keeper:workbuddy:end -->"
KEEPER_BLOCK = KS + "\n## Context Keeper\n\n- 测试规则\n".encode() + KE
DRIFTED_BLOCK = KS + "\n## Context Keeper\n\n- 被改写\n".encode() + KE
WB_BLOCK = WS + "\n## Context Keeper(WorkBuddy 桥接)\n\n- 测试规则\n".encode() + WE
AGENTS_BASE = b"# rules\n"
CLAUDE_IMPORT_ONLY = b"@AGENTS.md\n"
USER_MEMORY_BASE = b"# user memory\n"
NOW = "2026-10-29T00:00:00Z"


def _git(root, *args, check=True):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    result = subprocess.run(
        ["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    if check and result.returncode:
        raise AssertionError("git %s failed: %s" % (args, result.stderr.decode()))
    return result


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "check@test")
    _git(path, "config", "user.name", "check-test")
    (path / "README.md").write_bytes(b"init\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-q", "-m", "init")
    return path.resolve()


class Sandbox:
    """临时环境:home/provider/路径表(拷贝真实 agents.json)/backups/registry。"""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.home = self.root / "home"
        self.provider = self.root / "provider" / "context-keeper"
        self.table_dir = self.root / "table"
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.provider.mkdir(parents=True)
        self.table_dir.mkdir()
        (self.provider / "SKILL.md").write_text("# context-keeper\n", encoding="utf-8")
        shutil.copy(os.path.join(SCRIPTS_DIR, "agents.json"), self.table_dir / "agents.json")
        (self.table_dir / "backups").mkdir()
        with open(self.table_dir / "agents.json", "r", encoding="utf-8") as handle:
            self.table = json.load(handle)
        self.platform_config = self.table["platforms"]["darwin"]
        self.registry_path = self.runtime.registry

    def allowed_user_paths(self):
        return agm_paths.allowed_user_paths(self.platform_config, None, home=str(self.home))

    def manifest(self, name):
        directory = self.table_dir / "backups" / name
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "manifest.json"
        target.write_bytes(b"{}\n")
        return str(target)

    def write_registry(self, registry):
        reg.validate_registry(registry, allowed_user_paths=self.allowed_user_paths())
        self.registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        reg.load_registry(self.registry_path, allowed_user_paths=self.allowed_user_paths())

    def destroy(self):
        shutil.rmtree(self.root, ignore_errors=True)


def _obj(kind, path, agents, ownership, *, marker=None, fingerprint=None, link_target=None,
         manifest=None, scope="project", consumers=None):
    return {
        "kind": kind,
        "path": path,
        "scope": scope,
        "agents": list(agents),
        "ownership": ownership,
        "marker": marker,
        "fingerprint": fingerprint,
        "original_existed": None if ownership == "unknown" else (ownership == "reused"),
        "link_target": link_target,
        "backup_manifest": manifest,
        "consumers": consumers,
    }


def _fp(basis, value):
    return {"algorithm": "sha256", "basis": basis, "value": value}


def _unknown_fact():
    return {"status": "unknown", "observed_at": None, "evidence": None}


def build_installed_project(sb: Sandbox, name, *, auth="yes", runtime_passed=False,
                            wrong_common_dir=False):
    """装配一个健康的三执行器项目并登记;返回 (main_path, registry_dict)。"""
    main = _git_repo(sb.root / name)
    agents_md = render_block(AGENTS_BASE, KEEPER_BLOCK, KS, KE, expected_fingerprint=None)
    claude_md = render_block(CLAUDE_IMPORT_ONLY, KEEPER_BLOCK, KS, KE, expected_fingerprint=None)
    wb_memory = WB_BLOCK
    (main / "AGENTS.md").write_bytes(agents_md)
    (main / "CLAUDE.md").write_bytes(claude_md)
    (main / ".workbuddy" / "memory").mkdir(parents=True)
    (main / ".workbuddy" / "memory" / "MEMORY.md").write_bytes(wb_memory)
    for rel in (".agents/skills/context-keeper", ".codex/skills/context-keeper",
                ".claude/skills/context-keeper", ".workbuddy/skills/context-keeper"):
        target = Path(main / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(sb.provider), str(target))
    store = main / "docs" / "context-keeper"
    store.mkdir(parents=True)
    (store / "memory-keeper.md").write_text("store\n", encoding="utf-8")

    user_memory = sb.home / ".workbuddy" / "MEMORY.md"
    user_memory.parent.mkdir(parents=True, exist_ok=True)
    user_memory.write_bytes(render_block(USER_MEMORY_BASE, WB_BLOCK, WS, WE, expected_fingerprint=None))
    shared_id = str(user_memory) + "#keeper-exception"

    objects = {
        str(main / "AGENTS.md") + "#base": _obj("file", str(main / "AGENTS.md"), ["codex"], "reused",
                                                fingerprint=_fp("file_bytes", sha256(agents_md)),
                                                consumers=[str(main)]),
        str(main / "AGENTS.md") + "#keeper": _obj("block", str(main / "AGENTS.md"), ["codex"], "created",
                                                  marker={"start": KS.decode(), "end": KE.decode()},
                                                  fingerprint=_fp("block_bytes", sha256(KEEPER_BLOCK)),
                                                  manifest=sb.manifest("m-keepers"),
                                                  consumers=[str(main)]),
        str(main / "CLAUDE.md") + "#base": _obj("file", str(main / "CLAUDE.md"), ["claude"], "reused",
                                                fingerprint=_fp("file_bytes", sha256(claude_md)),
                                                consumers=[str(main)]),
        str(main / "CLAUDE.md") + "#keeper": _obj("block", str(main / "CLAUDE.md"), ["claude"], "created",
                                                  marker={"start": KS.decode(), "end": KE.decode()},
                                                  fingerprint=_fp("block_bytes", sha256(KEEPER_BLOCK)),
                                                  manifest=sb.manifest("m-keepers"),
                                                  consumers=[str(main)]),
        str(main / "CLAUDE.md") + "#import": _obj("import", str(main / "CLAUDE.md"), ["claude"], "reused",
                                                  fingerprint=_fp("file_bytes", sha256(CLAUDE_IMPORT_ONLY)),
                                                  consumers=[str(main)]),
        str(main / ".workbuddy" / "memory" / "MEMORY.md") + "#keeper": _obj(
            "block", str(main / ".workbuddy" / "memory" / "MEMORY.md"), ["workbuddy"], "created",
            marker={"start": WS.decode(), "end": WE.decode()},
            fingerprint=_fp("block_bytes", sha256(WB_BLOCK)),
            manifest=sb.manifest("m-keepers"), consumers=[str(main)]),
    }
    for rel, agent in ((".agents/skills/context-keeper", "codex"),
                       (".codex/skills/context-keeper", "codex"),
                       (".claude/skills/context-keeper", "claude"),
                       (".workbuddy/skills/context-keeper", "workbuddy")):
        path = str(main / rel)
        objects[path] = _obj("skill_symlink", path, [agent], "created",
                             fingerprint=_fp("link_target", link_fingerprint(sb.provider)),
                             link_target=str(sb.provider),
                             manifest=sb.manifest("m-links"), consumers=[str(main)])

    common_dir = str(main / (".git-x" if wrong_common_dir else ".git"))
    runtime = {"status": "pending", "evidence_path": None}
    if runtime_passed:
        evidence = main / "docs" / "runtime-evidence.md"
        evidence.write_text("new-session acceptance\n", encoding="utf-8")
        runtime = {"status": "passed", "evidence_path": str(evidence)}
    registry = {
        **installed_registry(),
        "projects": {
            str(main): {
                "main_checkout": str(main),
                "memory_authorization": auth,
                "authorization_evidence": None if auth is None else {
                    "confirmed_at": NOW, "reference": "fixture approval"},
                "provider_source": str(sb.provider),
                "checkouts": {
                    str(main): {
                        "git_common_dir": common_dir,
                        "agents": ["codex", "claude", "workbuddy"],
                        "states": {
                            "source_available": _unknown_fact(),
                            "skill_installed": {a: _unknown_fact() for a in ("codex", "claude", "workbuddy")},
                            "bridge_assembled": {a: _unknown_fact() for a in ("codex", "claude", "workbuddy")},
                            "store_authorized_ready": _unknown_fact(),
                        },
                        "store": {"path": str(store), "location_approved": True,
                                  "approval_evidence": {"confirmed_at": NOW, "reference": "fixture store"}},
                        "objects": objects,
                        "shared_object_ids": [shared_id],
                        "runtime_acceptance": runtime,
                    }
                },
            }
        },
        "shared_objects": {
            shared_id: _obj("user_convention", str(user_memory), ["workbuddy"], "created",
                            marker={"start": WS.decode(), "end": WE.decode()},
                            fingerprint=_fp("block_bytes", block_fingerprint(
                                user_memory.read_bytes(), WS.decode(), WE.decode())),
                            manifest=sb.manifest("m-user"), scope="user", consumers=[str(main)]),
        },
    }
    sb.write_registry(registry)
    return main, registry


def run_check(sb: Sandbox, argv, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    old_cwd = os.getcwd()
    if cwd is not None:
        os.chdir(str(cwd))
    try:
        code = agm.main(
            ["check-memory", *argv], stdin=io.StringIO(), stdout=out, stderr=err,
            platform="darwin", interactive=False, table_path=str(sb.table_dir / "agents.json"),
            home=str(sb.home),
        )
    finally:
        if cwd is not None:
            os.chdir(old_cwd)
    envelope = json.loads(out.getvalue())
    return envelope, code


def gap_codes(report):
    return [g["code"] for g in report["gaps"]]


def tree_state(root: Path):
    state = {}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                state[str(path)] = ("symlink", os.readlink(str(path)), path.lstat().st_mtime_ns)
            elif path.is_file():
                info = path.stat()
                state[str(path)] = ("file", sha256(path.read_bytes()), info.st_mtime_ns, info.st_size)
            else:
                state[str(path)] = ("dir", path.stat().st_mtime_ns)
    return state


@contextlib.contextmanager
def no_write_guard():
    """拦截本进程全部写入口;任何写尝试记录并立即失败。"""
    violations = []
    real_open = builtins_open = __builtins__["open"] if isinstance(__builtins__, dict) else __builtins__.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(ch in mode for ch in "wax+"):
            violations.append(("open", str(file), mode))
            raise AssertionError("write attempt via open: %s %s" % (file, mode))
        return real_open(file, mode, *args, **kwargs)

    def wrap_os(name):
        real = getattr(os, name)

        def wrapper(*args, **kwargs):
            violations.append((name,) + tuple(str(a) for a in args[:1]))
            raise AssertionError("write attempt via os.%s: %s" % (name, args))

        return wrapper

    real_os_open = os.open
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & write_flags:
            violations.append(("os.open", str(path), flags))
            raise AssertionError("write attempt via os.open: %s" % path)
        return real_os_open(path, flags, *args, **kwargs)

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch("builtins.open", guarded_open))
        stack.enter_context(mock.patch("io.open", guarded_open))
        for name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace",
                     "symlink", "link", "chmod", "lchmod", "truncate", "utime", "mknod", "rmdir"):
            if hasattr(os, name):
                stack.enter_context(mock.patch("os." + name, wrap_os(name)))
        stack.enter_context(mock.patch("os.open", guarded_os_open))
        yield violations


@contextlib.contextmanager
def subprocess_recorder():
    calls = []
    real_run = subprocess.run

    def wrapper(argv, *args, **kwargs):
        calls.append(list(argv) if isinstance(argv, (list, tuple)) else [str(argv)])
        return real_run(argv, *args, **kwargs)

    with mock.patch("subprocess.run", wrapper):
        yield calls


def make_tree_readonly(root: Path):
    for dirpath, dirnames, filenames in os.walk(str(root)):
        os.chmod(dirpath, 0o555)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o444)


def make_tree_writable(root: Path):
    for dirpath, dirnames, filenames in os.walk(str(root)):
        os.chmod(dirpath, 0o755)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o644)


class CheckReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.destroy)

    # ---- 健康现场与 envelope 合同 ----

    def test_unregistered_import_requires_target_rule_entry(self):
        main, _ = build_installed_project(self.sb, "proj")
        self.sb.registry_path.write_bytes(b"{broken")
        (main / "AGENTS.md").unlink()
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(code, 1)
        self.assertTrue(any(g["code"] == "rule_entry_unavailable" and g["path"] == str(main / "AGENTS.md") for g in envelope["projects"][0]["gaps"]))

    def test_corrupt_all_and_malformed_markers_never_write(self):
        main, _ = build_installed_project(self.sb, "proj")
        self.sb.registry_path.write_bytes(b"{broken")
        (main / "CLAUDE.md").write_bytes(CLAUDE_IMPORT_ONLY + KEEPER_BLOCK + b"\n" + KS)
        before = tree_state(self.sb.root)
        with no_write_guard() as violations:
            single, single_code = run_check(self.sb, ["--project", str(main)])
            all_result, all_code = run_check(self.sb, ["--all"])
        self.assertEqual((single_code, all_code), (1, 1))
        self.assertIn("bridge_conflict", gap_codes(single["projects"][0]))
        self.assertEqual(all_result["projects"], [])
        self.assertEqual(violations, [])
        self.assertEqual(before, tree_state(self.sb.root))

    def test_unregistered_missing_import_even_when_bridge_present(self):
        main, _ = build_installed_project(self.sb, "proj")
        self.sb.registry_path.write_bytes(b"{broken")
        (main / "CLAUDE.md").write_bytes(KEEPER_BLOCK)
        with no_write_guard() as violations:
            envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(code, 1)
        self.assertEqual(violations, [])
        self.assertIn("import_reference_missing", gap_codes(envelope["projects"][0]))

    def test_dangling_skill_is_not_ready_with_or_without_registry(self):
        main, _ = build_installed_project(self.sb, "proj")
        shutil.rmtree(self.sb.provider)
        for corrupt in (False, True):
            if corrupt:
                self.sb.registry_path.write_bytes(b"{broken")
            envelope, code = run_check(self.sb, ["--project", str(main)])
            self.assertEqual(code, 1)
            report = envelope["projects"][0]
            self.assertEqual(report["states"]["skill_installed"]["claude"]["status"], "blocked")
            self.assertIn("skill_conflict", gap_codes(report))

    def test_unrelated_object_gap_does_not_hide_skill_missing(self):
        main, registry = build_installed_project(self.sb, "proj")
        assembly = registry["projects"][str(main)]["checkouts"][str(main)]
        for oid in list(assembly["objects"]):
            obj = assembly["objects"][oid]
            if obj["kind"] == "skill_symlink" and "claude" in obj["agents"]:
                Path(obj["path"]).unlink()
                del assembly["objects"][oid]
        self.sb.write_registry(registry)
        (main / "CLAUDE.md").write_bytes(b"")
        envelope, _ = run_check(self.sb, ["--project", str(main)])
        self.assertIn("skill_missing", gap_codes(envelope["projects"][0]))

    def test_entry_budgets_and_legacy_convention_warn_without_body(self):
        main, _ = build_installed_project(self.sb, "proj")
        with (main / "AGENTS.md").open("ab") as handle:
            handle.write(b"x" * (32 * 1024))
        with (main / "CLAUDE.md").open("ab") as handle:
            handle.write(b"\nextra" * 200)
        user = self.sb.home / ".workbuddy" / "MEMORY.md"
        # 此处用无登记观察旧表述,正文不得进入报告。
        user.write_text("规则唯一来源 AGENTS.md PRIVATE_SENTINEL", encoding="utf-8")
        self.sb.registry_path.write_bytes(b"{broken")
        envelope, _ = run_check(self.sb, ["--project", str(main)])
        warnings = "\n".join(envelope["warnings"])
        self.assertEqual(warnings.count("entry_budget:"), 2)
        self.assertIn("workbuddy_convention_review:", warnings)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(envelope))

    def test_all_matrix_uses_registered_union_not_install_hints(self):
        main_a, registry_a = build_installed_project(self.sb, "projA")
        main_b, registry_b = build_installed_project(self.sb, "projB")
        # A 仅接入 codex, B 三家;B 的 claude 接入应产生 A 的矩阵缺口。
        project_a = registry_a["projects"][str(main_a)]
        assembly = project_a["checkouts"][str(main_a)]
        assembly["agents"] = ["codex"]
        for field in ("skill_installed", "bridge_assembled"):
            assembly["states"][field] = {"codex": _unknown_fact()}
        assembly["objects"] = {oid: obj for oid, obj in assembly["objects"].items() if obj["agents"] == ["codex"]}
        assembly["shared_object_ids"] = []
        registry_b["projects"][str(main_a)] = project_a
        self.sb.write_registry(registry_b)
        before = tree_state(self.sb.root)
        with no_write_guard() as violations:
            envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual(code, 1)
        self.assertEqual(violations, [])
        self.assertEqual(before, tree_state(self.sb.root))
        report = next(p for p in envelope["projects"] if p["main_checkout"] == str(main_a))
        missing = [g["agent"] for g in report["gaps"] if g["code"] == "agent_not_assembled"]
        self.assertEqual(missing, ["claude", "workbuddy"])

    def test_identity_mismatch_blocks_authorization_and_invalidates_runtime(self):
        main, _ = build_installed_project(self.sb, "proj", wrong_common_dir=True, runtime_passed=True)
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(code, 1)
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["store_authorized_ready"]["status"], "blocked")
        self.assertEqual(report["runtime_acceptance"]["status"], "pending")

    def test_healthy_registered_project_completes(self):
        main, _registry = build_installed_project(self.sb, "proj")
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(
            set(envelope),
            {"schema_version", "command", "status", "projects", "changes", "warnings",
             "errors", "approval_required", "next_action", "runtime_layout"},
        )
        self.assertEqual(envelope["command"], "check-memory")
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(envelope["changes"], [])
        self.assertFalse(envelope["approval_required"])
        self.assertIsNone(envelope["next_action"])
        self.assertEqual(code, 0)
        report = envelope["projects"][0]
        self.assertTrue(report["registered"])
        self.assertFalse(report["worktree"])
        self.assertEqual(report["main_checkout"], str(main))
        states = report["states"]
        self.assertEqual(states["source_available"]["status"], "ready")
        for agent in ("codex", "claude", "workbuddy"):
            self.assertEqual(states["skill_installed"][agent]["status"], "ready", agent)
            self.assertEqual(states["bridge_assembled"][agent]["status"], "ready", agent)
        # 第四态:库存在但只读证据不能判定可用/迁移 → unknown(不调用 Keeper 探针)
        self.assertEqual(states["store_authorized_ready"]["status"], "unknown")
        self.assertEqual(report["gaps"], [])
        # import 对象基线(仅引用行)与现文件(含块)不同 → baseline_changed,信息性不算缺口
        statuses = {item["id"]: item["status"] for item in report["objects"]}
        self.assertEqual(statuses[str(main / "CLAUDE.md") + "#import"], "baseline_changed")
        self.assertTrue(all(s == "ok" for i, s in statuses.items() if not i.endswith("#import")))

    def test_all_mode_healthy_matrix(self):
        main, _registry = build_installed_project(self.sb, "proj")
        envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertEqual([p["main_checkout"] for p in envelope["projects"]], [str(main)])
        self.assertEqual(envelope["projects"][0]["agents"], ["codex", "claude", "workbuddy"])

    # ---- 漂移/缺失/冲突 ----

    def test_bridge_block_drift_gaps_exit_1(self):
        main, _registry = build_installed_project(self.sb, "proj")
        # 直接改写块内容(保留标记),模拟块内漂移
        (main / "AGENTS.md").write_bytes(AGENTS_BASE + DRIFTED_BLOCK)
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "gaps")
        self.assertEqual(code, 1)
        self.assertIsNotNone(envelope["next_action"])
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["bridge_assembled"]["codex"]["status"], "blocked")
        codes = gap_codes(report)
        self.assertIn("object_drifted", codes)
        self.assertFalse([c for c in codes if c in ("bridge_missing", "skill_missing")])

    def test_workbuddy_reset_loses_block(self):
        main, _registry = build_installed_project(self.sb, "proj")
        (main / ".workbuddy" / "memory" / "MEMORY.md").write_bytes(b"")  # WorkBuddy 重置
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "gaps")
        self.assertEqual(code, 1)
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["bridge_assembled"]["workbuddy"]["status"], "missing")
        # 对象级缺口已覆盖同一落点,不再重复报事实级 bridge_missing
        self.assertEqual(gap_codes(report), ["object_missing"])

    def test_import_reference_missing(self):
        main, _registry = build_installed_project(self.sb, "proj")
        (main / "CLAUDE.md").write_bytes(KEEPER_BLOCK)  # 引用行被删,块保留
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "gaps")
        self.assertEqual(code, 1)
        report = envelope["projects"][0]
        self.assertIn("import_reference_missing", gap_codes(report))
        statuses = {item["id"]: item["status"] for item in report["objects"]}
        self.assertEqual(statuses[str(main / "CLAUDE.md") + "#import"], "missing")
        # 桥接块仍在 → bridge fact 保持 ready
        self.assertEqual(report["states"]["bridge_assembled"]["claude"]["status"], "ready")

    def test_rule_growth_outside_blocks_is_warning_only(self):
        main, _registry = build_installed_project(self.sb, "proj")
        claude = main / "CLAUDE.md"
        claude.write_bytes(claude.read_bytes() + "\n额外私有规则行\n".encode())
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertTrue(any("rule_growth" in w for w in envelope["warnings"]))
        self.assertEqual(envelope["projects"][0]["gaps"], [])

    def test_override_files_warn_only(self):
        main, _registry = build_installed_project(self.sb, "proj")
        (main / "AGENTS.override.md").write_text("hijack\n", encoding="utf-8")
        codex_override = self.sb.home / ".codex" / "AGENTS.override.md"
        codex_override.parent.mkdir(parents=True, exist_ok=True)
        codex_override.write_text("hijack\n", encoding="utf-8")
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertEqual(len([w for w in envelope["warnings"] if "override_present" in w]), 2)

    def test_skill_link_missing_and_drift(self):
        main, _registry = build_installed_project(self.sb, "proj")
        (main / ".claude" / "skills" / "context-keeper").unlink()
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["skill_installed"]["claude"]["status"], "missing")
        self.assertIn("object_missing", gap_codes(report))
        # 其他执行器不受影响
        self.assertEqual(report["states"]["skill_installed"]["codex"]["status"], "ready")

        other = self.sb.root / "provider-other"
        other.mkdir()
        os.symlink(str(other), str(main / ".claude" / "skills" / "context-keeper"))
        envelope2, _code = run_check(self.sb, ["--project", str(main)])
        report2 = envelope2["projects"][0]
        self.assertEqual(report2["states"]["skill_installed"]["claude"]["status"], "blocked")
        self.assertIn("object_drifted", gap_codes(report2))

    def test_shared_user_convention_drift(self):
        main, _registry = build_installed_project(self.sb, "proj")
        user_memory = self.sb.home / ".workbuddy" / "MEMORY.md"
        user_memory.write_bytes(USER_MEMORY_BASE + WS + "\n被改写\n".encode() + WE)
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        shared = [o for o in report["objects"] if o["scope"] == "user"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["status"], "drifted")

    def test_m1_shared_exception_uses_registered_bytes_not_install_template(self):
        from agm_core.enable import EXCEPTION_MARKER, _block
        main, data = build_installed_project(self.sb, "proj")
        user_memory = self.sb.home / ".workbuddy/MEMORY.md"
        block = _block(EXCEPTION_MARKER, "Previously approved user exception")
        content = USER_MEMORY_BASE + block + b"\nOutside user rules\n"
        user_memory.write_bytes(content)
        shared = next(iter(data["shared_objects"].values()))
        shared.update(marker=EXCEPTION_MARKER, fingerprint=_fp("block_bytes", sha256(block)))
        data["shared_objects"][str(user_memory) + "#base"] = _obj(
            "file", str(user_memory), ["workbuddy"], "reused", scope="user",
            fingerprint=_fp("file_bytes", sha256(content)), consumers=[str(main)])
        data["projects"][str(main)]["checkouts"][str(main)]["shared_object_ids"].append(str(user_memory) + "#base")
        self.sb.write_registry(data)
        before = tree_state(self.sb.root)
        envelope, _ = run_check(self.sb, ["--project", str(main)])
        shared_report = [o for o in envelope["projects"][0]["objects"] if o["scope"] == "user"]
        self.assertEqual([o["status"] for o in shared_report], ["ok", "ok"])
        self.assertEqual(tree_state(self.sb.root), before)
        user_memory.write_bytes(content.replace(b"Previously approved", b"Externally changed"))
        envelope, code = run_check(self.sb, ["--project", str(main)])
        shared_report = [o for o in envelope["projects"][0]["objects"] if o["scope"] == "user"]
        self.assertEqual(code, 1)
        self.assertTrue(all(o["status"] == "drifted" for o in shared_report))

    def test_runtime_passed_invalidated_on_drift(self):
        main, _registry = build_installed_project(self.sb, "proj", runtime_passed=True)
        (main / "AGENTS.md").write_bytes(AGENTS_BASE + DRIFTED_BLOCK)
        envelope, _code = run_check(self.sb, ["--project", str(main)])
        report = envelope["projects"][0]
        self.assertEqual(report["runtime_acceptance"], {"status": "pending", "evidence_path": None})
        self.assertTrue(any("runtime_invalidated" in w for w in envelope["warnings"]))

    def test_runtime_passed_kept_when_healthy(self):
        main, _registry = build_installed_project(self.sb, "proj", runtime_passed=True)
        envelope, _code = run_check(self.sb, ["--project", str(main)])
        report = envelope["projects"][0]
        self.assertEqual(report["runtime_acceptance"]["status"], "passed")

    # ---- 第四态与源码 ----

    def test_memory_not_enabled_reports_gap(self):
        main, _registry = build_installed_project(self.sb, "proj", auth="no")
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["store_authorized_ready"]["status"], "blocked")
        self.assertIn("memory_not_enabled", gap_codes(report))

    def test_store_missing_and_source_missing(self):
        main, _registry = build_installed_project(self.sb, "proj")
        shutil.rmtree(main / "docs" / "context-keeper")
        envelope, _code = run_check(self.sb, ["--project", str(main)])
        report = envelope["projects"][0]
        self.assertEqual(report["states"]["store_authorized_ready"]["status"], "missing")
        self.assertIn("store_missing", gap_codes(report))

        moved = self.sb.root / "provider-moved"
        (self.sb.root / "provider").rename(moved)
        envelope2, _code2 = run_check(self.sb, ["--project", str(main)])
        report2 = envelope2["projects"][0]
        self.assertEqual(report2["states"]["source_available"]["status"], "missing")
        self.assertIn("source_missing", gap_codes(report2))

    # ---- 未登记 / registry 不可用 ----

    def test_unregistered_project_reports_gap_and_discovery(self):
        main = _git_repo(self.sb.root / "fresh")
        (self.sb.home / ".codex").mkdir()
        self.sb.write_registry(installed_registry())
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertFalse(report["registered"])
        self.assertIn("project_unregistered", gap_codes(report))
        self.assertEqual(report["states"]["source_available"]["status"], "unknown")
        self.assertEqual(report["states"]["store_authorized_ready"]["status"], "unknown")
        for agent in ("codex", "claude", "workbuddy"):
            self.assertEqual(report["states"]["skill_installed"][agent]["status"], "missing")
        discovery = {d["agent"]: d["signals"] for d in report["agent_discovery"]}
        self.assertTrue(discovery["codex"][0]["exists"])
        self.assertFalse(discovery["claude"][0]["exists"])
        self.assertEqual(discovery["codex"][0]["strength"], "hint")

    def test_registry_corrupt_project_mode_in_memory_only(self):
        main, _registry = build_installed_project(self.sb, "proj")
        self.sb.registry_path.write_text("{ broken json", encoding="utf-8")
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertIsNone(report["registered"])
        self.assertIn("registry_unavailable", gap_codes(report))
        # 损坏登记不阻断内存观察:现场标记仍在 → bridge ready(所有权未知)
        self.assertEqual(report["states"]["bridge_assembled"]["codex"]["status"], "ready")
        self.assertTrue(any("registry_unavailable" in w for w in envelope["warnings"]))

    def test_registry_missing_all_mode_scope_incomplete(self):
        _main, _registry = build_installed_project(self.sb, "proj")
        self.sb.registry_path.unlink()
        envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        self.assertEqual(envelope["projects"], [])  # 不扫描未知项目,不宣称已巡检全部
        self.assertTrue(any("check_scope_incomplete" in w for w in envelope["warnings"]))

    def test_all_only_iterates_registered_projects(self):
        main_a, registry_a = build_installed_project(self.sb, "projA")
        main_b, _registry_b = build_installed_project(self.sb, "projB")
        _git_repo(self.sb.root / "unregistered")  # 磁盘存在但未登记,不进 --all
        # 第二次 build 覆盖了 registry,合并两项目后重写;两项目共享同一用户级入口,
        # shared 对象 consumers 需同时指向两个 checkout
        merged = copy.deepcopy(_registry_b)
        merged["projects"][str(main_a)] = copy.deepcopy(registry_a["projects"][str(main_a)])
        for shared in merged["shared_objects"].values():
            shared["consumers"] = [str(main_a), str(main_b)]
        self.sb.write_registry(merged)
        (main_b / ".workbuddy" / "memory" / "MEMORY.md").write_bytes(b"")
        envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        mains = [p["main_checkout"] for p in envelope["projects"]]
        self.assertEqual(set(mains), {str(main_a), str(main_b)})
        by_main = {p["main_checkout"]: p for p in envelope["projects"]}
        self.assertEqual(by_main[str(main_a)]["gaps"], [])
        self.assertIn("object_missing", gap_codes(by_main[str(main_b)]))

    def test_all_mode_corrupt_registry_reports_incomplete(self):
        build_installed_project(self.sb, "proj")
        self.sb.registry_path.write_text("[1,2,", encoding="utf-8")
        envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        self.assertEqual(envelope["projects"], [])

    # ---- 移动 / 重 clone / 身份失配 / worktree ----

    def test_all_mode_checkout_moved(self):
        main, _registry = build_installed_project(self.sb, "proj")
        make_tree_writable(main)
        shutil.rmtree(main)
        envelope, code = run_check(self.sb, ["--all"])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertTrue(report["registered"])
        self.assertIn("checkout_missing", gap_codes(report))
        self.assertEqual(report["states"]["source_available"]["status"], "unknown")

    def test_identity_mismatch_common_dir(self):
        main, _registry = build_installed_project(self.sb, "proj", wrong_common_dir=True)
        envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        self.assertIn("identity_mismatch", gap_codes(envelope["projects"][0]))

    def test_worktree_reported_unsupported(self):
        main, _registry = build_installed_project(self.sb, "proj")
        worktree = (self.sb.root / "wt").resolve()
        _git(main, "worktree", "add", "-q", str(worktree), "-b", "wt")
        envelope, code = run_check(self.sb, ["--project", str(worktree)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        report = envelope["projects"][0]
        self.assertTrue(report["worktree"])
        self.assertTrue(report["registered"])
        self.assertEqual(report["main_checkout"], str(main))
        self.assertEqual(report["checkout"], str(worktree))
        self.assertIn("worktree_unsupported", gap_codes(report))
        self.assertEqual(report["states"]["bridge_assembled"]["codex"]["status"], "unknown")
        _git(main, "worktree", "remove", "--force", str(worktree))

    # ---- 项目定位失败 ----

    def test_project_argument_failures_exit_2(self):
        plain = self.sb.root / "plain"
        plain.mkdir()
        envelope, code = run_check(self.sb, ["--project", str(plain)])
        self.assertEqual(envelope["status"], "failed")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["errors"][0]["code"], "project_invalid")
        self.assertEqual(envelope["projects"], [])

        main = _git_repo(self.sb.root / "repo")
        sub = main / "sub"
        sub.mkdir()
        envelope2, code2 = run_check(self.sb, ["--project", str(sub)])
        self.assertEqual(envelope2["status"], "failed")
        self.assertEqual(code2, 2)

    def test_default_cwd_locates_project(self):
        main, _registry = build_installed_project(self.sb, "proj")
        envelope, code = run_check(self.sb, [], cwd=main / ".workbuddy" / "memory")
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertEqual(envelope["projects"][0]["main_checkout"], str(main))

    # ---- 零写入证明 ----

    def test_no_writes_and_git_only_subprocess(self):
        main, _registry = build_installed_project(self.sb, "proj")
        before = tree_state(self.sb.root)
        with no_write_guard() as violations, subprocess_recorder() as calls:
            envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertEqual(violations, [])
        self.assertTrue(calls)
        self.assertTrue(all(call[0] == "git" for call in calls), calls)
        after = tree_state(self.sb.root)
        self.assertEqual(before, after)

    def test_no_writes_even_with_gaps(self):
        main, _registry = build_installed_project(self.sb, "proj")
        (main / "AGENTS.md").write_bytes(AGENTS_BASE + DRIFTED_BLOCK)
        (main / ".claude" / "skills" / "context-keeper").unlink()
        before = tree_state(self.sb.root)
        with no_write_guard() as violations, subprocess_recorder() as calls:
            envelope, code = run_check(self.sb, ["--project", str(main)])
        self.assertEqual((envelope["status"], code), ("gaps", 1))
        self.assertEqual(violations, [])
        self.assertTrue(all(call[0] == "git" for call in calls))
        self.assertEqual(before, tree_state(self.sb.root))

    def test_runs_on_readonly_directory_tree(self):
        main, _registry = build_installed_project(self.sb, "proj")
        before = tree_state(self.sb.root)
        make_tree_readonly(self.sb.root)
        try:
            envelope, code = run_check(self.sb, ["--project", str(main)])
        finally:
            make_tree_writable(self.sb.root)
        self.assertEqual(envelope["status"], "completed")
        self.assertEqual(code, 0)
        self.assertEqual(before, tree_state(self.sb.root))


class GapSchemaTests(unittest.TestCase):
    """缺口清单结构与输出合同的基础不变量。"""

    def test_gap_item_fields(self):
        gap = check_mod._gap("object_missing", "detail", agent="codex", path="/x", suggestion="enable")
        self.assertEqual(
            set(gap), {"code", "agent", "path", "detail", "suggestion"}
        )
        self.assertEqual(
            set(check_mod._fact("ready", "ev")), {"status", "observed_at", "evidence"}
        )
        unknown = check_mod._fact("unknown")
        self.assertEqual(unknown, {"status": "unknown", "observed_at": None, "evidence": None})


if __name__ == "__main__":
    unittest.main()
