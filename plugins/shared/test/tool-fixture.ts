import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { toolTreeDigest, type ToolAsset } from "../src/tool-assets.ts";

export async function assetFixture() {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-assets-")));
  const home = path.join(root, "home"), tree = path.join(root, "tree");
  fs.mkdirSync(home); fs.mkdirSync(path.join(tree, "bin"), { recursive: true });
  // Synthetic executable only; this fixture proves transport/approval paths,
  // not real CPython execution. The separate downloaded native run does that.
  fs.writeFileSync(path.join(tree, "bin", "python3"), `#!/bin/sh\nprintf '%s\\n' '{"version":"3.13.18","pythonVersion":"3.13.18","executable":"fixture","machine":"${process.arch}","platform":"Darwin","stdlibOk":true}'\n`, { mode: 0o755 });
  const archive = path.join(root, "fixture.tar.gz");
  const result = spawnSync("/usr/bin/tar", ["--format=ustar", "-czf", archive, "-C", tree, "."], { env: { ...process.env, COPYFILE_DISABLE: "1" } });
  if (result.status !== 0) throw new Error(String(result.stderr));
  const bytes = fs.readFileSync(archive); let requests = 0;
  let handler: (res: http.ServerResponse) => void = res => res.end(bytes);
  const server = http.createServer((_req, res) => { requests++; handler(res); });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const addr = server.address() as { port: number };
  const asset: ToolAsset = { tool: "python", id: "fixture-python", arch: "arm64", version: "3.13.18", url: `http://127.0.0.1:${addr.port}/fixture.tar.gz`, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex"), treeSha256: toolTreeDigest(tree), entry: "bin/python3", maxUnpackBytes: 65536, links: {}, license: "synthetic fixture", licenseUrls: ["https://example.invalid/license"], sourceUrls: ["https://example.invalid/source"] };
  return { root, home, asset, bytes, requests: () => requests, setHandler: (h: typeof handler) => { handler = h; },
    cleanup: async () => { await new Promise<void>(resolve => server.close(() => resolve())); fs.rmSync(root, { recursive: true, force: true }); } };
}
