// memSharing Paseo plugin — plugin directory resolution.
//
// The daemon subprocess's working directory is not documented as the
// plugin directory, so candidates are probed explicitly: the environment
// override (test hosts), the process cwd, and the directory chain above
// this module's file location when the bundler preserves it. A hit must
// contain paseo-plugin.json and payload/. Resolution failure is reported
// with every searched path so a real host can diagnose it immediately.

import fs from "node:fs";
import path from "node:path";

export interface PluginDirResolution {
  readonly dir: string | null;
  readonly searched: readonly string[];
}

function looksLikePluginDir(candidate: string): boolean {
  try {
    return (
      fs.statSync(path.join(candidate, "paseo-plugin.json")).isFile() &&
      fs.statSync(path.join(candidate, "payload")).isDirectory()
    );
  } catch {
    return false;
  }
}

export function resolvePluginDir(): PluginDirResolution {
  const searched: string[] = [];
  const push = (candidate: string | undefined): boolean => {
    if (!candidate || path.resolve(candidate) === path.sep) return false;
    const resolved = path.resolve(candidate);
    if (!searched.includes(resolved)) searched.push(resolved);
    return looksLikePluginDir(resolved);
  };

  if (process.env.MEMSHARING_PLUGIN_DIR && push(process.env.MEMSHARING_PLUGIN_DIR)) {
    return { dir: path.resolve(process.env.MEMSHARING_PLUGIN_DIR), searched };
  }
  if (push(process.cwd())) return { dir: path.resolve(process.cwd()), searched };

  let here: string | undefined;
  try {
    here = path.dirname(new URL(import.meta.url).pathname);
  } catch {
    here = undefined;
  }
  while (here && here !== path.sep) {
    if (push(here)) return { dir: path.resolve(here), searched };
    here = path.dirname(here);
  }
  return { dir: null, searched };
}
