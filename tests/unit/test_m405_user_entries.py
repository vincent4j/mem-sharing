"""M4-05 regressions: user-entry planning/approved assembly on synthetic HOME."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agm_core import layout, paths, registry, user_entries  # noqa: E402
from agm_core.entries import block_fingerprint, sha256  # noqa: E402
from agm_core.transaction import read_snapshot  # noqa: E402
from runtime_fixture import installed_registry, seed_runtime  # noqa: E402
from test_m405_detect import fake_codesign  # noqa: E402

BASE_MARKER = {"start": "<!-- mem-sharing:rules:start -->",
               "end": "<!-- mem-sharing:rules:end -->"}


class UserEntryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / "home"
        self.home.mkdir()
        self.runtime = layout.resolve_layout(self.home)
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.apps = self.area / "Applications"
        self.apps.mkdir()
        self.bin_dir = self.area / "bin"
        self.bin_dir.mkdir()
        # Machine installed: complete ledger + product code source C.
        seed_runtime(self.home)
        code = self.runtime.code
        (code / "scripts").mkdir(parents=True)
        (code / "SKILL.md").write_text("# agent-group-memory fixture skill\n")
        self.memory_index = self.runtime.root / "memories" / "MEMORY.md"

    # ---- fixture helpers ---------------------------------------------------

    def seed_codex_package(self, name="@openai/codex"):
        package_dir = self.area / "lib" / "node_modules" / name
        (package_dir / "bin").mkdir(parents=True, exist_ok=True)
        script = package_dir / "bin" / "codex"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        (package_dir / "package.json").write_text(json.dumps(
            {"name": name, "version": "0.162.0", "bin": {"codex": "bin/codex"}}))
        link = self.bin_dir / "codex"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to("../lib/node_modules/%s/bin/codex" % name)
        return package_dir

    def seed_workbuddy_bundle(self, *, version="1.4"):
        import plistlib
        bundle = self.apps / "WorkBuddy.app"
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        info = {"CFBundleName": "WorkBuddy", "CFBundleIdentifier": "com.fixture.workbuddy",
                "CFBundleExecutable": "WorkBuddy", "CFBundleShortVersionString": version}
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
        exe = bundle / "Contents" / "MacOS" / "WorkBuddy"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        return bundle

    def request(self, **overrides):
        request = {"home": str(self.home), "platform_config": self.config,
                   "agents": None, "search_paths": [str(self.bin_dir)],
                   "app_directories": [str(self.apps)]}
        request.update(overrides)
        return request

    def workbuddy_runner(self):
        return fake_codesign(identifier="com.fixture.workbuddy")

    def tree(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() and not p.is_symlink() else (None, None)
                for p in self.home.rglob("*")}

    def approval_for(self, result):
        self.assertEqual(result["status"], "approval_required", result)
        plan = json.loads(result["next_action"])
        plan.update(confirmed_at="2026-10-30T00:00:00Z", reference="user confirmed fixture plan")
        return plan

    def preview(self, **overrides):
        return user_entries.run_user_entries(self.request(**overrides))

    def execute(self, preview=None, **overrides):
        result = preview if preview is not None else self.preview(**overrides)
        approval = self.approval_for(result)
        return user_entries.run_user_entries(self.request(approval=approval, **overrides))

    def load_ledger(self):
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        return registry.load_registry(self.runtime.registry, allowed_user_paths=allowed)

    # ---- planning purity and target filtering ------------------------------

    def test_preview_is_read_only_and_requires_approval(self):
        self.seed_codex_package()
        before = self.tree()
        result = self.preview()
        self.assertEqual(result["status"], "approval_required", result)
        self.assertEqual(self.tree(), before)
        self.assertFalse(self.runtime.lock.exists())

    def test_only_codex_installed_plan_contains_no_other_agent_paths(self):
        self.seed_codex_package()
        result = self.preview()
        plan = json.loads(result["next_action"])
        written = [c["path"] for c in plan["changes"]] + plan["machine_objects"]
        self.assertTrue(written)
        for path in written:
            self.assertIn(".codex", path, path)
        self.assertEqual(plan["machine_agents"], ["codex"])
        self.assertEqual(plan["effective"], ["codex"])
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "absent")
        self.assertEqual(result["detection"]["agents"]["workbuddy"]["status"], "absent")

    def test_residual_claude_directory_is_unknown_and_never_written(self):
        self.seed_codex_package()
        (self.home / ".claude").mkdir()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "unknown")
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists())
        self.assertFalse((self.home / ".claude" / "skills").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())

    def test_explicit_not_installed_agent_stops_whole_request(self):
        self.seed_codex_package()
        before = self.tree()
        result = self.preview(agents=["codex", "claude"])
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "agent_not_installed")
        self.assertEqual(self.tree(), before)

    def test_no_effective_agents_reports_without_faking_readiness(self):
        result = self.preview()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["agents"]["effective"], [])
        self.assertEqual(result["agents"]["skipped"],
                         {a: "absent" for a in paths.AGENT_ORDER})

    # ---- approved execution -------------------------------------------------

    def test_execute_writes_entries_and_ledger_without_skill_projection(self):
        self.seed_codex_package()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        entry = self.home / ".codex" / "AGENTS.md"
        self.assertTrue(entry.is_file())
        data = entry.read_bytes()
        self.assertIn(BASE_MARKER["start"].encode(), data)
        self.assertIn(str(self.memory_index).encode(), data)
        # 公共分层(2026-10-31 裁定):入口=公共索引指针+自身专属规则;
        # 公共治理与 /mem-sharing 菜单不再复制进 Agent 入口,由公共源承载。
        self.assertIn(user_entries.CODEX_FALLBACK_TEXT.encode(), data)
        self.assertNotIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), data)
        self.assertNotIn("/mem-sharing 菜单".encode(), data)
        self.assertFalse((self.home / ".codex" / "skills").exists())
        ledger = self.load_ledger()
        self.assertEqual(ledger["machine"]["agents"]["codex"]["installation"]["status"], "installed")
        objects = ledger["machine"]["objects"]
        self.assertEqual(sorted(objects), [str(entry) + "#public-source"])
        for obj in objects.values():
            self.assertEqual(obj["scope"], "machine")
            self.assertEqual(obj["consumers"], [])
            self.assertEqual(obj["agents"], ["codex"])
        status = user_entries.connection_status(self.runtime, self.config, ledger, ["codex"])
        self.assertEqual(status["codex"]["status"], "connected")
        self.assertFalse(self.runtime.lock.exists())

    def test_second_assembly_is_idempotent_with_zero_writes(self):
        self.seed_codex_package()
        self.execute()
        before = self.tree()
        registry_bytes = self.runtime.registry.read_bytes()
        # execute 的事务备份按保留策略持续存在;幂等的判据是二次预览不再新增任何东西
        backups_before = sorted(str(p) for p in self.runtime.backups.rglob("*")) \
            if self.runtime.backups.exists() else []
        result = self.preview()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)
        backups_after = sorted(str(p) for p in self.runtime.backups.rglob("*")) \
            if self.runtime.backups.exists() else []
        self.assertEqual(backups_after, backups_before)

    def test_managed_block_drift_stops_all_writes(self):
        self.seed_codex_package()
        self.execute()
        entry = self.home / ".codex" / "AGENTS.md"
        registry_bytes = self.runtime.registry.read_bytes()
        drifted = entry.read_bytes().replace(
            b"mem-sharing:rules:start -->",
            b"mem-sharing:rules:start -- tampered", 1)
        entry.write_bytes(drifted)
        before = self.tree()
        result = self.preview()
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "drift")
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)

    def test_projection_targets_are_never_touched_by_entry_planning(self):
        # v1.11:产品 Skill 投影取消——预置的投影位(链接/目录)不再是受管对象,
        # 规划与执行都不触碰它们,也不再因占用而整单停写。
        self.seed_codex_package()
        target = self.home / ".codex" / "skills" / "agent-group-memory"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir()
        (target / "foreign").write_bytes(b"keep me")

        def skills_tree():
            root = self.home / ".codex" / "skills"
            return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                    if p.is_file() and not p.is_symlink() else (None, None)
                    for p in root.rglob("*")} if root.exists() else {}
        before = skills_tree()
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())
        self.assertTrue((target / "foreign").is_file())
        self.assertEqual(skills_tree(), before)
        ledger = self.load_ledger()
        self.assertFalse(any(obj["kind"] == "skill_symlink"
                             for obj in ledger["machine"]["objects"].values()))

    def test_symlinked_agent_dir_is_a_conflict(self):
        self.seed_codex_package()
        elsewhere = self.area / "elsewhere"
        elsewhere.mkdir()
        (self.home / ".codex").symlink_to(elsewhere, target_is_directory=True)
        result = self.preview()
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "path_conflict")

    def test_approval_mismatch_is_rejected_without_writes(self):
        self.seed_codex_package()
        result = self.preview()
        approval = self.approval_for(result)
        approval["changes"] = []
        before = self.tree()
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "approval_required", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "approval_mismatch")
        self.assertEqual(self.tree(), before)

    def test_scene_change_between_preview_and_execute_stops(self):
        self.seed_codex_package()
        result = self.preview()
        approval = self.approval_for(result)
        # User edits the target entry after previewing: the exact plan no longer
        # matches the scene; execution must stop before any write.
        (self.home / ".codex").mkdir(exist_ok=True)
        (self.home / ".codex" / "AGENTS.md").write_bytes(b"my own rules\n")
        registry_bytes = self.runtime.registry.read_bytes()
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "approval_required", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "approval_mismatch")
        self.assertFalse((self.home / ".codex" / "skills").exists())
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)
        self.assertFalse(self.runtime.lock.exists())

    def test_execution_requires_installed_machine_ledger(self):
        self.runtime.registry.unlink()
        self.seed_codex_package()
        result = self.preview()
        self.assertEqual(result["status"], "approval_required", result)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(self.request(approval=approval))
        self.assertEqual(outcome["status"], "failed", outcome)
        self.assertEqual(outcome["errors"][0]["code"], "machine_not_installed")
        self.assertFalse(self.runtime.registry.exists())
        self.assertFalse(self.runtime.lock.exists())

    # ---- per-mode entry semantics -------------------------------------------

    def test_generated_governance_separates_default_rules_and_ck_activation(self):
        text=user_entries.GOVERNANCE_RULES_TEXT
        self.assertIn('默认启用不创建 Context Keeper 记录库',text)
        self.assertIn('disabled 时，默认流程不得重新启用入口',text)
        self.assertIn('首次保存按其流程确认位置',text)
        self.assertNotIn('从启用时刻开始记',text)
        self.assertNotIn(' CK ',text)
        self.assertIn('已有正文必须完整保留',user_entries.CLAUDE_FALLBACK_TEXT)
        self.assertIn('仅追加缺失',user_entries.CLAUDE_FALLBACK_TEXT)
        self.assertIn('仅 WorkBuddy',user_entries.WORKBUDDY_FALLBACK_TEXT)

    def test_public_contract_and_guide_topic_layering(self):
        # 公共 MEMORY 契约:读取契约/预算/公共治理/指南指针;菜单与维护规则在主题。
        contract=user_entries.public_memory_contract_text()
        self.assertIn('L0 恒读本索引',contract)
        self.assertIn('≤200 行 / 25KB',contract)
        self.assertIn(user_entries.GOVERNANCE_RULES_TEXT,contract)
        self.assertIn('[使用约定](topics/使用约定.md)',contract)
        self.assertIn('同义自然语言操作',contract)
        self.assertIn('不回指其他菜单',contract)
        self.assertNotIn('批量启用项目记忆',contract)
        self.assertNotIn(user_entries.CLAUDE_FALLBACK_TEXT,contract)
        topic=user_entries.usage_convention_topic_text('/opt/code')
        self.assertLess(topic.index('## L1 概要'),topic.index('## L2 正文'))
        self.assertIn('/mem-sharing 菜单',topic)
        self.assertIn('批量启用项目记忆',topic)
        self.assertIn('python3 /opt/code/scripts/agm.py',topic)
        self.assertIn('/opt/code/SKILL.md',topic)
        self.assertIn('enable-memory --project <项目绝对路径> --agent <当前执行器>；',topic)
        self.assertNotIn('--agent <当前执行器> --memory',topic)
        self.assertIn('已 disabled 的项目跳过',topic)
        self.assertIn('不改变任何命令默认',topic)
        self.assertIn('L0 索引一主题一行',topic)
        self.assertIn('以本文件所在目录（topics/）解析',topic)
        self.assertNotIn(user_entries.GOVERNANCE_RULES_TEXT,topic)
        self.assertNotIn(user_entries.CLAUDE_FALLBACK_TEXT,topic)
        # 公共治理:各 Agent 只维护自身专属入口;AGENTS 是共享基座,不依赖 Codex。
        self.assertIn('AGENTS.md 是共享项目规则基座，不依赖 Codex',user_entries.GOVERNANCE_RULES_TEXT)
        self.assertIn('Codex 原生读取共享项目规则基座 AGENTS.md',user_entries.CODEX_FALLBACK_TEXT)
        self.assertNotIn('仅 Codex 首次实际使用时，按默认启用条款补缺失 AGENTS.md',user_entries.CODEX_FALLBACK_TEXT)

    def test_menu_exact_order_names_and_cli_mapping(self):
        # 用户裁定:菜单六项精确命名与排序;用户可见只用
        # 用户记忆/项目记忆/项目经历三类别;CLI/API 内部标识不变。
        menu = user_entries.agent_group_menu_text('/opt/code')
        lines = menu.splitlines()
        self.assertEqual(lines[0], '/mem-sharing 菜单:')
        names = [line.split('：')[0] for line in lines[1:]]
        self.assertEqual(names, ['添加新的 Agent', '批量启用项目记忆', '整理用户记忆',
                                 '健康检查', '给项目停用记忆', '给项目启用记忆'])
        # 逐项命令映射(渲染后的真实 CLI/路径)。
        self.assertIn('python3 /opt/code/scripts/install.py --agent <执行器名>', menu)
        self.assertIn('python3 /opt/code/scripts/agm.py enable-memory-batch --directory <目录绝对路径>', menu)
        self.assertIn('治理流程见 /opt/code/SKILL.md', menu)
        self.assertIn('python3 /opt/code/scripts/agm.py check-memory --project <项目绝对路径>', menu)
        self.assertIn('python3 /opt/code/scripts/agm.py remove-memory --project <项目绝对路径>', menu)
        self.assertIn('仅禁自动项目经历记录', menu)
        self.assertIn('python3 /opt/code/scripts/agm.py enable-memory --project <项目绝对路径> --memory', menu)
        # 末项启用说明:显式恢复/手动启用;默认语义不变。
        self.assertIn('显式恢复已停用项目或手动启用项目记忆', menu)
        self.assertIn('disabled 不自动恢复语义不变', menu)
        # 旧命名与新类别外用语不再出现。
        self.assertNotIn('整理用户规则', menu)
        self.assertNotIn('停用记忆：撤入口并保留数据', menu)
        self.assertNotIn('批量启用记忆：扫描', menu)
        # 指南派生文字随菜单同步(同源派生,不另造第二份)。
        topic = user_entries.usage_convention_topic_text('/opt/code')
        self.assertIn('批量启用项目记忆', topic)
        self.assertIn('整理用户记忆', topic)
        self.assertNotIn('整理用户规则', topic)

    def test_workbuddy_convention_uses_enable_template_text(self):
        enable_source = (REPO / "scripts" / "agm_core" / "enable.py").read_text(encoding="utf-8")
        self.assertIn('项目规则读取当前项目根 AGENTS.md。', enable_source)
        self.assertIn('保留已有公共源与用户约定', user_entries.WORKBUDDY_CONVENTION_TEXT)

    def test_workbuddy_shared_convention_is_referenced_not_duplicated(self):
        self.seed_workbuddy_bundle()
        entry = self.home / ".workbuddy" / "MEMORY.md"
        entry.parent.mkdir(parents=True)
        block = (BASE_MARKER["start"] + "\n项目规则读取当前项目根 AGENTS.md。保留已有公共源与用户约定。\n"
                 + BASE_MARKER["end"]).encode("utf-8")
        entry.write_bytes(b"existing header\n" + block + b"\n")
        data = installed_registry()
        data["shared_objects"]["wb-convention"] = {
            "kind": "user_convention", "path": str(entry), "scope": "user",
            "agents": ["workbuddy"], "ownership": "reused", "marker": BASE_MARKER,
            "fingerprint": {"algorithm": "sha256", "basis": "block_bytes",
                            "value": block_fingerprint(entry.read_bytes(), BASE_MARKER["start"], BASE_MARKER["end"])},
            "original_existed": True, "link_target": None, "backup_manifest": None,
            "consumers": []}
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(registry.serialize_registry(data, allowed_user_paths=allowed))
        before = entry.read_bytes()
        request = self.request(detect_runner=self.workbuddy_runner())
        result = user_entries.run_user_entries(request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "entry_semantics_missing")
        self.assertEqual(entry.read_bytes(), before)

    def test_workbuddy_machine_convention_carries_pointer_and_own_rules(self):
        self.seed_workbuddy_bundle()
        result = self.execute(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["status"], "completed", result)
        entry = self.home / ".workbuddy" / "MEMORY.md"
        data = entry.read_bytes()
        self.assertIn(user_entries.WORKBUDDY_CONVENTION_TEXT.encode(), data)
        self.assertIn(user_entries.WORKBUDDY_FALLBACK_TEXT.encode(), data)
        self.assertIn(str(self.memory_index).encode(), data)
        # 公共分层:治理条款与菜单不复制进 WorkBuddy 入口。
        self.assertNotIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), data)
        self.assertNotIn("/mem-sharing 菜单".encode(), data)
        self.assertFalse((self.home / ".codex").exists())

    def test_workbuddy_existing_entry_without_block_is_preserved(self):
        self.seed_workbuddy_bundle()
        entry = self.home / ".workbuddy" / "MEMORY.md"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(b"my own workbuddy memory\n")
        before = entry.read_bytes()
        request = self.request(detect_runner=self.workbuddy_runner())
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        self.assertTrue(entry.read_bytes().startswith(before))
        self.assertIn(str(self.memory_index).encode(), entry.read_bytes())
        ledger = self.load_ledger()
        obj = ledger["machine"]["objects"][str(entry) + "#convention"]
        from agm_core.entries import remove_block
        self.assertEqual(remove_block(entry.read_bytes(), **BASE_MARKER,
                         expected_fingerprint=obj["fingerprint"]["value"]), before)
        self.assertEqual(self.preview(detect_runner=self.workbuddy_runner())["changes"], [])

    def test_workbuddy_old_registered_block_update_is_approved_and_preserves_private_bytes(self):
        self.seed_workbuddy_bundle()
        self.assertEqual(self.execute(detect_runner=self.workbuddy_runner())["status"], "completed")
        entry = self.home / ".workbuddy/MEMORY.md"
        new = entry.read_bytes()
        old = new.replace((user_entries.public_read_text(self.memory_index) + "\n").encode(), b"")
        entry.write_bytes(b"private\r\n" + old + b"\r\ntail")
        ledger = self.load_ledger()
        ledger["machine"]["objects"][str(entry)+"#convention"]["fingerprint"]["value"] = sha256(old)
        self.runtime.registry.write_text(json.dumps(ledger))
        before = entry.read_bytes()
        preview = self.preview(detect_runner=self.workbuddy_runner())
        self.assertEqual(preview["status"], "approval_required", preview)
        self.assertEqual(before, entry.read_bytes())
        result = self.execute(preview, detect_runner=self.workbuddy_runner())
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(entry.read_bytes(), b"private\r\n" + new + b"\r\ntail")
        self.assertEqual(self.preview(detect_runner=self.workbuddy_runner())["changes"], [])
        entry.write_bytes(entry.read_bytes().replace(b"AGENTS.md", b"CHANGED.md"))
        result = self.preview(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["errors"][0]["code"], "drift")

    def test_shared_reference_does_not_claim_machine_connection(self):
        self.seed_workbuddy_bundle()
        self.execute(detect_runner=self.workbuddy_runner())
        ledger = self.load_ledger()
        oid = str(self.home / ".workbuddy/MEMORY.md") + "#convention"
        obj = ledger["machine"]["objects"].pop(oid)
        obj.update(scope="user", ownership="reused", original_existed=True, backup_manifest=None)
        ledger["shared_objects"][oid] = obj
        self.runtime.registry.write_text(json.dumps(ledger))
        before = self.tree()
        result = self.preview(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["changes"], [])
        self.assertEqual(before, self.tree())
        status = user_entries.connection_status(self.runtime, self.config, ledger, ["workbuddy"])
        self.assertEqual(status["workbuddy"]["status"], "pending")
        self.assertEqual(status["workbuddy"]["reason"], "machine_entry_not_registered_shared_reference")
        for agent in ("codex", "claude"):
            ledger["machine"]["agents"][agent] = copy.deepcopy(ledger["machine"]["agents"]["workbuddy"])
            obj = copy.deepcopy(obj)
            obj["path"] = paths.expand_path(self.config[agent]["user_entry"], home=str(self.home))
            obj["agents"] = [agent]
            ledger["shared_objects"][agent] = obj
            status = user_entries.connection_status(self.runtime, self.config, ledger, [agent])
            self.assertEqual(status[agent]["reason"], "machine_entry_not_registered_shared_reference")


    def test_workbuddy_unregistered_old_block_is_not_claimed(self):
        self.seed_workbuddy_bundle()
        entry = self.home / ".workbuddy/MEMORY.md"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(user_entries._wrap_block(BASE_MARKER, user_entries.WORKBUDDY_CONVENTION_TEXT))
        before = self.tree()
        result = self.preview(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["errors"][0]["code"], "entry_semantics_missing")
        self.assertEqual(before, self.tree())

    def test_workbuddy_unregistered_current_block_is_reused_without_ownership(self):
        self.seed_workbuddy_bundle()
        self.execute(detect_runner=self.workbuddy_runner())
        entry = self.home / ".workbuddy/MEMORY.md"
        raw = entry.read_bytes()
        ledger = self.load_ledger()
        ledger["machine"]["objects"] = {}
        self.runtime.registry.write_text(json.dumps(ledger))
        result = self.execute(detect_runner=self.workbuddy_runner())
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(raw, entry.read_bytes())
        self.assertEqual(self.load_ledger()["machine"]["objects"][str(entry)+"#convention"]["ownership"], "reused")

    def test_claude_receipt_import_line_references_common_source(self):
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        request = self.request(user_candidates={
            "claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        entry = self.home / ".claude" / "CLAUDE.md"
        data = entry.read_bytes()
        # 公共指针 import 行 + Claude 自身 fallback 受管块,两者都在本机入口。
        self.assertTrue(data.startswith(("@" + str(self.memory_index) + "\n").encode()))
        self.assertIn(user_entries._wrap_block(
            user_entries.CLAUDE_FALLBACK_MARKER, user_entries.CLAUDE_FALLBACK_TEXT), data)
        self.assertNotIn(user_entries.GOVERNANCE_RULES_TEXT.encode(), data)
        self.assertNotIn("/mem-sharing 菜单".encode(), data)
        ledger = self.load_ledger()
        objects = ledger["machine"]["objects"]
        self.assertEqual(sorted(objects), [str(entry) + "#claude-fallback", str(entry) + "#import"])
        self.assertEqual(objects[str(entry) + "#import"]["kind"], "import")
        self.assertEqual(objects[str(entry) + "#import"]["ownership"], "reused")
        # import 登记指纹按最终整文件字节(含其后追加的兜底块)重绑,不改 ownership。
        self.assertEqual(objects[str(entry) + "#import"]["fingerprint"],
                         {"algorithm": "sha256", "basis": "file_bytes", "value": sha256(data)})
        fallback = objects[str(entry) + "#claude-fallback"]
        self.assertEqual(fallback["kind"], "block")
        self.assertEqual(fallback["marker"], user_entries.CLAUDE_FALLBACK_MARKER)
        self.assertEqual(fallback["ownership"], "created")
        status = user_entries.connection_status(self.runtime, self.config, ledger, ["claude"])
        self.assertEqual(status["claude"]["status"], "connected")
        # 连接证据要求两类单元齐备:删掉兜底块字节即回落 pending,不算已接入。
        entry.write_bytes(("@" + str(self.memory_index) + "\n").encode())
        status = user_entries.connection_status(self.runtime, self.config, ledger, ["claude"])
        self.assertEqual(status["claude"]["status"], "pending")
        self.assertEqual(status["claude"]["reason"], "entry_drift_or_semantics_missing")
        # 已登记哈希一致但块内语义缺失(非模板内容)不算连接:哈希只证登记一致,
        # 不证块承载兜底语义;核验以标记内内容为准,不审核自由私人正文。
        wrong = user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER, "无关内容")
        entry.write_bytes(("@" + str(self.memory_index) + "\n").encode() + wrong)
        drift_ledger = copy.deepcopy(ledger)
        drift_ledger["machine"]["objects"][str(entry) + "#claude-fallback"]["fingerprint"]["value"] = \
            sha256(wrong)
        status = user_entries.connection_status(
            self.runtime, self.config, drift_ledger, ["claude"])
        self.assertEqual(status["claude"]["status"], "pending")
        self.assertEqual(status["claude"]["reason"], "entry_drift_or_semantics_missing")
        # 旧台账只有 import 登记(迁移前形态):证据类不齐,连接判定为 pending。
        entry.write_bytes(data)
        import_only = copy.deepcopy(ledger)
        import_only["machine"]["objects"].pop(str(entry) + "#claude-fallback")
        status = user_entries.connection_status(self.runtime, self.config, import_only, ["claude"])
        self.assertEqual(status["claude"]["status"], "pending")
        self.assertEqual(status["claude"]["reason"], "entry_evidence_incomplete")
        # 仅 Claude 接入不预建未安装执行器的用户文件(共享基座不属于任何单家)。
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.home / ".workbuddy").exists())

    def test_claude_existing_content_keeps_reference_append_only(self):
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"# my claude rules\n")
        request = self.request(user_candidates={
            "claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        data = entry.read_bytes()
        self.assertTrue(data.startswith(b"# my claude rules\n"))
        self.assertIn(("@" + str(self.memory_index)).encode(), data)
        self.assertIn(user_entries.CLAUDE_FALLBACK_TEXT.encode(), data)

    def test_claude_plus_workbuddy_shared_base_without_codex(self):
        # only Claude+WorkBuddy(无 Codex)也能独立建立共享规则入口:
        # 公共源指针各自落位,未安装的 Codex 不产生任何用户文件。
        self.seed_workbuddy_bundle()
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        request = self.request(detect_runner=self.workbuddy_runner(), user_candidates={
            "claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})
        result = user_entries.run_user_entries(request)
        self.assertEqual(result["detection"]["agents"]["codex"]["status"], "absent")
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        self.assertEqual(sorted(outcome["agents"]["effective"]), ["claude", "workbuddy"])
        self.assertIn(str(self.memory_index).encode(),
                      (self.home / ".claude" / "CLAUDE.md").read_bytes())
        self.assertIn(str(self.memory_index).encode(),
                      (self.home / ".workbuddy" / "MEMORY.md").read_bytes())
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse((self.home / ".codex" / "AGENTS.md").exists())

    # ---- shared 承载入口与 Claude 兜底块的互斥(2026-10-31 呱唧复验反例) ---------

    def _claude_shared_fixture(self, shared_objects, machine_objects=None, entry_bytes=None):
        """装好 Claude 收据探测,并按给定 shared/machine 单元重写台账。"""
        exe = self.area / "native" / "claude"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(entry_bytes if entry_bytes is not None else b"")
        data = installed_registry()
        data["shared_objects"].update(shared_objects)
        data["machine"]["objects"].update(machine_objects or {})
        allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
        self.runtime.registry.write_bytes(registry.serialize_registry(data, allowed_user_paths=allowed))
        return self.request(user_candidates={"claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})

    @staticmethod
    def _unit(kind, path, *, scope="user", marker=None, fingerprint_value):
        return {"kind": kind, "path": str(path), "scope": scope, "agents": ["claude"],
                "ownership": "reused", "marker": marker,
                "fingerprint": {"algorithm": "sha256",
                                "basis": "file_bytes" if marker is None else "block_bytes",
                                "value": fingerprint_value},
                "original_existed": True, "link_target": None, "backup_manifest": None,
                "consumers": []}

    def test_shared_import_without_fallback_is_rejected_zero_write(self):
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir()
        content = ("@" + str(self.memory_index) + "\n").encode()
        request = self._claude_shared_fixture(
            {"claude-import": self._unit("import", entry, fingerprint_value=sha256(content))},
            entry_bytes=content)
        registry_bytes = self.runtime.registry.read_bytes()
        before = self.tree()
        result = user_entries.run_user_entries(request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "ownership_conflict")
        self.assertIn("claude-import", result["errors"][0]["message"])
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.runtime.registry.read_bytes(), registry_bytes)

    def test_file_kind_record_at_import_slot_is_never_adopted(self):
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir()
        content = b"# shared claude rules\n"
        for scope, objects in (("user", "shared_objects"), ("machine", "machine_objects")):
            with self.subTest(scope=scope):
                data = installed_registry()
                unit = self._unit("file", entry, scope=scope, fingerprint_value=sha256(content))
                if scope == "user":
                    data["shared_objects"]["claude-file"] = unit
                else:
                    unit = dict(unit, scope="machine")
                    data["machine"]["objects"][str(entry) + "#file"] = unit
                    data["machine"]["agents"]["claude"] = {
                        "installation": {"status": "installed", "observed_at": "2026-10-31T00:00:00Z",
                                         "evidence": "fixture claude installed"},
                        "static": registry.unknown_fact(),
                        "runtime_acceptance": {"status": "pending", "evidence_path": None}}
                allowed = paths.allowed_user_paths(self.config, None, home=str(self.home))
                self.runtime.registry.write_bytes(
                    registry.serialize_registry(data, allowed_user_paths=allowed))
                entry.write_bytes(content)
                before = self.tree()
                result = user_entries.run_user_entries(self._claude_receipt_request())
                self.assertEqual(result["status"], "failed", result)
                self.assertEqual(result["errors"][0]["code"], "ownership_conflict")
                self.assertEqual(self.tree(), before)

    def _claude_receipt_request(self):
        exe = self.area / "native" / "claude"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        receipt = {"schema_version": 1, "product": "Claude Code", "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}]}
        receipt_path = self.area / "native" / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        return self.request(user_candidates={"claude": [{"kind": "user_receipt", "path": str(receipt_path)}]})

    def test_shared_fallback_hash_match_without_semantics_is_rejected(self):
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir()
        wrong = user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER, "无关共享内容")
        content = ("@" + str(self.memory_index) + "\n").encode() + wrong
        request = self._claude_shared_fixture(
            {"claude-fallback": dict(self._unit("block", entry, marker=user_entries.CLAUDE_FALLBACK_MARKER,
                                                fingerprint_value=sha256(wrong)),
                                     fingerprint={"algorithm": "sha256", "basis": "block_bytes",
                                                  "value": sha256(wrong)})},
            entry_bytes=content)
        before = self.tree()
        result = user_entries.run_user_entries(request)
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["errors"][0]["code"], "entry_semantics_missing")
        self.assertEqual(self.tree(), before)

    def test_shared_import_with_correct_fallback_references_without_writes(self):
        entry = self.home / ".claude" / "CLAUDE.md"
        entry.parent.mkdir()
        fallback = user_entries._wrap_block(user_entries.CLAUDE_FALLBACK_MARKER, user_entries.CLAUDE_FALLBACK_TEXT)
        content = ("@" + str(self.memory_index) + "\n").encode() + fallback
        request = self._claude_shared_fixture(
            {"claude-import": self._unit("import", entry, fingerprint_value=sha256(content))},
            entry_bytes=content)
        result = user_entries.run_user_entries(request)
        approval = self.approval_for(result)
        outcome = user_entries.run_user_entries(dict(request, approval=approval))
        self.assertEqual(outcome["status"], "completed", outcome)
        # 只引用:文件字节与 shared 指纹都不变,不登记机器兜底对象假冒连接。
        self.assertEqual(entry.read_bytes(), content)
        ledger = self.load_ledger()
        self.assertEqual(ledger["shared_objects"]["claude-import"]["fingerprint"]["value"], sha256(content))
        self.assertNotIn(str(entry) + "#claude-fallback", ledger["machine"]["objects"])
        status = user_entries.connection_status(self.runtime, self.config, ledger, ["claude"])
        self.assertEqual(status["claude"]["status"], "pending")
        self.assertEqual(status["claude"]["reason"], "machine_entry_not_registered_shared_reference")

    def test_codex_existing_rules_get_block_appended(self):
        self.seed_codex_package()
        entry = self.home / ".codex" / "AGENTS.md"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"# my codex rules\n")
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        data = entry.read_bytes()
        self.assertTrue(data.startswith(b"# my codex rules\n"))
        self.assertIn(BASE_MARKER["start"].encode(), data)
        # 重复规划:同标记同模板不再追加第二个块;收敛后零差异,直接完成无需批准。
        fingerprint = block_fingerprint(data, BASE_MARKER["start"], BASE_MARKER["end"])
        repeat = self.preview()
        self.assertEqual(repeat["status"], "completed", repeat)
        data2 = entry.read_bytes()
        self.assertEqual(data2, data)
        self.assertEqual(block_fingerprint(data2, BASE_MARKER["start"], BASE_MARKER["end"]), fingerprint)

    def test_unknown_and_absent_mixed_order_only_writes_installed(self):
        self.seed_codex_package()
        (self.home / ".workbuddy").mkdir()  # residual hint -> unknown
        result = self.execute()
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["detection"]["agents"]["workbuddy"]["status"], "unknown")
        self.assertEqual(result["detection"]["agents"]["claude"]["status"], "absent")
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())
        self.assertFalse((self.home / ".workbuddy" / "MEMORY.md").exists())
        self.assertFalse((self.home / ".workbuddy" / "skills").exists())


if __name__ == "__main__":
    unittest.main()
