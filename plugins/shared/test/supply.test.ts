import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { validateSupplyManifest, loadSupplyManifest, type SupplyManifest } from "../src/supply.ts";

function validManifest(): SupplyManifest {
  return {
    schema_version: 1,
    kind: "python-runtime",
    runtime_id: "cpython-3.13.18-pbs-20261026",
    version: "3.13.18",
    license: "PSF-2.0-like; see archive license files",
    entry: "python/bin/python3",
    archives: [
      {
        arch: "arm64",
        url: "https://example.invalid/aarch64-apple-darwin.tar.gz",
        sha256: "a".repeat(64),
        bytes: 40000000,
      },
    ],
    max_unpack_bytes: 500000000,
    source_note: "candidate only; pin from verified release metadata",
  };
}

test("a complete manifest validates", () => {
  assert.deepEqual(validateSupplyManifest(validManifest()), { ok: true, errors: [] });
});

test("http URLs are rejected — https only", () => {
  const manifest = validManifest();
  (manifest.archives[0] as { url: string }).url = "http://example.invalid/a.tar.gz";
  const result = validateSupplyManifest(manifest);
  assert.equal(result.ok, false);
  assert.ok(result.errors.some((error) => error.includes("https")));
});

test("non-64-hex sha256 is rejected", () => {
  const manifest = validManifest();
  (manifest.archives[0] as unknown as { sha256: string }).sha256 = "XYZ";
  assert.equal(validateSupplyManifest(manifest).ok, false);
});

test("entry paths with traversal or absolute components are rejected", () => {
  for (const entry of ["../bin/python3", "/bin/python3", "bin/../bin/python3"]) {
    const manifest = validManifest();
    (manifest as { entry: string }).entry = entry;
    assert.equal(validateSupplyManifest(manifest).ok, false, entry);
  }
});

test("duplicate or out-of-range archives are rejected", () => {
  const twoUp = validManifest();
  (twoUp as { archives: unknown }).archives = [
    ...(twoUp.archives as unknown as unknown[]),
    { arch: "arm64", url: "https://e.invalid/b.tar.gz", sha256: "b".repeat(64), bytes: 1 },
  ];
  assert.equal(validateSupplyManifest(twoUp).ok, false);

  const threeUp = validManifest();
  (threeUp as { archives: unknown }).archives = [
    { arch: "arm64", url: "https://e.invalid/a.tar.gz", sha256: "a".repeat(64), bytes: 1 },
    { arch: "x86_64", url: "https://e.invalid/b.tar.gz", sha256: "b".repeat(64), bytes: 1 },
    { arch: "x86_64", url: "https://e.invalid/c.tar.gz", sha256: "c".repeat(64), bytes: 1 },
  ];
  assert.equal(validateSupplyManifest(threeUp).ok, false);
});

test("byte and unpack caps are enforced", () => {
  const manifest = validManifest();
  (manifest.archives[0] as unknown as { bytes: number }).bytes = 0;
  assert.equal(validateSupplyManifest(manifest).ok, false);

  const unpack = validManifest();
  (unpack as unknown as { max_unpack_bytes: number }).max_unpack_bytes = 9 * 1024 * 1024 * 1024;
  assert.equal(validateSupplyManifest(unpack).ok, false);
});

test("missing required text fields are rejected", () => {
  const manifest = validManifest();
  delete (manifest as Partial<Record<string, unknown>>).license;
  assert.equal(validateSupplyManifest(manifest).ok, false);
});

test("allowed_symlinks entries must be safe relative paths", () => {
  const manifest = validManifest();
  (manifest as { allowed_symlinks?: string[] }).allowed_symlinks = ["python/bin/python3"];
  assert.equal(validateSupplyManifest(manifest).ok, true);

  const evil = validManifest();
  (evil as { allowed_symlinks?: string[] }).allowed_symlinks = ["../outside"];
  assert.equal(validateSupplyManifest(evil).ok, false);
});

test("loadSupplyManifest is fail-closed on missing and invalid files", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-supply-"));
  try {
    const missing = await loadSupplyManifest(path.join(dir, "absent.json"));
    assert.equal(missing.status, "not_ready");
    assert.match(missing.reason, /missing or unreadable/);

    const badJson = path.join(dir, "bad.json");
    fs.writeFileSync(badJson, "{nope");
    const parsed = await loadSupplyManifest(badJson);
    assert.equal(parsed.status, "not_ready");
    assert.match(parsed.reason, /not valid JSON/);

    const invalid = path.join(dir, "invalid.json");
    fs.writeFileSync(invalid, JSON.stringify({ schema_version: 1, kind: "python-runtime" }));
    const loaded = await loadSupplyManifest(invalid);
    assert.equal(loaded.status, "not_ready");
    assert.match(loaded.reason, /supply manifest invalid/);

    const good = path.join(dir, "good.json");
    fs.writeFileSync(good, JSON.stringify(validManifest()));
    const ready = await loadSupplyManifest(good);
    assert.equal(ready.status, "ready");
    assert.equal(ready.manifest?.runtime_id, "cpython-3.13.18-pbs-20261026");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
