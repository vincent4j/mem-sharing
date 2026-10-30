# M4-09-55 CK 失败与主产品保留

Execution status: blocked. No acceptance verdict.

Synthetic fixture preserved at `/private/tmp/M4-09-55-czgo7e1a`.

- Source contains exact baseline git-archive product bytes (scripts and four root documents; documentation cases retain full archive); source-manifest route is used. Synthetic SemVer 0.4.0 is an exercise identity, not a frozen formal release.
- CK fixture is the existing UPSTREAM literal from tests/unit/test_ck_install.py. No upstream real source or real HOME is read/executed. No temporary Git commit is created. Production CK source rejects OS-temp locations; no monkeypatch of source trust gates is used.
- Main installation and source-unavailable CK failure isolation captured. Injected upstream/partial-agent failure after a valid CK plan is blocked by durable pinned-source gate; no replacement source validator or fabricated success plan.

See index.json, per-command raw stdout/stderr, trees, byte diffs and content-addressed blobs.
