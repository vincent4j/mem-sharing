import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { probeGitEnvironment } from "../src/git.ts";

function fakeGit(dir: string, output: string, exitCode = 0): string {
  fs.mkdirSync(dir, { recursive: true });
  const target = path.join(dir, "git");
  fs.writeFileSync(target, `#!/bin/sh\nprintf '%s\\n' '${output}'\nexit ${exitCode}\n`, { mode: 0o755 });
  return target;
}

test("missing git in the scanned directories reports missing, never installs", async () => {
  const empty = fs.mkdtempSync(path.join(os.tmpdir(), "ms-git-none-"));
  try {
    const env = await probeGitEnvironment({ candidateDirs: [empty] });
    assert.equal(env.status, "missing");
    assert.match(env.detail, /no private Git supply exists/);
  } finally {
    fs.rmSync(empty, { recursive: true, force: true });
  }
});

test("a broken git executable reports unknown rather than ready", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-git-broken-"));
  try {
    fs.writeFileSync(path.join(dir, "git"), "#!/bin/sh\nexit 3\n", { mode: 0o755 });
    const env = await probeGitEnvironment({ candidateDirs: [dir] });
    assert.equal(env.status, "unknown");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("exit 0 with unexpected --version output is unknown, not ready", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-git-silent-"));
  try {
    fakeGit(dir, "not a git at all");
    const env = await probeGitEnvironment({ candidateDirs: [dir] });
    assert.equal(env.status, "unknown");
    assert.match(env.detail ?? "", /:unknown$/);
    assert.match(env.candidates?.[0]?.detail ?? "", /unexpected --version output/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("an invalid first candidate falls back to a later valid one", async () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "ms-git-fallback-"));
  try {
    const badDir = path.join(base, "bad");
    const goodDir = path.join(base, "good");
    fs.mkdirSync(badDir, { recursive: true });
    fs.writeFileSync(path.join(badDir, "git"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });
    fakeGit(goodDir, "git version 9.9.9");
    const env = await probeGitEnvironment({ candidateDirs: [badDir, goodDir] });
    assert.equal(env.status, "ready");
    assert.equal(env.path, path.join(goodDir, "git"));
    assert.match(env.version ?? "", /git version 9\.9\.9/);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test("the macOS CommandLineTools stub is blocked before execution", async () => {
  // /usr/bin/git is the documented stub location; with the read-only CLT
  // check reporting "not installed" the candidate must be blocked without
  // ever being executed. Skipped on hosts without /usr/bin/git.
  if (!fs.existsSync("/usr/bin/git")) return;
  const env = await probeGitEnvironment({
    candidateDirs: ["/usr/bin"],
    cltCheck: async () => false,
  });
  assert.equal(env.status, "blocked");
  assert.match(env.candidates?.[0]?.detail ?? "", /CommandLineTools/);
});

test("with CommandLineTools present the stub proceeds to a real probe", async () => {
  if (!fs.existsSync("/usr/bin/git")) return;
  const env = await probeGitEnvironment({
    candidateDirs: ["/usr/bin"],
    cltCheck: async () => true,
  });
  assert.equal(env.status, "ready");
});

test("real machine self-check: this host locates, executes, and verifies git", async () => {
  const env = await probeGitEnvironment();
  assert.equal(env.status, "ready");
  assert.match(env.version ?? "", /git version/);
});

// Daemon-host availability remains officially unverified (supplemental
// research 2026-10-31); this self-check only evidences the local dev host.
