"""One ordinary-logon DOS mapping, exact removal only; never product admission."""
import ctypes as C
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


def exercise(runtime, save):
    """Keep mutation/cleanup ordering testable without Windows."""
    result = dict(status='failed', started=time.time(), checks=[], created=False, define_attempted=False,
                  scope='current-token Local DOS logon namespace; not process-private',
                  production_write_authorized=False, race_free=False)
    letter = target = None
    try:
        result['preimage'] = runtime.preimage()
        letter, target = runtime.select(result['preimage'])
        result.update(letter=letter, target=target)
        save('intent', result)
        runtime.recheck(letter)
        # Durable possible-change intent precedes entering the external API.
        save('define-intent', dict(result, define_attempted=True,
                                  recovery='query exact letter and target; never pop/delete foreign definitions'))
        result['define_attempted'] = True
        runtime.define(letter, target)
        result['created'] = True
        result['after_create'] = runtime.query(letter)
        need(result['after_create'] == [target], 'Mapping changed or extra definitions; stop')
        result['checks'] = runtime.verify(letter)
        result['status'] = 'passed'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc),
                               winerror=getattr(exc, 'winerror', None))
    finally:
        if result['define_attempted']:
            try:
                current = runtime.query(letter)
                result['before_cleanup'] = current
                # Remove at most one exact definition, never pop a stack/other target.
                if current == [] and not result['created']:
                    result['definition_observed'] = False
                else:
                    need(current.count(target) == 1, 'Own definition missing/duplicated; preserve')
                    result['definition_observed'] = True
                    runtime.remove_exact(letter, target)
                result['after_cleanup'] = runtime.query(letter)
                need(target not in result['after_cleanup'], 'Own definition remains')
                need(result['after_cleanup'] == [], 'Foreign mapping remains; preserve')
                runtime.verify_restored(result['preimage'])
                result['cleanup_complete'] = True
            except BaseException as exc:
                result.update(status='needs_inspection', cleanup_complete=False,
                              cleanup_error=dict(type=type(exc).__name__, message=str(exc)))
        result['finished'] = time.time()
        save('result', result)
    return result


def main():
    need(PLAN is not None, 'Unbound plan')
    need(sys.flags.optimize == 0 and sys.flags.isolated and sys.flags.no_site
         and sys.dont_write_bytecode, 'Use -I -S -B')
    root = Path(PLAN['root'])
    os.environ.update(HOME=str(root/'synthetic-home'), USERPROFILE=str(root/'synthetic-home'),
                      TEMP=str(root/'tmp'), TMP=str(root/'tmp'))
    for path, digest in PLAN['sources'].items():
        need(hashlib.sha256((root/'code'/path).read_bytes()).hexdigest() == digest, 'Source drift')
    sys.path.insert(0, str(root/'code/scripts'))
    from agm_core import windows_native as w
    operation = str(uuid.uuid4())
    evidence = root/'evidence'/('dosdevice-'+operation)
    evidence.mkdir()

    def save(name, value):
        with (evidence/(name+'.json')).open('x', encoding='utf8') as f:
            json.dump(dict(value, run_id=PLAN['run_id'], operation_id=operation), f, indent=2)
            f.flush(); os.fsync(f.fileno())

    api = w._API()
    api.k.QueryDosDeviceW.argtypes = [C.c_wchar_p, C.c_void_p, w.DWORD]
    api.k.QueryDosDeviceW.restype = w.DWORD
    api.k.DefineDosDeviceW.argtypes = [w.DWORD, C.c_wchar_p, C.c_wchar_p]
    api.k.DefineDosDeviceW.restype = w.BOOL
    api.k.GetLogicalDrives.argtypes = []
    api.k.GetLogicalDrives.restype = w.DWORD

    def query(name):
        buf = C.create_unicode_buffer(65536)
        n = api.k.QueryDosDeviceW(name, buf, len(buf))
        if not n:
            error = C.get_last_error()
            if name is not None and error == 2:
                return []
            raise C.WinError(error)
        return [x for x in buf[:n].split('\0') if x]

    def drives():
        mask = api.k.GetLogicalDrives()
        need(mask != 0, 'GetLogicalDrives failed')
        return mask

    class Luid(C.Structure):
        _fields_ = [('low', w.DWORD), ('high', C.c_int32)]

    class Statistics(C.Structure):
        _fields_ = [('token', Luid), ('authentication', Luid), ('expires', C.c_int64),
                    ('type', C.c_int32), ('impersonation', C.c_int32),
                    ('charged', w.DWORD), ('available', w.DWORD), ('groups', w.DWORD),
                    ('privileges', w.DWORD), ('modified', Luid)]

    def token_scope():
        api.k.GetCurrentProcess.argtypes = []; api.k.GetCurrentProcess.restype = w.HANDLE
        api.a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, C.POINTER(w.HANDLE)]
        api.a.OpenProcessToken.restype = w.BOOL
        api.a.GetTokenInformation.argtypes = [w.HANDLE, C.c_int32, C.c_void_p, w.DWORD, C.POINTER(w.DWORD)]
        api.a.GetTokenInformation.restype = w.BOOL
        token = w.HANDLE()
        need(api.a.OpenProcessToken(api.k.GetCurrentProcess(), 8, C.byref(token)), 'Token open failed')
        try:
            elevated, returned, stats = w.DWORD(), w.DWORD(), Statistics()
            need(api.a.GetTokenInformation(token, 20, C.byref(elevated), 4, C.byref(returned)) and returned.value == 4, 'Elevation query failed')
            need(not elevated.value, 'Ordinary token required')
            need(C.sizeof(stats) == 56, 'TOKEN_STATISTICS ABI mismatch')
            need(api.a.GetTokenInformation(token, 10, C.byref(stats), C.sizeof(stats), C.byref(returned)) and returned.value == C.sizeof(stats), 'Statistics query failed')
            return dict(elevated=False, authentication_id=dict(low=stats.authentication.low, high=stats.authentication.high))
        finally:
            api.k.CloseHandle(token)

    case = PLAN['case_path']
    with w.inspect_path(case, security=True, candidate_metadata=True) as held:
        need(w.same_node(held, PLAN['identity']) and held['security']['sha256'] == PLAN['security_sha256'], 'Fixture drift')
        need(held['case_sensitive_directory'] is False and not list(Path(case).iterdir()), 'Empty restored fixture required')
        h = api.k.CreateFileW(case, 0x80, 3, None, 3, 0x02200000, None)
        need(h not in (None, C.c_void_p(-1).value), 'Target handle unavailable')
        try:
            need(w.same_node(api.inspect(h, case), held), 'Target handle identity mismatch')
            buf = C.create_unicode_buffer(32768)
            n = api.k.GetFinalPathNameByHandleW(h, buf, len(buf), 2)
            need(0 < n < len(buf) and buf.value.startswith('\\Device\\'), 'NT target unavailable')
            nt_target = buf.value

            class Runtime:
                def preimage(self):
                    return dict(logical_drives=drives(), device_names=query(None),
                                letters={x+':': query(x+':') for x in 'ZYXWVUTSRQPONMLKJIHGFE'},
                                token=token_scope(), target_identity=PLAN['identity'],
                                environment={x:os.environ.get(x) for x in ('HOME','USERPROFILE','TEMP','TMP','SystemRoot')})

                def select(self, pre):
                    for x in 'ZYXWVUTSRQPONMLKJIHGFE':
                        if not pre['logical_drives'] & (1 << (ord(x)-65)) and pre['letters'][x+':'] == [] and x+':' not in pre['device_names']:
                            return x+':', nt_target
                    raise RuntimeError('No unused letter; no changes')

                def query(self, letter):
                    return query(letter)

                def recheck(self, letter):
                    need(not query(letter) and not drives() & (1 << (ord(letter[0])-65)), 'Letter became occupied')
                    need(w.same_node(api.inspect(h, case), held), 'Target drift')

                def define(self, letter, target):
                    if not api.k.DefineDosDeviceW(1 | 8, letter, target):
                        raise C.WinError(C.get_last_error())

                def remove_exact(self, letter, target):
                    if not api.k.DefineDosDeviceW(1 | 2 | 4 | 8, letter, target):
                        raise C.WinError(C.get_last_error())

                def verify(self, letter):
                    alias = letter+'\\'
                    other = api.k.CreateFileW(alias, 0x80, 3, None, 3, 0x02200000, None)
                    need(other not in (None, C.c_void_p(-1).value), 'Alias open failed')
                    try:
                        identity = api.info(other, 18, w.FileIdInfo())
                        need(identity.volume == held['volume_id'] and bytes(identity.file_id).hex() == held['file_id'], 'Mapped identity differs')
                    finally:
                        api.k.CloseHandle(other)
                    try:
                        with w.inspect_candidate_path(alias, allowed_root=alias):
                            pass
                    except w.NativeInspectionError as exc:
                        need(exc.code == 'path_alias_refused', 'Unexpected refusal '+exc.code)
                        return [dict(name='mapped_same_identity_refused', status='passed', code=exc.code)]
                    raise RuntimeError('Mapped path admitted')

                def verify_restored(self, pre):
                    need(drives() == pre['logical_drives'], 'Logical drive preimage changed')
                    need(set(query(None)) == set(pre['device_names']), 'DOS namespace preimage changed')
                    need(all(query(x) == before for x, before in pre['letters'].items()), 'Drive definition preimage changed')
                    need(w.same_node(api.inspect(h, case), held), 'Target identity changed')

            result = exercise(Runtime(), save)
        finally:
            api.k.CloseHandle(h)
    # Only after held-chain exit revalidation succeeds may the operation complete.
    save('completion', dict(result, held_chain_exit_revalidated=True))
    print(json.dumps(dict(result, evidence=str(evidence))))
    return 0 if result['status'] == 'passed' and result.get('cleanup_complete') else 2


if __name__ == '__main__':
    raise SystemExit(main())
