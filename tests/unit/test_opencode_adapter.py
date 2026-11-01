"""OpenCode v2 adapter contract tests; synthetic HOME/binary only, no real session.

覆盖(2026-11-01 接入裁定):原生 Mach-O 签名识别(先于 npm 元数据,父
package.json 无 name 不阻断;错误签名不因包名放行)、npm 包装脚本仍走包名
门禁、不依赖文件名、配置根三变量 default-root-only 重定向整单零写且不回显
原值、私文保留/幂等零写、unknown/absent 零写、显式未装整单拒绝、check/
remove/disabled、迁移未登记读者扫描、大文件不误套 Codex 32KiB 预算、项目层
不预建执行器私文。
"""
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_m404_install import InstallFixture, approved
from test_m204_enable import EnableFixture
from test_m405_detect import DetectFixture, fake_codesign
from agm_core import check, detect, enable, paths, public_layout, registry, user_entries, user_install

# 64 位 arm64 Mach-O 魔数(小端);测试只写头部字节,从不执行。
MACHO_ARM64 = bytes.fromhex('cffaedfe')


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
            os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
            for p in [root, *root.rglob('*')]}


def opencode_facts(config, home, **statuses):
    facts = detect.detect_agents(config, None, home=str(home), search_paths=[], app_directories=[])
    facts['agents']['opencode'].update(statuses.get('opencode', {'status': 'installed', 'summary': 'synthetic'}))
    for agent, meta in statuses.items():
        if agent != 'opencode':
            facts['agents'][agent].update(meta)
    return facts


class OpenCodeDetectionTests(DetectFixture):
    def macho_binary(self, target, magic=MACHO_ARM64):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(magic + b'\x00' * 64)
        target.chmod(0o755)
        return target

    def scoped_opencode_package(self, name='@opencode/cli', macho=False):
        """npm scoped 包布局(链接名 opencode,包名可定制);fixture 的 npm_package
        链接名取 Path(name).name,对 scoped 包不适用,故自建。"""
        package = self.area / 'lib/node_modules/@opencode/cli'
        (package / 'bin').mkdir(parents=True, exist_ok=True)
        exe = package / 'bin/opencode'
        if macho:
            self.macho_binary(exe)
        else:
            exe.write_text('#!/usr/bin/env node\n')
            exe.chmod(0o755)
        (package / 'package.json').write_text(json.dumps(
            {'name': name, 'version': '2.2.5', 'bin': {'opencode': 'bin/opencode'}}))
        link = self.bin_dir / 'opencode'
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to('../lib/node_modules/@opencode/cli/bin/opencode')
        return package

    def test_signed_native_binary_is_installed_without_version(self):
        self.macho_binary(self.area / '.opencode/bin/opencode')
        self.request['search_paths'] = [str(self.area / '.opencode/bin')]
        before = snapshot(self.area)
        result = self.detect(['opencode'], runner=fake_codesign())
        self.assertEqual(result['agents']['opencode']['status'], 'installed')
        evidence = result['agents']['opencode']['evidence'][0]
        self.assertEqual(evidence['type'], 'macos_native_executable')
        self.assertNotIn('version', evidence)  # 无经认证的静态版本元数据,不伪造
        self.assertEqual(snapshot(self.area), before)  # 检测零写

    def test_native_under_nameless_parent_package_json_still_recognized(self):
        # 本机复现回归:官方安装器布局 ~/.opencode/bin/opencode(原生二进制)+
        # ~/.opencode/package.json(无 name/version),npm 元数据先判会误判 unknown。
        self.macho_binary(self.area / '.opencode/bin/opencode')
        (self.area / '.opencode/package.json').write_text(json.dumps({'private': True}))
        self.request['search_paths'] = [str(self.area / '.opencode/bin')]
        result = self.detect(['opencode'], runner=fake_codesign())
        self.assertEqual(result['agents']['opencode']['status'], 'installed')

    def test_native_verification_binds_product_and_team_requirement(self):
        self.macho_binary(self.bin_dir / 'opencode')
        calls = []
        signer = fake_codesign()

        def runner(argv):
            calls.append(argv)
            return signer(argv)

        self.assertEqual(self.detect(['opencode'], runner=runner)['agents']['opencode']['status'], 'installed')
        verify = next(argv for argv in calls if '--verify' in argv)
        requirement = verify[verify.index('-R') + 1]
        self.assertIn('identifier "opencode"', requirement)
        self.assertIn('anchor apple generic', requirement)
        self.assertIn('certificate leaf[subject.OU] = "5NZ4Q7NXJ4"', requirement)

    def test_wrong_signature_is_not_trusted_by_package_name(self):
        # Mach-O 且父 package.json 包名正确,但签名核验失败:直接 failed,不回落
        # npm 门禁假装可信。
        self.scoped_opencode_package(macho=True)
        result = self.detect(['opencode'], runner=fake_codesign(verify_rc=1))
        self.assertEqual(result['agents']['opencode']['status'], 'unknown')

    def test_npm_wrapper_script_still_requires_package_identity(self):
        self.scoped_opencode_package(macho=False)
        result = self.detect(['opencode'], runner=fake_codesign())
        self.assertEqual(result['agents']['opencode']['status'], 'installed')
        self.assertEqual(result['agents']['opencode']['evidence'][0]['type'], 'file')
        # npm 包装脚本包名不符仍 unknown:不因执行器同名而放行未知脚本。
        self.scoped_opencode_package(name='@evil/wrong-opencode')
        result = self.detect(['opencode'], runner=fake_codesign())
        self.assertEqual(result['agents']['opencode']['status'], 'unknown')

    def test_name_is_not_trusted_without_signature_or_package(self):
        # 同名裸二进制(非 Mach-O)且无 package.json:来源不明,unknown。
        script = self.bin_dir / 'opencode'
        script.write_text('#!/bin/sh\necho fake\n')
        script.chmod(0o755)
        self.assertEqual(self.detect(['opencode'])['agents']['opencode']['status'], 'unknown')

    def test_hint_only_and_absent_fail_closed(self):
        (self.home / '.opencode').mkdir()
        self.assertEqual(self.detect(['opencode'])['agents']['opencode']['status'], 'unknown')
        (self.home / '.opencode').rmdir()
        self.assertEqual(self.detect(['opencode'])['agents']['opencode']['status'], 'absent')


class OpenCodeRedirectGuardTests(EnableFixture):
    def test_only_unset_or_absolute_default_values_pass(self):
        default_config = self.home / '.config'
        default_root = default_config / 'opencode'
        # 每个变量只认自己的精确默认落点;指向另一变量的默认值同样拒绝。
        allow = {'XDG_CONFIG_HOME': {'', ' \t\n', str(default_config), str(default_config) + '/'},
                 'OPENCODE_CONFIG_DIR': {'', ' \t\n', str(default_root), str(default_root) + '/'},
                 'OPENCODE_CONFIG': {'', ' \t'}}
        for variable, values in allow.items():
            for value in values:
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, {variable: value}):
                    self.assertFalse(user_entries.opencode_config_redirected(self.home))
        common_deny = {'relative/path', '~/.config', '~/.config/opencode', './.config',
                       str(self.area / 'PRIVATE'), str(self.home) + '/.config/../.configx'}
        deny = {'XDG_CONFIG_HOME': common_deny | {str(default_root)},  # 另一变量默认值同样拒绝
                'OPENCODE_CONFIG_DIR': common_deny | {str(default_config)},
                'OPENCODE_CONFIG': common_deny | {str(default_config), str(default_root)}}
        for variable, values in deny.items():
            for value in values:
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, {variable: value}):
                    self.assertTrue(user_entries.opencode_config_redirected(self.home))
        # XDG 指向 .config 也不得放过 OPENCODE_CONFIG_DIR 的私有值,反之亦然。
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(default_config),
                                     'OPENCODE_CONFIG_DIR': str(self.area / 'PRIVATE')}):
            self.assertTrue(user_entries.opencode_config_redirected(self.home))
        with patch.dict(os.environ, clear=True):
            self.assertFalse(user_entries.opencode_config_redirected(self.home))


class OpenCodeInstallTests(InstallFixture):
    def setUp(self):
        super().setUp()
        self.facts = opencode_facts(self.config, self.home)
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', return_value=self.facts).start()
        patch.dict(os.environ, {'XDG_CONFIG_HOME': '', 'OPENCODE_CONFIG_DIR': '', 'OPENCODE_CONFIG': ''}).start()

    def entry_path(self):
        return self.home / '.config/opencode/AGENTS.md'

    def test_default_full_set_connects_installed_opencode(self):
        plan = self.plan()
        self.assertIn('opencode', plan['effective_agents'])
        self.assertEqual(self.execute(plan)['status'], 'completed')
        entry = self.entry_path()
        self.assertTrue(entry.is_file())
        self.assertIn(user_entries.OPENCODE_FALLBACK_TEXT.encode(), entry.read_bytes())
        self.assertNotIn(user_entries.CODEX_FALLBACK_TEXT.encode(), entry.read_bytes())
        self.assertFalse((entry.parent / 'skills').exists())  # v1.11:不建 Skill 投影
        ledger = registry.load_registry(self.runtime.registry,
            allowed_user_paths=paths.allowed_user_paths(self.config, None, home=str(self.home)))
        self.assertIn('opencode', ledger['machine']['agents'])
        self.assertEqual(user_entries.connection_status(self.runtime, self.config, ledger, ['opencode'])
                         ['opencode']['status'], 'connected')

    def test_private_bytes_preserved_and_idempotent_zero_write(self):
        self.request['agents'] = ['opencode']
        private = b'\xef\xbb\xbfprivate\xff\r\n<!-- context-keeper:start -->\nCK\n<!-- context-keeper:end -->'
        entry = self.entry_path()
        entry.parent.mkdir(parents=True)
        entry.write_bytes(private)
        before = snapshot(self.home)
        plan = self.plan()
        self.assertEqual(before, snapshot(self.home))
        self.assertEqual(self.execute(plan)['status'], 'completed')
        self.assertTrue(entry.read_bytes().startswith(private))
        before = snapshot(self.home)
        again = user_entries.run_user_entries(dict(self.request, home=str(self.home),
                                                   platform_config=self.config, runtime_layout=self.runtime))
        self.assertEqual(again['status'], 'completed', again)
        self.assertEqual(snapshot(self.home), before)
        # 受管块被第三方改动:整单拒绝零写,不以模板覆盖。
        entry.write_bytes(entry.read_bytes().replace(b'AGENTS.md', b'BROKEN.md'))
        before = snapshot(self.home)
        result = user_entries.run_user_entries(dict(self.request, home=str(self.home),
                                                    platform_config=self.config, runtime_layout=self.runtime))
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(snapshot(self.home), before)

    def test_unknown_and_absent_are_reported_not_written(self):
        self.request['agents'] = ['opencode']
        for status in ('absent', 'unknown'):
            self.facts['agents']['opencode']['status'] = status
            before = snapshot(self.home)
            with self.assertRaises(ValueError):
                self.plan()
            self.assertEqual(snapshot(self.home), before)
            self.assertFalse(self.entry_path().exists())
        # 缺省(全量)时未安装者只报告:effective 不含 opencode,不创建入口。
        self.request['agents'] = None
        plan = self.plan()
        self.assertNotIn('opencode', plan['effective_agents'])
        self.assertIn('opencode', plan['agent_facts'])

    def test_redirect_stops_whole_install_without_echoing_private_value(self):
        self.request['agents'] = ['opencode']
        for variable in ('XDG_CONFIG_HOME', 'OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG'):
            sentinel = str(self.area / 'PRIVATE_SENTINEL')
            with patch.dict(os.environ, {variable: sentinel}):
                before = snapshot(self.home)
                with self.assertRaises(ValueError) as ctx:
                    self.plan()
                self.assertNotIn(sentinel, str(ctx.exception))
                self.assertIn('opencode_config_redirected', str(ctx.exception))
                self.assertEqual(snapshot(self.home), before)
        # 相对值与字面 ~ 同样拒绝(应用解析语义未证实,不臆断放行)。
        for value in ('relative/x', '~/.config'):
            with self.subTest(value=value), patch.dict(os.environ, {'OPENCODE_CONFIG_DIR': value}):
                before = snapshot(self.home)
                with self.assertRaises(ValueError):
                    self.plan()
                self.assertEqual(snapshot(self.home), before)
        # 明确绝对默认值放行:正常装配。
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config'),
                                     'OPENCODE_CONFIG_DIR': str(self.home / '.config/opencode')}):
            plan = self.plan()
            self.assertEqual(plan['effective_agents'], ['opencode'])
            self.assertEqual(self.execute(plan)['status'], 'completed')

    def test_migration_reader_scan_covers_opencode_path(self):
        self.execute()
        runtime = user_install._runtime(dict(home=str(self.home)))
        ledger = registry.load_registry(runtime.registry, allowed_user_paths=paths.allowed_user_paths(
            self.config, None, home=str(self.home)))
        self.assertEqual(public_layout.scan_unregistered_readers(self.config, ledger, str(self.home), runtime), [])
        # 撤销登记(模拟未登记公共读者):扫描发现 opencode 入口,整单迁移拒绝。
        entry = self.entry_path()
        data = ledger['machine']['objects']
        for oid in [oid for oid, obj in data.items() if 'opencode' in obj['agents']]:
            del data[oid]
        readers = public_layout.scan_unregistered_readers(self.config, ledger, str(self.home), runtime)
        self.assertTrue(any(r['agent'] == 'opencode' for r in readers))
        with self.assertRaises(ValueError):
            public_layout.plan_migration({'home': str(self.home), 'platform_config': self.config})


class OpenCodeOrganizeClassificationTests(unittest.TestCase):
    """Review P2 回归:OpenCode 专属句不被通用词改判公共(默认 move 会挪私文)。"""

    def test_opencode_sentences_stay_specific_even_with_common_words(self):
        from agm_core import user_rules_organize as org
        label, reason, _ = org._classify('OpenCode 每次运行测试前先确认模型。', [])
        self.assertEqual(label, '独有')
        self.assertIn('执行器', reason)
        # 混合通用词(提交/简体中文)与专属名:专属优先,不因通用词改判公共。
        label, _, _ = org._classify('OpenCode 提交信息请使用简体中文。', [])
        self.assertEqual(label, '独有')
        # 专属路径/落点形态同样独有。
        label, _, _ = org._classify('配置在 ~/.config/opencode/AGENTS.md。', [])
        self.assertEqual(label, '独有')
        # 纯通用句仍公共:分类器既有语义不变。
        label, _, _ = org._classify('提交信息请使用简体中文。', [])
        self.assertEqual(label, '公共')

    def test_organize_execution_keeps_opencode_private_sentence(self):
        from test_m408_organize import OrganizeTests
        from agm_core import user_rules_organize as org
        fixture = OrganizeTests('runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        path = Path(paths.expand_path(fixture.config['opencode']['user_entry'], home=str(fixture.home)))
        path.parent.mkdir(parents=True)
        private = 'OpenCode 偏好使用本地模型。\n'.encode()
        path.write_bytes(private + '\n提交信息请使用简体中文。\n'.encode())
        fixture.request['agents'] = ['opencode']
        plan = fixture.preview()
        specific = next(i for i in plan['items'] if 'OpenCode' in i['text'])
        self.assertEqual((specific['classification'], specific['action']), ('独有', 'keep'))
        org.execute_organize(plan, fixture.approve(plan))
        self.assertIn(private, path.read_bytes())
        self.assertNotIn(private, (fixture.memories / 'user-rules.md').read_bytes())


class OpenCodeProjectTests(EnableFixture):
    def setUp(self):
        super().setUp()
        self.request['agents'] = ['opencode']
        facts = opencode_facts(self.config, self.home)
        self.addCleanup(patch.stopall)
        patch.object(detect, 'detect_agents', return_value=facts).start()

    def test_native_project_enable_check_remove_and_disabled(self):
        private = b'\xef\xbb\xbfproject private\xff\r\n'
        entry = self.root / 'AGENTS.md'
        entry.write_bytes(private)
        self.apply('follow_ck')
        # OpenCode native:项目只落共享基座,不预建执行器专属私文。
        self.assertFalse((self.root / 'CLAUDE.md').exists())
        self.assertFalse((self.root / '.opencode').exists())
        self.assertFalse((self.root / '.config/opencode').exists())
        self.assertFalse((self.root / '.workbuddy').exists())
        self.assertTrue(entry.read_bytes().startswith(private))
        result = check.run(self.request)
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['projects'][0]['agents'], ['opencode'])
        before=entry.read_bytes()
        self.apply_tombstone();self.request.update(approval=None)
        result=enable.run(self.request)
        self.assertEqual(result['status'],'gaps',result)
        self.assertEqual(entry.read_bytes(),before)
        self.assertIn(private,entry.read_bytes())
        self.assertEqual(self.load()['projects'][str(self.root)]['memory_policy'],'disabled')

    def test_large_native_entry_does_not_inherit_codex_budget_warning(self):
        self.apply('follow_ck')
        entry = self.root / 'AGENTS.md'
        entry.write_bytes(entry.read_bytes() + b'x' * 40000)
        self.assertEqual(check._entry_warnings(['opencode'], self.config, home=str(self.home),
                                               checkout=str(self.root)), [])
        warnings = check._entry_warnings(['codex'], self.config, home=str(self.home),
                                         checkout=str(self.root))
        self.assertTrue(any('32KiB' in w for w in warnings))

    def test_project_default_remains_three_agents_not_six(self):
        # 项目命令缺省仍三家:机器安装全量默认不得改变项目实际使用入口策略。
        self.request['agents'] = None
        result = enable.run(dict(self.request))
        self.assertEqual(result['status'], 'gaps', result)  # 合成 HOME 无三家 installed
        self.assertEqual(result['installation']['requested'], ['codex', 'claude', 'workbuddy'])
