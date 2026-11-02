// Host staging cleanup: independent preview → exact approval → byte-preserving
// externalization → per-artifact verified delete → host-receipt.json as the
// only remaining staging content. P1 regression matrix (2026-11-01 窄审):
// A host binding (no fake Python argv), B approved-plan-only iteration with
// fresh comparison, C full-hierarchy fsync + whole-tree digest before the
// first source deletion.
import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { Orchestrator, type CliRunOutcome, type Runner } from "../server/orchestrator";

function tempHome(): { home: string; cleanup: () => void } {
  const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-staging-")));
  return { home, cleanup: () => fs.rmSync(home, { recursive: true, force: true }) };
}

const sha = (bytes: Buffer): string => createHash("sha256").update(bytes).digest("hex");

function makeOrchestrator(home: string) {
  const runner: Runner = { async run(): Promise<CliRunOutcome> { throw new Error("cleanup flow must not run a CLI"); } };
  return new Orchestrator({
    runner, home, pluginDir: null, searchedPluginDirs: [],
    now: () => new Date("2026-11-01T12:00:00Z"),
  });
}

interface StagingDir { root: string; evidence: string; op: string; file: string }

function seedTerminalOp(home: string, name = "op-abc123", payload = b("terminal evidence")): StagingDir {
  const root = path.join(home, ".local", "share", "mem-sharing-plugin-staging");
  const pending = path.join(root, "pending");
  fs.mkdirSync(pending, { mode: 0o700, recursive: true });
  const op = fs.mkdtempSync(path.join(pending, name.startsWith("op-") ? name : `op-${name}`));
  fs.chmodSync(op, 0o700);
  const record = { id: "0f0e0d0c-1111-2222-3333-444455556666", flow: "enable", phase: "execute", journal: null, home, host: os.hostname(), state: "completed", started_at: "2026-11-01T11:00:00Z" };
  fs.writeFileSync(path.join(op, "operation.json"), JSON.stringify(record), { mode: 0o600 });
  fs.writeFileSync(path.join(op, "enable-approval.json"), payload, { mode: 0o600 });
  const evidence = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-evidence-")));
  return { root, evidence, op, file: path.join(op, "operation.json") };
}

function b(content: string): Buffer { return Buffer.from(content, "utf8"); }

function approve(preview: { confirmationToken?: string }): { action: "confirm"; confirmationToken?: string } {
  assert.ok(preview.confirmationToken, "preview must expose a confirmation token");
  return { action: "confirm", confirmationToken: preview.confirmationToken };
}

test("normal preview and confirm: externalize, receipt-only staging, mtime preserved", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const before = fs.readFileSync(seeded.file);
    const mtime = fs.statSync(seeded.file).mtime;
    const preview = await orch.stagingCleanupPreview(seeded.evidence);
    assert.equal(preview.status, "approval_required", JSON.stringify(preview));
    assert.ok(preview.digest && preview.confirmationToken);
    const result = await orch.stagingCleanupConfirm(approve(preview));
    assert.equal(result.status, "completed", JSON.stringify(result));
    const envelope = (result as { envelope: Record<string, unknown> }).envelope;
    const backupRoot = String(envelope.backup_root);
    const copy = path.join(backupRoot, path.basename(seeded.op), "operation.json");
    assert.deepEqual(fs.readFileSync(copy), before);
    assert.deepEqual(fs.statSync(copy).mtime, mtime); // TTL 可核验:源 mtime 保留
    const receiptPath = String(envelope.receipt);
    const receipt = JSON.parse(fs.readFileSync(receiptPath, "utf8"));
    assert.equal(receipt.kind, "host-staging-retired");
    assert.equal(receipt.staging_after ?? undefined, undefined); // receipt 键集不含该字段
    assert.equal(new Set(Object.keys(receipt)).size, 12);
    const pending = path.join(seeded.root, "pending");
    assert.equal(fs.existsSync(pending), false); // 空目录已随最后 op 移除
    assert.deepEqual(fs.readdirSync(seeded.root), ["host-receipt.json"]);
    assert.equal(fs.statSync(receiptPath).mode & 0o777, 0o600);
  } finally { cleanup(); }
});

test("preview is zero-write when evidence dir missing or invalid", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const missing = await orch.stagingCleanupPreview(path.join(seeded.evidence, "does-not-exist"));
    assert.equal(missing.status, "failed");
    assert.equal((missing as { code?: string }).code, "evidence_dir_invalid");
    const inside = await orch.stagingCleanupPreview(path.join(seeded.root));
    assert.equal((inside as { code?: string }).code, "evidence_dir_invalid"); // 与产品根重叠
    assert.deepEqual(fs.readdirSync(seeded.op).sort(), ["enable-approval.json", "operation.json"]); // 现场未动
  } finally { cleanup(); }
});

test("hash or mode drift after approval is rejected with zero externalization", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const preview = await orch.stagingCleanupPreview(seeded.evidence);
    assert.equal(preview.status, "approval_required");
    fs.writeFileSync(seeded.file, b("edited after approval")); // 同名内容变更
    const rejected = await orch.stagingCleanupConfirm(approve(preview));
    assert.ok(rejected.status === "stale_plan" || (rejected as { code?: string }).code === "staging_changed_before_externalize", JSON.stringify(rejected));
    assert.equal(fs.existsSync(path.join(seeded.evidence, "memsharing-host-staging")), false); // 零外置
    assert.ok(fs.existsSync(seeded.file)); // 源保留
  } finally { cleanup(); }
});

test("new file injected in the second fresh window aborts before any deletion", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const preview = await orch.stagingCleanupPreview(seeded.evidence);
    assert.equal(preview.status, "approval_required");
    // 批准后注入未知新文件:重建比较失败(P1-B),零外置零删除。
    fs.writeFileSync(path.join(seeded.op, "surprise.txt"), b("unknown"), { mode: 0o600 });
    const rejected = await orch.stagingCleanupConfirm(approve(preview));
    assert.equal(rejected.status, "stale_plan", JSON.stringify(rejected));
    assert.equal(fs.existsSync(path.join(seeded.evidence, "memsharing-host-staging")), false);
    assert.ok(fs.existsSync(seeded.op));
    // 复核通过后若删除窗口内出现新文件:逐工件删除保留未知文件现场。
    fs.rmSync(path.join(seeded.op, "surprise.txt"));
    const preview2 = await orch.stagingCleanupPreview(seeded.evidence);
    assert.equal(preview2.status, "approval_required");
    const injected = approve(preview2);
    const realUnlink = fs.unlinkSync;
    let unlinked = 0;
    (fs as unknown as { unlinkSync: typeof fs.unlinkSync }).unlinkSync = ((target: fs.PathLike) => {
      unlinked += 1;
      if (unlinked === 2) fs.writeFileSync(path.join(seeded.op, "late-arrival.json"), b("new"), { mode: 0o600 });
      return realUnlink(target);
    }) as typeof fs.unlinkSync;
    let kept: unknown;
    try {
      kept = await orch.stagingCleanupConfirm(injected);
    } finally {
      (fs as unknown as { unlinkSync: typeof fs.unlinkSync }).unlinkSync = realUnlink;
    }
    assert.equal((kept as { code?: string }).code, "staging_dir_not_empty");
    assert.ok(fs.existsSync(path.join(seeded.op, "late-arrival.json"))); // 未知新文件保留
  } finally { cleanup(); }
});

test("fsync failure preserves source and external additions; retry uses a new evidence directory", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const preview = await orch.stagingCleanupPreview(seeded.evidence);
    const before = fs.readFileSync(seeded.file);
    const realFsync = fs.fsyncSync;
    let failed = false;
    (fs as unknown as { fsyncSync: typeof fs.fsyncSync }).fsyncSync = ((fd: number) => {
      if (!failed) {
        failed = true;
        fs.writeFileSync(path.join(seeded.evidence,"memsharing-host-staging","new-private.json"),"unapproved new external bytes",{mode:0o600});
        throw Object.assign(new Error("disk flush failed (fixture)"), { code: "EIO" });
      }
      return realFsync(fd);
    }) as typeof fs.fsyncSync;
    let outcome: unknown;
    try { outcome = await orch.stagingCleanupConfirm(approve(preview)); }
    finally { (fs as unknown as { fsyncSync: typeof fs.fsyncSync }).fsyncSync = realFsync; }
    assert.equal((outcome as { status?: string }).status, "failed");
    assert.deepEqual(fs.readFileSync(seeded.file), before); // 零删除
    assert.equal(fs.readFileSync(path.join(seeded.evidence,"memsharing-host-staging","new-private.json"),"utf8"),"unapproved new external bytes");
    assert.equal((outcome as {envelope:Record<string,unknown>}).envelope.source_deletion_started,false);
    assert.equal((await orch.stagingCleanupPreview(seeded.evidence)).status,"failed");
    const retry=path.join(seeded.evidence,"retry");fs.mkdirSync(retry);
    const preview2 = await orch.stagingCleanupPreview(retry);
    assert.equal(preview2.status, "approval_required"); // 原证据树保留,新目录另批
    assert.equal((await orch.stagingCleanupConfirm(approve(preview2))).status, "completed");
  } finally { cleanup(); }
});

test("uninstall preview refuses while claimable or blocked staging exists", async () => {
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedTerminalOp(home);
    const orch = makeOrchestrator(home);
    const blocked = await orch.uninstallPreview(path.join(seeded.evidence, "backup"));
    assert.equal((blocked as { code?: string }).code, "staging_cleanup_required");
    // 运行中记录→block;未知目录内容→block。
    fs.writeFileSync(path.join(seeded.op, "operation.json"), JSON.stringify({ id: "x", flow: "enable", phase: "execute", journal: null, home, host: os.hostname(), state: "running", started_at: "2026-11-01T11:00:00Z" }));
    const inventory = await orch.stagingInventory();
    assert.equal(inventory.entries[0].disposition, "block");
    assert.equal(inventory.entries[0].activity, "unknown");  // 孤儿 running(无内存属主)=unknown,仅原 journal 可归结
    const stranger = fs.mkdtempSync(path.join(path.join(seeded.root, "pending"), "op-"));
    fs.writeFileSync(path.join(stranger, "mystery.bin"), b("?"), { mode: 0o600 });
    const unknown = await orch.stagingInventory().entries.find(e => e.path === stranger);
    assert.equal(unknown?.ownership, "unverified");
    assert.equal(unknown?.disposition, "block");
  } finally { cleanup(); }
});

function seedJournalOp(home: string, journalStatus: "committed" | "rolled_back" | "prepare"): { op: string; journal: string } {
  const root = path.join(home, ".local", "share", "mem-sharing-plugin-staging");
  const pending = path.join(root, "pending"); fs.mkdirSync(pending, { mode: 0o700, recursive: true });
  const op = fs.mkdtempSync(path.join(pending, "op-")); fs.chmodSync(op, 0o700);
  const install = path.join(home, ".mem-sharing-install-opfixture");
  fs.mkdirSync(install, { mode: 0o700, recursive: true });
  const journal = path.join(install, "journal.json");  // 合法已知根
  fs.writeFileSync(journal, JSON.stringify({ status: journalStatus, plan: { layout: { root: path.join(home, ".mem-sharing") } } }), { mode: 0o600 });
  fs.writeFileSync(path.join(op, "operation.json"), JSON.stringify({ id: "99999999-8888-7777-6666-555544443333", flow: "machine", phase: "execute", journal, home, host: os.hostname(), state: "running", started_at: "2026-11-01T11:00:00Z" }), { mode: 0o600 });
  return { op, journal };
}

test("journal-resolved records (committed / rolled_back) are claimable with accurate journal_status", async () => {
  for (const status of ["committed", "rolled_back"] as const) {
    const { home, cleanup } = tempHome();
    try {
      const seeded = seedJournalOp(home, status);
      const orch = makeOrchestrator(home);
      const inventory = await orch.stagingInventory();
      assert.equal(inventory.entries[0].activity, "terminal", status);
      assert.equal(inventory.entries[0].disposition, "preserve_external_then_clean", status);
      const evidenceDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-ev-")));
      const preview = await orch.stagingCleanupPreview(evidenceDir);
      assert.equal(preview.status, "approval_required", status);
      const done = await orch.stagingCleanupConfirm(approve(preview));
      assert.equal(done.status, "completed", status + " " + JSON.stringify(done));
      const receipt = JSON.parse(fs.readFileSync(String((done as { envelope: { receipt: string } }).envelope.receipt), "utf8"));
      assert.equal(receipt.terminal_evidence[0].record_state, "recovered");
      assert.equal(receipt.terminal_evidence[0].journal_status, status); // 真实终态,不恒 null
      fs.rmSync(evidenceDir, { recursive: true, force: true });
    } finally { cleanup(); }
  }
});

test("non-terminal or unresolvable journal blocks cleanup with zero deletion", async () => {
  for (const status of ["prepare", "committed"] as const) {
    const { home, cleanup } = tempHome();
    try {
      const seeded = seedJournalOp(home, "prepare");
      if (status === "prepare") {
        // 另测任意路径 journal(合法状态内容但位置不在固定根)→不可认领阻断。
        const stranger = path.join(home, "stranger-journal.json");
        fs.writeFileSync(stranger, JSON.stringify({ status: "committed", plan: { layout: { root: path.join(home, ".mem-sharing") } } }), { mode: 0o600 });
        const recordPath = path.join(seeded.op, "operation.json");
        const record = JSON.parse(fs.readFileSync(recordPath, "utf8"));
        fs.writeFileSync(recordPath, JSON.stringify({ ...record, journal: stranger }), { mode: 0o600 });
      }
      if (status === "committed") {
        // 可归结路径但故意破坏布局匹配 → 不可归结。
        fs.writeFileSync(seeded.journal, JSON.stringify({ status: "committed", plan: { layout: { root: "/other/home/.mem-sharing" } } }), { mode: 0o600 });
      }
      void seeded;
      const orch = makeOrchestrator(home);
      const inventory = await orch.stagingInventory();
      assert.equal(inventory.entries[0].disposition, "block", status);
      const evidenceDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-ev-")));
      const preview = await orch.stagingCleanupPreview(evidenceDir);
      assert.equal((preview as { code?: string }).code, "staging_blocked", status);
      assert.ok(fs.existsSync(path.join(seeded.op, "operation.json"))); // 零删除
      fs.rmSync(evidenceDir, { recursive: true, force: true });
    } finally { cleanup(); }
  }
});

function seedCkOp(home: string, state: "completed" | "running", journal?: string): { root: string; op: string; file: string } {
  const root = path.join(home, ".local", "share", "mem-sharing-plugin-staging");
  const pending = path.join(root, "pending"); fs.mkdirSync(pending, { mode: 0o700, recursive: true });
  const op = fs.mkdtempSync(path.join(pending, "op-")); fs.chmodSync(op, 0o700);
  const record: Record<string, unknown> = { id: "aaaa1111-2222-3333-4444-555566667777", flow: "ck", phase: "execute", home, host: os.hostname(), state, started_at: "2026-11-02T05:00:00Z" };
  if (journal !== undefined) record.journal = journal;
  fs.writeFileSync(path.join(op, "operation.json"), JSON.stringify(record), { mode: 0o600 });
  return { root, op, file: path.join(op, "operation.json") };
}

test("completed CK record without the non-transactional audit journal is claimable and consumed by real Python parser", async () => {
  // 修复后形态:ck 完成记录不携带 var/ck-install-*.json 审计 journal(7 键)。
  const { execFileSync } = await import("node:child_process");
  const { fileURLToPath } = await import("node:url");
  const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const { home, cleanup } = tempHome();
  try {
    const seeded = seedCkOp(home, "completed");
    assert.equal("journal" in JSON.parse(fs.readFileSync(seeded.file, "utf8")), false);
    const orch = makeOrchestrator(home);
    const inventory = await orch.stagingInventory();
    assert.equal(inventory.entries[0].activity, "terminal");
    assert.equal(inventory.entries[0].disposition, "preserve_external_then_clean");
    const evidenceDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-ev-")));
    try {
      const preview = await orch.stagingCleanupPreview(evidenceDir);
      assert.equal(preview.status, "approval_required", JSON.stringify(preview));
      const done = await orch.stagingCleanupConfirm(approve(preview));
      assert.equal(done.status, "completed", JSON.stringify(done));
      const receipt = JSON.parse(fs.readFileSync(String((done as { envelope: { receipt: string } }).envelope.receipt), "utf8"));
      assert.equal(receipt.terminal_evidence[0].record_state, "completed");
      assert.equal(receipt.terminal_evidence[0].journal_status, null);
      // 真实 Python receipt 消费:内核 uninstall 侧按同口径接受该 ck 记录。
      const source = "from pathlib import Path; from agm_core.layout import resolve_layout; from agm_core.uninstall import _host_staging_receipt; import sys; r=resolve_layout(sys.argv[1]); _host_staging_receipt(r,r.code.parent/'mem-sharing-plugin-staging',Path(sys.argv[2])); print('accepted')";
      const parsed = execFileSync("python3", ["-B", "-c", source, home, path.join(evidenceDir, "core-backup")], { encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "scripts") } });
      assert.equal(parsed.trim(), "accepted");
    } finally { fs.rmSync(evidenceDir, { recursive: true, force: true }); }
  } finally { cleanup(); }
});

test("interrupted CK record without journal stays unknown and blocks; foreign journals keep blocking cleanup", async () => {
  const { home, cleanup } = tempHome();
  try {
    // 中断的 ck 执行(无内存属主、无 transaction journal)→ unknown → block。
    const interrupted = seedCkOp(home, "running");
    const orch = makeOrchestrator(home);
    let inventory = await orch.stagingInventory();
    let entry = inventory.entries.find(e => e.path === interrupted.op);
    assert.equal(entry?.activity, "unknown");
    assert.equal(entry?.disposition, "block");
    // 错误 CK journal(不在本 HOME var/ck-install 已知形态)→ 原样保留 → 不可归结阻断。
    fs.writeFileSync(interrupted.file, JSON.stringify({ ...JSON.parse(fs.readFileSync(interrupted.file, "utf8")), state: "completed", journal: "/tmp/ck-install-evil.json" }), { mode: 0o600 });
    inventory = await orch.stagingInventory();
    entry = inventory.entries.find(e => e.path === interrupted.op);
    assert.equal(entry?.activity, "unknown");
    assert.equal(entry?.disposition, "block");
    assert.match(String(entry?.reason), /不可归结/);
    // 非CK流程携带 var/ck-install 审计路径 → 修复不清洗非ck记录 → 依旧阻断。
    const stranger = seedCkOp(home, "completed", path.join(home, ".mem-sharing", "var", "ck-install-paseo-20261102045403Z-1c107197.json"));
    fs.writeFileSync(stranger.file, JSON.stringify({ ...JSON.parse(fs.readFileSync(stranger.file, "utf8")), flow: "machine" }), { mode: 0o600 });
    inventory = await orch.stagingInventory();
    entry = inventory.entries.find(e => e.path === stranger.op);
    assert.equal(entry?.activity, "unknown");
    assert.equal(entry?.disposition, "block");
    assert.match(String(entry?.reason), /不可归结/);
    const evidenceDir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "ms-ev-")));
    const preview = await orch.stagingCleanupPreview(evidenceDir);
    assert.equal((preview as { code?: string }).code, "staging_blocked");
    assert.ok(fs.existsSync(interrupted.file) && fs.existsSync(stranger.file)); // 零删除
    fs.rmSync(evidenceDir, { recursive: true, force: true });
  } finally { cleanup(); }
});

test("known persisted outcomes are phase scoped and consumed by real Python parser", async () => {
  const { execFileSync } = await import("node:child_process");
  const { fileURLToPath } = await import("node:url");
  const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const table = [
    ["bootstrap","execute","acquired",true], ["enable","execute","stale_plan",true],
    ["enable","execute","no_pending_plan",true], ["bootstrap","preview","already_prepared",true],
    ["bootstrap","preview","identity_missing",true], ["bootstrap","preview","payload_missing",true],
    ["ck","execute","completed",true], ["ck","execute","running",false],
    ["enable","preview","acquired",false], ["enable","execute","already_prepared",false],
    ["bootstrap","execute","identity_missing",false], ["enable","execute","canceled",false],
    ["enable","execute","unknown",false],
  ] as const;
  for (const [flow,phase,state,accepted] of table) {
    const {home,cleanup}=tempHome();const seeded=seedTerminalOp(home,"op-status",b('{}'));
    try {
      const record=JSON.parse(fs.readFileSync(seeded.file,"utf8"));Object.assign(record,{flow,phase,state});fs.writeFileSync(seeded.file,JSON.stringify(record));
      const orch=new Orchestrator({home,pluginDir:null,searchedPluginDirs:[],runner:{async run(){throw Error("No CLI allowed")}}});
      const preview=await orch.stagingCleanupPreview(seeded.evidence);
      assert.equal(preview.status,accepted?"approval_required":"failed",`${flow}/${phase}/${state}: ${JSON.stringify(preview)}`);
      if(accepted){
        assert.equal((await orch.stagingCleanupConfirm(approve(preview))).status,"completed");
        const source="from pathlib import Path; from agm_core.layout import resolve_layout; from agm_core.uninstall import _host_staging_receipt; import sys; r=resolve_layout(sys.argv[1]); _host_staging_receipt(r,r.code.parent/'mem-sharing-plugin-staging',Path(sys.argv[2])); print('accepted')";
        const parsed=execFileSync("python3",["-B","-c",source,home,path.join(seeded.evidence,"core-backup")],{encoding:"utf8",env:{...process.env,PYTHONPATH:path.join(repo,"scripts")}});
        assert.equal(parsed.trim(),"accepted");
      } else assert.ok(fs.existsSync(seeded.file));
    } finally { cleanup();fs.rmSync(seeded.evidence,{recursive:true,force:true}); }
  }
});
