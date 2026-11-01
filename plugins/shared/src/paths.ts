// memSharing plugin common layer — product-owned filesystem locations.
// True source: plugins/shared/src. Generated copy: plugin server bundles.
//
// Product layout constants mirror agm_core.layout / design §6/§7:
//   ~/.mem-sharing                         active kernel R
//   ~/.local/share/mem-sharing             active code C
//   ~/.local/share/mem-sharing-sources     durable source exports
//   ~/.local/share/mem-sharing-runtimes    private tool runtimes
// Nothing here writes; callers own locking and ordering via the Python core.

import { homedir } from "node:os";
import path from "node:path";
import fs from "node:fs";

export interface ProductPaths {
  readonly home: string;
  readonly registryFile: string;
  readonly codeRoot: string;
  readonly durableSourceRoot: string;
  readonly runtimeRoot: string;
  readonly pluginStagingRoot: string;
}

export function productPaths(home: string = homedir()): ProductPaths {
  return {
    home,
    registryFile: path.join(home, ".mem-sharing", "var", "registry.json"),
    codeRoot: path.join(home, ".local", "share", "mem-sharing"),
    durableSourceRoot: path.join(home, ".local", "share", "mem-sharing-sources"),
    runtimeRoot: path.join(home, ".local", "share", "mem-sharing-runtimes"),
    pluginStagingRoot: path.join(home, ".local", "share", "mem-sharing-plugin-staging"),
  };
}

// Private runtime layout: <runtimeRoot>/<runtime-id>/<arch>/bin/python3.
export function privatePythonCandidates(runtimeRoot: string): string[] {
  const candidates: string[] = [];
  let runtimeIds: string[] = [];
  try {
    runtimeIds = fs
      .readdirSync(runtimeRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort();
  } catch {
    return [];
  }
  for (const runtimeId of runtimeIds) {
    const runtimeDir = path.join(runtimeRoot, runtimeId);
    let arches: string[] = [];
    try {
      arches = fs
        .readdirSync(runtimeDir, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
        .sort();
    } catch {
      continue;
    }
    for (const arch of arches) {
      candidates.push(path.join(runtimeDir, arch, "bin", "python3"));
    }
  }
  return candidates;
}
