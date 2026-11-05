import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { acquireCkSource, CK_URL, ckDestination, ckAcquisitionPlan } from "../server/ck-source";
import { realRunner, type Runner } from "../server/orchestrator";



test("Context Keeper fetches advancing main with a local remote and preserves foreign destination", { timeout: 60_000 }, () => run());
async function run() {
  const raw = fs.mkdtempSync(new URL("./ck-acquisition-", import.meta.url).pathname);
  const home = fs.realpathSync(raw);
  const source = path.join(home, "upstream"); fs.mkdirSync(source);
  const git = (...args: string[]) => execFileSync("git", ["-C", source, ...args], { encoding: "utf8" }).trim();
  git("init", "-b", "main");
  fs.writeFileSync(path.join(source, "SKILL.md"), "first"); git("add", ".");
  git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "first");
  let head = git("rev-parse", "HEAD");
  const base = realRunner(home);
  let fetches = 0;
  const runner: Runner = { async run(argv, options) {
    const actual = [...argv];
    const fetch = actual.indexOf("fetch");
    if (fetch >= 0) {
      assert.equal(actual[fetch + 2], "origin");
      assert.equal(actual[fetch + 3], "+refs/heads/main:refs/remotes/origin/main");
      actual[fetch + 2] = source; // only the test runner replaces transport
      fetches++;
    }
    return base.run(actual, options);
  } };
  try {
    const dest = await acquireCkSource(home, "git", runner);
    assert.equal(dest, ckDestination(home));
    assert.equal(execFileSync("git", ["-C", dest, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(), head);
    assert.equal(execFileSync("git", ["-C", dest, "remote", "get-url", "origin"], { encoding: "utf8" }).trim(), CK_URL);
    assert.equal(fetches, 1);
    fs.writeFileSync(path.join(source, "SKILL.md"), "second"); git("add", ".");
    git("-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-m", "second");
    head = git("rev-parse", "HEAD");
    await acquireCkSource(home, "git", runner);
    assert.equal(fetches, 2, "each install must fetch current main");
    assert.equal(execFileSync("git", ["-C", dest, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(), head);
    const offline: Runner = { async run(argv, options) {
      if (argv.includes("fetch")) throw new Error("offline");
      return runner.run(argv, options);
    } };
    await assert.rejects(acquireCkSource(home, "git", offline), /offline/);
    assert.equal(execFileSync("git", ["-C", dest, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(), head);
    execFileSync("git", ["-C", dest, "update-index", "--assume-unchanged", "SKILL.md"]);
    fs.writeFileSync(path.join(dest, "SKILL.md"), "hidden private edit");
    await assert.rejects(acquireCkSource(home, "git", runner), /drift/);
    assert.equal(fs.readFileSync(path.join(dest, "SKILL.md"), "utf8"), "hidden private edit");
    fs.writeFileSync(path.join(dest, "SKILL.md"), "second");
    fs.writeFileSync(path.join(dest, "PRIVATE"), "keep me");
    await assert.rejects(acquireCkSource(home, "git", runner), /drift/);
    assert.equal(fs.readFileSync(path.join(dest, "PRIVATE"), "utf8"), "keep me");
    fs.mkdirSync(dest + ".lock");
    await assert.rejects(acquireCkSource(home, "git", runner), /EEXIST/);
    assert.ok(fs.existsSync(dest + ".lock"));
  } finally { fs.rmSync(home, { recursive: true, force: true }); }
}

test("CK source parent symlink is rejected before foreign writes or Git execution", async () => {
  for (const relative of [".local", ".local/share", ".local/share/context-keeper-sources"]) {
    const raw = fs.mkdtempSync(new URL("./ck-path-", import.meta.url).pathname);
    const home = fs.realpathSync(raw);
    try {
      const foreign = path.join(home, "foreign");
      fs.mkdirSync(foreign, { mode: 0o750 });
      fs.writeFileSync(path.join(foreign, "PRIVATE"), "keep", { mode: 0o640 });
      const before = [fs.statSync(foreign).mode, fs.statSync(foreign).mtimeMs, fs.statSync(path.join(foreign, "PRIVATE")).mode];
      const link = path.join(home, relative);
      fs.mkdirSync(path.dirname(link), { recursive: true });
      fs.symlinkSync(foreign, link);
      let calls = 0;
      const runner: Runner = { async run() { calls++; throw new Error("unexpected Git"); } };
      await assert.rejects(acquireCkSource(home, "git", runner), /unsafe directory ancestor/);
      assert.equal(calls, 0);
      assert.deepEqual(fs.readdirSync(foreign), ["PRIVATE"]);
      assert.equal(fs.readFileSync(path.join(foreign, "PRIVATE"), "utf8"), "keep");
      assert.deepEqual([fs.statSync(foreign).mode, fs.statSync(foreign).mtimeMs, fs.statSync(path.join(foreign, "PRIVATE")).mode], before);
    } finally { fs.rmSync(home, { recursive: true, force: true }); }
  }
});


test("CK acquisition declares all six supported hosts", () => {
  assert.deepEqual(ckAcquisitionPlan("/Users/fixture").agents,
    ["codex", "claude", "workbuddy", "zcode", "dsh", "opencode"]);
});
