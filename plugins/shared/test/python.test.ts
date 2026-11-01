import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { probePythonEnvironment } from "../src/python.ts";
import { productPaths, privatePythonCandidates } from "../src/paths.ts";

function tempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

// Fake interpreter scripts answering the fixed probe program with a JSON
// line on argv "-B -c <program>".
function fakeInterpreter(dir: string, name: string, probeJson: string): string {
  const binDir = path.join(dir, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  const target = path.join(binDir, name);
  const script = [
    "#!/bin/sh",
    `echo '${probeJson}'`,
    "exit 0",
  ].join("\n");
  fs.writeFileSync(target, script, { mode: 0o755 });
  return target;
}

function runtimeFixture(runtimeId: string, arch: string, probeJson: string): { runtimeRoot: string; home: string } {
  const home = tempDir("ms-py-home-");
  const runtimeRoot = path.join(home, ".local", "share", "mem-sharing-runtimes");
  const runtimeDir = path.join(runtimeRoot, runtimeId, arch);
  fs.mkdirSync(runtimeDir, { recursive: true });
  fakeInterpreter(runtimeDir, "python3", probeJson);
  return { runtimeRoot, home };
}

const READY_PROBE =
  '{"pythonVersion":"3.13.18","executable":"/fake/python3","machine":"arm64","platform":"Darwin","stdlibOk":true}';

test("private runtime is preferred over system candidates", async () => {
  const { runtimeRoot, home } = runtimeFixture("cpython-test", "arm64", READY_PROBE);
  try {
    const system = fakeInterpreter(tempDir("ms-py-sys-"), "python3", READY_PROBE);
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [system] });
    assert.equal(env.status, "ready");
    assert.equal(env.selected?.origin, "private-runtime");
    assert.match(env.selected?.path ?? "", /mem-sharing-runtimes\/cpython-test\/arm64\/bin\/python3$/);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("version below the 3.9 floor is blocked", async () => {
  const home = tempDir("ms-py-old-");
  const runtimeRoot = path.join(home, "runtimes");
  const runtimeDir = path.join(runtimeRoot, "old", "arm64");
  fs.mkdirSync(runtimeDir, { recursive: true });
  fakeInterpreter(
    runtimeDir,
    "python3",
    '{"pythonVersion":"3.8.5","executable":"/fake","machine":"arm64","platform":"Darwin","stdlibOk":true}',
  );
  try {
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [] });
    assert.equal(env.status, "blocked");
    assert.match(env.candidates[0]?.detail ?? "", /below floor 3\.9/);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("missing stdlib modules are blocked", async () => {
  const home = tempDir("ms-py-stdlib-");
  const runtimeRoot = path.join(home, "runtimes");
  const runtimeDir = path.join(runtimeRoot, "thin", "arm64");
  fs.mkdirSync(runtimeDir, { recursive: true });
  fakeInterpreter(
    runtimeDir,
    "python3",
    '{"pythonVersion":"3.13.0","executable":"/fake","machine":"arm64","platform":"Darwin","stdlibOk":false}',
  );
  try {
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [] });
    assert.equal(env.status, "blocked");
    assert.match(env.candidates[0]?.detail ?? "", /standard library/);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("no candidates at all is missing, with evidence recorded", async () => {
  const home = tempDir("ms-py-none-");
  const runtimeRoot = path.join(home, "runtimes");
  try {
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [] });
    assert.equal(env.status, "missing");
    assert.equal(env.candidates.length, 0);
    assert.equal(env.evidence, "no candidate paths");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("probe failure (non-JSON stdout) is unknown and does not select", async () => {
  const home = tempDir("ms-py-bad-");
  const runtimeRoot = path.join(home, "runtimes");
  const runtimeDir = path.join(runtimeRoot, "bad", "arm64");
  fs.mkdirSync(runtimeDir, { recursive: true });
  const binDir = path.join(runtimeDir, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  fs.writeFileSync(path.join(binDir, "python3"), "#!/bin/sh\necho not-json\n", { mode: 0o755 });
  try {
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [] });
    assert.equal(env.status, "missing");
    assert.equal(env.candidates[0]?.status, "unknown");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("system candidates fall back after an absent private runtime", async () => {
  const home = tempDir("ms-py-fallback-");
  const runtimeRoot = path.join(home, "runtimes");
  const systemDir = tempDir("ms-py-sysdir-");
  const system = fakeInterpreter(systemDir, "python3", READY_PROBE);
  try {
    const env = await probePythonEnvironment({ runtimeRoot, systemCandidates: [system] });
    assert.equal(env.status, "ready");
    assert.equal(env.selected?.origin, "system");
    assert.equal(env.selected?.path, system);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
    fs.rmSync(systemDir, { recursive: true, force: true });
  }
});

test("privatePythonCandidates scans <runtime-id>/<arch>/bin/python3 in sorted order", () => {
  const home = tempDir("ms-py-scan-");
  const runtimeRoot = path.join(home, "runtimes");
  for (const pair of [
    ["b-runtime", "arm64"],
    ["a-runtime", "x86_64"],
    ["a-runtime", "arm64"],
  ]) {
    const dir = path.join(runtimeRoot, pair[0], pair[1], "bin");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "python3"), "#!/bin/sh\n", { mode: 0o755 });
  }
  try {
    const found = privatePythonCandidates(runtimeRoot);
    assert.deepEqual(found, [
      path.join(runtimeRoot, "a-runtime", "arm64", "bin", "python3"),
      path.join(runtimeRoot, "a-runtime", "x86_64", "bin", "python3"),
      path.join(runtimeRoot, "b-runtime", "arm64", "bin", "python3"),
    ]);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("productPaths mirrors the fixed product layout", () => {
  const paths = productPaths("/tmp/fake-home");
  assert.equal(paths.registryFile, "/tmp/fake-home/.mem-sharing/var/registry.json");
  assert.equal(paths.codeRoot, "/tmp/fake-home/.local/share/mem-sharing");
  assert.equal(paths.durableSourceRoot, "/tmp/fake-home/.local/share/mem-sharing-sources");
  assert.equal(paths.runtimeRoot, "/tmp/fake-home/.local/share/mem-sharing-runtimes");
});

// Note: the macOS CommandLineTools stub guard (xcode-select -p before
// executing /usr/bin/python3) is path-triggered and cannot run against the
// real /usr/bin in hermetic tests; it is exercised on the isolated test
// host during PA-01/PA-10.
test("real machine self-check: this host has a usable interpreter via private-or-system scan", async () => {
  const paths = productPaths();
  const env = await probePythonEnvironment({ runtimeRoot: paths.runtimeRoot });
  assert.equal(env.status, "ready");
  assert.match(env.selected?.probe?.pythonVersion ?? "", /^3\.(9|[0-9][0-9])\./);
});
