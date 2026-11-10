import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { WindowsPreviewBinding, verifyPreviewSource, PREVIEW_FILES } from "../server/windows-preview-source";
import { WindowsPreviewHost } from "../server/windows-preview";
import { runProcess, type RunProcessOptions } from "../server/shared/common/process";
import contribute from "../index.server";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const hash = (raw: Buffer) => createHash("sha256").update(raw).digest("hex");
function fixture() {
  const area = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-win-plugin-")));
  const plugin = path.join(area, "plugin"), source = path.join(plugin, "windows-preview"), home = path.join(area, "home");
  fs.mkdirSync(home); fs.mkdirSync(source, { recursive: true });
  fs.writeFileSync(path.join(plugin, "paseo-plugin.json"), '{"id":"memsharing"}');
  const files: Record<string, { size: number; sha256: string }> = {};
  for (const relative of [...PREVIEW_FILES, "INSTALL.md"]) {
    const raw = relative === "INSTALL.md" ? Buffer.from("synthetic preview guide") : fs.readFileSync(path.join(ROOT, relative));
    const file = path.join(source, relative); fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, raw);
    files[relative] = { size: raw.length, sha256: hash(raw) };
  }
  const manifest = Buffer.from(JSON.stringify({ schema: "memsharing-windows-preview-package-1", repository: "https://github.com/vincent4j/mem-sharing",
    channel: "windows-preview", entrypoint: "scripts/windows_preview.py", core_version: "0.1.11", preview_revision: "a".repeat(40),
    clients: ["zcode", "workbuddy"], general_windows_support: false, upgrade_or_migration: false, files }));
  fs.writeFileSync(path.join(source, "preview-manifest.json"), manifest);
  const digest = hash(manifest), sources = { memsharing: { source: "directory" as const, path: plugin } };
  return { area, home, plugin, source, digest, sources, close: () => fs.rmSync(area, { recursive: true, force: true }) };
}

test("preview package binding rejects missing identities, duplicates, byte drift and source resurrection", () => {
  const f = fixture();
  try {
    assert.throws(() => verifyPreviewSource(f.plugin, ""), /identity_missing/);
    const binding = new WindowsPreviewBinding(f.digest);
    assert.equal(binding.get(f.sources), f.source);
    assert.throws(() => new WindowsPreviewBinding(f.digest).get({ ...f.sources, alias: f.sources.memsharing }), /ambiguous/);
    const file = path.join(f.source, PREVIEW_FILES[0]), before = fs.readFileSync(file);
    fs.appendFileSync(file, "foreign");
    assert.throws(() => binding.get(f.sources));
    fs.writeFileSync(file, before);
    assert.throws(() => binding.get(f.sources), /reload_required/);
    assert.equal(new WindowsPreviewBinding(f.digest).get(f.sources), f.source);
    fs.writeFileSync(path.join(f.source, "extra"), "foreign");
    assert.throws(() => verifyPreviewSource(f.plugin, f.digest), /extra/);
  } finally { f.close(); }
});

test("preview binding rejects links, hardlinks, disabled records and noncanonical extra directories", () => {
  for (const mode of ["link", "hardlink", "directory", "disabled"] as const) {
    const f = fixture();
    try {
      if (mode === "link") {
        const leaf = path.join(f.source, PREVIEW_FILES[0]); fs.renameSync(leaf, path.join(f.area, "saved")); fs.symlinkSync(path.join(f.area, "saved"), leaf);
      }
      if (mode === "hardlink") fs.linkSync(path.join(f.source, PREVIEW_FILES[0]), path.join(f.area, "hardlink"));
      if (mode === "directory") fs.mkdirSync(path.join(f.source, "unexpected"));
      assert.throws(() => new WindowsPreviewBinding(f.digest).get(mode === "disabled" ? { memsharing: { ...f.sources.memsharing, enabled: false } } : f.sources));
    } finally { f.close(); }
  }
});

test("Windows daemon exposes its preview mode and closes production RPCs before reading config", async () => {
  const previous = Object.getOwnPropertyDescriptor(process, "platform")!;
  Object.defineProperty(process, "platform", { ...previous, value: "win32" });
  const handlers = new Map<string, Function>();
  const cleanup = contribute({ handle(contract: { name: string }, handler: Function) { handlers.set(contract.name, handler); } } as never);
  try {
    const mode = await handlers.get("memsharing.host.platform")!({}, {});
    assert.deepEqual(mode, { platform: "win32", mode: "windows-preview" });
    let reads = 0;
    const context = { paseo: { config: { get: async () => { reads++; throw new Error("DUMMY_SECRET_NEVER_RETURN"); } } } };
    for (const name of ["memsharing.bootstrap.preview", "memsharing.env.status", "memsharing.fusion.preview"]) {
      await assert.rejects(handlers.get(name)!({}, context), /production_host_unsupported/);
    }
    assert.equal(reads, 0);
    await assert.rejects(handlers.get("memsharing.windows-preview.status")!({}, context), error => {
      assert(!String(error).includes("DUMMY_SECRET")); return /source_unavailable/.test(String(error));
    });
  } finally { cleanup(); Object.defineProperty(process, "platform", previous); }
});

// This is POSIX file/transaction integration, with only the OS admission
// values simulated. It deliberately does NOT establish Win32/Paseo acceptance.
function syntheticHost(f: ReturnType<typeof fixture>, overrides: { now?: () => number; run?: (opts: RunProcessOptions) => ReturnType<typeof runProcess> } = {}) {
  const python = execFileSync("python3", ["-c", "import sys;print(sys.executable)"], { encoding: "utf8" }).trim();
  const captured: RunProcessOptions[] = [];
  const host = new WindowsPreviewHost({ home: f.home, source: () => verifyPreviewSource(f.plugin, f.digest), platform: "win32", now: overrides.now,
    python: async () => ({ status: "ready", selected: { origin: "system", path: python, status: "ready" }, candidates: [], evidence: "synthetic POSIX host" }),
    run: async opts => {
      captured.push(opts);
      if (overrides.run) return overrides.run(opts);
      const argv = [...opts.argv];
      const program = argv.indexOf("-c") + 1;
      argv[program] = "import sys,platform,types,tempfile,shutil,subprocess\nsys.platform='win32'\nsys.getwindowsversion=lambda:types.SimpleNamespace(build=22631)\nplatform.machine=lambda:'AMD64'\n" + argv[program];
      const result = await runProcess({ ...opts, argv });
      if (result.kind === "completed" && !result.stdout) assert.fail(result.stderr);
      return result;
    } });
  return { host, captured };
}

test("real preview kernel via stdin: preview/reject/install/add/drift/exit preserves original bytes and exports public text", async () => {
  const f = fixture();
  try {
    const original = Buffer.from("\ufeff私人内容\r\n", "utf8");
    for (const native of [".zcode/AGENTS.md", ".workbuddy/MEMORY.md"]) {
      fs.mkdirSync(path.dirname(path.join(f.home, native)), { recursive: true }); fs.writeFileSync(path.join(f.home, native), original);
    }
    const { host, captured } = syntheticHost(f);
    const initial = await host.status(); assert.equal(initial.status, "not_installed", JSON.stringify(initial));
    const rejected = await host.preview("install"); assert.equal(rejected.status, "approval_required");
    assert(!JSON.stringify(rejected).includes(original.toString("hex")));
    assert.equal(fs.existsSync(path.join(f.home, ".mem-sharing")), false);
    assert.equal(host.cancel().status, "rejected");
    assert.equal((await host.confirm(String(rejected.confirmationToken))).status, "failed");
    const install = await host.preview("install"); assert.equal(install.status, "approval_required", JSON.stringify(install));
    assert.equal((await host.confirm(String(install.confirmationToken))).status, "committed");
    assert.equal((await host.confirm(String(install.confirmationToken))).status, "failed");
    assert.equal((await host.status()).status, "installed");
    const add = await host.preview("add", "显式新增：两端共用 $() `echo` 中文"); assert.equal(add.status, "approval_required");
    assert.equal((await host.confirm(String(add.confirmationToken))).status, "committed");
    assert(captured.every(c => !c.argv.join(" ").includes("显式新增")));
    const publicPath = path.join(f.home, ".mem-sharing/memories/MEMORY.md");
    const fresh = await host.preview("add", "不应写入");
    fs.appendFileSync(publicPath, "\n外部保留\n");
    assert.equal((await host.confirm(String(fresh.confirmationToken))).status, "failed");
    const publicBefore = fs.readFileSync(publicPath);
    const exit = await host.preview("exit"); assert.equal(exit.status, "approval_required", JSON.stringify(exit));
    const done = await host.confirm(String(exit.confirmationToken)); assert.equal(done.status, "committed", JSON.stringify(done));
    assert.deepEqual(fs.readFileSync(String((done.export as Record<string, unknown>).path)), publicBefore);
    for (const native of [".zcode/AGENTS.md", ".workbuddy/MEMORY.md"]) assert.deepEqual(fs.readFileSync(path.join(f.home, native)), original);
    assert.equal(fs.existsSync(publicPath), false);
  } finally { f.close(); }
});

test("tokens expire, source changes reject, and ambiguous execution results block further writes", async () => {
  const f = fixture();
  try {
    let now = 0; const { host } = syntheticHost(f, { now: () => now });
    const plan = await host.preview("install"); now = 11 * 60_000;
    assert.equal((await host.confirm(String(plan.confirmationToken))).status, "failed");
    assert.equal(fs.existsSync(path.join(f.home, ".mem-sharing")), false);
    const changed = await host.preview("install"); fs.appendFileSync(path.join(f.source, PREVIEW_FILES[0]), "drift");
    assert.equal((await host.confirm(String(changed.confirmationToken))).status, "failed");
  } finally { f.close(); }
  const g = fixture();
  try {
    const real = syntheticHost(g); const plan = await real.host.preview("install");
    let calls = 0;
    const unknown = syntheticHost(g, { run: async () => ++calls === 1
      ? { kind: "completed", exitCode: 0, stdout: JSON.stringify({ status: "approval_required", plan: { home: g.home, operations: [] }, digest: "a".repeat(64) }), stderr: "", stdoutTruncated: false, stderrTruncated: false }
      : { kind: "timeout", partialStdout: "", partialStderr: "" } });
    const pending = await unknown.host.preview("install");
    assert.equal((await unknown.host.confirm(String(pending.confirmationToken))).status, "unknown");
    assert.equal((await unknown.host.preview("install")).status, "failed");
    assert.equal(calls, 2);
    assert.equal((await unknown.host.confirm(String(plan.confirmationToken))).status, "failed");
  } finally { g.close(); }
});
