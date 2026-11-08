"""Exact synthetic native/body sharing, update, return and uninstall chains."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import memory_share as ms, paths, entries, user_rules_organize as org
from agm_core import uninstall, uninstall_recovery as recovery, detect
from test_ck_common_trigger import BODY, block
from test_m404_install import InstallFixture
from test_uninstall import approval

AGENTS = ['codex', 'claude', 'workbuddy', 'zcode', 'dsh', 'opencode']


class CKChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'; self.home.mkdir()
        self.config = paths.select_platform(paths.load_agents_table(), 'darwin')
        self.req = dict(home=str(self.home), platform_config=self.config, agents=AGENTS)
        self.native = {}
        for agent in AGENTS:
            p = Path(paths.expand_path(self.config[agent]['user_entry'], home=str(self.home)))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(('private '+agent+'\n# Different '+agent+'\n').encode()+block(agent)+b'private suffix\n')
            self.native[agent] = p
        self.original = {a:p.read_bytes() for a,p in self.native.items()}
        self.topic = self.home / '.mem-sharing/memories/user-rules.md'

    def proposal(self):
        r = ms.plan_share(self.req); self.assertEqual(r['status'], 'completed', r)
        return dict(schema_version=1, basis=r['basis'], groups=[dict(summary='完整通用触发', same_content=True,
            items=[{k:s[k] for k in ('agent','start','end')} for s in r['segments'] if s.get('kind') == 'ck_common_trigger'])])

    def share(self):
        p = ms.plan_share(dict(self.req, proposal=self.proposal(), selection='共享 1'))
        self.assertEqual(p['status'], 'approval_required', p)
        plan=p['approval_plan']
        r=ms.execute_share(plan, dict(plan, confirmed_at='2026-11-06T09:00:00Z', reference='synthetic selection'),request=self.req)
        self.assertEqual(r['status'], 'completed', r)
        return r

    def test_six_complete_body_one_public_readers_source_counts_and_return(self):
        self.share()
        self.assertEqual(self.topic.read_bytes().count(BODY), 1)
        index=self.topic.parent/'MEMORY.md'
        self.assertIn(ms.ck.READ_RULE,index.read_bytes())
        rt=ms._runtime(self.req)
        available=ms._available_migrations(rt)
        self.assertEqual(len(available),6)
        for r in available.values():
            self.assertEqual(r['scope'],['Different '+r['agent']])
            self.assertEqual(r['context'],[[1,'Different '+r['agent'],1]])
        for a,p in self.native.items():
            self.assertNotIn(BODY,p.read_bytes())
            self.assertIn(ms.ck.MARKERS[a=='workbuddy'][2].encode(),p.read_bytes())
            self.assertTrue(ms._entry_ok(a,p.read_bytes(),rt))
        raw=self.topic.read_bytes()
        items=[dict(ref=ref[0],migration=ref[1],public_span=dict(start=r['public_offset'],end=r['public_end'],text_hex=BODY.hex()),target=dict(path=r['path'],mode='in_place')) for ref,r in available.items()]
        agent_plan=dict(schema_version=1,basis={str(self.topic):entries.sha256(raw)},items=items,remove_entries=True)
        result=ms.run_return(dict(self.req,return_plan=agent_plan))
        self.assertEqual(result['status'],'approval_required',result)
        plan=result['approval_plan']
        done=ms.run_return(dict(self.req,return_plan=agent_plan,approval=dict(plan,confirmed_at='2026-11-06T09:01:00Z',reference='synthetic return')))
        self.assertEqual(done['status'],'completed',done)
        for a,p in self.native.items():self.assertIn(block(a),p.read_bytes())

    def test_view_decline_partial_overlap_source_drift_zero_write(self):
        proposal=self.proposal();before=recovery.tree(self.home)
        for selection in ('查看 1','暂不整理'):
            r=ms.plan_share(dict(self.req,proposal=proposal,selection=selection))
            self.assertIn(r['status'],('viewed','completed'),r)
            self.assertEqual(recovery.tree(self.home),before)
        proposal['groups'][0]['items'][0]['end']-=1
        self.assertEqual(ms.plan_share(dict(self.req,proposal=proposal))['status'],'failed')
        self.assertEqual(recovery.tree(self.home),before)
        proposal=self.proposal();self.native['codex'].write_bytes(self.native['codex'].read_bytes()+b'edit')
        edited=recovery.tree(self.home)
        self.assertEqual(ms.plan_share(dict(self.req,proposal=proposal))['status'],'failed')
        self.assertEqual(recovery.tree(self.home),edited)

    def test_upstream_writeback_reuses_one_copy_and_one_return_per_host(self):
        self.share();before=self.topic.read_bytes()
        for a,p in self.native.items():
            raw=p.read_bytes();first,last,title=ms.ck.MARKERS[a=='workbuddy']
            raw=raw.replace(first+b'\n'+title.encode()+b'\n\n'+last,block(a).rstrip(b'\n'))
            p.write_bytes(raw)
        self.share()
        self.assertEqual(self.topic.read_bytes(),before)
        # A third upstream writeback must also reuse the original producer.
        for a,p in self.native.items():
            first,last,title=ms.ck.MARKERS[a=='workbuddy']
            p.write_bytes(p.read_bytes().replace(first+b'\n'+title.encode()+b'\n\n'+last,block(a).rstrip(b'\n')))
        self.share()
        self.assertEqual(self.topic.read_bytes(),before)
        rt=ms._runtime(self.req);records=ms._available_migrations(rt);consumed=ms._consumed_index(rt)
        self.assertEqual(len(records),18);self.assertEqual(len(consumed),12)
        state={str(self.topic):dict(kind='file',hex=before.hex())}
        from agm_core import uninstall_memory
        restored,_=uninstall_memory.source_returns(rt,state,{str(p) for p in self.native.values()})
        for p in self.native.values():self.assertEqual(restored[str(p)].count(BODY),1)

    def test_public_edit_blocks_reshare_without_writes(self):
        self.share();self.topic.write_bytes(self.topic.read_bytes().replace(BODY,BODY.replace(b'SKILL',b'OTHER')))
        for a,p in self.native.items():p.write_bytes(self.original[a])
        # Restore a full known block without relying on real upstream installation.
        self.native['codex'].write_bytes(self.original['codex'])
        before=recovery.tree(self.home)
        r=ms.plan_share(dict(self.req,proposal=self.proposal()))
        self.assertEqual(r['status'],'failed',r);self.assertEqual(recovery.tree(self.home),before)

    def test_installed_organize_uninstall_standalone_recover(self):
        f=InstallFixture();f.setUp();self.addCleanup(f.doCleanups)
        real=detect.detect_agents
        def installed(*args,**kw):
            r=real(*args,**kw)
            for item in r['agents'].values():item.update(status='installed',summary='synthetic')
            return r
        native={}
        for a in AGENTS:
            p=Path(paths.expand_path(f.config[a]['user_entry'],home=str(f.home)))
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('private prefix\n# '+a+' 专属\n## native detail\n').encode()+block(a)+b'private suffix\n');native[a]=p
        with patch.object(detect,'detect_agents',side_effect=installed):
            self.assertEqual(f.execute()['status'],'completed')
            # Compare the final return with the same installation's pre-share
            # uninstall layout (including its existing separator bytes).
            baseline = uninstall.preview(home=f.home, backup_dir=f.area/'pre-share-exit')
            native_expected = {a: bytes.fromhex(next(c['after']['hex'] for c in baseline['changes']
                               if c['path'] == str(p))) for a, p in native.items()}
            req=dict(f.request,agents=AGENTS)
            result=org.plan_organize(req);self.assertEqual(result['status'],'approval_required',result)
            plan=result['approval_plan']
            selected=next(g['number'] for g in plan['groups'] if any(i.get('kind') == ms.ck.KIND for i in g['sources']))
            excluded=[g['number'] for g in plan['groups'] if g['number'] != selected]
            selection='共享 '+str(selected)+('，不共享 '+','.join(map(str,excluded)) if excluded else '')
            result=org.plan_organize(dict(req,selection=selection));plan=result['approval_plan']
            self.assertEqual(len(plan['operation_metadata']['share_user_memory']['migrations']),6)
            done=org.execute_organize(plan,dict(plan,confirmed_at='2026-11-06T09:00:00Z',reference='synthetic selection'),request=dict(req,selection=selection))
            self.assertEqual(done['status'],'completed',done)
            self.assertEqual((f.runtime.root/'memories/user-rules.md').read_bytes().count(BODY),1)
            public = (f.runtime.root/'memories/user-rules.md').read_bytes()
            self.assertIn('## Context Keeper 通用触发\n\n'.encode() + BODY, public)
            self.assertNotIn('claude 专属'.encode(), public)
            migrated = ms._available_migrations(f.runtime).values()
            claude = next(item for item in migrated if item['agent'] == 'claude')
            self.assertEqual(claude['context'], [[1, 'claude 专属', 1], [2, 'native detail', 1]])
            for hosts in (AGENTS, ['codex']):
                for a in hosts:
                    first, last, title = ms.ck.MARKERS[a == 'workbuddy']
                    p = native[a]
                    p.write_bytes(p.read_bytes().replace(first+b'\n'+title.encode()+b'\n\n'+last,
                                                       block(a).rstrip(b'\n')))
                if 'claude' in hosts:
                    p = native['claude']; clean = p.read_bytes()
                    p.write_bytes(clean + b'unapproved private edit\n')
                    protected = recovery.tree(f.home)
                    rejected = org.plan_organize(req)
                    self.assertEqual(rejected['status'], 'failed')
                    self.assertEqual(recovery.tree(f.home), protected)
                    p.write_bytes(clean)
                preview = org.plan_organize(req)
                self.assertEqual(preview['status'], 'approval_required', preview)
                selected = [g['number'] for g in preview['approval_plan']['groups']
                            if any(i.get('kind') == ms.ck.KIND for i in g['sources'])]
                excluded = [g['number'] for g in preview['approval_plan']['groups'] if g['number'] not in selected]
                selection = '共享 '+','.join(map(str,selected))+('，不共享 '+','.join(map(str,excluded)) if excluded else '')
                plan = org.plan_organize(dict(req,selection=selection))['approval_plan']
                done = org.execute_organize(plan,dict(plan,confirmed_at='2026-11-06T09:00:00Z',reference='synthetic update'),request=dict(req,selection=selection))
                self.assertEqual(done['status'], 'completed', done)
                self.assertEqual((f.runtime.root/'memories/user-rules.md').read_bytes().count(BODY),1)
            before=recovery.tree(f.home)
            backup=f.area/'independent-ck-recovery'
            up=uninstall.preview(home=f.home,backup_dir=backup)
            done=uninstall.execute(approval(recovery.summary(up)),home=f.home,backup_dir=backup)
            self.assertEqual(done['status'],'completed')
            self.assertFalse(f.runtime.root.exists())
            for a,p in native.items():
                self.assertEqual(p.read_bytes().count(BODY),1)
                self.assertIn(block(a),p.read_bytes());self.assertIn(b'private prefix',p.read_bytes());self.assertIn(b'private suffix',p.read_bytes())
                self.assertNotIn('## Context Keeper 通用触发'.encode(), p.read_bytes())
                self.assertEqual(p.read_bytes(), native_expected[a], a)
            preview=recovery.recover(backup/'manifest.json')
            approved=f.area/'recover-approval.json';approved.write_text(json.dumps(approval(preview['plan'])))
            run=subprocess.run([sys.executable,str(backup/'recover.py'),'--manifest',str(backup/'manifest.json'),'--approval-file',str(approved)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(recovery.tree(f.home),before)

    def test_superseded_reference_tampering_cannot_consume_other_path_or_ordinary(self):
        first=self.share()
        self.native['codex'].write_bytes(self.original['codex'])
        second=self.share()
        path=Path(second['manifest']);current=json.loads(path.read_text())
        meta=current['operation_metadata']['share_user_memory']
        self.assertEqual(len(meta['superseded_ck_sources']),1)
        original=json.loads(Path(first['manifest']).read_text())
        old=original['operation_metadata']['share_user_memory']['migrations']
        # Another path in the same original producer is not replaced by this one-host update.
        other=next(n for n,r in enumerate(old) if r['agent'] != 'codex')
        import copy
        for change in ('other_path','ordinary','other_span'):
            bad=copy.deepcopy(current)
            oldbad=copy.deepcopy(original)
            ref=bad['operation_metadata']['share_user_memory']['superseded_ck_sources'][0]
            if change=='other_path':ref['migration']=other
            elif change=='ordinary':oldbad['operation_metadata']['share_user_memory']['migrations'][ref['migration']].pop('kind')
            else:oldbad['operation_metadata']['share_user_memory']['migrations'][ref['migration']]['public_end']+=1
            path.write_text(json.dumps(bad));Path(first['manifest']).write_text(json.dumps(oldbad))
            before=recovery.tree(self.home)
            with self.assertRaises(ms.ShareError):ms._consumed_index(ms._runtime(self.req))
            self.assertEqual(recovery.tree(self.home),before)
        path.write_text(json.dumps(current));Path(first['manifest']).write_text(json.dumps(original))

    def test_legacy_36_plain_sources_remain_outstanding_and_cli_preview(self):
        rules=[('- synthetic common rule '+str(n)+'\n').encode() for n in range(6)]
        for a,p in self.native.items():p.write_bytes(b''.join(rules)+self.original[a])
        preview=ms.plan_share(self.req)
        groups=[]
        for rule in rules:
            groups.append(dict(summary=rule.decode().strip(),same_content=True,
                items=[{k:i[k] for k in ('agent','start','end')} for i in preview['segments'] if i['text']==rule.decode()]))
        proposal=dict(schema_version=1,basis=preview['basis'],groups=groups)
        result=ms.plan_share(dict(self.req,proposal=proposal));plan=result['approval_plan']
        done=ms.execute_share(plan,dict(plan,confirmed_at='2026-11-06T09:00:00Z',reference='synthetic ordinary selection'),request=self.req)
        self.assertEqual(done['status'],'completed',done)
        from agm_core.user_entries import public_memory_contract_text
        index=self.topic.parent/'MEMORY.md'
        index.write_bytes(('# 公共记忆\n\n'+public_memory_contract_text()).encode())
        self.share()
        rt=ms._runtime(self.req);records=ms._available_migrations(rt)
        self.assertEqual(len(records),42);self.assertEqual(ms._consumed_index(rt),set())
        from agm_core import uninstall_memory
        restored,_=uninstall_memory.source_returns(rt,{str(self.topic):dict(kind='file',hex=self.topic.read_bytes().hex())},{str(p) for p in self.native.values()})
        for a,p in self.native.items():
            self.assertIn(block(a),restored[str(p)])
            for rule in rules:self.assertEqual(restored[str(p)].count(rule),1)
        cmd=[sys.executable,str(Path(__file__).resolve().parents[2]/'scripts/memory_share.py'),'share-user-memory','--home',str(self.home)]
        for agent in AGENTS:cmd += ['--agent',agent]
        before=recovery.tree(self.home)
        cli=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(cli.returncode,0,cli.stderr+cli.stdout)
        self.assertEqual(json.loads(cli.stdout)['status'],'completed')
        self.assertEqual(recovery.tree(self.home),before)

    def test_split_ck_proposal_emits_one_public_body_and_preserves_all_sources(self):
        proposal=self.proposal();items=proposal['groups'][0]['items']
        proposal['groups']=[dict(summary='CK '+str(n),same_content=True,items=[item]) for n,item in enumerate(items)]
        result=ms.plan_share(dict(self.req,proposal=proposal,selection='共享 1,2,3,4,5,6'))
        self.assertEqual(result['status'],'approval_required',result)
        plan=result['approval_plan']
        public=next(bytes.fromhex(c['after_hex']) for c in plan['changes'] if c['path']==str(self.topic))
        self.assertEqual(public.count(BODY),1)
        self.assertEqual(len(plan['operation_metadata']['share_user_memory']['migrations']),6)

    def test_fenced_and_outer_private_protocol_replays_are_zero_write(self):
        for wrapper in ('fenced','private'):
            for a,p in self.native.items():
                inner=block(a)
                raw=(b'```md\n'+inner+b'```\n' if wrapper=='fenced' else
                     b'<!-- mem-sharing:private:start -->\n'+inner+b'<!-- mem-sharing:private:end -->\n')
                p.write_bytes(raw)
            before=recovery.tree(self.home);preview=ms.plan_share(self.req)
            self.assertFalse(any(i.get('kind')==ms.ck.KIND for i in preview['segments']))
            self.assertEqual(recovery.tree(self.home),before)


    def test_cycle_and_unproven_replacement_reject_before_source_returns(self):
        import copy
        from agm_core import uninstall_memory
        first = self.share()
        self.native['codex'].write_bytes(self.original['codex'])
        second = self.share()
        oldpath, newpath = Path(first['manifest']), Path(second['manifest'])
        oldraw, newraw = oldpath.read_bytes(), newpath.read_bytes()
        old, new = json.loads(oldraw), json.loads(newraw)
        rt = ms._runtime(self.req)
        for attack in ('cycle', 'no_entries', 'no_delete', 'bad_before', 'old_changed', 'no_public'):
            with self.subTest(attack=attack):
                a, b = copy.deepcopy(old), copy.deepcopy(new)
                am = a['operation_metadata']['share_user_memory']
                bm = b['operation_metadata']['share_user_memory']
                if attack == 'cycle':
                    am['superseded_ck_sources'] = [dict(manifest=newpath.parent.name, migration=0,
                                                      manifest_sha256=entries.sha256(newraw))]
                elif attack == 'no_entries': b['entries'] = []
                elif attack == 'no_delete':
                    row = next(r for r in b['entries'] if r['path'] == str(self.native['codex']))
                    row['after'] = dict(row['before'])
                elif attack == 'bad_before':
                    row = next(r for r in b['entries'] if r['path'] == str(self.native['codex']))
                    row['before']['fingerprint'] = '0'*64
                elif attack == 'old_changed': am['migrations'][0]['summary'] = 'changed after replacement'
                else:
                    a['entries'] = [r for r in a['entries'] if r['path'] != str(self.topic)]
                    altered = json.dumps(a).encode()
                    bm['superseded_ck_sources'][0]['manifest_sha256'] = entries.sha256(altered)
                oldpath.write_bytes(json.dumps(a).encode() if attack in ('cycle','old_changed','no_public') else oldraw)
                newpath.write_bytes(json.dumps(b).encode())
                before = recovery.tree(self.home)
                with self.assertRaises(ms.ShareError):
                    uninstall_memory.source_returns(rt,
                        {str(self.topic): dict(kind='file',hex=self.topic.read_bytes().hex())},
                        {str(p) for p in self.native.values()})
                self.assertEqual(recovery.tree(self.home), before)
        oldpath.write_bytes(oldraw); newpath.write_bytes(newraw)
        restored, _ = uninstall_memory.source_returns(rt,
            {str(self.topic): dict(kind='file',hex=self.topic.read_bytes().hex())},
            {str(p) for p in self.native.values()})
        for path in self.native.values(): self.assertEqual(restored[str(path)].count(BODY), 1)


    def test_multi_round_single_then_final_return(self):
        self.share()
        for a,p in self.native.items():
            first,last,title=ms.ck.MARKERS[a=='workbuddy']
            p.write_bytes(p.read_bytes().replace(first+b'\n'+title.encode()+b'\n\n'+last,block(a).rstrip(b'\n')))
        self.share()
        rt=ms._runtime(self.req)
        for hosts in (['codex'], [a for a in AGENTS if a != 'codex']):
            records=ms._available_migrations(rt);consumed=ms._consumed_index(rt)
            items=[dict(ref=ref[0],migration=ref[1],
                        public_span=dict(start=r['public_offset'],end=r['public_end'],text_hex=BODY.hex()),
                        target=dict(path=r['path'],mode='in_place'))
                   for ref,r in records.items() if ref not in consumed and r['agent'] in hosts]
            proposal=dict(schema_version=1,basis={str(self.topic):entries.sha256(self.topic.read_bytes())},
                          items=items,remove_entries=len(hosts)>1)
            preview=ms.run_return(dict(self.req,return_plan=proposal))
            self.assertEqual(preview['status'],'approval_required',preview)
            plan=preview['approval_plan']
            done=ms.run_return(dict(self.req,return_plan=proposal,approval=dict(plan,confirmed_at='2026-11-06T09:00:00Z',reference='synthetic return')))
            self.assertEqual(done['status'],'completed',done)
            self.assertEqual(self.topic.read_bytes().count(BODY),1 if len(hosts)==1 else 0)
        for a,p in self.native.items():
            self.assertIn(self.original[a],p.read_bytes())
            self.assertEqual(p.read_bytes().count(BODY),1)
