# memSharing for Paseo

memSharing lets coding agents (Codex, Claude Code, WorkBuddy, DSH, ZCode) share one set of
project rules and memories. The release plugin is designed to expose onboarding and exact
plan confirmation inside Paseo. This development source has not been installed or accepted
in a real host session; missing Python/Git currently blocks onboarding.

## What it does

- Connects this Mac to memSharing ("接入本机"): prepares the durable product source from
  the plugin's own verified payload, then runs the official machine installer with an
  exact preview you confirm in the host dialog.
- Checks and enables shared memory for the current workspace ("检查当前项目" /
  "启用当前项目"), again through the official CLI's exact-plan approval.
- Reports dependency and install status on demand ("接入状态").

Machine/project/CK installation writes go through the original Python installer/CLIs.
The host keeps private request, approval and operation-status evidence, without a second
machine transaction ledger. Declining a plan executes none of its proposed writes.
Optional CK source acquisition is a separate host-approved Git fetch before a second
independent CK installation approval; no source-path input or terminal is required.

## How it works

The plugin is a thin Paseo client plus a daemon-side bridge:

- Commands live in the Command Center (⌘K / Ctrl+K). They open one-time screens; there is
  no persistent management page.
- Each write shows the exact plan (summary plus full JSON) and asks for an explicit
  confirm or reject in a host modal. The plan digest stays stable for identical plans; a separate single-use server token
  binds the preview to host, HOME, stored arguments and kernel bytes. Re-preview
  invalidates the old token. Full plan JSON is expanded by default.
- The daemon side runs the bundled product payload with the machine's Python. If Python or
  Git is missing, the plugin reports exactly that and stops — it does not silently install
  or fake a runtime. Private runtime preparation is designed but not enabled until a
  verified supply manifest exists.

## Setup

Requirements: Paseo 0.13.2 or later on macOS (the plugin uses only client/server RPC and
Command Center surfaces, type-verified against the 0.13.2 SDK; real-host verification
pending), plus Python 3.9+ and Git available to the Paseo daemon (the installer refuses
to run without Git).

Install from the repository subdirectory:

```text
git:vincent4j/mem-sharing:plugins/paseo
```

No service account is needed. The plan lists product files, explicitly selected executor
user entries and the project you enable. Optional CK source acquisition contacts only its
fixed upstream URL and integration pin after explicit approval.

## Scope and limitations

- The release payload and its identity digest are generated at release time; a development
  checkout cannot bootstrap machine installation (it reports 发行身份缺失 by design).
- Enable/remove use the original kernel’s explicit read-only `--preview`; confirmation
  preserves its JSON template except the two evidence placeholders. Registry rebuild
  plans require a separate approval that this version deliberately blocks.
- Running cancellation aborts the owned process group and reports outcome unknown until
  the original journal is inspected. Recovery selects only a CLI/toolkit matching the
  original journal; a durable export survives plugin deletion. Host status evidence is
  advisory and never substitutes for that journal.
- CK acquisition is pinned to `695074ee4b6ddb9999be858093f833d6377bd641`; CK supports
  Codex, Claude Code and WorkBuddy only. It does not initialize project record stores.
- First-run auto-onboarding without any user action is not claimed: v1 is command-driven.
  Automatic guidance on install requires host lifecycle hooks (Paseo 0.14+) and real-host
  verification.
- Windows, Linux, and remote daemon hosts are untested.
