// GENERATED FILE — do not edit by hand.
// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).
// Node-only dependency preparation. No kernel plans or machine policy here.
import fs from "node:fs";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { hostname } from "node:os";
import { downloadVerified } from "./download";
import { extractTarGz } from "./tar";
import { runProcess } from "./process";

export interface ToolAsset {
  readonly tool: "python" | "git";
  readonly id: string;
  readonly arch: "arm64" | "x86_64";
  readonly version: string;
  readonly url: string;
  readonly bytes: number;
  readonly sha256: string;
  readonly treeSha256: string;
  readonly entry: string;
  readonly maxUnpackBytes: number;
  readonly links: Readonly<Record<string, string>>;
  readonly license: string;
  readonly licenseUrls: readonly string[];
  readonly sourceUrls: readonly string[];
  readonly minimumMacos?: string;
  readonly noticeFile?: string;
  readonly disclosure?: string;
  readonly blockedReason?: string;
}

// Validate existing ancestors before any mkdir; never follow foreign symlinks.
export function realDirectory(directory: string, create = false): void {
  if (!path.isAbsolute(directory) || path.resolve(directory) !== directory) throw new Error("absolute canonical directory required");
  const parts = directory.split(path.sep).filter(Boolean);
  let current = path.parse(directory).root;
  for (const part of parts) {
    current = path.join(current, part);
    try {
      const stat = fs.lstatSync(current);
      if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error("unsafe directory ancestor: " + current);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      if (create) fs.mkdirSync(current, { mode: 0o700 });
      else return;
    }
  }
}

export function toolTreeDigest(root: string): string {
  root = fs.realpathSync(root);
  const hash = createHash("sha256");
  const visit = (relative: string): void => {
    const file = path.join(root, relative), stat = fs.lstatSync(file);
    if (stat.isSymbolicLink()) {
      const actual = fs.realpathSync(file);
      if (!actual.startsWith(root + path.sep)) throw new Error("runtime symlink escaped");
      hash.update(JSON.stringify([relative, "link", fs.readlinkSync(file)]) + "\n");
    } else if (stat.isDirectory()) {
      if (relative) hash.update(JSON.stringify([relative, "directory"]) + "\n");
      for (const name of fs.readdirSync(file).sort()) visit(relative ? relative + "/" + name : name);
    } else if (stat.isFile()) {
      hash.update(JSON.stringify([relative, "file", stat.mode & 0o777, createHash("sha256").update(fs.readFileSync(file)).digest("hex")]) + "\n");
    } else throw new Error("special runtime node refused");
  };
  visit("");
  return hash.digest("hex");
}

export function assetDestination(runtimeRoot: string, asset: ToolAsset): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/.test(asset.id) || !["arm64", "x86_64"].includes(asset.arch)) throw new Error("invalid fixed asset identity");
  return path.join(runtimeRoot, asset.id, asset.arch);
}

function sameObject(file: string, original: fs.Stats): boolean {
  try { const now = fs.lstatSync(file); return now.dev === original.dev && now.ino === original.ino && now.isDirectory() && !now.isSymbolicLink(); }
  catch { return false; }
}

function alive(pid: number): boolean {
  try { process.kill(pid, 0); return true; } catch (e) { return (e as NodeJS.ErrnoException).code !== "ESRCH"; }
}

export function assetScene(runtimeRoot: string, asset: ToolAsset): Record<string, unknown> {
  const destination = assetDestination(runtimeRoot, asset);
  realDirectory(path.dirname(destination));
  try {
    const st = fs.lstatSync(destination);
    if (!st.isDirectory() || st.isSymbolicLink() || (process.getuid && st.uid !== process.getuid())) return { state: "conflict", destination };
    const receiptFile = path.join(destination, "asset.json");
    const receiptStat = fs.lstatSync(receiptFile);
    if (!receiptStat.isFile() || receiptStat.isSymbolicLink() || (process.getuid && receiptStat.uid !== process.getuid())) throw new Error("foreign marker");
    const receipt = JSON.parse(fs.readFileSync(receiptFile, "utf8"));
    if (receipt.schema !== 1 || receipt.id !== asset.id || receipt.sha256 !== asset.sha256 || receipt.home !== runtimeRoot || receipt.host !== hostname()) throw new Error("foreign marker");
    const names = fs.readdirSync(destination);
    if (names.some(n => !["asset.json", "payload", "lease.json"].includes(n) && !/^download-[a-f0-9-]+\.tar\.gz(?:\.part-\d+-\d+-[a-f0-9]+)?$/.test(n) && !/^payload\.extract-[A-Za-z0-9]+$/.test(n))) throw new Error("foreign runtime files");
    let lease: Record<string, unknown> | undefined;
    if (names.includes("lease.json")) {
      const ls = fs.lstatSync(path.join(destination, "lease.json"));
      if (!ls.isFile() || ls.isSymbolicLink()) throw new Error("foreign lease");
      const data = JSON.parse(fs.readFileSync(path.join(destination, "lease.json"), "utf8"));
      if (!Number.isSafeInteger(data.pid) || data.pid <= 0 || typeof data.nonce !== "string") throw new Error("invalid lease");
      lease = { pid: data.pid, nonce: data.nonce, active: alive(data.pid), dev: ls.dev, ino: ls.ino };
    }
    let state = "interrupted";
    if (names.includes("payload")) {
      const payload = path.join(destination, "payload");
      realDirectory(payload);
      state = toolTreeDigest(payload) === asset.treeSha256 ? (receipt.verified === true ? "ready" : "probe_required") : "conflict";
    }
    if (names.some(n => n.startsWith("payload.extract-")) && !lease?.active) throw new Error("interrupted extraction staging requires inspection; preserved");
    const retained = names.filter(n => n.startsWith("download-")).sort().map(n => {
      const file = path.join(destination, n), stat = fs.lstatSync(file);
      if (!stat.isFile() || stat.isSymbolicLink()) throw new Error("foreign download artifact");
      return { path: file, bytes: stat.size, dev: stat.dev, ino: stat.ino };
    });
    return { state, destination, dev: st.dev, ino: st.ino, marker: { dev: receiptStat.dev, ino: receiptStat.ino, sha256: createHash("sha256").update(fs.readFileSync(receiptFile)).digest("hex") }, lease, retained };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT" && !fs.existsSync(destination)) return { state: "absent", destination };
    return { state: "conflict", destination };
  }
}

export function toolEnvironment(runtimeRoot: string, git: ToolAsset | undefined): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { PYTHONDONTWRITEBYTECODE: "1", PYTHONNOUSERSITE: "1" };
  if (git && assetScene(runtimeRoot, git).state === "ready") {
    const root = path.join(assetDestination(runtimeRoot, git), "payload");
    Object.assign(env, privateGitEnvironment(root));
  }
  return env;
}

function privateGitEnvironment(root: string): NodeJS.ProcessEnv {
  return { PATH: path.join(root, "bin") + path.delimiter + (process.env.PATH ?? "/usr/bin:/bin"), GIT_EXEC_PATH: path.join(root, "libexec", "git-core"), GIT_TEMPLATE_DIR: path.join(root, "share", "git-core", "templates"), GIT_CONFIG_NOSYSTEM: "1" };
}

export async function probeTool(runtimeRoot: string, asset: ToolAsset, home: string, signal?: AbortSignal): Promise<void> {
  const root = path.join(assetDestination(runtimeRoot, asset), "payload");
  const env: NodeJS.ProcessEnv = { ...process.env, ...(asset.tool === "git" ? privateGitEnvironment(root) : {}), HOME: home, PYTHONHOME: "", PYTHONPATH: "", PYTHONDONTWRITEBYTECODE: "1", GIT_CONFIG_GLOBAL: "/dev/null" };
  const argv = asset.tool === "python"
    ? [path.join(root, asset.entry), "-I", "-B", "-c", "import json,ssl,sqlite3,zlib,hashlib,sys; print(json.dumps({'version':'.'.join(map(str,sys.version_info[:3]))}))"]
    : [path.join(root, asset.entry), "--version"];
  const result = await runProcess({ argv, env, signal, timeoutMs: 15000 });
  if (result.kind !== "completed" || result.exitCode !== 0 || !result.stdout.includes(asset.version)) throw new Error("private " + asset.tool + " probe failed");
  if (asset.tool === "git") {
    const exec = await runProcess({ argv: [path.join(root, asset.entry), "--exec-path"], env, signal, timeoutMs: 5000 });
    if (exec.kind !== "completed" || exec.exitCode !== 0 || exec.stdout.trim() !== env.GIT_EXEC_PATH) throw new Error("Git helper relocation failed");
    for (const helper of ["git-remote-http", "git-remote-https"]) fs.accessSync(path.join(env.GIT_EXEC_PATH!, helper), fs.constants.X_OK);
  }
}

/** Install only a server-held exact asset plan. Retain interrupted evidence;
 * never remove an unknown destination, stale payload, or foreign replacement. */
export async function prepareToolAsset(options: { runtimeRoot: string; home: string; asset: ToolAsset; scene: Record<string, unknown>; signal?: AbortSignal; allowInsecureTransportForTests?: boolean; totalTimeoutMs?: number }): Promise<void> {
  const { runtimeRoot, home, asset } = options;
  const inputSignal = options.signal;
  if (asset.blockedReason) throw new Error("supply_blocked: " + asset.blockedReason);
  if (!options.allowInsecureTransportForTests && !asset.url.startsWith("https://")) throw new Error("https asset required");
  if (inputSignal?.aborted) throw new Error("canceled");
  if (!Number.isSafeInteger(options.totalTimeoutMs ?? 180000) || (options.totalTimeoutMs ?? 180000) <= 0) throw new Error("invalid asset timeout");
  if (JSON.stringify(assetScene(runtimeRoot, asset)) !== JSON.stringify(options.scene)) throw new Error("asset_scene_drift");
  if (options.scene.state === "conflict") throw new Error("foreign_runtime_conflict");
  if ((options.scene.lease as Record<string, unknown> | undefined)?.active) throw new Error("asset_busy");
  const destination = assetDestination(runtimeRoot, asset);
  realDirectory(path.dirname(destination), true);
  let owned: fs.Stats;
  if (options.scene.state === "absent") {
    fs.mkdirSync(destination, { mode: 0o700 });
    owned = fs.lstatSync(destination);
    if (!sameObject(destination, owned)) throw new Error("runtime_destination_drift");
    fs.writeFileSync(path.join(destination, "asset.json"), JSON.stringify({ schema: 1, id: asset.id, sha256: asset.sha256, home: runtimeRoot, host: hostname() }), { flag: "wx", mode: 0o600 });
    if (!sameObject(destination, owned)) throw new Error("runtime_destination_drift");
  } else {
    owned = fs.lstatSync(destination);
    if (owned.dev !== options.scene.dev || owned.ino !== options.scene.ino) throw new Error("runtime_destination_drift");
  }
  const markerFile = path.join(destination, "asset.json");
  const markerStat = fs.lstatSync(markerFile), markerBytes = fs.readFileSync(markerFile);
  const lease = path.join(destination, "lease.json");
  const previous = options.scene.lease as Record<string, unknown> | undefined;
  if (previous) {
    const st = fs.lstatSync(lease);
    if (st.dev !== previous.dev || st.ino !== previous.ino || alive(Number(previous.pid))) throw new Error("lease_drift");
    fs.unlinkSync(lease);
  }
  const fd = fs.openSync(lease, "wx", 0o600);
  const leaseStat = fs.fstatSync(fd);
  fs.writeFileSync(fd, JSON.stringify({ pid: process.pid, nonce: randomUUID() }));
  fs.closeSync(fd);
  const controller = new AbortController(), signal = controller.signal;
  const onAbort = () => controller.abort();
  inputSignal?.addEventListener("abort", onAbort, { once: true });
  if (inputSignal?.aborted) controller.abort();
  let timedOut = false;
  const timer = setTimeout(() => { if (!signal.aborted) { timedOut = true; controller.abort(); } }, options.totalTimeoutMs ?? 180000);
  const recheck = () => {
    if (!sameObject(destination, owned)) throw new Error("runtime_destination_drift");
    realDirectory(destination);
    const st = fs.lstatSync(lease);
    if (st.dev !== leaseStat.dev || st.ino !== leaseStat.ino) throw new Error("lease_drift");
    const marker = fs.lstatSync(markerFile);
    if (marker.dev !== markerStat.dev || marker.ino !== markerStat.ino || marker.isSymbolicLink() || !fs.readFileSync(markerFile).equals(markerBytes)) throw new Error("marker_drift");
    if (signal?.aborted) throw new Error("canceled");
  };
  try {
    recheck();
    // Lock acquisition is not permission to use a stale scene. Recompute
    // contents under our exclusive lease before executing any private tool.
    const locked = assetScene(runtimeRoot, asset);
    if (locked.state === "conflict" || locked.dev !== owned.dev || locked.ino !== owned.ino || (options.scene.state !== "absent" && (locked.state !== options.scene.state || JSON.stringify(locked.marker) !== JSON.stringify(options.scene.marker)))) throw new Error("asset_scene_drift_under_lock");
    if (options.scene.state !== "ready" && options.scene.state !== "probe_required") {
      const archive = path.join(destination, "download-" + randomUUID() + ".tar.gz");
      const result = await downloadVerified({ url: asset.url, expectedSha256: asset.sha256, maxBytes: asset.bytes, stagingPath: archive, signal, timeoutMs: 60000, allowInsecureTransportForTests: options.allowInsecureTransportForTests });
      if (result.kind !== "ok") throw new Error(result.code + ": " + result.message);
      if (result.bytes !== asset.bytes) throw new Error("size_mismatch");
      recheck();
      const unpacked = await extractTarGz({ archivePath: archive, destDir: path.join(destination, "payload"), maxBytes: asset.maxUnpackBytes, allowedSymlinks: Object.keys(asset.links), expectedLinks: asset.links, signal });
      if (unpacked.kind !== "ok") throw new Error(unpacked.code + ": " + unpacked.message);
      recheck();
      if (toolTreeDigest(path.join(destination, "payload")) !== asset.treeSha256) throw new Error("runtime_tree_mismatch");
    }
    await probeTool(runtimeRoot, asset, home, signal);
    recheck();
    if (toolTreeDigest(path.join(destination, "payload")) !== asset.treeSha256) throw new Error("runtime_tree_drift");
    // A complete tree alone is not a successful runtime installation.
    // Persist success only after the real probe and the final drift check.
    const markerFd = fs.openSync(markerFile, fs.constants.O_RDWR | fs.constants.O_NOFOLLOW);
    try {
      const bound = fs.fstatSync(markerFd);
      if (bound.dev !== markerStat.dev || bound.ino !== markerStat.ino || !bound.isFile()) throw new Error("marker_drift");
      fs.ftruncateSync(markerFd);
      fs.writeFileSync(markerFd, JSON.stringify({ schema: 1, id: asset.id, sha256: asset.sha256, home: runtimeRoot, host: hostname(), verified: true }));
      fs.fsyncSync(markerFd);
    } finally { fs.closeSync(markerFd); }
  } catch (error) {
    if (timedOut) throw new Error("asset_timeout");
    throw error;
  } finally {
    clearTimeout(timer);
    inputSignal?.removeEventListener("abort", onAbort);
    // Retain downloaded archive/payload for audit and separately approved
    // retry. A replaced lease/directory is left untouched.
    if (sameObject(destination, owned)) {
      try { const st = fs.lstatSync(lease); if (st.dev === leaseStat.dev && st.ino === leaseStat.ino) fs.unlinkSync(lease); } catch { /* preserve foreign evidence */ }
    }
  }
}
