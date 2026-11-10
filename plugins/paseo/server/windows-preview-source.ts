import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import type { PluginSources } from "./payload";

export const PREVIEW_FILES = [
  "scripts/windows_preview.py", "scripts/agm_core/__init__.py", "scripts/agm_core/entries.py",
  "scripts/agm_core/transaction.py", "scripts/agm_core/windows_preview.py",
  "scripts/agm_core/windows_native.py", "scripts/agm_core/platform_diagnostics.py", "scripts/agm_core/paths.py",
] as const;
const sha = (raw: Buffer) => createHash("sha256").update(raw).digest("hex");

// Unlike the production payload, the standalone preview has a byte/size
// manifest. Windows ACL/reparse admission remains the native kernel's job;
// POSIX modes are neither skipped from that contract nor invented on NTFS.
export function verifyPreviewSource(plugin: string, expected: string): string {
  if (!/^[a-f0-9]{64}$/.test(expected)) throw new Error("windows_preview_identity_missing");
  const source = path.join(plugin, "windows-preview");
  for (const leaf of [plugin, source]) {
    if (!fs.lstatSync(leaf).isDirectory() || fs.lstatSync(leaf).isSymbolicLink()) throw new Error("preview_source_unsafe");
  }
  if (JSON.parse(fs.readFileSync(path.join(plugin, "paseo-plugin.json"), "utf8")).id !== "memsharing") throw new Error("preview_plugin_identity");
  const raw = fs.readFileSync(path.join(source, "preview-manifest.json"));
  if (sha(raw) !== expected) throw new Error("preview_manifest_drift");
  const manifest = JSON.parse(raw.toString("utf8"));
  const names = [...PREVIEW_FILES, "INSTALL.md"].sort();
  if (manifest.schema !== "memsharing-windows-preview-package-1" || manifest.repository !== "https://github.com/vincent4j/mem-sharing"
    || manifest.channel !== "windows-preview" || manifest.entrypoint !== "scripts/windows_preview.py"
    || JSON.stringify(manifest.clients) !== '["zcode","workbuddy"]' || manifest.general_windows_support !== false
    || manifest.upgrade_or_migration !== false || !/^[a-f0-9]{40}$|^[a-f0-9]{64}$/.test(manifest.preview_revision)
    || JSON.stringify(Object.keys(manifest.files).sort()) !== JSON.stringify(names)) throw new Error("preview_scope_invalid");
  const expectedFiles = new Set([...names, "preview-manifest.json"]);
  const walk = (dir: string, prefix = "") => {
    for (const name of fs.readdirSync(dir)) {
      const relative = prefix + name, file = path.join(dir, name), st = fs.lstatSync(file);
      if (st.isSymbolicLink()) throw new Error("preview_source_link");
      if (st.isDirectory()) {
        if (![...expectedFiles].some(n => n.startsWith(relative + "/"))) throw new Error("preview_extra_directory");
        walk(file, relative + "/");
      } else {
        if (!st.isFile() || st.nlink !== 1 || !expectedFiles.delete(relative)) throw new Error("preview_extra_or_unsafe_file");
        if (relative !== "preview-manifest.json") {
          const bytes = fs.readFileSync(file), meta = manifest.files[relative];
          if (meta.size !== bytes.length || meta.sha256 !== sha(bytes)) throw new Error("preview_source_drift");
        }
      }
    }
  };
  walk(source);
  if (expectedFiles.size) throw new Error("preview_source_incomplete");
  return source;
}

// Once selected, any config, inode or byte drift permanently invalidates
// this worker. Restoring files never revives a pending confirmation token.
export class WindowsPreviewBinding {
  private bound?: string;
  private invalid = false;
  private readonly digest: string;
  constructor(digest: string) { this.digest = digest; }
  invalidate() { this.invalid = true; }
  get(sources: PluginSources | undefined): string {
    if (this.invalid) throw new Error("preview_source_changed_reload_required");
    try {
      const matches = Object.entries(sources ?? {}).flatMap(([id, record]) => {
        if (record.source !== "directory" || record.enabled === false || !path.isAbsolute(record.path)) return [];
        try {
          const plugin = fs.realpathSync(record.path);
          const source = verifyPreviewSource(plugin, this.digest), st = fs.lstatSync(plugin), sourceStat = fs.lstatSync(source);
          return [{ id, path: record.path, plugin, source, dev: st.dev, ino: st.ino, sourceDev: sourceStat.dev, sourceIno: sourceStat.ino }];
        } catch { return []; }
      });
      if (matches.length !== 1) throw new Error("windows_preview_source_missing_or_ambiguous");
      const scene = JSON.stringify(matches);
      if (this.bound && this.bound !== scene) throw new Error("preview_source_changed");
      this.bound = scene;
      return matches[0].source;
    } catch (error) { this.invalid = true; throw error; }
  }
}
