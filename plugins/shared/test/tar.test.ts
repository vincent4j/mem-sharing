import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { gzipSync } from "node:zlib";
import { extractTarGz } from "../src/tar.ts";

// Minimal in-test ustar builder so malicious archives are constructed from
// raw bytes (no external tool in the parsing path under test).
interface TarEntry {
  name: string;
  data?: Buffer;
  typeflag?: string;
  linkname?: string;
  mode?: number;
}

function octal(value: number, length: number): string {
  return value.toString(8).padStart(length - 1, "0") + "\x00";
}

function header(entry: TarEntry, size: number): Buffer {
  const block = Buffer.alloc(512);
  block.write(entry.name.slice(0, 100), 0, "utf8");
  block.write(octal(entry.mode ?? (entry.typeflag === "5" ? 0o755 : 0o644), 8), 100, "utf8");
  block.write("0000000\x00", 108, "utf8");
  block.write("0000000\x00", 116, "utf8");
  block.write(octal(size, 12), 124, "utf8");
  block.write("00000000000\x00", 136, "utf8");
  block.write(entry.typeflag ?? "0", 156, "utf8");
  block.write(entry.linkname?.slice(0, 100) ?? "", 157, "utf8");
  block.write("ustar\x00", 257, "utf8");
  block.write("00", 263, "utf8");
  let checksum = 0;
  for (let i = 0; i < 512; i += 1) {
    checksum += i >= 148 && i < 156 ? 32 : block[i];
  }
  block.write(octal(checksum, 8), 148, "utf8");
  return block;
}

function buildTar(entries: TarEntry[]): Buffer {
  const chunks: Buffer[] = [];
  for (const entry of entries) {
    const data = entry.data ?? Buffer.alloc(0);
    chunks.push(header(entry, data.length));
    if (data.length > 0) {
      chunks.push(data);
      const padding = (512 - (data.length % 512)) % 512;
      if (padding > 0) chunks.push(Buffer.alloc(padding));
    }
  }
  chunks.push(Buffer.alloc(1024));
  return Buffer.concat(chunks);
}

function writeArchive(dir: string, tar: Buffer): string {
  const archive = path.join(dir, "runtime.tar.gz");
  fs.writeFileSync(archive, gzipSync(tar));
  return archive;
}

function tempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "ms-tar-"));
}

function regularTree(): TarEntry[] {
  return [
    { name: "python/", typeflag: "5" },
    { name: "python/bin/", typeflag: "5" },
    { name: "python/bin/python3", data: Buffer.from("#!/bin/sh\n"), mode: 0o755 },
    { name: "python/lib/readme.txt", data: Buffer.from("hello tar\n") },
  ];
}

test("extracts a regular tree with nested directories", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar(regularTree()));
    const dest = path.join(dir, "out");
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "ok");
    if (result.kind === "ok") {
      assert.equal(result.files, 2);
      assert.ok(result.bytes > 0);
      assert.equal(fs.readFileSync(path.join(dest, "python/bin/python3")).toString(), "#!/bin/sh\n");
      assert.equal(fs.readFileSync(path.join(dest, "python/lib/readme.txt")).toString(), "hello tar\n");
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("preserves the archive execute bit and verifies X_OK", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar(regularTree()));
    const dest = path.join(dir, "out");
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "ok");
    const mode = (fs.statSync(path.join(dest, "python/bin/python3")).mode & 0o777);
    assert.equal(mode, 0o755);
    fs.accessSync(path.join(dest, "python/bin/python3"), fs.constants.X_OK);
    const readme = fs.statSync(path.join(dest, "python/lib/readme.txt")).mode & 0o777;
    assert.equal(readme, 0o644);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("refuses an existing destination and never removes it", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar(regularTree()));
    const dest = path.join(dir, "out");
    fs.mkdirSync(dest);
    fs.writeFileSync(path.join(dest, "foreign.txt"), "keep me");
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "dest_exists");
    assert.equal(fs.readFileSync(path.join(dest, "foreign.txt")).toString(), "keep me");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a failing extraction leaves a pre-existing foreign destination intact", async () => {
  const dir = tempDir();
  try {
    // Valid-looking tree whose second entry escapes; the whole extract must
    // fail and clean only its own staging directory.
    const archive = writeArchive(
      dir,
      buildTar([{ name: "python/bin/python3", data: Buffer.from("x") }, { name: "../evil.sh", data: Buffer.from("x") }]),
    );
    const dest = path.join(dir, "out");
    fs.mkdirSync(dest);
    fs.writeFileSync(path.join(dest, "foreign.txt"), "still here");
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "failed");
    assert.equal(fs.readFileSync(path.join(dest, "foreign.txt")).toString(), "still here");
    assert.equal(fs.existsSync(path.join(dir, "evil.sh")), false);
    const leftovers = fs.readdirSync(dir).filter((name) => name.startsWith("out.extract-"));
    assert.deepEqual(leftovers, []);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a predictable staging name cannot make us clean a foreign directory", async () => {
  const dir = tempDir();
  try {
    // Pin time, pre-create the exact directory the old pid+millis scheme
    // would use, and fail an extraction: mkdtemp staging means the foreign
    // directory is never entered nor removed.
    const realNow = Date.now;
    Date.now = () => 42;
    const dest = path.join(dir, "out");
    const predicted = `${dest}.extract-${process.pid}-42`;
    fs.mkdirSync(predicted, { recursive: true });
    fs.writeFileSync(path.join(predicted, "foreign.bin"), "foreign");
    const archive = writeArchive(dir, buildTar([{ name: "../escape", data: Buffer.from("x") }]));
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    Date.now = realNow;
    assert.equal(result.kind, "failed");
    assert.equal(fs.readFileSync(path.join(predicted, "foreign.bin")).toString(), "foreign");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a replaced destination placeholder is preserved, not published into (inode binding)", async () => {
  const dir = tempDir();
  try {
    // A large archive widens the extraction window: as soon as the staging
    // directory exists (the claim already happened), the attacker moves
    // our placeholder away and puts a foreign EMPTY directory at the same
    // path. Publish must refuse (dev/ino drift) and leave the foreign
    // directory untouched.
    const entries: TarEntry[] = [];
    for (let i = 0; i < 3000; i += 1) {
      entries.push({ name: `python/lib/file-${i}.txt`, data: Buffer.from(`content ${i}\n`) });
    }
    const archive = writeArchive(dir, buildTar(entries));
    const dest = path.join(dir, "out");
    const extractPromise = extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 64 * 1024 * 1024 });
    const stagingGlob = `${dest}.extract-`;
    const deadline = Date.now() + 5000;
    let stagingDir: string | null = null;
    while (Date.now() < deadline) {
      const candidates = fs.readdirSync(dir).filter((name) => name.startsWith(path.basename(stagingGlob)));
      if (candidates.length > 0) {
        stagingDir = path.join(dir, candidates[0]);
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 1));
    }
    assert.ok(stagingDir, "staging directory never appeared");
    const stolen = path.join(dir, "stolen-placeholder");
    fs.renameSync(dest, stolen);
    fs.mkdirSync(dest); // foreign empty replacement at the same path
    const result = await extractPromise;
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "dest_drift");
    // The foreign replacement stays an empty directory; our extracted tree
    // was never renamed over it and our stolen placeholder survives.
    assert.equal(fs.statSync(dest).isDirectory(), true);
    assert.deepEqual(fs.readdirSync(dest), []);
    assert.equal(fs.existsSync(stolen), true);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a replaced placeholder is preserved on the failure-cleanup path too", async () => {
  const dir = tempDir();
  try {
    // Same swap attack, but the archive is poisoned at the end so the
    // extraction FAILS: cleanup must not rmdir the foreign replacement.
    const entries: TarEntry[] = [];
    for (let i = 0; i < 3000; i += 1) {
      entries.push({ name: `python/lib/file-${i}.txt`, data: Buffer.from(`content ${i}\n`) });
    }
    entries.push({ name: "../evil.sh", data: Buffer.from("x") });
    const archive = writeArchive(dir, buildTar(entries));
    const dest = path.join(dir, "out");
    const extractPromise = extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 64 * 1024 * 1024 });
    const glob = `${dest}.extract-`;
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      if (fs.readdirSync(dir).some((name) => name.startsWith(path.basename(glob)))) break;
      await new Promise((resolve) => setTimeout(resolve, 1));
    }
    fs.renameSync(dest, path.join(dir, "stolen"));
    fs.mkdirSync(dest);
    const result = await extractPromise;
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "path_escape");
    // The foreign empty replacement is still there, untouched.
    assert.deepEqual(fs.readdirSync(dest), []);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("two racing extractions to one destination: exactly one wins", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar(regularTree()));
    const dest = path.join(dir, "out");
    const [first, second] = await Promise.all([
      extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 }),
      extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 }),
    ]);
    const outcomes = [first, second].map((result) => (result.kind === "ok" ? "ok" : result.code)).sort();
    assert.ok(outcomes.includes("ok"), JSON.stringify(outcomes));
    const failures = outcomes.filter((code) => code !== "ok");
    assert.deepEqual(failures, failures.every((code) => code === "dest_exists") ? ["dest_exists"] : failures);
    assert.equal(fs.existsSync(path.join(dest, "python/bin/python3")), true);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("rejects '../' path escape", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar([{ name: "../evil.sh", data: Buffer.from("x") }]));
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "path_escape");
    assert.equal(fs.existsSync(path.join(dir, "evil.sh")), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("rejects absolute paths", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar([{ name: "/etc/passwd", data: Buffer.from("x") }]));
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "absolute_path");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("rejects unlisted symlinks and escaping link targets", async () => {
  const dir = tempDir();
  try {
    const unlisted = writeArchive(
      dir,
      buildTar([
        { name: "python/bin/python3", data: Buffer.from("real\n") },
        { name: "python/bin/py", typeflag: "2", linkname: "python3" },
      ]),
    );
    const result = await extractTarGz({ archivePath: unlisted, destDir: path.join(dir, "out-a"), maxBytes: 8192 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "link_not_allowed");

    const escaping = writeArchive(dir, buildTar([{ name: "python/bin/py", typeflag: "2", linkname: "../../../etc/passwd" }]));
    const escapeResult = await extractTarGz({
      archivePath: escaping,
      destDir: path.join(dir, "out-b"),
      maxBytes: 8192,
      allowedSymlinks: ["python/bin/py"],
    });
    assert.equal(escapeResult.kind, "failed");
    if (escapeResult.kind === "failed") assert.equal(escapeResult.code, "link_escape");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("allowlisted internal symlink extracts", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(
      dir,
      buildTar([
        { name: "python/bin/", typeflag: "5" },
        { name: "python/bin/python3.13", data: Buffer.from("binary\n"), mode: 0o755 },
        { name: "python/bin/python3", typeflag: "2", linkname: "python3.13" },
      ]),
    );
    const dest = path.join(dir, "out");
    const result = await extractTarGz({
      archivePath: archive,
      destDir: dest,
      maxBytes: 8192,
      allowedSymlinks: ["python/bin/python3"],
    });
    assert.equal(result.kind, "ok");
    assert.equal(fs.readlinkSync(path.join(dest, "python/bin/python3")), "python3.13");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("hardlink copies count against the byte cap", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(
      dir,
      buildTar([
        { name: "python/data.bin", data: Buffer.alloc(24, 1) },
        { name: "python/data-copy.bin", typeflag: "1", linkname: "python/data.bin" },
      ]),
    );
    // Stream cost: file header+data block (1024) + link header (512) +
    // one terminating zero block (512; the second is optional) = 2048; the
    // hardlink copy adds the source's 24 bytes. A cap of exactly 2048 fits
    // the stream but must trip on the copy charge.
    const generous = await extractTarGz({
      archivePath: archive,
      destDir: path.join(dir, "out-generous"),
      maxBytes: 4096,
      allowedSymlinks: ["python/data-copy.bin"],
    });
    assert.equal(generous.kind, "ok");
    if (generous.kind === "ok") assert.equal(generous.bytes, 2072);

    const tight = await extractTarGz({
      archivePath: archive,
      destDir: path.join(dir, "out-tight"),
      maxBytes: 2048,
      allowedSymlinks: ["python/data-copy.bin"],
    });
    assert.equal(tight.kind, "failed");
    if (tight.kind === "failed") assert.equal(tight.code, "size_cap");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("rejects special file types", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar([{ name: "dev/evil", typeflag: "3" }]));
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "entry_type_rejected");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("enforces the unpacked byte cap including headers", async () => {
  const dir = tempDir();
  try {
    const archive = writeArchive(dir, buildTar([{ name: "big.bin", data: Buffer.alloc(4096, 9) }]));
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "size_cap");
    assert.equal(fs.existsSync(path.join(dir, "out")), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("oversized pax extended headers are refused before allocation", async () => {
  const dir = tempDir();
  try {
    // Declares a 1 GiB pax record but provides almost no data; the declared
    // size itself must trip the bound before any Buffer is allocated.
    const block = header({ name: "PaxHeader", typeflag: "x" }, 1024 * 1024 * 1024);
    const tar = Buffer.concat([block, Buffer.alloc(1024, 0), Buffer.alloc(1024)]);
    const archive = writeArchive(dir, tar);
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 64 * 1024 * 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") {
      assert.ok(result.code === "size_cap" || result.code === "truncated", result.code);
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("truncated archive fails without leaving the destination", async () => {
  const dir = tempDir();
  try {
    const full = buildTar([{ name: "a.txt", data: Buffer.from("data") }]);
    const truncated = full.subarray(0, 700);
    const archive = writeArchive(dir, truncated);
    const result = await extractTarGz({ archivePath: archive, destDir: path.join(dir, "out"), maxBytes: 1024 });
    assert.equal(result.kind, "failed");
    if (result.kind === "failed") assert.equal(result.code, "truncated");
    assert.equal(fs.existsSync(path.join(dir, "out")), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("handles pax path override records", async () => {
  const dir = tempDir();
  try {
    const longName = `python/lib/${"very/".repeat(30)}deep.py`;
    // The parser reads "path=<value>" records; the length prefix is not
    // validated, so a fixed placeholder digit is enough for the fixture.
    const record = `999 path=${longName}\n`;
    const archive = writeArchive(
      dir,
      buildTar([
        { name: "PaxHeader", typeflag: "x", data: Buffer.from(record, "utf8") },
        { name: "placeholder.py", data: Buffer.from("print('deep')\n") },
      ]),
    );
    const dest = path.join(dir, "out");
    const result = await extractTarGz({ archivePath: archive, destDir: dest, maxBytes: 1024 * 1024 });
    assert.equal(result.kind, "ok");
    assert.equal(fs.existsSync(path.join(dest, longName)), true);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
