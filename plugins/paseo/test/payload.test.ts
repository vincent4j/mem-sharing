import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { HostPayloadBinding } from "../server/payload";

function fixture() {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-host-payload-")));
  const bytes = Buffer.from("# synthetic fixture, no executable business\n");
  const raw = JSON.stringify({ files: [{ path: "scripts/install.py", mode: 0o644, sha256: createHash("sha256").update(bytes).digest("hex") }] });
  const digest = createHash("sha256").update(raw).digest("hex");
  function plugin(relative: string) {
    const dir = path.join(root, relative);
    fs.mkdirSync(path.join(dir, "payload/core/scripts"), { recursive: true });
    fs.writeFileSync(path.join(dir, "paseo-plugin.json"), JSON.stringify({ id: "memsharing" }));
    fs.writeFileSync(path.join(dir, "payload/release.json"), raw);
    fs.writeFileSync(path.join(dir, "payload/core/scripts/install.py"), bytes, { mode: 0o644 });
    return dir;
  }
  const sources = (dir: string) => ({ synthetic: { source: "directory", path: dir } });
  return { root, digest, plugin, sources, close: () => fs.rmSync(root, { recursive: true, force: true }) };
}

test("host source binding works for directory and Git subdirectory layouts without ambient paths", () => {
  const f = fixture();
  try {
    for (const layout of ["directory", "managed/uuid/checkout/plugins/paseo"]) {
      const dir = f.plugin(layout);
      let calls = 0;
      const binding = new HostPayloadBinding(f.digest, resolution => ({ ...resolution, serial: ++calls }), () => "fixed-host");
      const first = binding.get(f.sources(dir));
      assert.equal(first.dir, dir);
      assert.strictEqual(binding.get(f.sources(dir)), first);
      assert.equal(calls, 1);
    }
  } finally { f.close(); }
});

test("disabled, absent, relative and wrong-digest sources never become payload roots", () => {
  const f = fixture();
  try {
    const dir = f.plugin("plugin");
    for (const sources of [undefined, {}, { x: { source: "directory", path: dir, enabled: false } }, { x: { source: "directory", path: "relative" } }]) {
      assert.equal(new HostPayloadBinding(f.digest, r => r).get(sources).dir, null);
    }
    assert.equal(new HostPayloadBinding("f".repeat(64), r => r).get(f.sources(dir)).dir, null);
    assert.equal(new HostPayloadBinding("", r => r).get(f.sources(dir)).dir, null);
  } finally { f.close(); }
});

test("canonical aliases deduplicate; different physical matching roots fail closed", () => {
  const f = fixture();
  try {
    const a = f.plugin("a"); const b = f.plugin("b"); const alias = path.join(f.root, "alias");
    fs.symlinkSync(a, alias);
    const binding = new HostPayloadBinding(f.digest, r => r);
    assert.equal(binding.get({ ...f.sources(a), alias: { source: "directory", path: alias } }).dir, a);
    assert.throws(() => new HostPayloadBinding(f.digest, r => r).get({ ...f.sources(a), other: { source: "directory", path: b } }), /plugin_source_ambiguous/);
  } finally { f.close(); }
});

test("source drift rejects before consuming a pending one-use token and never rebuilds runtime", () => {
  const f = fixture();
  try {
    const a = f.plugin("a"); const b = f.plugin("b"); let creates = 0;
    const binding = new HostPayloadBinding(f.digest, () => {
      creates++;
      const pending = new Set(["approved-token"]);
      return { confirm(token: string) { assert(pending.delete(token)); return "executed"; } };
    });
    const first = binding.get(f.sources(a));
    assert.throws(() => binding.get(f.sources(b)).confirm("approved-token"), /plugin_source_changed/);
    assert.throws(() => binding.get({}).confirm("approved-token"), /plugin_source_changed/);
    assert.throws(() => binding.get(f.sources(a)).confirm("approved-token"), /plugin_source_changed/);
    // Restoring the old source does not revive an earlier approval.
    const stable = new HostPayloadBinding(f.digest, () => first);
    assert.equal(stable.get(f.sources(a)).confirm("approved-token"), "executed");
    assert.throws(() => stable.get(f.sources(a)).confirm("approved-token"));
    assert.equal(creates, 1);
  } finally { f.close(); }
});

test("manifest/core bytes, modes, links, extras and replaced directory invalidate the binding", () => {
  const f = fixture();
  try {
    for (const tamper of ["manifest", "bytes", "mode", "link", "extra", "replace"] as const) {
      const dir = f.plugin(tamper); const installer = path.join(dir, "payload/core/scripts/install.py");
      const binding = new HostPayloadBinding(f.digest, r => r); assert.equal(binding.get(f.sources(dir)).dir, dir);
      if (tamper === "manifest") fs.appendFileSync(path.join(dir, "payload/release.json"), "\n");
      if (tamper === "bytes") fs.appendFileSync(installer, "drift");
      if (tamper === "mode") fs.chmodSync(installer, 0o600);
      if (tamper === "link") { fs.renameSync(installer, installer + ".saved"); fs.symlinkSync(installer + ".saved", installer); }
      if (tamper === "extra") fs.writeFileSync(path.join(dir, "payload/core/foreign"), "extra");
      if (tamper === "replace") { fs.renameSync(dir, dir + ".old"); f.plugin(tamper); }
      assert.throws(() => binding.get(f.sources(dir)), /plugin_source_changed/);
    }
  } finally { f.close(); }
});

test("ambient runtime environment changes invalidate earlier binding without adopting a new instance", () => {
  const f = fixture();
  try {
    let env = "first"; let calls = 0; const dir = f.plugin("plugin");
    const binding = new HostPayloadBinding(f.digest, r => { calls++; return r; }, () => env);
    binding.get(f.sources(dir)); env = "changed";
    assert.throws(() => binding.get(f.sources(dir)), /plugin_source_changed/); assert.equal(calls, 1);
  } finally { f.close(); }
});


test("another plugin with the same core payload is neither selected nor an ambiguity", () => {
  const f = fixture();
  try {
    const own = f.plugin("own"); const foreign = f.plugin("foreign");
    fs.writeFileSync(path.join(foreign, "paseo-plugin.json"), JSON.stringify({ id: "another-plugin" }));
    assert.equal(new HostPayloadBinding(f.digest, r => r).get(f.sources(foreign)).dir, null);
    const binding = new HostPayloadBinding(f.digest, r => r);
    const sources = { arbitraryRuntimeAlias: { source: "directory", path: own }, another: { source: "directory", path: foreign } };
    // The config key is a runtime alias, not the fixed source package ID.
    assert.equal(binding.get(sources).dir, own);
    assert.equal(binding.get(sources).dir, own);
  } finally { f.close(); }
});

test("selected manifest ID drift permanently closes the binding even when ID is restored", () => {
  const f = fixture();
  try {
    const dir = f.plugin("own"); const binding = new HostPayloadBinding(f.digest, r => r);
    assert.equal(binding.get(f.sources(dir)).dir, dir);
    fs.writeFileSync(path.join(dir, "paseo-plugin.json"), JSON.stringify({ id: "third-plugin" }));
    assert.throws(() => binding.get(f.sources(dir)), /plugin_source_changed/);
    fs.writeFileSync(path.join(dir, "paseo-plugin.json"), JSON.stringify({ id: "memsharing" }));
    assert.throws(() => binding.get(f.sources(dir)), /plugin_source_changed/);
  } finally { f.close(); }
});
