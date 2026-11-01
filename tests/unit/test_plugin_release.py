"""Synthetic Git S/R and HOME only; no host, network or installed daemon."""
import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'scripts'))
from agm_core import legacy_import as legacy, paths, plugin_release as release, user_install, upgrade, versions

spec = importlib.util.spec_from_file_location('plugin_install_cli', REPO/'scripts/install.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)


def approved(plan):
    return dict(plan, confirmed_at='2026-10-31T08:00:00Z', reference='synthetic fixture approval')


class ReleaseFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve(); self.repo = self.area/'source'; self.repo.mkdir()
        self.home = self.area/'home'; self.home.mkdir()
        self.git('init', '-q'); self.git('config','user.name','Fixture'); self.git('config','user.email','fixture@example.invalid')
        for rel in release.SHIPPED_DOCS:
            target = self.repo/rel; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO/rel, target); target.chmod(0o644)
        for p in (REPO/'scripts').rglob('*'):
            rel = str(p.relative_to(REPO))
            if p.is_file() and release.managed_source(rel) and '__pycache__' not in p.parts and p.suffix != '.pyc':
                target = self.repo/rel; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target); target.chmod(0o644)
        self.s = self.commit('synthetic source S')
        self.built = self.area/'generated'
        self.generated = release.generate(self.repo, self.s, '0.9.0', self.built)
        self.manifest = self.generated['manifest']
        self.install_generated()
        self.r = self.commit('synthetic generated R')

    def git(self, *args):
        return subprocess.run(['git','-C',str(self.repo),*args],capture_output=True,check=True,
            env=dict(os.environ,GIT_CONFIG_NOSYSTEM='1')).stdout.decode().strip()

    def commit(self, message):
        self.git('add','.'); self.git('commit','-qm',message); return self.git('rev-parse','HEAD')

    def install_generated(self):
        for p in self.built.rglob('*'):
            if p.is_file():
                target = self.repo/p.relative_to(self.built); target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)

    def delivery(self):
        return release.checkout_delivery(self.repo, self.r, '0.9.0')

    def plugin(self):
        return {'kind':'plugin-package','payload':str(self.repo/release.PAYLOAD),
                'manifest_sha256':self.generated['manifest_sha256']}

    def request(self, source, op='fixture-release-install'):
        return {'home':str(self.home),'platform_config':paths.select_platform(paths.load_agents_table(),'darwin'),
                'source':source,'agents':[], 'search_paths':[], 'app_directories':[], 'operation_id':op}

    def export(self, delivery=None):
        plan = release.plan_export(delivery or self.delivery(), self.home, 'fixture-export')
        return release.execute_export(plan, approved(plan))

    def invoke(self, *args):
        out = io.StringIO()
        with patch.dict(os.environ, HOME=str(self.home)), redirect_stdout(out):
            code = cli.main(list(args))
        return code, json.loads(out.getvalue())

    def approval_file(self, plan):
        path = self.area/'approval.json'; path.write_bytes(legacy.encoded(approved(plan))); return str(path)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.lstat().st_mode, p.lstat().st_mtime_ns,
            p.read_bytes() if p.is_file() else None) for p in [self.home,*self.home.rglob('*')]}


class ReleaseTests(ReleaseFixture):
    def test_deterministic_generation_s_r_and_only_paseo(self):
        self.git('checkout','--detach',self.s)
        other = self.area/'generated-again'
        again = release.generate(self.repo, self.s, '0.9.0', other)
        self.assertEqual(again, self.generated)
        expected = {str(p.relative_to(self.built)):(p.read_bytes(),p.stat().st_mode & 0o777) for p in self.built.rglob('*') if p.is_file()}
        actual = {str(p.relative_to(other)):(p.read_bytes(),p.stat().st_mode & 0o777) for p in other.rglob('*') if p.is_file()}
        self.assertEqual(expected, actual); self.assertFalse((other/'plugins/orca').exists())
        self.assertNotIn(self.r, (other/release.ROOT_MANIFEST).read_text())
        self.git('checkout','--detach',self.r)
        self.assertEqual(self.delivery()['commit'], self.r)

    def test_root_plugin_source_identity_inventory_marker_and_same_version(self):
        root_source = self.export()['source']
        root_plan = release.plan_export(self.delivery(), self.home, 'root-reuse')
        plugin_plan = release.plan_export(self.plugin(), self.home, 'plugin-reuse')
        self.assertTrue(root_plan['reused']); self.assertTrue(plugin_plan['reused'])
        self.assertEqual(release.export_result(plugin_plan)['source'], root_source)
        request = self.request(root_source)
        source, files = user_install._source(request)
        runtime = user_install._runtime(request)
        expected = versions.descriptor(runtime, source, files)
        self.assertEqual(expected['release']['source']['commit'], self.s)
        plan = user_install.plan_install(request)
        user_install.execute_install(plan, approved(plan), request=request)
        plugin_request = self.request(release.export_result(plugin_plan)['source'], 'fixture-plugin-reuse')
        same = upgrade.plan_upgrade(plugin_request)
        self.assertTrue(same['noop']); self.assertEqual(same['target_inventory'], expected)
        before = self.snapshot()
        self.assertTrue(upgrade.execute_upgrade(same, request=plugin_request)['noop'])
        self.assertEqual(before, self.snapshot())
        marker = json.loads((runtime.code/'.agm-code-manifest.json').read_bytes())
        self.assertEqual(legacy.encoded(marker).hex(), expected['marker_hex'])
        versions.verify(runtime, expected)

    def test_plain_source_s_install_reuses_release_r_without_replacement(self):
        self.git('checkout','--detach',self.s)
        source = cli.checkout_source(str(self.repo), self.s, '0.9.0')
        request = self.request(source)
        plan = user_install.plan_install(request)
        user_install.execute_install(plan, approved(plan), request=request)
        self.git('checkout','--detach',self.r)
        exported = self.export()['source']
        same = upgrade.plan_upgrade(self.request(exported,'fixture-s-to-r'))
        self.assertTrue(same['noop'])
        self.assertEqual(same['before_inventory'],same['target_inventory'])

    def test_export_preview_zero_write_and_exact_approval(self):
        before = self.snapshot()
        plan = release.plan_export(self.plugin(), self.home, 'fixture-export')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(plan['source_trust'], 'caller-trusted-package-required')
        wrong = approved(plan); wrong['destination'] += '-other'
        with self.assertRaises(ValueError): release.execute_export(plan, wrong)
        self.assertEqual(before, self.snapshot())
        done = release.execute_export(plan, approved(plan)); self.assertEqual(done['status'], 'acquired')
        self.assertFalse(done['installation_complete'])

    def test_dirty_checkout_pin_and_r_source_changes_are_rejected(self):
        (self.repo/'untracked').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'Dirty'): self.delivery()
        (self.repo/'untracked').unlink()
        with self.assertRaisesRegex(ValueError, 'pinned'): release.checkout_delivery(self.repo, self.s)
        (self.repo/'README.md').write_text('modified S bytes in R')
        self.r = self.commit('bad R')
        with self.assertRaisesRegex(ValueError, 'S/R'): self.delivery()

    def test_hidden_git_worktree_change_is_rejected(self):
        self.git('update-index','--assume-unchanged','README.md')
        (self.repo/'README.md').write_text('hidden from status')
        with self.assertRaisesRegex(ValueError, 'differs from S/R'): self.delivery()

    def test_hidden_release_descriptor_change_is_rejected(self):
        for name in (release.ROOT_MANIFEST, release.PAYLOAD+'/release.json'):
            self.git('update-index','--assume-unchanged',name)
        forged = copy.deepcopy(self.manifest); forged['source']['version'] = '9.9.9'
        for name in (release.ROOT_MANIFEST, release.PAYLOAD+'/release.json'):
            (self.repo/name).write_bytes(legacy.encoded(forged))
        with self.assertRaisesRegex(ValueError, 'descriptor differs from R'): self.delivery()

    def test_manifest_digest_mode_extra_file_and_symlink_tampering(self):
        original = self.repo/release.PAYLOAD
        copied = self.area/'standalone-payload'; shutil.copytree(original, copied)
        delivery = dict(self.plugin(), payload=str(copied))
        target = copied/'core/README.md'; raw = target.read_bytes()
        for mutate, restore in (
            (lambda: target.write_bytes(b'tampered'), lambda: target.write_bytes(raw)),
            (lambda: target.chmod(0o755), lambda: target.chmod(0o644)),
            (lambda: (copied/'core/extra').write_bytes(b'x'), lambda: (copied/'core/extra').unlink()),
            (lambda: (copied/'core/link').symlink_to(target), lambda: (copied/'core/link').unlink()),
        ):
            mutate()
            with self.assertRaises(ValueError): release.plan_export(delivery, self.home, 'fixture-export')
            restore()
        forged = dict(delivery, manifest_sha256='0'*64)
        with self.assertRaisesRegex(ValueError, 'package-bound'): release.plan_export(forged, self.home, 'fixture-export')
        path = copied/'release.json'; path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError): release.plan_export(delivery, self.home, 'fixture-export')

    def test_durable_export_survives_plugin_removal_and_install_recovery(self):
        source = self.export(self.plugin())['source']
        request = self.request(source)
        plan = user_install.plan_install(request)
        def interrupt(stage, path):
            if stage == 'after_output':
                raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError): user_install.execute_install(plan, approved(plan), request=request, hook=interrupt)
        shutil.rmtree(self.repo/'plugins')
        recovery = user_install.plan_recovery(plan['journal'], action='continue')
        result = user_install.recover_install(recovery, approved(recovery), request=request)
        self.assertEqual(result['status'], 'completed')

    def test_same_version_other_content_and_missing_conversion_remain_blocked(self):
        source = self.export()['source']; request = self.request(source)
        plan = user_install.plan_install(request); user_install.execute_install(plan, approved(plan), request=request)
        other = self.area/'changed-core'; shutil.copytree(Path(source['root']), other)
        (other/'README.md').write_bytes(b'changed bytes')
        candidate = dict(source, root=str(other), files=dict(source['files']))
        candidate['files']['README.md'] = legacy.digest(b'changed bytes')
        changed = self.request(candidate, 'fixture-changed')
        self.assertEqual(user_install.inspect_machine(changed)['channel'], 'stop')
        with self.assertRaises(ValueError): upgrade.plan_upgrade(changed)
        candidate['version'] = '0.9.1'
        with self.assertRaises(ValueError): upgrade.plan_upgrade(changed)
        old = json.loads(user_install._runtime(request).registry.read_bytes())
        after_source, files = user_install._source(changed)
        target = versions.descriptor(user_install._runtime(changed), after_source, files)
        conversion = {'before':{'schema_version':3,'product_structure_version':1,'product_code_version':'0.9.0','source':old['product']['source']},
                      'after':dict(target['release']['versions'], source=target['release']['source']), 'direction':'upgrade','entries':'preserve'}
        changed['conversions'] = [conversion]
        next_plan = upgrade.plan_upgrade(changed)
        self.assertEqual(next_plan['conversion'], conversion)
        self.assertEqual(upgrade.execute_upgrade(next_plan, approved(next_plan), request=changed)['status'], 'completed')

    def test_cli_root_and_package_prepare_then_original_machine_plan(self):
        before = self.snapshot()
        code, report = self.invoke('--source',str(self.repo),'--commit',self.r,'--version','0.9.0')
        self.assertEqual(code,5,report); self.assertEqual(report['approval_plan']['command'],'prepare-release-source')
        self.assertEqual(before,self.snapshot())
        code, done = self.invoke('--approval-file',self.approval_file(report['approval_plan']))
        self.assertEqual(code,0,done); self.assertEqual(done['source']['commit'],self.s)
        request_file = self.area/'delivery.json'; request_file.write_bytes(legacy.encoded(self.plugin()))
        inputs = self.area/'inputs.json'; inputs.write_text(json.dumps({'search_paths':[],'app_directories':[]}))
        code, report = self.invoke('--release-request',str(request_file),'--request-file',str(inputs))
        self.assertEqual(code,5,report); self.assertEqual(report['approval_plan']['command'],'install-machine-cli')
        self.assertEqual(report['source']['root'],done['source']['root'])
        self.assertEqual(report['source']['commit'],self.s)

    def test_export_symlink_destination_drift_and_asset_lock_rejected(self):
        plan = release.plan_export(self.plugin(), self.home, 'fixture-export')
        lock = self.home/'.mem-sharing-source.lock'; lock.mkdir()
        with self.assertRaises(ValueError): release.execute_export(plan,approved(plan))
        lock.rmdir()
        target = self.home/'.local'; target.symlink_to(self.area, target_is_directory=True)
        with self.assertRaises(ValueError): release.execute_export(plan,approved(plan))
        target.unlink()
        (self.repo/release.PAYLOAD/'core/README.md').write_bytes(b'late drift')
        with self.assertRaises(ValueError): release.execute_export(plan,approved(plan))


if __name__ == '__main__':
    unittest.main()
