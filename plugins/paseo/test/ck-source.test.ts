import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { acquireCkSource, CK_PIN, CK_URL, ckDestination } from "../server/ck-source";
import { realRunner, type Runner } from "../server/orchestrator";

const source = "/Users/vincent4j/Tools/Source/context-keeper";

test("fixed CK Git acquisition uses a local pin fixture without network, reuses clean source and preserves foreign destination", { timeout: 60_000 }, () => run());
async function run() {
  // Explicit prerequisite: no substitute pin and no remote fallback.
  execFileSync("git", ["-C", source, "cat-file", "-e", CK_PIN + "^{commit}"]);
  const raw = fs.mkdtempSync(new URL("./ck-acquisition-", import.meta.url).pathname);
  const home = fs.realpathSync(raw);
  const base = realRunner(home);
  let fetches = 0;
  const runner: Runner = { async run(argv, options) {
    const actual = [...argv];
    const fetch = actual.indexOf("fetch");
    if (fetch >= 0) {
      assert.equal(actual[fetch + 3], "origin");
      assert.equal(actual[fetch + 4], CK_PIN);
      actual[fetch + 3] = source; // only the test runner replaces transport
      fetches++;
    }
    return base.run(actual, options);
  } };
  try {
    const dest = await acquireCkSource(home, "git", runner);
    assert.equal(dest, ckDestination(home));
    assert.equal(execFileSync("git", ["-C", dest, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(), CK_PIN);
    assert.equal(execFileSync("git", ["-C", dest, "remote", "get-url", "origin"], { encoding: "utf8" }).trim(), CK_URL);
    assert.equal(fetches, 1);
    await acquireCkSource(home, "git", runner);
    assert.equal(fetches, 1, "clean source should be reused without network");
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
