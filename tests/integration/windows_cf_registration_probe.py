"""Plan-bound Cloud Files experiment. Not production admission or a provider."""
import ctypes as C
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time
import uuid

PLAN = None


def need(value, message):
    if not value:
        raise RuntimeError(message)


class PolicyPair(C.Structure):
    _fields_ = [('primary', C.c_uint16), ('modifier', C.c_uint16)]


class Policies(C.Structure):
    _fields_ = [('size', C.c_uint32), ('hydration', PolicyPair), ('population', PolicyPair),
                ('in_sync', C.c_int32), ('hard_link', C.c_int32), ('management', C.c_int32)]


class Guid(C.Structure):
    _fields_ = [('data1', C.c_uint32), ('data2', C.c_uint16), ('data3', C.c_uint16),
                ('data4', C.c_ubyte * 8)]


class Registration(C.Structure):
    _fields_ = [('size', C.c_uint32), ('name', C.c_void_p), ('version', C.c_void_p),
                ('root_identity', C.c_void_p), ('root_identity_length', C.c_uint32),
                ('file_identity', C.c_void_p), ('file_identity_length', C.c_uint32),
                ('provider_id', Guid)]


class Standard(C.Structure):
    # WCHAR is explicitly 16 bits; ctypes.c_wchar is 32 bits on the Mac test host.
    _fields_ = [('file_id', C.c_int64), ('hydration', PolicyPair), ('population', PolicyPair),
                ('in_sync', C.c_int32), ('hard_link', C.c_int32), ('status', C.c_int32),
                ('name', C.c_uint16 * 256), ('version', C.c_uint16 * 256),
                ('identity_length', C.c_uint32), ('identity', C.c_ubyte * 1)]


def decode_standard(raw, returned, marker, name, version):
    offset = Standard.identity.offset
    need(offset <= returned <= len(raw), 'STANDARD return length invalid')
    need(len(raw) >= C.sizeof(Standard), 'STANDARD buffer too small')
    header = Standard.from_buffer_copy(raw[:C.sizeof(Standard)])
    length = header.identity_length
    need(0 < length <= 4096 and offset+length <= returned, 'Identity tail bounds invalid')

    def text(array):
        values = list(array)
        need(0 in values, 'Unterminated provider field')
        return bytes(C.string_at(C.addressof(array), values.index(0)*2)).decode('utf-16le')

    found = raw[offset:offset+length]
    return dict(owned=found == marker and text(header.name) == name and text(header.version) == version,
                identity_length=length, identity_sha256=hashlib.sha256(found).hexdigest(),
                sync_root_file_id=header.file_id, provider_status=header.status,
                provider_id_returned=False)


def compare_dimensions(before, after):
    left, right = before['root'], after['root']
    return dict(tree_empty=after['entries'] == [],
                identity_equal=left['identity'] == right['identity'],
                security_equal=left['security_sha256'] == right['security_sha256'],
                attrs_equal=left['attributes'] == right['attributes'],
                tag_equal=left['reparse_tag'] == right['reparse_tag'])


def exercise(runtime, save):
    result = dict(status='failed', started=time.time(), register_attempted=False,
                  unregister_attempted=False, provider_connect_attempted=False,
                  placeholders_created=False, production_write_authorized=False,
                  r2_admission_satisfied=False, full_cf_gate_verified=False, race_free=False)
    try:
        result['before'] = runtime.preflight()
        save('baseline-before-register', result['before'])
        save('intent', dict(result, registration=runtime.describe()))
        result['register_attempted'] = True
        result['register_hresult'] = runtime.register()
        result['after_register'] = runtime.snapshot()
        save('after-register', result['after_register'])
        need(result['register_hresult'] == 0, 'Register returned non-S_OK')
        result['ownership'] = runtime.ownership()
        need(result['ownership'].get('owned') is True, 'Registration identity unverified')
        result['checks'] = runtime.verify_refusal()
        result['status'] = 'observed_positive'
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        if result['register_attempted']:
            try:
                # Repeat ownership observation on exceptions/interruptions as well.
                result['cleanup_ownership'] = runtime.ownership()
                need(result['cleanup_ownership'].get('owned') is True,
                     'Cannot attribute registration; no blind unregister')
                runtime.cleanup_guard()
                result['before_unregister'] = runtime.snapshot()
                save('before-unregister', result['before_unregister'])
                save('unregister-intent', dict(result, registration=runtime.describe()))
                result['unregister_attempted'] = True
                result['unregister_hresult'] = runtime.unregister()
                result['unregister_succeeded'] = result['unregister_hresult'] == 0
                result['after_unregister_before_delete'] = runtime.snapshot()
                save('after-unregister-before-delete', result['after_unregister_before_delete'])
                need(result['unregister_hresult'] == 0, 'Unregister returned non-S_OK; no retry')
                result['after'] = runtime.after()
                result['dimensions'] = result['after']['dimensions']
                need(all(result['dimensions'].values()), 'Physical fixture dimension mismatch')
                # Physical cleanup and API return are distinct from CF query evidence.
                result['fixture_cleanup_complete'] = True
            except BaseException as exc:
                result.update(status='needs_inspection', fixture_cleanup_complete=False,
                              cleanup_error=dict(type=type(exc).__name__, message=str(exc)))
        result['finished'] = time.time()
        save('result', result)
    return result


def main():
    need(PLAN is not None and PLAN.get('operation_id'), 'Unbound experiment')
    need(sys.flags.optimize == 0 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
         'Use -I -S -B')
    need(os.name == 'nt' and C.sizeof(C.c_wchar) == 2 and platform.machine().upper() in ('AMD64','X86_64'),
         'Windows x64 wchar ABI required')
    need(C.sizeof(C.c_void_p) == 8 and C.sizeof(Registration) == 72 and C.sizeof(Policies) == 24
         and C.sizeof(Standard) == 1064 and Standard.identity.offset == 1056, 'Unsupported ABI')
    expected_offsets = {
        'Registration': {'size':0,'name':8,'version':16,'root_identity':24,'root_identity_length':32,
                         'file_identity':40,'file_identity_length':48,'provider_id':52},
        'Policies': {'size':0,'hydration':4,'population':8,'in_sync':12,'hard_link':16,'management':20},
        'Standard': {'file_id':0,'hydration':8,'population':12,'in_sync':16,'hard_link':20,'status':24,
                     'name':28,'version':540,'identity_length':1052,'identity':1056}}
    observed_offsets = {kind.__name__:{name:getattr(kind,name).offset for name,_ in kind._fields_}
                        for kind in (Registration,Policies,Standard)}
    need(observed_offsets == expected_offsets and C.alignment(Guid) == 4 and C.sizeof(Guid) == 16,
         'CF field offset/alignment mismatch')
    root = Path(PLAN['root'])
    os.environ.update(HOME=str(root/'synthetic-home'), USERPROFILE=str(root/'synthetic-home'),
                      TEMP=str(root/'tmp'), TMP=str(root/'tmp'))
    for path, digest in PLAN['sources'].items():
        need(hashlib.sha256((root/'code'/path).read_bytes()).hexdigest() == digest, 'Source drift')
    sys.path.insert(0, str(root/'code/scripts'))
    from agm_core import windows_native as w
    operation = str(uuid.UUID(PLAN['operation_id']))
    fixture = root/'synthetic-home'/('cf-register-'+operation)
    evidence = root/'evidence'/('cf-register-'+operation)
    child = fixture/('known-ordinary-'+operation+'.bin')
    child_payload = ('memSharing CF ordinary fixture '+operation+'\r\n').encode('ascii')
    child_hash = hashlib.sha256(child_payload).hexdigest()
    marker = bytes.fromhex(PLAN['marker_hex'])
    need(len(marker) == 32, 'Identity marker length invalid')
    provider = 'memSharing-R2-'+operation
    version = 'fixture-1'
    abi = dict(field_offsets=observed_offsets,
               sizes={kind.__name__:C.sizeof(kind) for kind in (Guid,PolicyPair,Registration,Policies,Standard)},
               alignment={kind.__name__:C.alignment(kind) for kind in (Guid,PolicyPair,Registration,Policies,Standard)},
               pointer_size=C.sizeof(C.c_void_p), wchar_size=C.sizeof(C.c_wchar), machine=platform.machine(),
               enum_values=dict(BASIC=0,STANDARD=1,REGISTER_NONE=0,PLACEHOLDER_NO_STATES=0),
               sdk_compile_verified=False, register_attempted=False)
    need(sys.argv[1:] in ([], ['--abi-check']), 'No arbitrary action/arguments')
    if sys.argv[1:] == ['--abi-check']:
        with (root/'evidence'/('cf-abi-'+operation+'.json')).open('x', encoding='utf8') as f:
            json.dump(dict(abi, operation_id=operation, sources=PLAN['sources']), f, indent=2)
            f.flush(); os.fsync(f.fileno())
        print(json.dumps(abi))
        return 0
    evidence.mkdir()

    def save(name, value):
        with (evidence/(name+'.json')).open('x', encoding='utf8') as f:
            json.dump(dict(value, operation_id=operation, fixture=str(fixture)), f, indent=2)
            f.flush(); os.fsync(f.fileno())

    api = w._API()
    api.k.GetCurrentProcess.argtypes = []; api.k.GetCurrentProcess.restype = w.HANDLE
    api.a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, C.POINTER(w.HANDLE)]
    api.a.OpenProcessToken.restype = w.BOOL
    api.a.GetTokenInformation.argtypes = [w.HANDLE, C.c_int32, C.c_void_p, w.DWORD, C.POINTER(w.DWORD)]
    api.a.GetTokenInformation.restype = w.BOOL
    token = w.HANDLE()
    need(api.a.OpenProcessToken(api.k.GetCurrentProcess(), 8, C.byref(token)), 'Token open failed')
    try:
        elevated, returned = w.DWORD(), w.DWORD()
        need(api.a.GetTokenInformation(token, 20, C.byref(elevated), 4, C.byref(returned))
             and returned.value == 4 and not elevated.value, 'Ordinary token required')
    finally:
        api.k.CloseHandle(token)
    library = C.WinDLL('CldApi.dll', winmode=0x800)
    register = library.CfRegisterSyncRoot
    register.argtypes = [C.c_wchar_p, C.POINTER(Registration), C.POINTER(Policies), C.c_int32]
    register.restype = C.c_int32
    unregister = library.CfUnregisterSyncRoot
    unregister.argtypes = [C.c_wchar_p]; unregister.restype = C.c_int32
    query = library.CfGetSyncRootInfoByHandle
    query.argtypes = [w.HANDLE, C.c_int32, C.c_void_p, w.DWORD, C.POINTER(w.DWORD)]
    query.restype = C.c_int32
    placeholder_state = library.CfGetPlaceholderStateFromAttributeTag
    placeholder_state.argtypes = [w.DWORD, w.DWORD]; placeholder_state.restype = C.c_int32
    name_buffer, version_buffer = C.create_unicode_buffer(provider), C.create_unicode_buffer(version)
    identity_buffer = C.create_string_buffer(marker)
    registration = Registration()
    registration.size = C.sizeof(registration)
    registration.name = C.cast(name_buffer, C.c_void_p)
    registration.version = C.cast(version_buffer, C.c_void_p)
    registration.root_identity = C.cast(identity_buffer, C.c_void_p)
    registration.root_identity_length = len(marker)
    registration.provider_id = Guid.from_buffer_copy(uuid.UUID(PLAN['provider_id']).bytes_le)
    policies = Policies()
    policies.size = C.sizeof(policies)
    # Every remaining field is an explicit defined PARTIAL/NONE/DEFAULT zero value.
    with w.inspect_path(PLAN['case_path'], security=True, candidate_metadata=True) as anchor:
        need(w.same_node(anchor, PLAN['identity']) and anchor['security']['sha256'] == PLAN['security_sha256']
             and anchor['case_sensitive_directory'] is False, 'Anchor drift')
        save('setup-intent', dict(child=str(child), child_sha256=child_hash,
                                  child_bytes=len(child_payload), register_attempted=False, abi=abi))
        fixture.mkdir()
        h = api.k.CreateFileW(str(fixture), 0x80 | 0x20000, 3, None, 3, 0x02200000, None)
        need(h not in (None, C.c_void_p(-1).value), 'Fixture handle unavailable')
        child_held = [None]
        try:
            def root_snapshot():
                node = api.info(h, 18, w.FileIdInfo())
                tag = api.info(h, 9, w.AttributeTagInfo())
                return dict(identity=dict(volume_id=node.volume, file_id=bytes(node.file_id).hex()),
                            attributes=tag.attributes, reparse_tag=tag.reparse_tag,
                            security_sha256=api.security(h)['sha256'])

            root_created = dict(root=root_snapshot(), entries=[], child=None)
            need(not list(fixture.iterdir()), 'New root not empty')
            save('root-created-before-child', root_created)
            with child.open('xb') as f:
                f.write(child_payload); f.flush(); os.fsync(f.fileno())
            child_h = api.k.CreateFileW(str(child), 0x80000000, 3, None, 3, 0x00200000, None)
            need(child_h not in (None, C.c_void_p(-1).value), 'Ordinary query child unavailable')
            child_held[0] = child_h
            initial = api.inspect(h, str(fixture))
            child_initial = api.inspect(child_h, str(child))
            need(not child_initial['directory'], 'Query child must be ordinary file')
            root_metadata = api.candidate_metadata(h, True)
            need(not root_metadata['case_sensitive_directory'], 'Sensitive experiment root refused')
            security_hash = api.security(h)['sha256']
            need(security_hash == root_created['root']['security_sha256'], 'Security drift during child creation')

            def ordinary_child_guard():
                need(child_held[0] is not None, 'Query child already closed')
                item = api.inspect(child_held[0], str(child))
                need(w.same_node(item, child_initial), 'Query child handle drift')
                state = placeholder_state(item['attributes'], item['reparse_tag']) & 0xffffffff
                need(state == 0, 'Child is placeholder or state unknown; preserve')
                need(child.read_bytes() == child_payload, 'Query child content drift')
                with w.inspect_path(str(child), candidate_metadata=True) as named:
                    need(w.same_node(named, child_initial) and named['number_of_links'] == 1, 'Named child identity/link drift')
                need(list(fixture.iterdir()) == [child], 'Foreign tree entry; never unregister')
                return dict(identity=dict(volume_id=item['volume_id'], file_id=item['file_id']),
                            sha256=child_hash, attributes=item['attributes'], placeholder_state=state, reparse_tag=item['reparse_tag'])

            def physical_guard(expect_child=True):
                info = api.info(h, 18, w.FileIdInfo())
                need(info.volume == initial['volume_id'] and bytes(info.file_id).hex() == initial['file_id'], 'Held identity drift')
                fresh = api.k.CreateFileW(str(fixture), 0x80 | 0x20000, 3, None, 3, 0x02200000, None)
                need(fresh not in (None, C.c_void_p(-1).value), 'Named fixture unavailable')
                try:
                    named = api.info(fresh, 18, w.FileIdInfo())
                    need(named.volume == info.volume and bytes(named.file_id) == bytes(info.file_id), 'Named fixture drift')
                    need(api.security(fresh)['sha256'] == security_hash, 'Fixture security drift')
                finally:
                    api.k.CloseHandle(fresh)
                if expect_child:
                    ordinary_child_guard()
                else:
                    need(not list(fixture.iterdir()), 'Fixture not empty after own child cleanup')

            class Runtime:
                def describe(self):
                    return dict(provider_id=PLAN['provider_id'], provider_name=provider, provider_version=version,
                                marker_sha256=hashlib.sha256(marker).hexdigest(), marker_length=len(marker),
                                register_flags=0, policy_bytes=bytes(policies).hex(), token_elevated=False,
                                unique_known_child=str(child), child_sha256=child_hash,
                                cleanup_scope='only one known ordinary nonplaceholder child; no foreign traversal',
                                recovery_bound_source=__file__, operation_id=operation,
                                abi=dict(registration=C.sizeof(registration), policies=C.sizeof(policies),
                                         standard=C.sizeof(Standard), identity_offset=Standard.identity.offset,
                                         field_offsets=observed_offsets, sdk_compile_verified=False,
                                         enum_values=dict(BASIC=0,STANDARD=1,REGISTER_NONE=0,PLACEHOLDER_NO_STATES=0)))

                def ownership(self):
                    raw, returned = C.create_string_buffer(8192), w.DWORD()
                    need(child_held[0] is not None, 'No document-supported file query handle')
                    hr = query(child_held[0], 1, raw, len(raw), C.byref(returned)) & 0xffffffff
                    if hr != 0:
                        return dict(owned=False, hresult=hr, returned=returned.value, state='unknown')
                    return dict(decode_standard(raw.raw, returned.value, marker, provider, version), hresult=hr, returned=returned.value)

                def snapshot(self):
                    entries = sorted(item.name for item in fixture.iterdir())
                    child_snapshot = None
                    if child_held[0] is not None:
                        info = api.info(child_held[0], 18, w.FileIdInfo())
                        tag = api.info(child_held[0], 9, w.AttributeTagInfo())
                        state = placeholder_state(tag.attributes, tag.reparse_tag) & 0xffffffff
                        expected_id = info.volume == child_initial['volume_id'] and bytes(info.file_id).hex() == child_initial['file_id']
                        # Never hydrate/read unknown content just to improve evidence.
                        data_hash = hashlib.sha256(child.read_bytes()).hexdigest() if expected_id and state == 0 and not tag.attributes & 0x400 else None
                        child_snapshot = dict(identity=dict(volume_id=info.volume,file_id=bytes(info.file_id).hex()),
                                              attributes=tag.attributes,reparse_tag=tag.reparse_tag,
                                              placeholder_state=state,sha256=data_hash)
                    return dict(root=root_snapshot(), entries=entries, child=child_snapshot)

                def preflight(self):
                    physical_guard()
                    observed = self.ownership()
                    need(observed.get('hresult') != 0, 'Existing registered ancestor/root; refuse registration')
                    baseline = self.snapshot()
                    need(baseline['child']['sha256'] == child_hash, 'Baseline child content differs')
                    self.baseline_with_child = baseline
                    return dict(root_created_before_child=root_created, baseline_with_child=baseline,
                                cloud_query=observed, known_child=ordinary_child_guard(),
                                no_registration_claim_from_non_s_ok=True,
                                environment={x:os.environ.get(x) for x in ('HOME','USERPROFILE','TEMP','TMP','SystemRoot')})

                def register(self):
                    physical_guard()
                    return register(str(fixture), C.byref(registration), C.byref(policies), 0) & 0xffffffff

                def verify_refusal(self):
                    try:
                        api.registered_cloud_root(child_held[0])
                    except w.NativeInspectionError as exc:
                        need(exc.code == 'registered_cloud_root_refused', 'Registered root refusal not observed')
                        return [dict(name='registered_root_refused', code=exc.code, status='passed')]
                    raise RuntimeError('Registered root not refused')

                def cleanup_guard(self):
                    physical_guard()
                    need(self.ownership().get('owned') is True, 'Registration marker drift')

                def unregister(self):
                    # Never connected by this experiment; API also rejects connected providers.
                    return unregister(str(fixture)) & 0xffffffff

                def after(self):
                    physical_guard()
                    observed = self.ownership()
                    save('post-unregister-cloud-query', observed)
                    need(observed.get('hresult') != 0, 'Registration still reported; preserve query child')
                    child_after = ordinary_child_guard()
                    before_delete = self.snapshot()
                    save('before-own-child-delete', before_delete)
                    closing = child_held[0]; child_held[0] = None
                    need(api.k.CloseHandle(closing), 'Query child close failed; preserve')
                    # Recheck identity/hash before removing only our known ordinary file.
                    with w.inspect_path(str(child), candidate_metadata=True) as fresh:
                        need(w.same_node(fresh, child_initial) and fresh['number_of_links'] == 1, 'Child cleanup identity drift')
                    need(child.read_bytes() == child_payload, 'Child cleanup content drift')
                    child.unlink()
                    physical_guard(expect_child=False)
                    after_delete = self.snapshot()
                    save('after-own-child-delete', after_delete)
                    dimensions = compare_dimensions(root_created, after_delete)
                    roundtrip = compare_dimensions(self.baseline_with_child, before_delete)
                    roundtrip.pop('tree_empty')
                    roundtrip['tree_equal'] = before_delete['entries'] == self.baseline_with_child['entries']
                    for field in ('identity','sha256','attributes','reparse_tag'):
                        roundtrip['child_'+field+'_equal'] = before_delete['child'][field] == self.baseline_with_child['child'][field]
                    return dict(dimensions=dimensions, registration_roundtrip_dimensions=roundtrip,
                                before_own_child_delete=before_delete, after_own_child_delete=after_delete,
                                child_preserved_through_unregister=child_after,
                                child_removed_after_success=True, cloud_query=observed,
                                query_classification='inferred_not_root' if observed.get('hresult') == 0x80070186 else 'unknown',
                                negative_hresult_mapping_inferred=True, full_cf_gate_verified=False)

            result = exercise(Runtime(), save)
        finally:
            if child_held[0] is not None:
                api.k.CloseHandle(child_held[0])
            api.k.CloseHandle(h)
    save('completion', dict(result, held_anchor_exit_revalidated=True, fixture_preserved=True))
    print(json.dumps(dict(status=result['status'], fixture_cleanup_complete=result.get('fixture_cleanup_complete'), evidence=str(evidence))))
    return 0 if result['status'] == 'observed_positive' and result.get('fixture_cleanup_complete') else 2


if __name__ == '__main__':
    raise SystemExit(main())
