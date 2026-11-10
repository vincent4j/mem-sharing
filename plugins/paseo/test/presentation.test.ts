import assert from "node:assert/strict";
import { test } from "node:test";
import { WindowsPreviewHost } from "../server/windows-preview";
import { flowCopy, flowStage } from "../client/presentation-model";
import { previewOperation, previewStatus, previewRows, publicPreview } from "../client/windows-preview-model";

test("status readiness cannot turn an uninstall command into installation or addition", () => {
  for (const installed of [false, true]) assert.equal(previewOperation("uninstall", installed), "exit");
  assert.equal(previewOperation("onboard", false), "install");
  assert.equal(previewOperation("onboard", true), "add");
});

test("rendered Windows preview retains exact added text, output paths and digest without private snapshots or capabilities", () => {
  const text = "中文\r\n$() `literal`";
  const reply = { operation: "add", confirmationToken: "secret-capability", before: { text_hex: "private-bytes" },
    digest: "a".repeat(64), home: "C:\\用户", backup_root: "C:\\用户\\backup", changes: [{ path: "MEMORY.md", before: "a", after: "b" }] };
  const shown = publicPreview(reply, text);
  assert.equal(shown.text, text); assert.deepEqual(shown.changes, reply.changes); assert.equal(shown.digest, reply.digest);
  assert(!JSON.stringify(shown).includes("secret-capability")); assert(!JSON.stringify(shown).includes("private-bytes"));
  assert.equal(previewRows(reply, text).find(row => row.label === "新增正文")?.value, text);
  const exit = { operation: "exit", export: { path: "C:\\用户\\导出\\MEMORY.md" } };
  assert.equal(previewRows(exit, "").find(row => row.label === "导出位置")?.value, exit.export.path);
  assert(!("text" in publicPreview(exit, "stale text")));
});

test("both adapters share command identity and distinguish unknown result from successful execution", () => {
  assert.equal(flowCopy("onboard").title, "设置记忆共享");
  assert.equal(flowCopy("uninstall").title, "memSharing 整机卸载");
  assert.equal(flowCopy("ck").title, "memSharing 可选安装 Context Keeper");
  assert.notEqual(flowStage("result", false), flowStage("result", true));
  assert.equal(flowStage("gate"), "预览受阻");
  assert.equal(flowStage("loading"), flowStage("busy"));
});


test("busy, failed and unknown status replies cannot establish ready state or leave a setup page without a notice", () => {
  const busy = previewStatus({ status: "busy", message: "已有操作进行中，请等待。" });
  assert.equal(busy.available, false); assert.equal(busy.installed, false); assert.equal(busy.waiting, true);
  assert(busy.notice); assert(!busy.headline.includes("✓"));
  for (const value of [undefined, {}, { status: "unknown" }, { status: "unexpected" }, { status: "failed", message: "核验失败" }]) {
    const state = previewStatus(value);
    assert.equal(state.available, false); assert.equal(state.waiting, false); assert(state.error); assert(!state.headline.includes("✓"));
  }
  for (const status of ["installed", "not_installed"]) {
    const state = previewStatus({ status });
    assert.equal(state.available, true); assert.equal(state.waiting, false); assert.equal(state.error, undefined);
  }
  assert.equal(previewStatus({ status: "installed" }).installed, true);
  assert.equal(previewStatus({ status: "not_installed" }).installed, false);
});


test("a concurrent real host busy reply stays retryable and readiness appears only after the first query completes", async () => {
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  let runs = 0;
  const host = new WindowsPreviewHost({ home: "/synthetic-home", source: () => "/synthetic-source", platform: "win32",
    python: async () => { await held; return { status: "ready", selected: { origin: "system", path: "C:\\Python\\python.exe", status: "ready" }, candidates: [], evidence: "synthetic" }; },
    run: async () => { runs++; return { kind: "completed", exitCode: 0, stdout: '{"status":"not_installed"}', stderr: "", stdoutTruncated: false, stderrTruncated: false }; },
  });
  const first = host.status();
  try {
    const concurrent = await host.status(); assert.equal(concurrent.status, "busy");
    const displayed = previewStatus(concurrent);
    assert.equal(displayed.available, false); assert.equal(displayed.waiting, true); assert(displayed.notice);
    assert(!displayed.headline.includes("检查完成")); assert.equal(runs, 0);
  } finally { release(); }
  assert.equal(previewStatus(await first).available, true); assert.equal(runs, 1);
});
