"""New ordinary-file control. No Cloud Files calls or attribute repair."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

PLAN = None


def need(value, message):
    if not value:
        raise RuntimeError(message)


def compare_root(before, after):
    return dict(tree_empty=after['entries'] == [],
                identity_equal=before['identity'] == after['identity'],
                security_equal=before['security_sha256'] == after['security_sha256'],
                attrs_equal=before['attributes'] == after['attributes'],
                tag_equal=before['reparse_tag'] == after['reparse_tag'])


def exercise(runtime, save):
    result = dict(started=time.time(), status='needs_inspection',
                  cf_calls_attempted=False, attribute_repair_attempted=False,
                  production_write_authorized=False, race_free=False)
    try:
        result['root_created'] = runtime.snapshot()
        save('root-created', result['root_created'])
        save('create-intent', runtime.describe())
        result['child_create_attempted'] = True
        runtime.create_child()
        result['after_create'] = runtime.snapshot()
        save('after-child-create', result['after_create'])
        save('delete-intent', runtime.describe())
        runtime.remove_child()
        result['after_delete'] = runtime.snapshot()
        save('after-child-delete', result['after_delete'])
        result['dimensions'] = compare_root(result['root_created'], result['after_delete'])
        result['status'] = 'observed'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
        # No retries or guessed cleanup: retain this new control fixture on failure.
    result['finished'] = time.time()
    save('result', result)
    return result


def main():
    need(PLAN is not None and PLAN.get('operation_id'), 'Unbound plan')
    need(sys.flags.optimize == 0 and sys.flags.isolated and sys.flags.no_site
         and sys.dont_write_bytecode, 'Use -I -S -B')
    root = Path(PLAN['root'])
    os.environ.update(HOME=str(root/'synthetic-home'), USERPROFILE=str(root/'synthetic-home'),
                      TEMP=str(root/'tmp'), TMP=str(root/'tmp'))
    for path, digest in PLAN['sources'].items():
        need(hashlib.sha256((root/'code'/path).read_bytes()).hexdigest() == digest, 'Source drift')
    sys.path.insert(0, str(root/'code/scripts'))
    from agm_core import windows_native as w
    import ctypes as C
    api = w._API()
    api.k.GetCurrentProcess.argtypes = []; api.k.GetCurrentProcess.restype = w.HANDLE
    api.a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, C.POINTER(w.HANDLE)]; api.a.OpenProcessToken.restype = w.BOOL
    api.a.GetTokenInformation.argtypes = [w.HANDLE,C.c_int32,C.c_void_p,w.DWORD,C.POINTER(w.DWORD)]; api.a.GetTokenInformation.restype = w.BOOL
    token = w.HANDLE()
    need(api.a.OpenProcessToken(api.k.GetCurrentProcess(),8,C.byref(token)), 'Token query failed')
    try:
        elevated,returned=w.DWORD(),w.DWORD()
        need(api.a.GetTokenInformation(token,20,C.byref(elevated),4,C.byref(returned)) and returned.value==4 and not elevated.value, 'Ordinary token required')
    finally:
        api.k.CloseHandle(token)
    op = str(uuid.UUID(PLAN['operation_id']))
    fixture = root/'synthetic-home'/('cf-ordinary-control-'+op)
    child = fixture/('ordinary-'+op+'.bin')
    raw = ('memSharing ordinary control '+op+'\r\n').encode('ascii')
    evidence = root/'evidence'/('cf-ordinary-control-'+op)
    evidence.mkdir()

    def save(name, value):
        with (evidence/(name+'.json')).open('x', encoding='utf8') as f:
            json.dump(dict(value, operation_id=op, fixture=str(fixture)), f, indent=2)
            f.flush(); os.fsync(f.fileno())

    def snap(path):
        with w.inspect_path(str(path), security=True, candidate_metadata=True) as value:
            need(value['number_of_links'] == 1 and not value['case_sensitive_directory'], 'Unsupported node metadata')
            return dict(identity=dict(volume_id=value['volume_id'], file_id=value['file_id']),
                        attributes=value['attributes'], reparse_tag=value['reparse_tag'],
                        security_sha256=value['security']['sha256'])

    with w.inspect_path(PLAN['case_path'], security=True, candidate_metadata=True) as anchor:
        need(w.same_node(anchor, PLAN['identity']) and anchor['security']['sha256'] == PLAN['security_sha256']
             and not anchor['case_sensitive_directory'], 'Anchor drift')
        save('setup-intent', dict(child=str(child), child_sha256=hashlib.sha256(raw).hexdigest(),
                                  cf_calls_attempted=False, token_elevated=False,
                                  environment={x:os.environ.get(x) for x in ('HOME','USERPROFILE','TEMP','TMP','SystemRoot')}))
        fixture.mkdir()
        initial = snap(fixture)

        class Runtime:
            owned_child = None

            def describe(self):
                return dict(child=str(child), expected_sha256=hashlib.sha256(raw).hexdigest(),
                            owned_child=self.owned_child, deletion_scope='exact own ID/hash only')

            def snapshot(self):
                current = snap(fixture)
                need(current['identity'] == initial['identity'] and current['security_sha256'] == initial['security_sha256'], 'Control root identity/security drift')
                entries = sorted(item.name for item in fixture.iterdir())
                need(entries in ([], [child.name]), 'Foreign entry; preserve')
                current['entries'] = entries
                if entries:
                    need(self.owned_child is not None, 'Unattributed file; preserve')
                    item = snap(child)
                    need(item['identity'] == self.owned_child['identity'] and child.read_bytes() == raw,
                         'Control child drift; preserve')
                    current['child'] = dict(item, sha256=hashlib.sha256(raw).hexdigest())
                return current

            def create_child(self):
                self.snapshot()
                need(not list(fixture.iterdir()), 'Nonempty before own creation')
                with child.open('xb') as f:
                    f.write(raw); f.flush(); os.fsync(f.fileno())
                self.owned_child = snap(child)
                need(child.read_bytes() == raw, 'Creation readback differs')

            def remove_child(self):
                self.snapshot()
                need(self.owned_child is not None and snap(child)['identity'] == self.owned_child['identity']
                     and child.read_bytes() == raw, 'Deletion identity/hash differs')
                child.unlink()

        result = exercise(Runtime(), save)
    save('completion', dict(result, held_anchor_exit_revalidated=True, fixture_preserved=True))
    print(json.dumps(dict(status=result['status'], dimensions=result.get('dimensions'), evidence=str(evidence))))
    return 0 if result['status'] == 'observed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
