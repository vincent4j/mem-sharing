import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { downloadVerified } from "../src/download.ts";

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

function serveOnce(handler: (request: http.IncomingMessage, response: http.ServerResponse) => void): Promise<{ url: string; close: () => Promise<void> }> {
  const server = http.createServer(handler);
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = server.address() as { port: number };
      resolve({
        url: `http://127.0.0.1:${address.port}/archive.tar.gz`,
        close: () => new Promise((done) => server.close(() => done())),
      });
    });
  });
}

function download(options: Omit<Parameters<typeof downloadVerified>[0], "allowInsecureTransportForTests">) {
  // Local http fixtures: transport security is a test seam here; production
  // URLs must pass validateSupplyManifest (https enforced there).
  return downloadVerified({ ...options, allowInsecureTransportForTests: true });
}

test("downloads, verifies hash, and renames into place", async () => {
  const payload = Buffer.alloc(64 * 1024, 7);
  const fixture = await serveOnce((_request, response) => {
    response.end(payload);
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-ok-"));
  try {
    const staging = path.join(dir, "runtime.tar.gz");
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: payload.length + 1024,
      stagingPath: staging,
    });
    assert.equal(result.kind, "ok");
    if (result.kind === "ok") {
      assert.equal(result.sha256, sha256(payload));
      assert.equal(result.bytes, payload.length);
      assert.deepEqual(fs.readFileSync(staging), payload);
      assert.equal(fs.readdirSync(dir).length, 1);
    }
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("hash mismatch fails and removes this call's partial file", async () => {
  const payload = Buffer.from("not the approved bytes");
  const fixture = await serveOnce((_request, response) => response.end(payload));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-hash-"));
  try {
    const staging = path.join(dir, "runtime.tar.gz");
    const result = await download({
      url: fixture.url,
      expectedSha256: "0".repeat(64),
      maxBytes: 4096,
      stagingPath: staging,
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "hash_mismatch");
    assert.equal(fs.existsSync(staging), false);
    assert.equal(fs.readdirSync(dir).length, 0);
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("byte cap aborts the transfer", async () => {
  const payload = Buffer.alloc(8192, 1);
  const fixture = await serveOnce((_request, response) => response.end(payload));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-cap-"));
  try {
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: 1024,
      stagingPath: path.join(dir, "runtime.tar.gz"),
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "size_cap");
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("non-200 responses fail with http_status", async () => {
  const fixture = await serveOnce((_request, response) => {
    response.statusCode = 404;
    response.end("gone");
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-404-"));
  try {
    const result = await download({
      url: fixture.url,
      expectedSha256: "0".repeat(64),
      maxBytes: 1024,
      stagingPath: path.join(dir, "runtime.tar.gz"),
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "http_status");
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("cancellation cleans up the partial download", async () => {
  const fixture = await serveOnce((_request, response) => {
    response.write(Buffer.alloc(1024, 2));
    // Never end: the client must abort.
    setTimeout(() => response.end(Buffer.alloc(1024, 2)), 3000).unref();
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-cancel-"));
  try {
    const controller = new AbortController();
    const pending = download({
      url: fixture.url,
      expectedSha256: "0".repeat(64),
      maxBytes: 65536,
      stagingPath: path.join(dir, "runtime.tar.gz"),
      signal: controller.signal,
    });
    setTimeout(() => controller.abort(), 200);
    const result = await pending;
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "canceled");
    assert.equal(fs.readdirSync(dir).length, 0);
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("non-https URLs are refused outright", async () => {
  const result = await downloadVerified({
    url: "http://127.0.0.1:1/x.tar.gz",
    expectedSha256: "0".repeat(64),
    maxBytes: 1024,
    stagingPath: "/tmp/should-not-exist.tar.gz",
  });
  assert.equal(result.kind, "failed");
  if (result.kind === "failed") assert.equal(result.code, "url_rejected");
});

test("a malformed redirect Location fails structurally", async () => {
  const fixture = await serveOnce((_request, response) => {
    response.statusCode = 302;
    response.setHeader("Location", "http://[::invalid-host]");
    response.end();
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-redir-"));
  try {
    const result = await download({
      url: fixture.url,
      expectedSha256: "0".repeat(64),
      maxBytes: 4096,
      stagingPath: path.join(dir, "runtime.tar.gz"),
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "bad_redirect");
    assert.equal(fs.readdirSync(dir).length, 0);
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a staging path that cannot be written fails without crashing", async () => {
  const payload = Buffer.from("bytes");
  const fixture = await serveOnce((_request, response) => response.end(payload));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-eisdir-"));
  try {
    // stagingPath points at a directory: the exclusive part file is a
    // sibling, but publishing must refuse to clobber the existing target.
    const blocked = path.join(dir, "blocked");
    fs.mkdirSync(blocked);
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: 4096,
      stagingPath: blocked,
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "target_conflict");
    assert.equal(fs.statSync(blocked).isDirectory(), true);
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a predictable part-file name cannot make us delete a foreign file", async () => {
  // Pins Date.now and Math.random, pre-creates the exact part path the old
  // scheme would use, and fails the transfer: the foreign file must remain
  // byte-identical because the exclusive create ('ax') never succeeded.
  const realNow = Date.now;
  const realRandom = Math.random;
  const payload = Buffer.from("approved bytes");
  const fixture = await serveOnce((_request, response) => response.end(payload));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-part-"));
  try {
    const staging = path.join(dir, "runtime.tar.gz");
    Date.now = () => 42;
    Math.random = (() => 0.1337) as () => number;
    const predictedPart = `${staging}.part-${process.pid}-42-${(0.1337).toString(16).slice(2, 10)}`;
    fs.writeFileSync(predictedPart, "foreign content");
    const result = await download({
      url: fixture.url,
      expectedSha256: "0".repeat(64), // force a hash mismatch after transfer
      maxBytes: 4096,
      stagingPath: staging,
    });
    assert.equal(result.kind, "failed");
    assert.equal(fs.readFileSync(predictedPart).toString(), "foreign content");
    assert.equal(fs.existsSync(staging), false);
  } finally {
    Date.now = realNow;
    Math.random = realRandom;
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// Handler that swaps the caller's part file before responding: find the
// single `.part-` file in the staging directory, rename it to `.owned`, and
// write FOREIGN_UNVERIFIED at the original path. Deterministic — the swap
// always precedes the response bytes.
function partSwappingFixture(dir: string): Promise<{ url: string; close: () => Promise<void> }> {
  const payload = Buffer.from("approved bytes for the swap attack");
  return serveOnce((_request, response) => {
    const part = fs.readdirSync(dir).find((name) => name.includes(".part-"));
    if (part) {
      fs.renameSync(path.join(dir, part), path.join(dir, `${part}.owned`));
      fs.writeFileSync(path.join(dir, part), "FOREIGN_UNVERIFIED");
    }
    response.end(payload);
  }).then((fixture) => ({ ...fixture, payload }));
}

test("a part file swapped mid-transfer never becomes the final artifact", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-swap-ok-"));
  try {
    const staging = path.join(dir, "runtime.tar.gz");
    const payload = Buffer.from("approved bytes for the swap attack");
    const fixture = await partSwappingFixture(dir);
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: 4096,
      stagingPath: staging,
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "part_drift");
    // No final artifact was created from the foreign path.
    assert.equal(fs.existsSync(staging), false);
    // The foreign replacement is preserved untouched.
    const foreign = fs.readdirSync(dir).find((name) => name.includes(".part-") && !name.endsWith(".owned"));
    assert.ok(foreign, "foreign replacement missing");
    assert.equal(fs.readFileSync(path.join(dir, foreign)).toString(), "FOREIGN_UNVERIFIED");
    // Our renamed original survives with the approved bytes.
    const owned = fs.readdirSync(dir).find((name) => name.endsWith(".owned"));
    assert.ok(owned);
    assert.equal(fs.readFileSync(path.join(dir, owned)).toString(), payload.toString());
    await fixture.close();
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a part file swapped mid-transfer is preserved on the hash-failure path too", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-swap-hash-"));
  try {
    const staging = path.join(dir, "runtime.tar.gz");
    const payload = Buffer.from("approved bytes for the swap attack");
    const fixture = await partSwappingFixture(dir);
    const result = await download({
      url: fixture.url,
      expectedSha256: "0".repeat(64), // hash mismatch drives the failure path
      maxBytes: 4096,
      stagingPath: staging,
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "hash_mismatch");
    assert.equal(fs.existsSync(staging), false);
    const foreign = fs.readdirSync(dir).find((name) => name.includes(".part-") && !name.endsWith(".owned"));
    assert.ok(foreign, "foreign replacement was deleted on the failure path");
    assert.equal(fs.readFileSync(path.join(dir, foreign)).toString(), "FOREIGN_UNVERIFIED");
    await fixture.close();
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a target created during transfer is never overwritten", async () => {
  const payload = Buffer.from("verified bytes");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-race-"));
  const staging = path.join(dir, "runtime.tar.gz");
  const fixture = await serveOnce((_request, response) => {
    // The foreign target appears while the transfer is still running.
    fs.writeFileSync(staging, "foreign target");
    response.end(payload);
  });
  try {
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: 4096,
      stagingPath: staging,
    });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "target_conflict");
    assert.equal(fs.readFileSync(staging).toString(), "foreign target");
    const leftovers = fs.readdirSync(dir).filter((name) => name.includes(".part-"));
    assert.deepEqual(leftovers, []);
  } finally {
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("chunked transfer with backpressure completes byte-exact without listener warnings", async () => {
  // Many small chunks exercise the pause/drain path; the old fire-and-
  // forget drain handlers tripped MaxListeners warnings here.
  const chunk = Buffer.alloc(2048, 7);
  const totalChunks = 512;
  const payload = Buffer.alloc(chunk.length * totalChunks, 7);
  const warnings: unknown[] = [];
  const onWarning = (warning: unknown): void => {
    warnings.push(warning);
  };
  process.on("warning", onWarning);
  const fixture = await serveOnce((_request, response) => {
    let sent = 0;
    const sendNext = (): void => {
      if (sent === totalChunks) {
        response.end();
        return;
      }
      sent += 1;
      response.write(chunk, () => setImmediate(sendNext));
    };
    sendNext();
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ms-dl-bp-"));
  try {
    const result = await download({
      url: fixture.url,
      expectedSha256: sha256(payload),
      maxBytes: payload.length + 1024,
      stagingPath: path.join(dir, "runtime.tar.gz"),
    });
    assert.equal(result.kind, "ok");
    if (result.kind === "ok") {
      assert.equal(result.bytes, payload.length);
      assert.deepEqual(fs.readFileSync(path.join(dir, "runtime.tar.gz")), payload);
    }
    assert.deepEqual(warnings, []);
  } finally {
    process.off("warning", onWarning);
    await fixture.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
