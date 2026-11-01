import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const sharedSrc = path.resolve(here, "../../shared/src");
const generatedDir = path.resolve(here, "../server/shared/common");

const HEADER = [
  "// GENERATED FILE — do not edit by hand.",
  "// True source: plugins/shared/src/<name> (run plugins/shared/sync-to-plugins.mjs).",
  "",
].join("\n");

// Mirrors the deterministic transformation of sync-to-plugins.mjs.
function toBundleSource(body: string): string {
  return body.replace(/(from\s+|import\s*\(\s*)(")(\.\/[^"]+)\.ts(")/g, "$1$2$3$4");
}

test("every generated common module matches the true source deterministically", () => {
  const sources = fs.readdirSync(sharedSrc).filter((name) => name.endsWith(".ts")).sort();
  for (const name of sources) {
    const generatedPath = path.join(generatedDir, name);
    assert.equal(fs.existsSync(generatedPath), true, `${name} missing from generated copy`);
    const expected = HEADER + toBundleSource(fs.readFileSync(path.join(sharedSrc, name), "utf8"));
    assert.equal(fs.readFileSync(generatedPath, "utf8"), expected, `${name} drifted from the true source`);
  }
});

test("the generated copy contains no extra modules", () => {
  const sources = new Set(fs.readdirSync(sharedSrc).filter((name) => name.endsWith(".ts")));
  for (const name of fs.readdirSync(generatedDir)) {
    assert.equal(sources.has(name), true, `unexpected generated module ${name}`);
  }
});

test("the committed release identity is fail-closed: no fake hash in dev source", async () => {
  const identityPath = path.resolve(here, "../server/shared/release-identity.ts");
  const text = fs.readFileSync(identityPath, "utf8");
  const match = /export const CORE_RELEASE_MANIFEST_SHA256 = "([^"]*)";/.exec(text);
  assert.ok(match, "release identity export not found");
  const value = match[1];
  // An empty string is the dev sentinel; anything else must be a real
  // digest — a plausible-looking hash committed by hand fails this test.
  if (value.length > 0) {
    assert.match(value, /^[0-9a-f]{64}$/, "release identity must be empty (dev) or a real 64-hex digest");
    assert.fail("a concrete digest is release-generated only; do not commit one from a development source");
  }
});
test("supplier notices are generated from shared disclosure source", () => {
  assert.equal(fs.readFileSync(path.resolve(here, "../../shared/THIRD_PARTY_NOTICES.md"), "utf8"), fs.readFileSync(path.resolve(here, "../THIRD_PARTY_NOTICES.md"), "utf8"));
  const source = path.resolve(here, "../../shared/notices"), target = path.resolve(here, "../notices");
  assert.deepEqual(fs.readdirSync(source).sort(), fs.readdirSync(target).sort());
  for (const name of fs.readdirSync(source)) assert.equal(fs.readFileSync(path.join(source, name), "utf8"), fs.readFileSync(path.join(target, name), "utf8"));
});
