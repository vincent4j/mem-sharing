"""M4-05 regressions: three-state installation detection on synthetic fixtures."""
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from agm_core import detect, paths  # noqa: E402


def fake_codesign(identifier=None, verify_rc=0):
    """Static-verification stand-in; never launches anything on the host."""
    calls = []

    def runner(command):
        calls.append(list(command))
        if command[1:2] == ["--verify"]:
            return SimpleNamespace(returncode=verify_rc, stdout="", stderr="")
        if command[1:2] == ["-d"]:
            text = "" if identifier is None else "Identifier=%s\n" % identifier
            return SimpleNamespace(returncode=0, stdout="", stderr=text)
        raise AssertionError("unexpected command: %r" % (command,))

    runner.calls = calls
    return runner


class DetectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / "home"
        self.home.mkdir()
        self.apps = self.area / "Applications"
        self.apps.mkdir()
        self.bin_dir = self.area / "bin"
        self.bin_dir.mkdir()
        self.config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.request = dict(search_paths=[str(self.bin_dir)], app_directories=[str(self.apps)])

    def tree(self):
        return sorted(str(p.relative_to(self.area)) for p in self.area.rglob("*"))

    def detect(self, agents=None, **overrides):
        options = dict(self.request)
        options.update(overrides)
        return detect.detect_agents(self.config, agents, home=str(self.home), **options)

    def npm_package(self, name, version="1.2.3", bin_name=None, executable="#!/usr/bin/env node\n"):
        package_dir = self.area / "lib" / "node_modules" / name
        (package_dir / "bin").mkdir(parents=True, exist_ok=True)
        script = package_dir / "bin" / (bin_name or Path(name).name)
        script.write_text(executable)
        script.chmod(0o755)
        (package_dir / "package.json").write_text(json.dumps(
            {"name": name, "version": version, "bin": {Path(name).name: "bin/" + Path(name).name}}))
        link = self.bin_dir / Path(name).name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to("../lib/node_modules/%s/bin/%s" % (name, Path(name).name))
        return package_dir

    def app_bundle(self, directory, bundle_name, *, product, executable=True,
                   version=None, bundle_id="com.example.fixture"):
        bundle = directory / bundle_name
        (bundle / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        info = {"CFBundleName": product, "CFBundleIdentifier": bundle_id,
                "CFBundleExecutable": bundle_name[:-4]}
        if version is not None:
            info["CFBundleShortVersionString"] = version
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
        if executable is not False:
            exe = bundle / "Contents" / "MacOS" / bundle_name[:-4]
            exe.write_text("#!/bin/sh\nexit 0\n")
            exe.chmod(0o755)
        return bundle


class PathExecutableTests(DetectFixture):
    def test_exact_package_match_is_installed_with_full_evidence(self):
        self.npm_package("@openai/codex", "0.162.0")
        report = self.detect()
        record = report["agents"]["codex"]
        self.assertEqual(record["status"], "installed")
        verified = [item for item in record["evidence"] if item["result"] == "verified"]
        self.assertEqual(len(verified), 1)
        item = verified[0]
        self.assertEqual(item["name"], "@openai/codex")
        self.assertEqual(item["version"], "0.162.0")
        self.assertTrue(os.path.isabs(item["path"]))
        self.assertEqual(len(item["sha256"]), 64)
        self.assertEqual(record["rules_version"], detect.DETECT_RULES_VERSION)
        self.assertTrue(record["observed_at"].endswith("Z"))

    def test_wrong_package_name_is_unknown_wrapper(self):
        self.npm_package("@openai/codex")
        # A wrapper script with a nearest package.json of a different product.
        wrapped = self.area / "lib" / "node_modules" / "@openai/codex" / "package.json"
        wrapped.write_text(json.dumps({"name": "@evil/fake-codex", "version": "1.0"}))
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")

    def test_bare_binary_without_package_is_unknown(self):
        raw = self.bin_dir / "codex"
        raw.write_text("#!/bin/sh\n")
        raw.chmod(0o755)
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")
        self.assertIn("package.json", report["agents"]["codex"]["summary"])

    def test_broken_path_link_is_unknown(self):
        (self.bin_dir / "codex").symlink_to("../lib/missing/codex")
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")

    def test_two_verified_copies_make_active_source_undeterminable(self):
        self.npm_package("@openai/codex")
        other = self.area / "bin2"
        other.mkdir()
        package_dir = self.area / "lib2" / "node_modules" / "@openai/codex"
        (package_dir / "bin").mkdir(parents=True)
        script = package_dir / "bin" / "codex"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        (package_dir / "package.json").write_text(json.dumps(
            {"name": "@openai/codex", "version": "2.0.0"}))
        (other / "codex").symlink_to("../lib2/node_modules/@openai/codex/bin/codex")
        report = self.detect(search_paths=[str(other), str(self.bin_dir)])
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")
        self.assertIn("无法确定活动来源", report["agents"]["codex"]["summary"])

    def test_declared_bin_missing_is_unknown(self):
        package_dir = self.npm_package("@openai/codex")
        (package_dir / "bin" / "codex").unlink()
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")


class AppBundleTests(DetectFixture):
    def test_valid_codex_bundle_is_installed_without_identifier_match(self):
        self.app_bundle(self.apps, "Codex.app", product="Codex")
        report = self.detect(runner=fake_codesign())
        self.assertEqual(report["agents"]["codex"]["status"], "installed")
        verified = [item for item in report["agents"]["codex"]["evidence"] if item["result"] == "verified"]
        self.assertEqual(verified[0]["type"], "app_bundle")
        self.assertEqual(verified[0]["name"], "com.example.fixture")

    def test_workbuddy_requires_version_and_identifier_match(self):
        self.app_bundle(self.apps, "WorkBuddy.app", product="WorkBuddy", version="1.0",
                        bundle_id="com.example.workbuddy")
        good = self.detect(runner=fake_codesign(identifier="com.example.workbuddy"))
        self.assertEqual(good["agents"]["workbuddy"]["status"], "installed")
        wrong = self.detect(runner=fake_codesign(identifier="com.other.component"))
        self.assertEqual(wrong["agents"]["workbuddy"]["status"], "unknown")
        self.assertIn("identifier", wrong["agents"]["workbuddy"]["summary"])

    def test_workbuddy_without_version_is_unknown(self):
        self.app_bundle(self.apps, "WorkBuddy.app", product="WorkBuddy", version=None)
        report = self.detect(runner=fake_codesign(identifier="com.example.fixture"))
        self.assertEqual(report["agents"]["workbuddy"]["status"], "unknown")
        self.assertIn("版本为空", report["agents"]["workbuddy"]["summary"])

    def test_product_name_mismatch_is_unknown(self):
        self.app_bundle(self.apps, "Codex.app", product="Something Else")
        report = self.detect(runner=fake_codesign())
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")

    def test_missing_signature_backend_is_unknown_not_absent(self):
        self.app_bundle(self.apps, "Codex.app", product="Codex")
        report = self.detect(runner=lambda command: None)
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")

    def test_failing_signature_is_unknown(self):
        self.app_bundle(self.apps, "Codex.app", product="Codex")
        report = self.detect(runner=fake_codesign(verify_rc=3))
        self.assertEqual(report["agents"]["codex"]["status"], "unknown")

    def test_user_provided_bundle_path_extends_probing(self):
        elsewhere = self.area / "opt"
        elsewhere.mkdir()
        bundle = self.app_bundle(elsewhere, "WorkBuddy.app", product="WorkBuddy",
                                 version="3.1", bundle_id="com.wb")
        report = self.detect(runner=fake_codesign(identifier="com.wb"),
                             user_candidates={"workbuddy": [{"kind": "macos_app_bundle", "path": str(bundle)}]})
        self.assertEqual(report["agents"]["workbuddy"]["status"], "installed")

    def test_real_codesign_adhoc_bundle_verifies(self):
        if shutil.which("codesign") is None:
            self.skipTest("codesign unavailable on this host")
        bundle = self.app_bundle(self.apps, "Codex.app", product="Codex",
                                 bundle_id="com.agm.fixture.codex")
        result = subprocess.run(["codesign", "--sign", "-", "--identifier",
                                 "com.agm.fixture.codex", str(bundle)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            self.skipTest("host cannot ad-hoc sign: %s" % result.stderr.strip())
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "installed", report["agents"]["codex"]["summary"])


class ReceiptTests(DetectFixture):
    def receipt(self, product="Claude Code", *, hash_files=True, extra=None):
        native = self.area / "native"
        native.mkdir(exist_ok=True)
        exe = native / "claude"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        import hashlib
        digest = hashlib.sha256(exe.read_bytes()).hexdigest()
        receipt = {"schema_version": 1, "product": product, "version": "2.1.0",
                   "executable": str(exe),
                   "files": [{"path": str(exe), "sha256": digest if hash_files else "0" * 64}]}
        if extra:
            receipt.update(extra)
        path = native / "receipt.json"
        path.write_text(json.dumps(receipt))
        return path

    def test_valid_receipt_makes_claude_installed(self):
        report = self.detect(user_candidates={"claude": [{"kind": "user_receipt", "path": str(self.receipt())}]})
        self.assertEqual(report["agents"]["claude"]["status"], "installed")
        verified = [item for item in report["agents"]["claude"]["evidence"] if item["result"] == "verified"]
        self.assertEqual(verified[0]["type"], "receipt_manifest")

    def test_receipt_hash_mismatch_is_unknown(self):
        report = self.detect(user_candidates={"claude": [{"kind": "user_receipt", "path": str(self.receipt(hash_files=False))}]})
        self.assertEqual(report["agents"]["claude"]["status"], "unknown")

    def test_receipt_wrong_product_is_unknown(self):
        report = self.detect(user_candidates={"claude": [{"kind": "user_receipt", "path": str(self.receipt(product="Other"))}]})
        self.assertEqual(report["agents"]["claude"]["status"], "unknown")

    def test_no_receipt_and_no_signal_is_absent_not_blocked(self):
        report = self.detect()
        self.assertEqual(report["agents"]["claude"]["status"], "absent")


class ThreeStateRulesTests(DetectFixture):
    def test_residual_directory_hint_alone_is_unknown(self):
        (self.home / ".claude").mkdir()
        report = self.detect()
        self.assertEqual(report["agents"]["claude"]["status"], "unknown")
        self.assertIn("hint", report["agents"]["claude"]["summary"])

    def test_all_checkable_and_missing_without_hint_is_absent(self):
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "absent")
        self.assertEqual(report["agents"]["claude"]["status"], "absent")
        self.assertEqual(report["agents"]["workbuddy"]["status"], "absent")

    def test_residual_dir_does_not_flip_other_agents(self):
        (self.home / ".claude").mkdir()
        report = self.detect()
        self.assertEqual(report["agents"]["codex"]["status"], "absent")
        self.assertEqual(report["agents"]["workbuddy"]["status"], "absent")

    def test_detection_writes_nothing(self):
        self.npm_package("@openai/codex")
        self.app_bundle(self.apps, "WorkBuddy.app", product="WorkBuddy", version="1")
        before = self.tree()
        self.detect(runner=fake_codesign(identifier="com.example.fixture"))
        self.assertEqual(before, self.tree())

    def test_fingerprint_ignores_observation_timestamps(self):
        self.npm_package("@openai/codex")
        # detect(None) 现枚举五家(顶层+每Agent各一时间戳),两轮共 12 个值,给足余量。
        clock = iter("2026-10-30T04:39:0%dZ" % n for n in range(30))
        original, detect._utc_now = detect._utc_now, lambda: next(clock)
        try:
            first = self.detect()
            second = self.detect()
        finally:
            detect._utc_now = original
        self.assertNotEqual(first["agents"]["codex"]["observed_at"],
                            second["agents"]["codex"]["observed_at"])
        self.assertEqual(detect.detection_fingerprint(first["agents"]["codex"]),
                         detect.detection_fingerprint(second["agents"]["codex"]))
        first["agents"]["codex"]["evidence"][0]["detail"] = "tampered"
        self.assertNotEqual(detect.detection_fingerprint(first["agents"]["codex"]),
                            detect.detection_fingerprint(second["agents"]["codex"]))

    def test_malformed_user_candidates_rejected(self):
        with self.assertRaises(detect.DetectionError):
            self.detect(user_candidates={"claude": [{"kind": "user_receipt"}]})

    def test_home_must_be_absolute(self):
        with self.assertRaises(detect.DetectionError):
            detect.detect_agents(self.config, home="relative/home")


class SignalTableTests(unittest.TestCase):
    def _write(self, data):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(path).write_text(json.dumps(data))
        self.addCleanup(os.unlink, path)
        return path

    def test_repo_table_strong_signals_valid(self):
        table = paths.load_agents_table()
        codex = table["platforms"]["darwin"]["codex"]["installation_signals"]
        self.assertEqual([s["kind"] for s in codex],
                         ["directory_exists", "path_executable", "macos_app_bundle"])
        self.assertTrue(all(s["strength"] == "strong" for s in codex[1:]))

    def test_repo_table_has_no_user_skill_roots(self):
        # v1.11:产品 Skill 投影取消,路径表不再携带用户级 Skill 根字段。
        table = paths.load_agents_table()
        for agent, entry in table["platforms"]["darwin"].items():
            self.assertNotIn("user_skill_roots", entry, agent)

    def _invalid(self, mutate):
        table = json.loads((REPO / "scripts" / "agents.json").read_text(encoding="utf-8"))
        mutate(table["platforms"]["darwin"]["codex"])
        path = self._write(table)
        with self.assertRaises(paths.PathsError) as ctx:
            paths.load_agents_table(path)
        self.assertEqual(ctx.exception.code, "agents_table_invalid")

    def test_user_skill_roots_field_rejected(self):
        self._invalid(lambda entry: entry.update(user_skill_roots=["{home}/.codex/skills"]))

    def test_strong_kind_with_hint_strength_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][1].update(strength="hint"))

    def test_bundle_name_with_separator_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][2].update(bundle_name="../Codex.app"))

    def test_executable_with_path_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][1].update(executable="bin/codex"))

    def test_extra_field_in_strong_signal_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][1].update(ttl=5))

    def test_non_bool_require_flag_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][2].update(require_bundle_version="yes"))

    def test_hint_with_strong_strength_rejected(self):
        self._invalid(lambda entry: entry["installation_signals"][0].update(strength="strong"))

    def test_hints_output_only_contains_directory_hints(self):
        config = paths.select_platform(paths.load_agents_table(), "darwin")
        hints = paths.installation_hints(config, ["codex"], home="/TestHome")
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["kind"], "directory_exists")
        self.assertEqual(hints[0]["strength"], "hint")
        self.assertEqual(hints[0]["path"], "/TestHome/.codex")

    def test_allowed_user_paths_contain_entries_only(self):
        # v1.11:产品 Skill 投影取消,用户级受管路径仅含入口文件。
        config = paths.select_platform(paths.load_agents_table(), "darwin")
        self.assertEqual(paths.allowed_user_paths(config, ["claude"], home="/TestHome"),
                         ["/TestHome/.claude/CLAUDE.md"])
        self.assertFalse(hasattr(paths, "user_skill_paths"))


if __name__ == "__main__":
    unittest.main()
