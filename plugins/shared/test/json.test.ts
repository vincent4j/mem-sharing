import assert from "node:assert/strict";
import { test } from "node:test";
import { parseCliJson, classifyExitCode } from "../src/json.ts";

test("parses a single-line sorted-keys JSON document", () => {
  const result = parseCliJson('{"status":"approval_required","x":1}\n');
  assert.equal(result.ok, true);
  assert.deepEqual(result.value, { status: "approval_required", x: 1 });
});

test("parses an indented envelope", () => {
  const result = parseCliJson('{\n  "status": "completed",\n  "errors": []\n}');
  assert.equal(result.ok, true);
  assert.deepEqual(result.value, { status: "completed", errors: [] });
});

test("rejects empty stdout", () => {
  assert.equal(parseCliJson("").ok, false);
  assert.equal(parseCliJson("   \n").ok, false);
});

test("rejects non-JSON stdout", () => {
  assert.equal(parseCliJson("Traceback (most recent call last): ...").ok, false);
});

test("rejects two concatenated JSON documents", () => {
  assert.equal(parseCliJson('{"a":1}{"b":2}').ok, false);
});

test("exit code mapping mirrors the Python CLI contract", () => {
  assert.equal(classifyExitCode(5), "approval_required");
  assert.equal(classifyExitCode(0), "completed");
  assert.equal(classifyExitCode(2), "failed");
  assert.equal(classifyExitCode(1), "failed");
});
