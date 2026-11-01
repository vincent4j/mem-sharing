// Paseo 0.13.2 evaluates server bundles as CJS without a plugin filename or
// cwd. Its public context has no self-path. Consume only config.plugins from
// the supported daemon config API; managed Git installs also publish their
// final plugin subdirectory here. RPC input/env/cwd/import.meta are not sources.
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

export interface HostPluginRecord {
  /** 真实安装 ID(config.plugins 键,非包身份 EXPECTED_PLUGIN_ID)。 */
  readonly id: string;
  /** 宿主来源类型,仅原样透传精确值(如 directory),不猜。 */
  readonly source: string;
  /** 规范绝对路径(等于被匹配的 source_dir)。 */
  readonly path: string;
  readonly enabled?: boolean;
}
export interface PluginDirResolution {
  readonly dir: string | null;
  readonly searched: readonly string[];
  /** 与本次选中目录匹配的全部 config alias 记录(同物理目录可多别名)。 */
  readonly records: readonly HostPluginRecord[];
}
export type PluginSources = Readonly<Record<string, { source: string; path: string; enabled?: boolean }>>;

interface Match {
  readonly dir: string;
  readonly inode: number;
  readonly device: number;
  readonly records: readonly HostPluginRecord[];
}
// Package identity is fixed in source, independent of the user-selected CLI --id.
const EXPECTED_PLUGIN_ID = "memsharing";
const hash = (bytes: Buffer): string => createHash("sha256").update(bytes).digest("hex");

function completePayload(dir: string, digest: string): boolean {
  const pluginManifest = path.join(dir, "paseo-plugin.json");
  const payload = path.join(dir, "payload");
  const release = path.join(payload, "release.json");
  if (!fs.lstatSync(pluginManifest).isFile() || !fs.lstatSync(payload).isDirectory() || !fs.lstatSync(release).isFile()) return false;
  const plugin = JSON.parse(fs.readFileSync(pluginManifest, "utf8"));
  if (plugin.id !== EXPECTED_PLUGIN_ID) return false;
  const raw = fs.readFileSync(release);
  if (hash(raw) !== digest) return false;
  const manifest = JSON.parse(raw.toString("utf8"));
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) return false;
  const expected = new Map<string, { mode: number; sha256: string }>();
  for (const file of manifest.files) {
    if (typeof file.path !== "string" || file.path.split("/").some((part: string) => !part || part === "." || part === "..") || file.path.includes("\\") || path.isAbsolute(file.path) || expected.has(file.path) || !Number.isInteger(file.mode) || !/^[a-f0-9]{64}$/.test(file.sha256)) return false;
    expected.set(file.path, file);
  }
  let count = 0;
  const walk = (directory: string, prefix: string): boolean => {
    if (!fs.lstatSync(directory).isDirectory()) return false;
    for (const name of fs.readdirSync(directory)) {
      const relative = prefix ? `${prefix}/${name}` : name;
      const absolute = path.join(directory, name);
      const info = fs.lstatSync(absolute);
      if (info.isDirectory()) { if (!walk(absolute, relative)) return false; }
      else {
        const file = expected.get(relative);
        if (!info.isFile() || !file || (info.mode & 0o7777) !== file.mode || hash(fs.readFileSync(absolute)) !== file.sha256) return false;
        count++;
      }
    }
    return true;
  };
  return walk(path.join(payload, "core"), "") && count === expected.size;
}

// A physical source may have multiple configured aliases. Distinct matching
// directories are ambiguous. Once a runtime has been constructed, every RPC
// must observe the same selection/inode/digest; pending approvals are never
// transferred to a newly constructed Orchestrator.
export class HostPayloadBinding<T> {
  private selection: string | undefined;
  private invalidated = false;
  private instance: T | undefined;
  private readonly environment: string;
  private readonly manifestSha256: string;
  private readonly create: (resolution: PluginDirResolution) => T;
  private readonly readEnvironment: () => string;

  constructor(
    manifestSha256: string,
    create: (resolution: PluginDirResolution) => T,
    readEnvironment: () => string = () => JSON.stringify([process.env.HOME, process.env.PASEO_HOME, process.env.MEMSHARING_PLUGIN_DIR]),
  ) {
    this.manifestSha256 = manifestSha256;
    this.create = create;
    this.readEnvironment = readEnvironment;
    this.environment = readEnvironment();
  }

  invalidate(): void { this.invalidated = true; }

  get(sources: PluginSources | undefined): T {
    if (this.environment !== this.readEnvironment()) this.invalidate();
    if (this.invalidated) throw new Error("plugin_source_changed: reload before creating a new approval");
    const searched: string[] = [];
    const matches = new Map<string, Match>();
    if (/^[a-f0-9]{64}$/.test(this.manifestSha256)) {
      for (const [id, source] of Object.entries(sources ?? {}).sort(([a], [b]) => a.localeCompare(b))) {
        if (source.source !== "directory" || source.enabled === false || !path.isAbsolute(source.path)) continue;
        searched.push(source.path);
        try {
          const dir = fs.realpathSync(source.path);
          const info = fs.statSync(dir);
          if (!info.isDirectory() || !completePayload(dir, this.manifestSha256)) continue;
          const previous = matches.get(dir);
          matches.set(dir, { dir, inode: info.ino, device: info.dev,
            records: [...(previous?.records ?? []), { id, source: source.source, path: source.path, enabled: source.enabled }] });
        } catch { /* Not this compiled release; retain no unrelated file contents. */ }
      }
    }
    if (matches.size > 1) {
      if (this.selection !== undefined) this.invalidate();
      throw new Error("plugin_source_ambiguous: multiple configured sources match this compiled release");
    }
    const match = [...matches.values()][0] ?? null;
    const selection = JSON.stringify(match);
    if (this.selection !== undefined) {
      if (selection !== this.selection) {
        this.invalidate();
        throw new Error("plugin_source_changed: reload before creating a new approval");
      }
      return this.instance as T;
    }
    this.instance = this.create({ dir: match?.dir ?? null, searched, records: match?.records ?? [] });
    this.selection = selection;
    return this.instance;
  }
}
