import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { WindowsCkHost, ckWorkingTree } from "../server/windows-ck";
import type { RunProcessOptions } from "../server/shared/common/process";

function fixture() {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "windows-ck-")));
  fs.mkdirSync(path.join(root, "scripts")); fs.writeFileSync(path.join(root, "scripts/install.py"), "fixture"); fs.writeFileSync(path.join(root, "SKILL.md"), "fixture");
  let now = 0, executions = 0, acquisitions = 0, timeout = false;
  const host = new WindowsCkHost({ home: root, previewSource: () => root, platform: "win32", now: () => now,
    python: async () => ({ status: "ready", selected: { path: "/python" } } as never),
    git: async () => ({ status: "ready", path: "/git", detail: "fixture" }),
    acquire: async () => { acquisitions++; return root; },
    run: async (options: RunProcessOptions) => {
      const request = JSON.parse(options.stdin!);
      if (request.action === "confirm") { executions++; if (timeout) return { kind: "timeout", partialStdout: "", partialStderr: "" }; }
      const value = request.action === "plan" ? { status: "approval_required", plan: { agents: ["zcode"], skipped: ["workbuddy"], files: { rules: { before: { sha256: "before", hex: "PRIVATE_SNAPSHOT_SENTINEL_678" }, after: { sha256: "after", hex: "PRIVATE_SNAPSHOT_SENTINEL_678" } } }, links: { skill: { kind: "absent" } } } } : { status: "committed" };
      return { kind: "completed", exitCode: 0, stdout: JSON.stringify(value), stderr: "", stdoutTruncated: false, stderrTruncated: false };
    } });
  return { root, host, expire: () => { now += 600001; }, counters: () => ({ executions, acquisitions }), timeout: () => { timeout = true; }, close: () => fs.rmSync(root, { recursive: true, force: true }) };
}
async function complete(host: WindowsCkHost, token: string) {
  const started = host.confirm(token);
  if (started.status !== "running") return started;
  for (let i = 0; i < 100; i++) {
    await new Promise(resolve => setTimeout(resolve, 1));
    const result = host.status(); if (result.status !== "running") return result;
  }
  throw new Error("Background operation did not complete");
}
async function prepared(f: ReturnType<typeof fixture>) {
  const p = await f.host.preview("prepare"); assert.equal(f.counters().acquisitions, 0);
  const result = await complete(f.host, String(p.confirmationToken)); assert.equal(result.status, "source_prepared");
}

test("Context Keeper fetch and install need distinct single-use approvals; display excludes private snapshots and reports skipped agents", async () => {
  const f = fixture(); try {
    await prepared(f); const plan = await f.host.preview("install");
    assert.equal(plan.status, "approval_required"); assert.deepEqual(plan.skipped, ["workbuddy"]);
    assert(!JSON.stringify(plan).includes("PRIVATE_SNAPSHOT_SENTINEL_678")); assert.equal(f.counters().executions, 0);
    assert.equal((await complete(f.host, String(plan.confirmationToken))).status, "committed");
    assert.equal((await complete(f.host, String(plan.confirmationToken))).status, "failed");
    assert.deepEqual(f.counters(), { executions: 1, acquisitions: 1 });
    assert.equal((await f.host.preview("install")).status, "failed", "new intent needs a fresh main fetch");
  } finally { f.close(); }
});
test("Context Keeper expired, cancelled or source-drifted plans never execute", async () => {
  for (const reason of ["expire", "cancel", "drift"]) {
    const f = fixture(); try {
      await prepared(f); const plan = await f.host.preview("install");
      if (reason === "expire") f.expire();
      if (reason === "cancel") assert.equal(f.host.cancel().status, "rejected");
      if (reason === "drift") fs.appendFileSync(path.join(f.root, "SKILL.md"), "foreign");
      assert.equal((await complete(f.host, String(plan.confirmationToken))).status, "failed"); assert.equal(f.counters().executions, 0);
    } finally { f.close(); }
  }
});
test("Context Keeper ambiguous write result blocks further operations instead of replaying the installer", async () => {
  const f = fixture(); try {
    await prepared(f); const plan = await f.host.preview("install"); f.timeout();
    assert.equal((await complete(f.host, String(plan.confirmationToken))).status, "unknown");
    assert.equal((await f.host.preview("prepare")).status, "failed"); assert.equal(f.counters().executions, 1);
  } finally { f.close(); }
});
test("Context Keeper source snapshot rejects aliases and detects hidden raw-byte edits", () => {
  const f = fixture(); try {
    const before = ckWorkingTree(f.root); fs.writeFileSync(path.join(f.root, "scripts/install.py"), "edited"); assert.notEqual(ckWorkingTree(f.root), before);
    fs.symlinkSync(path.join(f.root, "SKILL.md"), path.join(f.root, "alias")); assert.throws(() => ckWorkingTree(f.root), /link refused/);
  } finally { f.close(); }
});

test("Context Keeper confirmation returns before acquisition and read-only status recovers its result", async () => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "context-keeper-job-")));
  fs.mkdirSync(path.join(root, "scripts")); fs.writeFileSync(path.join(root, "scripts/install.py"), "fixture"); fs.writeFileSync(path.join(root, "SKILL.md"), "fixture");
  let release!: () => void; let acquisitions = 0;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const host = new WindowsCkHost({ home: root, platform: "win32", previewSource: () => root,
    python: async () => ({ status: "ready", selected: { path: "/python" } } as never),
    git: async () => ({ status: "ready", path: "/git", detail: "fixture" }),
    acquire: async () => { acquisitions++; await gate; return root; } });
  try {
    assert.equal(host.status().status, "idle");
    const plan = await host.preview("prepare");
    assert.deepEqual(host.confirm(String(plan.confirmationToken)), { status: "running" });
    await new Promise(resolve => setTimeout(resolve, 1));
    assert.equal(host.status().status, "running"); assert.equal(host.confirm(String(plan.confirmationToken)).status, "busy");
    assert.equal(host.cancel().status, "busy"); assert.equal((await host.preview("prepare")).status, "busy");
    release();
    for (let i = 0; i < 100 && host.status().status === "running"; i++) await new Promise(resolve => setTimeout(resolve, 1));
    assert.equal(host.status().status, "source_prepared"); assert.equal(acquisitions, 1);
    assert(!JSON.stringify(host.status()).includes("confirmationToken"));
  } finally { release(); fs.rmSync(root, { recursive: true, force: true }); }
});
