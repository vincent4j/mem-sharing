# M4-09-01 只读权限源的冷启动补证

Execution status: executed. No acceptance verdict.

Synthetic fixture preserved at `/private/tmp/M4-09-01-ut4fbohb`.

- Source contains exact baseline git-archive product bytes (scripts and four root documents; documentation cases retain full archive); source-manifest route is used. Synthetic SemVer 0.4.0 is an exercise identity, not a frozen formal release.
- All S regular files are mode 0444 and directories 0555 before the cold commands. These are filesystem permission bits under the ordinary user, not a separate VM or read-only mount.

See index.json, per-command raw stdout/stderr, trees, byte diffs and content-addressed blobs.
