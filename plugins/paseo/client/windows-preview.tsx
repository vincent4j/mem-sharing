import { useEffect, useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { useRpc } from "@getpaseo/plugin/client";
import { windowsPreviewStatusRpc, windowsPreviewPlanRpc, windowsPreviewConfirmRpc, windowsPreviewCancelRpc } from "../shared/contracts";
import { Action, Details } from "./ui";
import { FlowPage, StatusPage, PlanPreview, PlanConfirmation, OperationResult, PrimaryAction } from "./presentation";
import { flowCopy, flowStage } from "./presentation-model";
import { OPERATION_LABELS, WINDOWS_SCOPE, WINDOWS_SETUP, previewOperation, previewStatus, publicPreview, previewRows, type PreviewReply } from "./windows-preview-model";

function usePreviewStatus(flow: string) {
  const status = useRpc(windowsPreviewStatusRpc);
  const [snapshot, setSnapshot] = useState<PreviewReply>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState("");
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  const refreshing = useRef(false);
  useEffect(() => {
    let active = true; generation.current++; refreshing.current = true;
    setLoading(true); setSnapshot(undefined); setError(undefined);
    void status({}).then(value => {
      if (!active) return;
      setSnapshot(value); setCheckedAt(new Date().toLocaleTimeString());
    }).catch(() => { if (active) setError("无法读取此 Host 的预览状态，请核对插件来源与 Python 环境。"); })
      .finally(() => { if (active) { setLoading(false); refreshing.current = false; } });
    return () => { active = false; generation.current++; };
  }, [status, flow, revision]);
  const state = previewStatus(snapshot);
  return { status, snapshot, setSnapshot, state, error: error ?? (loading ? undefined : state.error), loading, checkedAt, generation,
    refresh: () => { if (refreshing.current) return; refreshing.current = true; setRevision(value => value + 1); } };
}

export function WindowsStatusScreen({ theme, layout }: PluginScreenProps) {
  const { snapshot, state, error, loading, checkedAt, refresh } = usePreviewStatus("status");
  const { installed, available } = state;
  // A successful status RPC actually verifies Python and the pinned package.
  // Git is absent here because this limited capability does not require Git.
  return <StatusPage theme={theme} layout={layout} loading={loading} error={error}
    headline={state.headline} checkedAt={available ? checkedAt : ""} onRefresh={refresh}
    guidance={state.notice ? `${state.notice} 请稍后刷新状态。` : installed ? "ZCode 与 WorkBuddy 已接入。新增内容请从命令中心的“设置记忆共享”继续，也可在两端聊天中明确要求新增公共记忆。" : "环境就绪不代表记忆已接入。请从命令中心的“设置记忆共享”继续。"}
    groups={available ? [
      { title: "运行环境", rows: [{ title: "Python", state: "ready" }] },
      { title: "插件与来源", rows: [{ title: "插件载荷", state: "ready" }, { title: "持久来源", state: "ready" }, { title: "记忆接入", state: installed ? "ready" : "absent" }] },
    ] : []}
    details={snapshot ? JSON.stringify({ ...snapshot, public_text: undefined }, null, 2) : undefined}>
    {snapshot?.externally_edited ? <Text style={{ color: theme.colors.statusDanger, lineHeight: 23 }}>公共记忆有外部修改，新增将停止；退出前仍会完整导出。</Text> : null}
    {typeof snapshot?.public_text === "string" ? <Details theme={theme} title="当前公共记忆" text={snapshot.public_text} /> : null}
    <Details theme={theme} title="Windows 支持范围" text={WINDOWS_SCOPE + " " + WINDOWS_SETUP} />
  </StatusPage>;
}

export function WindowsFlowScreen({ theme, layout, params }: PluginScreenProps) {
  const flow = params.flow ?? "onboard";
  const { snapshot, setSnapshot, status, state, error, loading, generation, refresh } = usePreviewStatus(flow);
  const plan = useRpc(windowsPreviewPlanRpc), confirm = useRpc(windowsPreviewConfirmRpc), cancel = useRpc(windowsPreviewCancelRpc);
  const [pending, setPending] = useState<PreviewReply>();
  const [reply, setReply] = useState<PreviewReply>();
  const [text, setText] = useState("");
  const [verifiedSetup, setVerifiedSetup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [showPlan, setShowPlan] = useState(false);
  const lock = useRef(false);
  useEffect(() => {
    setPending(undefined); setReply(undefined); setText(""); setVerifiedSetup(false);
    setBusy(false); setModalOpen(false); setShowPlan(false); lock.current = false;
  }, [status, flow]);
  const { installed, available: ready, waiting } = state;
  const operation = previewOperation(flow, installed);
  const unsupported = !["onboard", "uninstall"].includes(flow);
  const blocked = unsupported || Boolean(error) || waiting;
  async function run(work: () => Promise<PreviewReply>, preview = false) {
    if (lock.current || loading) return;
    lock.current = true; const epoch = generation.current;
    setBusy(true); setReply(undefined);
    const current = () => epoch === generation.current;
    try {
      const value = await work(); if (!current()) return;
      if (preview && value.status === "approval_required") {
        // Freeze the reviewed text separately from the editable form.
        setPending({ ...value, newText: operation === "add" ? text : undefined }); setShowPlan(false);
      } else {
        setPending(undefined); setReply(value); setModalOpen(false);
        if (value.status === "committed") {
          setText("");
          try { const fresh = await status({}); if (current()) setSnapshot(fresh); }
          catch { /* Keep the authoritative commit result if refresh fails. */ }
        }
      }
    } catch {
      if (current()) { setPending(undefined); setReply({ status: "unknown", message: "RPC 中断，结果未知；请保留备份和事务记录，核对状态后再操作。" }); }
    } finally { if (current()) { lock.current = false; setBusy(false); } }
  }
  const previewText = String(pending?.newText ?? "");
  const planKind = pending ? OPERATION_LABELS[pending.operation as keyof typeof OPERATION_LABELS] : "";
  const ok = reply?.status === "committed" || reply?.status === "rejected";
  const message = reply?.status === "committed" ? reply.action === "add" ? "公共记忆已新增。" : reply.action === "exit" ? "预览接入已退出，共享内容已导出保留。" : "记忆共享已接入。"
    : reply?.status === "rejected" ? "已拒绝本次计划，未执行变更。" : String(reply?.message ?? "操作结果待核对");
  const c = theme.colors;
  const inputStyle = { color: c.foreground, borderColor: c.border, borderWidth: 1, borderRadius: 8, padding: 14, minHeight: 100, textAlignVertical: "top" as const, backgroundColor: c.surface1 };
  return <View style={{ flex: 1, backgroundColor: c.surface0 }}>
    <FlowPage theme={theme} layout={layout} {...flowCopy(flow)} blocked={blocked && !pending && !reply}
      stage={flowStage(loading || busy ? "loading" : pending ? "preview" : reply ? "result" : waiting ? "loading" : blocked ? "gate" : "form", Boolean(ok))}>

      {loading || busy ? <Text accessibilityLiveRegion="polite" style={{ color: c.foreground, lineHeight: 24 }}>◌ 正在读取或准备当前步骤，请稍候…</Text> : blocked && !pending && !reply ? <>
        <Text style={{ color: c.foreground, lineHeight: 24 }}>{unsupported ? "此操作在 Windows 双端预览中暂不可用。" : state.notice ?? error}</Text>
        <Details theme={theme} title="Windows 支持范围" text={WINDOWS_SCOPE} />
        {!unsupported ? <PrimaryAction theme={theme} label={waiting ? "刷新状态" : "重新预览"} onPress={refresh} /> : null}
      </> : pending ? <PlanPreview theme={theme} summary={previewRows(pending, previewText)}
        planText={JSON.stringify(publicPreview(pending, previewText), null, 2)} planKind={planKind} digest={String(pending.digest)}
        expanded={showPlan} onExpandedChange={setShowPlan} onConfirm={() => setModalOpen(true)} /> : reply ? <>
        <OperationResult theme={theme} ok={Boolean(ok)} message={message} detail={JSON.stringify(reply, null, 2)}
          rows={reply.export && typeof reply.export === "object" ? [{ label: "导出位置", value: String((reply.export as PreviewReply).path) }] : undefined} />
        {!ok ? <Action onPress={() => setReply(undefined)}><Text style={{ color: c.accent }}>返回填写并重试</Text></Action> : null}
      </> : ready ? <View style={{ gap: 12 }}>
        <Text style={{ color: c.foregroundMuted, fontSize: 13, lineHeight: 22 }}>{WINDOWS_SCOPE}</Text>
        {flow === "uninstall" ? <Text style={{ color: c.foreground, lineHeight: 24 }}>{installed ? "本次退出预览接入：先导出当前公共记忆，再恢复两端原有入口，保留备份。不同于 macOS 的完整融合归还。" : "当前尚未接入预览，无需退出。"}</Text> : <>
          <Text style={{ color: c.foreground, fontSize: 14, lineHeight: 24 }}>参与共享的 Agent</Text>
          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>{["ZCode", "WorkBuddy"].map(name => <View key={name} style={{ paddingVertical: 10, paddingHorizontal: 12, borderRadius: 999, borderWidth: 1, borderColor: c.accent, backgroundColor: c.surface2 }}><Text style={{ color: c.foreground }}>✓ {name}</Text></View>)}</View>
          {installed ? <>
            <Text style={{ color: c.foregroundMuted, lineHeight: 22 }}>两端已接入。平时可在聊天中要求“把这条记忆加入公共记忆：……”。也可在下方填写新增内容。</Text>
            <TextInput multiline value={text} onChangeText={setText} accessibilityLabel="明确新增的公共记忆" placeholder="输入要共享的新内容" placeholderTextColor={c.foregroundMuted} style={inputStyle} />
          </> : <Action accessibilityRole="checkbox" accessibilityState={{ checked: verifiedSetup }} onPress={() => setVerifiedSetup(value => !value)}>
            <Text style={{ color: c.foreground, lineHeight: 24 }}>{verifiedSetup ? "☑" : "☐"} 已核对 {WINDOWS_SETUP}</Text>
          </Action>}
        </>}
        <PrimaryAction theme={theme} label="生成精确预览" disabled={flow === "uninstall" ? !installed : installed ? !text.trim() : !verifiedSetup}
          onPress={() => run(() => plan({ operation, text: operation === "add" ? text : undefined, verifiedSetup }), true)} />
      </View> : null}
    </FlowPage>
    <PlanConfirmation theme={theme} layout={layout} open={modalOpen && Boolean(pending)} onOpenChange={setModalOpen}
      planKind={planKind} digest={String(pending?.digest ?? "")} danger={flow === "uninstall"} busy={busy}
      onConfirm={() => { setModalOpen(false); return run(() => confirm({ confirmationToken: String(pending?.confirmationToken) })); }}
      onReject={() => { setModalOpen(false); return run(() => cancel({})); }} />
  </View>;
}
