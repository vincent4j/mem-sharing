import assert from "node:assert/strict";
import { test } from "node:test";
import contribute from "../index.server";
import { Orchestrator } from "../server/orchestrator";

test("entry obtains only plugins from SDK context and does not serialize sensitive config", async () => {
  const handlers = new Map<string, Function>();
  const cleanup = contribute({ handle(contract: { name: string }, handler: Function) { handlers.set(contract.name, handler); } } as never);
  const logs: string[] = [];
  const previous = console.log;
  console.log = (...args) => { logs.push(JSON.stringify(args)); };
  try {
    let reads = 0;
    const config = new Proxy({ plugins: undefined, dummySecret: "DUMMY_SENSITIVE_CONFIG_DO_NOT_LOG" }, {
      get(target, key) { assert.equal(key, "plugins"); return target.plugins; },
    });
    const context = { paseo: { config: { get: async () => { reads++; return { config }; } } } };
    const handler = handlers.get("memsharing.operation.status"); assert(handler);
    const result = await handler({}, context);
    assert.equal(reads, 1);
    assert(!JSON.stringify(result).includes("DUMMY_SENSITIVE"));
    assert(!logs.join("").includes("DUMMY_SENSITIVE"));
  } finally { console.log = previous; cleanup(); }
});

test("SDK config failure is sanitized and never exposes raw configuration or exception", async () => {
  const handlers = new Map<string, Function>();
  const cleanup = contribute({ handle(contract: { name: string }, handler: Function) { handlers.set(contract.name, handler); } } as never);
  try {
    const handler = handlers.get("memsharing.operation.status"); assert(handler);
    await assert.rejects(handler({}, { paseo: { config: { get: async () => { throw new Error("DUMMY_SENSITIVE_CONFIG_DO_NOT_LOG"); } } } }), {
      message: "plugin_source_unavailable: daemon plugin sources could not be read",
    });
    await assert.rejects(handler({}, { paseo: { config: { get: async () => ({ config: { plugins: {} } }) } } }), /plugin_source_changed/);
  } finally { cleanup(); }
});


test("config/source failure cancels existing pending operations through the original Orchestrator", async () => {
  const handlers = new Map<string, Function>();
  const cleanup = contribute({ handle(contract: { name: string }, handler: Function) { handlers.set(contract.name, handler); } } as never);
  const original = Orchestrator.prototype.cancel;
  const calls: string[] = [];
  Orchestrator.prototype.cancel = function(flow) { calls.push(flow); return original.call(this, flow); };
  try {
    const handler = handlers.get("memsharing.operation.status"); assert(handler);
    await handler({}, { paseo: { config: { get: async () => ({ config: { plugins: {} } }) } } });
    await assert.rejects(handler({}, { paseo: { config: { get: async () => { throw new Error("DUMMY_SECRET"); } } } }), /plugin_source_unavailable/);
    assert.deepEqual(calls.sort(), ["bootstrap", "ck", "ckUninstall", "dependency", "enable", "machine", "recover", "stagingCleanup", "uninstall"]);
  } finally { cleanup(); Orchestrator.prototype.cancel = original; }
});
