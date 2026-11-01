#!/usr/bin/env node
// Syncs the common-layer true source (plugins/shared/src) into each host
// plugin's server bundle as a generated copy. Generated files carry a
// header and are never edited by hand; the sync test fails if the copies
// drift. This script only manages files it owns (src/*.ts) and leaves
// sibling generated artifacts (e.g. release-identity.ts) untouched.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.join(here, "src");
const targets = [path.resolve(here, "../paseo/server/shared/common")];

const HEADER = [
  "// GENERATED FILE — do not edit by hand.",
  "// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).",
  "",
].join("\n");

// The true source keeps explicit .ts extensions so Node's type-stripping
// test runner can import it directly; the host plugin bundler expects
// extensionless relative specifiers, so the generated copy rewrites them.
function toBundleSource(body) {
  return body.replace(/(from\s+|import\s*\(\s*)(")(\.\/[^"]+)\.ts(")/g, "$1$2$3$4");
}

const files = fs
  .readdirSync(srcDir)
  .filter((name) => name.endsWith(".ts"))
  .sort();

for (const target of targets) {
  fs.mkdirSync(target, { recursive: true });
  for (const name of files) {
    const body = fs.readFileSync(path.join(srcDir, name), "utf8");
    fs.writeFileSync(path.join(target, name), HEADER + toBundleSource(body), "utf8");
  }
  // Remove only generated copies of sources that no longer exist.
  for (const name of fs.readdirSync(target)) {
    if (name.endsWith(".ts") && !files.includes(name)) {
      fs.rmSync(path.join(target, name));
    }
  }
  console.log(`synced ${files.length} modules -> ${path.relative(process.cwd(), target)}`);
}
