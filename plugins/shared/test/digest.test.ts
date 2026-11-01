import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { canonicalJson, planDigest, utcConfirmedAt, buildEvidence, buildApproval, isSha256Hex } from "../src/digest.ts";

test("canonicalJson sorts keys recursively and preserves array order", () => {
  assert.equal(canonicalJson({ b: 1, a: { d: [3, 2], c: null } }), '{"a":{"c":null,"d":[3,2]},"b":1}');
});

test("planDigest is stable across key order and matches direct sha256", () => {
  const a = planDigest({ z: 1, a: [1, 2, { y: "x" }] });
  const b = planDigest({ a: [1, 2, { y: "x" }], z: 1 });
  assert.equal(a, b);
  assert.equal(a, createHash("sha256").update('{"a":[1,2,{"y":"x"}],"z":1}').digest("hex"));
});

test("planDigest changes when any value changes", () => {
  assert.notEqual(planDigest({ a: 1 }), planDigest({ a: 2 }));
  assert.notEqual(planDigest({ a: [1, 2] }), planDigest({ a: [2, 1] }));
});

test("utcConfirmedAt matches the kernel UTC-Z timestamp pattern", () => {
  const value = utcConfirmedAt(new Date("2026-10-31T12:34:56.789Z"));
  assert.equal(value, "2026-10-31T12:34:56Z");
  assert.match(value, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
});

test("buildEvidence rejects empty and oversized references", () => {
  assert.throws(() => buildEvidence("   "));
  assert.throws(() => buildEvidence("x".repeat(513)));
  const evidence = buildEvidence("paseo-host:test confirm-screen user press");
  assert.match(evidence.confirmed_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  assert.equal(typeof evidence.reference, "string");
});

test("buildApproval merges plan plus evidence keys without mutating the plan", () => {
  const plan = { command: "install-machine", version: "0.1.3" };
  const approval = buildApproval(plan, { confirmed_at: "2026-10-31T08:00:00Z", reference: "r" });
  assert.deepEqual(approval, {
    command: "install-machine",
    version: "0.1.3",
    confirmed_at: "2026-10-31T08:00:00Z",
    reference: "r",
  });
  assert.deepEqual(plan, { command: "install-machine", version: "0.1.3" });
});

test("isSha256Hex accepts only 64 lowercase hex", () => {
  assert.equal(isSha256Hex("a".repeat(64)), true);
  assert.equal(isSha256Hex("A".repeat(64)), false);
  assert.equal(isSha256Hex("a".repeat(63)), false);
  assert.equal(isSha256Hex(""), false);
});
