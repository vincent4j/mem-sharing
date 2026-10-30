"""M2-07 故障矩阵单元层:enable/check/remove run() 级真实文件回归。

全部夹具在 TemporaryDirectory 内(临时 HOME/项目仓库/安装目录/Keeper 桩 checkout),
调用真实 enable.run/check.run/remove.run;仅经文档化的 Python-only 注入点
(install_dir/runner/registry_path)隔离 registry 位置与上游安装器。
read-only/rollback 断言一律基于真实文件字节/mtime,不以 mock 成功替代文件行为。

运行:仓库根目录 `python3 -m unittest tests.unit.test_m207_faults`。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from runtime_fixture import seed_runtime, installed_registry, seed_project_executors
from agm_core import check as check_mod
from agm_core import enable, paths, registry
from agm_core.remove import run as remove_run


class M207Fixture(unittest.TestCase):
    """临时安装目录 + 临时 HOME + 真实 git 项目 + 子进程 Keeper 桩。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.area / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.install = self.area / "agm" / "scripts"
        self.install.mkdir(parents=True)
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = seed_runtime(self.home)
        self.install = self.runtime.var
        self.source = self._keeper_source()
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.calls = []
        self.request = {"project": str(self.root), "agents": ["codex", "claude", "workbuddy"],
                        "memory_choice": "no", "approval": None, "interactive": False,
                        "home": str(self.home), "platform_config": self.config,
                        "agents_table_path": str(self.install / "agents.json"),
                        "runtime_layout": self.runtime, "runner": self.runner}
        (self.install / "agents.json").write_bytes((SCRIPTS / "agents.json").read_bytes())

        self.request.update(seed_project_executors(self.home))

    def _keeper_source(self):
        source = self.area / "keeper"
        (source / "scripts").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        (source / "SKILL.md").write_text("name: context-keeper\n")
        (source / "scripts/install.py").write_text(
            'BRIDGE_START = "<!-- context-keeper:start -->"\n'
            'WORKBUDDY_BRIDGE_START = "<!-- context-keeper:workbuddy:start -->"\n'
            'WORKBUDDY_BRIDGE_END = "<!-- context-keeper:workbuddy:end -->"\n'
            'WORKBUDDY_BRIDGE = f"{WORKBUDDY_BRIDGE_START}\\nUpstream WorkBuddy rules\\n{WORKBUDDY_BRIDGE_END}\\n"\n'
            'BRIDGE_END = "<!-- context-keeper:end -->"\n'
            'BRIDGE = f"{BRIDGE_START}\\nKeeper rules\\n{BRIDGE_END}\\n"\n'
        )
        (source / "scripts/context_keeper_probe.py").write_text("# isolated stub\n")
        return source

    def runner(self, argv, **kwargs):
        self.calls.append(argv)
        rc, data = 0, {}
        if argv[1].endswith("install.py"):
            if "--ensure-bridge" in argv:
                name = ".workbuddy/memory/MEMORY.md" if "--workbuddy" in argv else "AGENTS.md" if "--codex" in argv else "CLAUDE.md"
                data = {"scope": "project", "bridge": str(self.root / name), "action": "unchanged"}
            elif "--approved" not in argv:
                links, rules = [], []
                for agent in self.request["agents"]:
                    for template in self.config[agent]["project_skill_roots"]:
                        base = template.split("{project}/", 1)[1]
                        links.append(str(self.root / base / "context-keeper"))
                    rules.append(paths.expand_path(self.config[agent]["project_bridge_entry"], home=str(self.home), project=str(self.root)))
                data = {"approval_required": True, "skill_entries": links, "rule_files": rules}
            else:
                data = {"scope": "project", "project": str(self.root)}
        else:
            store = Path(argv[argv.index("--store-dir") + 1])
            if "--approved" in argv:
                store.mkdir(parents=True, exist_ok=True)
                (store / "memory-keeper.md").write_text("# memory\n")
                for name in ("plans", "worklogs", "evolution"):
                    (store / name).mkdir(exist_ok=True)
        return subprocess.CompletedProcess(argv, rc, json.dumps(data), "")

    def preview(self, memory="no", source=False):
        self.request["memory_choice"] = memory
        if memory=="yes" and "workbuddy" in self.request["agents"]:
            (self.root/".workbuddy/memory").mkdir(parents=True,exist_ok=True)  # WorkBuddy-native precondition, §8.2.
        if source:
            alias = self.root / ".agents/skills/context-keeper"
            alias.parent.mkdir(parents=True, exist_ok=True)
            if not alias.is_symlink():
                alias.symlink_to(self.source, target_is_directory=True)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="m2-07 fault matrix")
        return plan

    def apply(self, memory="no", source=False):
        plan = self.preview(memory, source)
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        return result

    def check(self, **extra):
        request = {"project": str(self.root), "agents": None, "memory_choice": None,
                   "all": False, "approval": None, "interactive": False,
                   "home": str(self.home), "platform_config": self.config,
                   "agents_table_path": str(self.install / "agents.json")}
        request.update(extra)
        return check_mod.run(request)

    def remove(self):
        return remove_run({"project": str(self.root), "home": str(self.home),
                           "platform_config": self.config, "approval": None},
                          registry_path=self.install / "registry.json")

    def remove_approval(self, preview, root=None):
        root = Path(root or self.root)
        assembly = self.load()["projects"][str(root)]["checkouts"][str(root)]
        return {"command": "remove-memory",
                "main_checkout": str(root), "checkout": str(root),
                "git_common_dir": self._git_common(root),
                "agents": assembly["agents"],
                "memory_authorization": None,
                "store_path": assembly["store"]["path"],
                "provider_source": self.load()["projects"][str(root)]["provider_source"],
                "provider_fingerprints": [],
                "changes": [{"path": c["path"], "operation": c["operation"],
                             "before_fingerprint": c["before_fingerprint"],
                             "after_fingerprint": c["after_fingerprint"]}
                            for c in preview["changes"]],
                "confirmed_at": "2026-10-29T00:00:00Z", "reference": "m2-07 removal"}

    def _git_common(self, root):
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                                check=True, capture_output=True, text=True)
        return str((Path(root) / result.stdout.strip()).resolve())

    def load(self):
        return registry.load_registry(
            self.install / "registry.json",
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home)),
        )


class FaultMatrixTests(M207Fixture):
    def test_store_deleted_check_reports_and_enable_reinits_without_new_approval(self):
        """库目录被外部清空:check 只报缺口;enable 幂等补装重建库,不需要新批准。"""
        self.apply("yes", True)
        store = self.root / "docs/context-keeper"
        store_bytes = {p.name: p.read_bytes() for p in store.rglob("*") if p.is_file()}
        self.assertTrue(store_bytes)
        import shutil
        shutil.rmtree(store)
        result = self.check()
        self.assertEqual(result["status"], "gaps", result)
        self.assertIn("store_missing", [g["code"] for g in result["projects"][0]["gaps"]])
        self.assertFalse(store.exists(), "check 不得重建或修复库")
        self.request.update(approval=None, memory_choice=None)
        repaired = enable.run(self.request)
        self.assertEqual(repaired["status"], "completed", repaired)
        self.assertTrue((store / "memory-keeper.md").is_file())
        self.assertEqual({p.name: p.read_bytes() for p in store.rglob("*") if p.is_file()},
                         {"memory-keeper.md": store_bytes["memory-keeper.md"]})

    def test_registry_missing_all_three_commands_conservative(self):
        """registry 整体丢失:enable 待授权、check 报范围不完整、remove 不推断删除权。"""
        self.apply("yes", True)
        outputs = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        outputs[self.home / ".workbuddy/MEMORY.md"] = (self.home / ".workbuddy/MEMORY.md").read_bytes()
        (self.install / "registry.json").unlink()

        self.request.update(approval=None, memory_choice=None)
        self.assertEqual(enable.run(self.request)["errors"][0]["code"], "machine_not_installed")

        result = self.check()
        self.assertEqual(result["status"], "gaps", result)
        self.assertIn("registry_unavailable",
                      [g["code"] for g in result["projects"][0]["gaps"]])

        removal = self.remove()
        self.assertEqual(removal["status"], "failed", removal)
        self.assertEqual(removal["errors"][0]["code"], "machine_not_installed")
        for path, data in outputs.items():
            self.assertEqual(path.read_bytes(), data, "registry 丢失不得触发任何删除")
        self.assertFalse((self.install / "registry.json").exists(), "remove 不得凭空重建 registry")

    def test_registry_corrupt_check_and_remove_touch_nothing(self):
        """registry 损坏:check 保持损坏字节仅内存观察;remove 拒绝且不删任何文件。"""
        self.apply("yes", True)
        outputs = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        user_entry = self.home / ".workbuddy/MEMORY.md"
        outputs[user_entry] = user_entry.read_bytes()
        corrupt = b"{broken"
        (self.install / "registry.json").write_bytes(corrupt)

        result = self.check()
        self.assertEqual(result["status"], "gaps", result)
        self.assertIn("registry 校验失败", result["warnings"][0])
        self.assertEqual((self.install / "registry.json").read_bytes(), corrupt,
                         "check 不得重写或'修复'损坏 registry")

        removal = self.remove()
        self.assertEqual(removal["status"], "failed", removal)
        self.assertEqual(removal["errors"][0]["code"], "registry_invalid")
        for path, data in outputs.items():
            self.assertEqual(path.read_bytes(), data, "损坏 registry 下不得删除任何输出")
        self.assertEqual((self.install / "registry.json").read_bytes(), corrupt)

    def test_shared_user_entry_two_project_lifecycle(self):
        """两个项目共享用户级入口:真实 enable×2 建 created 共享对象;remove 逐项目消费,字节全程不变。"""
        self.apply()
        second = self.area / "second"
        second.mkdir()
        subprocess.run(["git", "init", "-q", str(second)], check=True)
        request = dict(self.request, project=str(second))
        result = enable.run(request)
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="second project")
        result = enable.run(dict(request, approval=plan))
        self.assertEqual(result["status"], "completed", result)

        entry = self.home / ".workbuddy/MEMORY.md"
        shared_bytes = entry.read_bytes()
        ledger = self.load()
        shared_ids = [p["checkouts"][k]["shared_object_ids"]
                      for p in ledger["projects"].values() for k in p["checkouts"]]
        self.assertTrue(all(shared_ids), "两个项目都应引用共享对象")
        self.assertEqual(list(ledger["shared_objects"]), shared_ids[0])
        self.assertEqual(len(ledger["shared_objects"][shared_ids[0][0]]["consumers"]), 2)

        preview = self.remove()
        self.assertEqual(preview["status"], "approval_required", preview)
        removal = remove_run({"project": str(self.root), "home": str(self.home),
                              "platform_config": self.config,
                              "approval": self.remove_approval(preview)},
                             registry_path=self.install / "registry.json")
        self.assertEqual(removal["status"], "completed", removal)
        self.assertEqual(entry.read_bytes(), shared_bytes, "仍有消费者时共享入口字节不变")

        request2 = {"project": str(second), "home": str(self.home),
                    "platform_config": self.config, "approval": None}
        preview2 = remove_run(request2, registry_path=self.install / "registry.json")
        self.assertEqual(preview2["status"], "approval_required", preview2)
        removal2 = remove_run(dict(request2, approval=self.remove_approval(preview2, second)),
                              registry_path=self.install / "registry.json")
        self.assertEqual(removal2["status"], "completed", removal2)
        self.assertEqual(entry.read_bytes(), shared_bytes,
                         "O2:最后一个消费者移除后仍保留用户级入口与证据")
        kept = self.load()["shared_objects"]
        self.assertTrue(kept and kept[shared_ids[0][0]]["ownership"] == "created")

    def test_agents_md_replaced_by_directory_rejected_before_any_write(self):
        """AGENTS.md 落点被目录占用:计划期即拒绝,不产生 registry/备份/入口。"""
        (self.root / "AGENTS.md").mkdir()
        marker = self.root / "AGENTS.md/keep"
        marker.write_bytes(b"occupied")
        result = enable.run(self.request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "path_conflict")
        self.assertEqual(marker.read_bytes(), b"occupied")
        self.assertEqual(json.loads((self.install / "registry.json").read_bytes()), installed_registry())
        self.assertFalse((self.runtime.backups).exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_workbuddy_native_bytes_survive_enable_and_remove_cycle(self):
        """WorkBuddy 原生日志字节:用户追加后 enable 幂等不改写;remove 只摘桥接块。"""
        self.apply("yes", True)
        entry = self.root / ".workbuddy/memory/MEMORY.md"
        with entry.open("ab") as handle:
            handle.write(b"native daily log\r\n\xff\xfe raw bytes\n")
        native = entry.read_bytes()
        before_mtime = entry.stat().st_mtime_ns

        self.request.update(approval=None, memory_choice=None)
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changes"], [], "幂等重装不得改写入口")
        self.assertEqual(entry.read_bytes(), native)
        self.assertEqual(entry.stat().st_mtime_ns, before_mtime)

        preview = self.remove()
        removal = remove_run({"project": str(self.root), "home": str(self.home),
                              "platform_config": self.config,
                              "approval": self.remove_approval(preview)},
                             registry_path=self.install / "registry.json")
        self.assertEqual(removal["status"], "completed", removal)
        data = entry.read_bytes()
        self.assertNotIn(b"workbuddy:start", data)
        self.assertTrue(data.endswith(b"native daily log\r\n\xff\xfe raw bytes\n"),
                        "remove 后原生字节必须原样保留")

    def test_no_to_yes_requires_explicit_approval_no_silent_flip(self):
        """memory 授权 no→yes 必须显式批准;不因源码在场或重复运行静默翻转。"""
        self.apply()
        alias = self.root / ".agents/skills/context-keeper"
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(self.source, target_is_directory=True)
        # §8.2: native directory is supplied by WorkBuddy, never by AGM.
        (self.root / ".workbuddy/memory").mkdir(parents=True, exist_ok=True)
        self.request.update(approval=None, memory_choice="yes")
        result = enable.run(self.request)
        self.assertEqual(result["status"], "approval_required", result)
        self.assertEqual(self.load()["projects"][str(self.root)]["memory_authorization"], "no")
        plan = json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-29T00:00:00Z", reference="explicit switch to yes")
        self.request["approval"] = plan
        result = enable.run(self.request)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.load()["projects"][str(self.root)]["memory_authorization"], "yes")
        self.assertTrue((self.root / "docs/context-keeper/memory-keeper.md").is_file())


if __name__ == "__main__":
    unittest.main()
