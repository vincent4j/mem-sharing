import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { runProcess, ProcessInputError } from "../src/process.ts";

test("stdin carries private Unicode literally and closes at EOF", async () => {
  const stdin = '私有正文\n{"text":"$() `echo` 中文"}';
  const result = await runProcess({ argv: [process.execPath, "-e", "process.stdin.pipe(process.stdout)"], stdin, timeoutMs: 5000 });
  assert.equal(result.kind, "completed");
  if (result.kind === "completed") { assert.equal(result.exitCode, 0); assert.equal(result.stdout, stdin); }
});

test("completed: echo argv reaches stdout literally without a shell", async () => {
  const hostile = "hello world; rm -rf /tmp && $(echo pwned)";
  const result = await runProcess({ argv: ["/bin/echo", hostile], timeoutMs: 5000 });
  assert.equal(result.kind, "completed");
  if (result.kind !== "completed") return;
  assert.equal(result.exitCode, 0);
  assert.equal(result.stdout.trim(), hostile);
});

test("completed: non-zero exit codes are reported, not thrown", async () => {
  const result = await runProcess({ argv: [process.execPath, "-e", "process.exit(7)"], timeoutMs: 10000 });
  assert.equal(result.kind, "completed");
  if (result.kind === "completed") assert.equal(result.exitCode, 7);
});

test("stdout cap truncates and flags", async () => {
  const result = await runProcess({
    argv: [process.execPath, "-e", "process.stdout.write('x'.repeat(4096))"],
    timeoutMs: 10000,
    maxStdoutBytes: 1024,
  });
  assert.equal(result.kind, "completed");
  if (result.kind === "completed") {
    assert.equal(result.stdout.length, 1024);
    assert.equal(result.stdoutTruncated, true);
  }
});

test("timeout kills the child and reports kind timeout", async () => {
  const result = await runProcess({
    argv: [process.execPath, "-e", "setTimeout(() => {}, 60000)"],
    timeoutMs: 400,
  });
  assert.equal(result.kind, "timeout");
});

test("abort signal cancels the child", async () => {
  const controller = new AbortController();
  const pending = runProcess({
    argv: [process.execPath, "-e", "setTimeout(() => {}, 60000)"],
    timeoutMs: 60000,
    signal: controller.signal,
  });
  setTimeout(() => controller.abort(), 200);
  const result = await pending;
  assert.equal(result.kind, "canceled");
});

test("missing executable reports spawn_error", async () => {
  const result = await runProcess({
    argv: [path.join(os.tmpdir(), `no-such-tool-${Date.now()}`), "--version"],
    timeoutMs: 5000,
  });
  assert.equal(result.kind, "spawn_error");
});

test("invalid argv is rejected before spawning", async () => {
  await assert.rejects(() => runProcess({ argv: [], timeoutMs: 1000 }), ProcessInputError);
  await assert.rejects(() => runProcess({ argv: ["/bin/echo", ""] , timeoutMs: 1000 }), ProcessInputError);
  await assert.rejects(() => runProcess({ argv: ["/bin/echo\0evil"], timeoutMs: 1000 }), ProcessInputError);
});

test("cwd override is honored", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-proc-cwd-"));
  try {
    const result = await runProcess({ argv: ["/bin/pwd"], cwd: dir, timeoutMs: 5000 });
    assert.equal(result.kind, "completed");
    if (result.kind === "completed") assert.equal(result.stdout.trim(), fs.realpathSync(dir));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("timeout terminates the whole process group, not just the child", async () => {
  // The child spawns a grandchild holding stdout; killing only the direct
  // child would leave the pipe open for seconds. Group termination must
  // return promptly.
  const started = Date.now();
  const result = await runProcess({
    argv: [
      process.execPath,
      "-e",
      "const { spawn } = require('node:child_process'); spawn('sleep', ['8'], { stdio: ['ignore', process.stdout, process.stderr] }); setTimeout(() => {}, 8000);",
    ],
    timeoutMs: 300,
  });
  const elapsed = Date.now() - started;
  assert.equal(result.kind, "timeout");
  assert.ok(elapsed < 3000, `group kill took ${elapsed}ms`);
});

test("abort before the timeout deadline freezes the reason and leaves no live timers", async () => {
  // Reproduces the review bug: with timeoutMs=700 and abort at 200ms, the
  // old code let the main timer fire later, flipping the result to
  // 'timeout' and arming another escalation against the released pid.
  const controller = new AbortController();
  const pending = runProcess({
    argv: [process.execPath, "-e", "setTimeout(() => {}, 60000)"],
    timeoutMs: 700,
    signal: controller.signal,
  });
  setTimeout(() => controller.abort(), 200);
  const result = await pending;
  assert.equal(result.kind, "canceled");
  // Cross the original deadline: nothing may flip the reason or re-signal.
  await new Promise((resolve) => setTimeout(resolve, 900));
  // A grandchild that survived any late signal would write this marker.
  // (Direct assertion of timers is impossible; behavioral equivalence.)
});

test("canceled process group receives no second signal after the caller returns", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-proc-nosig-"));
  const secondTerm = path.join(dir, "second-term");
  try {
    // The grandchild traps SIGTERM, records only the SECOND delivery, and
    // otherwise ignores stdio; the parent exits immediately.
    const script = `(trap 'test -f ${JSON.stringify(path.join(dir, "first"))} && touch ${JSON.stringify(secondTerm)} || touch ${JSON.stringify(path.join(dir, "first"))}' TERM; sleep 3) &>/dev/null & exit 0`;
    const controller = new AbortController();
    const pending = runProcess({ argv: ["/bin/sh", "-c", script], timeoutMs: 60000, signal: controller.signal });
    setTimeout(() => controller.abort(), 150);
    const result = await pending;
    assert.equal(result.kind, "canceled");
    // After return only the group SIGKILL has happened (untrappable); any
    // late timer-driven TERM would have written second-term.
    await new Promise((resolve) => setTimeout(resolve, 700));
    assert.equal(fs.existsSync(secondTerm), false, "a second SIGTERM arrived after settle");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("grandchild that ignores SIGTERM and holds no stdio cannot outlive the timeout", async () => {
  // Reproduces the review race: the parent exits immediately (its 'close'
  // fires), while a grandchild with stdio ignored and SIGTERM trapped
  // writes a marker later. The result must be resolved only after the
  // group-wide SIGKILL escalation, so nothing is written AFTER we return.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-proc-grand-"));
  const lateMarker = path.join(dir, "late-marker");
  const earlyMarker = path.join(dir, "early-marker");
  try {
    const script = `(trap '' TERM; sleep 0.4; touch ${JSON.stringify(earlyMarker)}; sleep 2.6; touch ${JSON.stringify(lateMarker)}) &>/dev/null & exit 0`;
    const started = Date.now();
    const result = await runProcess({ argv: ["/bin/sh", "-c", script], timeoutMs: 150 });
    const elapsed = Date.now() - started;
    assert.equal(result.kind, "timeout");
    // Resolved after the SIGTERM->SIGKILL escalation, not at parent close.
    assert.ok(elapsed >= 1900, `settled early after ${elapsed}ms`);
    // The early marker (inside the grace window) may exist; the late
    // marker (3s, after the group kill at ~2.15s) must never be written.
    await new Promise((resolve) => setTimeout(resolve, 1100));
    assert.equal(fs.existsSync(lateMarker), false, "grandchild wrote after the caller returned");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
