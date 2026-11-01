import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { assetFixture } from "./tool-fixture.ts";
import { assetScene, assetDestination, prepareToolAsset } from "../src/tool-assets.ts";

test("local HTTP exact archive -> private persistent asset -> probe -> same-version reuse", async () => {
  const f = await assetFixture();
  try {
    const runtimeRoot = path.join(f.home, "runtimes");
    const run = () => prepareToolAsset({ runtimeRoot, home: f.home, asset: f.asset, scene: assetScene(runtimeRoot, f.asset), allowInsecureTransportForTests: true });
    assert.equal(assetScene(runtimeRoot, f.asset).state, "absent");
    await run(); assert.equal(assetScene(runtimeRoot, f.asset).state, "ready");
    await run(); assert.equal(f.requests(), 1);
    fs.writeFileSync(path.join(assetDestination(runtimeRoot, f.asset), "payload/bin/python3"), "foreign");
    const scene = assetScene(runtimeRoot, f.asset); assert.equal(scene.state, "conflict");
    await assert.rejects(run(), /foreign_runtime_conflict/);
    assert.equal(fs.readFileSync(path.join(assetDestination(runtimeRoot, f.asset), "payload/bin/python3"), "utf8"), "foreign");
  } finally { await f.cleanup(); }
});

test("bad hash/size, cancellation, concurrent leases, drift and approved retry preserve evidence", async () => {
  const f = await assetFixture();
  try {
    const root = path.join(f.home, "runtimes");
    const run = (asset = f.asset, signal?: AbortSignal, scene = assetScene(root, asset)) => prepareToolAsset({ runtimeRoot: root, home: f.home, asset, scene, signal, allowInsecureTransportForTests: true });
    const wrongHash = { ...f.asset, id: "bad-hash", sha256: "0".repeat(64) };
    await assert.rejects(run(wrongHash), /hash_mismatch/);
    const wrongSize = { ...f.asset, id: "bad-size", bytes: f.bytes.length + 1 };
    await assert.rejects(run(wrongSize), /size_mismatch/);
    const shortSize = { ...f.asset, id: "short-size", bytes: f.bytes.length - 1 };
    await assert.rejects(run(shortSize), /size_cap/);
    const oldScene = assetScene(root, f.asset);
    fs.mkdirSync(assetDestination(root, f.asset), { recursive: true });
    fs.writeFileSync(path.join(assetDestination(root, f.asset), "private.txt"), "keep");
    await assert.rejects(run(f.asset, undefined, oldScene), /asset_scene_drift/);
    assert.equal(fs.readFileSync(path.join(assetDestination(root, f.asset), "private.txt"), "utf8"), "keep");
    const retry = { ...f.asset, id: "retry" };
    let entered!: () => void;
    const started = new Promise<void>(r => { entered = r; });
    f.setHandler(res => { entered(); res.write(f.bytes.subarray(0, 20)); });
    const controller = new AbortController();
    const active = run(retry, controller.signal); await started;
    await assert.rejects(run(retry), /asset_busy/);
    controller.abort(); await assert.rejects(active, /canceled/);
    assert.equal(assetScene(root, retry).state, "interrupted");
    f.setHandler(res => res.end(f.bytes)); await run(retry);
    assert.equal(assetScene(root, retry).state, "ready");
  } finally { await f.cleanup(); }
});

test("symlink ancestors and replaced destinations are preserved", async () => {
  const f = await assetFixture();
  try {
    const outside = path.join(f.root, "outside"); fs.mkdirSync(outside);
    const root = path.join(f.home, "runtimes"); fs.symlinkSync(outside, root);
    assert.throws(() => assetScene(root, f.asset), /unsafe directory/);
    assert.deepEqual(fs.readdirSync(outside), []);
  } finally { await f.cleanup(); }
});

test("mid-download destination replacement remains untouched, dead lease needs fresh scene", async () => {
  const f = await assetFixture();
  try {
    const runtimeRoot = path.join(f.home, "runtimes"), destination = assetDestination(runtimeRoot, f.asset);
    f.setHandler(res => {
      fs.renameSync(destination, destination + "-owned-moved");
      fs.mkdirSync(destination); fs.writeFileSync(path.join(destination, "foreign.txt"), "preserve");
      res.end(f.bytes);
    });
    await assert.rejects(prepareToolAsset({ runtimeRoot, home: f.home, asset: f.asset, scene: assetScene(runtimeRoot, f.asset), allowInsecureTransportForTests: true }), /part_drift|runtime_destination_drift/);
    assert.deepEqual(fs.readdirSync(destination), ["foreign.txt"]);
    const asset = { ...f.asset, id: "recover-dead-lease" };
    const canceled = new AbortController();
    let entered!: () => void; const started = new Promise<void>(r => { entered = r; });
    f.setHandler(res => { entered(); res.write(f.bytes.subarray(0, 20)); });
    const active = prepareToolAsset({ runtimeRoot, home: f.home, asset, scene: assetScene(runtimeRoot, asset), signal: canceled.signal, allowInsecureTransportForTests: true });
    await started; canceled.abort(); await assert.rejects(active, /canceled/);
    const lease = path.join(assetDestination(runtimeRoot, asset), "lease.json");
    fs.writeFileSync(lease, JSON.stringify({ pid: 2147483647, nonce: "synthetic-dead-process" }));
    f.setHandler(res => res.end(f.bytes));
    await prepareToolAsset({ runtimeRoot, home: f.home, asset, scene: assetScene(runtimeRoot, asset), allowInsecureTransportForTests: true });
    assert.equal(assetScene(runtimeRoot, asset).state, "ready");
  } finally { await f.cleanup(); }
});

test("unprobed complete tree is not ready and retry probes without another download", async () => {
  const f = await assetFixture();
  try {
    const runtimeRoot = path.join(f.home, "runtimes"), asset = { ...f.asset, version: "99.0.0" };
    const run = (value = asset) => prepareToolAsset({ runtimeRoot, home: f.home, asset: value, scene: assetScene(runtimeRoot, value), allowInsecureTransportForTests: true });
    await assert.rejects(run(), /probe failed/);
    assert.equal(assetScene(runtimeRoot, asset).state, "probe_required");
    assert.equal(f.requests(), 1);
    await run(f.asset); assert.equal(f.requests(), 1);
    assert.equal(assetScene(runtimeRoot, f.asset).state, "ready");
  } finally { await f.cleanup(); }
});

test("asset total deadline stops an active slow response and releases its lease", async () => {
  const f = await assetFixture();
  try {
    const runtimeRoot = path.join(f.home, "runtimes");
    f.setHandler(res => {
      const interval = setInterval(() => res.write(Buffer.from([1])), 10);
      res.on("close", () => clearInterval(interval));
    });
    await assert.rejects(prepareToolAsset({ runtimeRoot, home: f.home, asset: f.asset, scene: assetScene(runtimeRoot, f.asset), allowInsecureTransportForTests: true, totalTimeoutMs: 100 }), /asset_timeout/);
    assert.equal(fs.existsSync(path.join(assetDestination(runtimeRoot, f.asset), "lease.json")), false);
  } finally { await f.cleanup(); }
});
