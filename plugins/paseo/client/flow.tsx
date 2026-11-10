// memSharing Paseo plugin — one-time flow screen.
// Opened from Command Center items with string params. Runs one preview,
// shows the exact plan summary (and the full plan JSON on demand), and asks
// for an explicit confirm/reject press in a host Modal for planned operations.
// Fusion selection executes directly without that modal. Confirm sends only
// the plan digest — the server holds the plan and builds the approval file.
// The modal closes after confirm or reject; this is not a management page.

import { useMemo, useState, useRef, useEffect } from "react";
import { Text, TextInput, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import type { PluginTheme } from "@getpaseo/plugin";
import { useRpc } from "@getpaseo/plugin/client";
import { FlowPage, PlanPreview, PlanConfirmation, OperationResult, PrimaryAction } from "./presentation";
import {
  fusionPreviewRpc, fusionSelectRpc, fusionConfirmRpc,
  dependencyConfirmRpc, dependencyPreviewRpc,
  cancelPendingRpc,
  operationStatusRpc,
  bootstrapPreviewRpc,
  bootstrapConfirmRpc,
  machinePreviewRpc,
  machineConfirmRpc,
  projectCheckRpc,
  projectEnablePreviewRpc,
  projectEnableConfirmRpc,
  ckPreviewRpc, detectAgentsRpc,
  ckConfirmRpc,
  recoverPreviewRpc,
  recoverConfirmRpc,
  uninstallPreviewRpc, uninstallConfirmRpc, stagingCleanupPreviewRpc, stagingCleanupConfirmRpc,
  uninstallRecoverPreviewRpc, uninstallRecoverConfirmRpc,
} from "../shared/contracts";

import { Action as Pressable, Details, AGENT_LABELS } from "./ui";
import { fusionGroups, fusionResult, record, contextKeeperResult } from "./fusion";
import { uninstallResult, externalSteps, publicPlan } from "./uninstall-result";
import { PlatformScreen } from "./platform";
import { flowCopy, flowStage } from "./presentation-model";

type Phase =
  | { kind: "ckChoice"; prompt: string; agents: string[]; choices: string[] }
  | { kind: "fusion"; envelope: Record<string, unknown>; original?: string }
  | { kind: "form" }
  | { kind: "loading" }
  | { kind: "preview"; flow: "fusion" | "dependency" | "onboard" | "machine" | "enable" | "uninstall" | "stagingCleanup" | "uninstallRecover" | "ck" | "recover"; planKind: string; digest: string; confirmationToken: string; summary: { label: string; value: string }[]; planText: string }
  | { kind: "gate"; message: string; detail?: string; needsConversion?: boolean }
  | { kind: "busy"; message: string }
  | { kind: "result"; ok: boolean; message: string; detail?: string; continuation?: string; rows?: { label: string; value: string }[] };

const AGENT_CHOICES = ["codex", "claude", "workbuddy", "dsh", "zcode", "opencode"] as const;
type AgentName = (typeof AGENT_CHOICES)[number];

function JsonBlock({ theme, text }: { theme: PluginTheme; text: string }) {
  return <View style={{ backgroundColor: theme.colors.surface2, padding: 16, borderRadius: 12, minWidth: 0 }}>
    <Text selectable style={{ color: theme.colors.foregroundMuted, fontSize: 12, lineHeight: 21, flexShrink: 1 }}>{text}</Text>
  </View>;
}

function describe(status: string, detail?: string): string {
  const suffix = detail && detail.length > 0 ? `：${detail}` : "";
  if (status === "missing_dependency") return "缺少运行依赖" + suffix;
  if (status === "identity_missing") return "发行身份缺失（开发源码不能引导安装）" + suffix;
  if (status === "payload_missing") return "插件载荷缺失" + suffix;
  if (status === "already_prepared") return "来源已就绪" + suffix;
  if (status === "completed") return "操作完成（无需批准）";
  if (status === "failed") return "执行失败" + suffix;
  return status + suffix;
}


function gateOutcome(result: { status: string; message?: string; detail?: string; envelope?: Record<string, unknown> }): Extract<Phase, { kind: "gate" }> {
  let errors: unknown = result.envelope?.errors;
  if (!Array.isArray(errors) && result.message) {
    try { errors = JSON.parse(result.message); } catch { /* Non-JSON errors retain the original presentation. */ }
  }
  const missingConversion = Array.isArray(errors) && errors.some(value => {
    const error = record(value);
    return error?.code === "machine_route_future" && typeof error.message === "string" && error.message.includes("no supported source conversion");
  });
  if (missingConversion) return {
    kind: "gate", needsConversion: true,
    message: "当前安装与目标版本之间缺少已审核的转换方案，已停止预览。",
    detail: JSON.stringify(result.envelope ?? result, null, 2),
  };
  return { kind: "gate", message: describe(result.status, result.message ?? result.detail) };
}


export function FlowScreen(props: PluginScreenProps) {
  return <PlatformScreen screen={props}><MacFlowScreen {...props} /></PlatformScreen>;
}

function MacFlowScreen({ params, theme, layout }: PluginScreenProps) {
  const fusionPreview = useRpc(fusionPreviewRpc);
  const fusionSelect = useRpc(fusionSelectRpc);
  const fusionConfirm = useRpc(fusionConfirmRpc);
  const [fusionScope, setFusionScope] = useState<"user" | "project">("user");
  const [fusionToken, setFusionToken] = useState<string>();
  const [selection, setSelection] = useState("按默认方案");
  const [retentions, setRetentions] = useState("");
  const [retentionError, setRetentionError] = useState("");
  const flow = params.flow ?? "onboard";
  const projectRoot = params.projectRoot ?? "";
  const bootstrapPreview = useRpc(bootstrapPreviewRpc);
  const dependencyPreview = useRpc(dependencyPreviewRpc);
  const dependencyConfirm = useRpc(dependencyConfirmRpc);
  const bootstrapConfirm = useRpc(bootstrapConfirmRpc);
  const machinePreview = useRpc(machinePreviewRpc);
  const machineConfirm = useRpc(machineConfirmRpc);
  const projectCheck = useRpc(projectCheckRpc);
  const enablePreview = useRpc(projectEnablePreviewRpc);
  const enableConfirm = useRpc(projectEnableConfirmRpc);
  const ckPreview = useRpc(ckPreviewRpc);
  const ckConfirm = useRpc(ckConfirmRpc);
  const recoverPreviewRpcCall = useRpc(recoverPreviewRpc);
  const recoverConfirmRpcCall = useRpc(recoverConfirmRpc);

  const uninstallPreview = useRpc(uninstallPreviewRpc);
  const uninstallConfirm = useRpc(uninstallConfirmRpc);
  const stagingPreview = useRpc(stagingCleanupPreviewRpc);
  const stagingConfirm = useRpc(stagingCleanupConfirmRpc);
  const uninstallRecoverPreview = useRpc(uninstallRecoverPreviewRpc);
  const uninstallRecoverConfirm = useRpc(uninstallRecoverConfirmRpc);
  const [backupDir, setBackupDir] = useState("");
  const [evidenceDir, setEvidenceDir] = useState("");
  const [manifestPath, setManifestPath] = useState("");
  const [uninstallAction, setUninstallAction] = useState<"restore" | "resume">("restore");
  const [phase, setPhase] = useState<Phase>({ kind: "form" });
  const [showPlan, setShowPlan] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [agents, setAgents] = useState<AgentName[]>([]);
  const detectAgents = useRpc(detectAgentsRpc);
  const [detectionEvidence, setDetectionEvidence] = useState("");
  const [showDetection, setShowDetection] = useState(false);
  const [availableAgents, setAvailableAgents] = useState<AgentName[]>([]);
  const [detectionDetail, setDetectionDetail] = useState("正在读取实际安装事实…");
  useEffect(() => {
    if (flow !== "onboard" && flow !== "enable") return;
    let active = true;
    void detectAgents({}).then(result => {
      if (!active) return;
      const facts = record(record(result.envelope.facts)?.agents);
      const installed = AGENT_CHOICES.filter(name => record(facts?.[name])?.status === "installed");
      setDetectionEvidence(JSON.stringify(facts ?? result.envelope, null, 2));
      setAvailableAgents(installed); setAgents(installed);
      setDetectionDetail(result.status === "completed" ? "实际安装名单；CLI 与 App 的证据分别保留在探测详情。" : "探测未完成，请重开入口后重试。");
    }).catch(() => { if (active) setDetectionDetail("探测失败，请重开入口后重试。"); });
    return () => { active = false; };
  }, [detectAgents, flow]);
  const cancelPending = useRpc(cancelPendingRpc);
  const operations = useRpc(operationStatusRpc);
  const currentFlow = useRef<"fusion" | "dependency" | "bootstrap" | "machine" | "enable" | "uninstall" | "stagingCleanup" | "ck" | "recover">("bootstrap");
  const previewLock = useRef(false);
  const fusionLock = useRef(false);
  const confirmLock = useRef(false);
  const [cancelMessage, setCancelMessage] = useState("");
  const [journalPath, setJournalPath] = useState("");
  const [recoverAction, setRecoverAction] = useState<"continue" | "rollback">("continue");

  const styles = useMemo(
    () => ({
      screen: { flex: 1, backgroundColor: theme.colors.surface0 },
      label: { color: theme.colors.foregroundMuted, fontSize: 13, lineHeight: 22 },
      detail: { color: theme.colors.foreground, fontSize: 14, lineHeight: 24, flexShrink: 1 },
      button: { minHeight: 44, justifyContent: "center" as const, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 10, backgroundColor: theme.colors.accent, alignSelf: "flex-start" as const },
      buttonText: { color: theme.colors.accentForeground, fontWeight: "600" as const },
      secondary: { minHeight: 44, justifyContent: "center" as const, paddingVertical: 12, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: theme.colors.border, alignSelf: "flex-start" as const, backgroundColor: theme.colors.surface1 },
      secondaryText: { color: theme.colors.foreground, fontWeight: "600" as const },
      chip: (active: boolean) => ({
        minHeight: 44,
        justifyContent: "center" as const,
        paddingVertical: 10,
        paddingHorizontal: 12,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: active ? theme.colors.accent : theme.colors.border,
        backgroundColor: active ? theme.colors.surface2 : theme.colors.surface1,
      }),
      chipText: (active: boolean) => ({ color: active ? theme.colors.foreground : theme.colors.foregroundMuted, fontSize: 13 }),
    }),
    [theme, layout.compact],
  );

  function finishUserMemory(envelope: Record<string, unknown>, message = fusionResult(envelope)) {
    const ck = record(envelope.context_keeper);
    if (ck?.status === "pending_selection" && typeof ck.prompt === "string") {
      setPhase({ kind: "ckChoice", prompt: ck.prompt, agents: Array.isArray(ck.agents) ? ck.agents.map(String) : [],
        choices: Array.isArray(ck.choices) ? ck.choices.map(String) : [] });
    } else setPhase({ kind: "result", ok: true, message, detail: JSON.stringify(envelope, null, 2) });
  }

  async function startFusion(envelope: Record<string, unknown>, scope: "user" | "project") {
    if (envelope.approval_plan === null && Array.isArray(envelope.changes) && envelope.changes.length === 0) {
      setPhase({ kind: "result", ok: true, message: "已安装，已接入。" }); return;
    }
    const stage = record(envelope.fusion);
    if (stage?.status === "blocked") {
      setPhase({ kind: "result", ok: false, message: "接入已完成；记忆融合预览受阻。", detail: JSON.stringify(stage.preview, null, 2) }); return;
    }
    if (!stage || stage.automatic_continue !== true) {
      if (scope === "user") finishUserMemory(envelope, "接入完成。");
      else setPhase({ kind: "result", ok: true, message: "项目规则接入完成。", detail: JSON.stringify(envelope, null, 2) });
      return;
    }
    setFusionScope(scope); setFusionToken(undefined); setSelection("按默认方案"); setRetentions("");
    currentFlow.current = "fusion";
    const next = await fusionPreview({ scope, ...(scope === "project" ? { projectRoot } : {}) });
    setFusionToken(next.contextToken);
    if (next.status === "completed" && ["completed", "declined", "unchanged"].includes(String(next.envelope.fusion_status))) {
      if (scope === "user") finishUserMemory(next.envelope);
      else setPhase({ kind: "result", ok: true, message: fusionResult(next.envelope) });
      return;
    }
    setPhase(next.status === "completed" ? { kind: "fusion", envelope: next.envelope } : { kind: "result", ok: false, message: "融合预览受阻；接入结果保留。", detail: JSON.stringify(next.envelope, null, 2) });
  }

  async function chooseFusion(choice?: string, decline = false) {
    if (fusionLock.current) return;
    let locations: Record<string, string> | undefined;
    if (!decline && !(choice ?? selection).trim().startsWith("查看") && retentions.trim()) {
      try {
        const parsed: unknown = JSON.parse(retentions);
        if (!record(parsed) || !Object.values(parsed as Record<string, unknown>).every(value => typeof value === "string" && value.trim().length > 0)) {
          throw new Error("请使用编号到原生文件路径的 JSON 对象");
        }
        locations = parsed as Record<string, string>;
      } catch {
        setRetentionError('保留位置格式有误。请输入 JSON 对象，例如 {"1":"CLAUDE.md"}；本次未发送请求，原编号和输入保留。');
        return;
      }
    }
    setRetentionError("");
    fusionLock.current = true;
    setCancelMessage(""); setPhase({ kind: "loading" }); currentFlow.current = "fusion";
    try {
      const next = await fusionSelect({ scope: fusionScope, ...(fusionScope === "project" ? { projectRoot } : {}),
        contextToken: fusionToken!, ...(decline ? { decline: true } : { selection: choice ?? selection }),
        ...(locations && !decline && !(choice ?? selection).trim().startsWith("查看") ? { retentions: locations } : {}) });
      if (next.status === "failed") { setPhase({ kind: "result", ok: false, message: "融合未完成，写入结果需核对；请保留现场，查看错误与 manifest 后恢复。", detail: JSON.stringify(next.envelope, null, 2) }); return; }
      setFusionToken(next.contextToken);
      if (["completed", "declined", "unchanged"].includes(String(next.envelope.fusion_status))) {
        if (fusionScope === "user") finishUserMemory(next.envelope);
        else setPhase({ kind: "result", ok: true, message: fusionResult(next.envelope) }); return;
      }
      const plan = record(next.envelope.approval_plan);
      const viewed = typeof plan?.view === "number" ? fusionGroups(next.envelope).find(g => g.number === plan.view) : undefined;
      setPhase({ kind: "fusion", envelope: next.envelope, original: viewed?.original });
    } catch (error) { setPhase({ kind: "result", ok: false, message: "融合请求未能确认结果；请重新预览并核对现场。", detail: String(error) }); } finally { fusionLock.current = false; }
  }

  async function runPreview(): Promise<void> {
    if (previewLock.current) return;
    previewLock.current = true;
    currentFlow.current = flow === "onboard" ? "bootstrap" : flow === "check" ? "enable" : flow === "uninstallRecover" ? "recover" : flow as typeof currentFlow.current;
    setPhase({ kind: "loading" });
    try {
      if (flow === "uninstall") {
        const result = await uninstallPreview({ backupDir: backupDir.trim() });
        adoptPreview("uninstall", "uninstall-machine", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "stagingCleanup") {
        const result = await stagingPreview({ evidenceDir: evidenceDir.trim() });
        adoptPreview("stagingCleanup", "host-staging-cleanup", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "uninstallRecover") {
        const result = await uninstallRecoverPreview({ manifest: manifestPath.trim(), action: uninstallAction });
        adoptPreview("uninstallRecover", "recover-uninstall", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "check") {
        const result = await projectCheck({ projectRoot });
        setPhase({
          kind: "result",
          ok: result.status === "completed",
          message: result.status === "completed" ? "项目检查完成，未发现接入缺口。" : result.status === "gaps" ? "发现项目接入缺口，请查看完整结果。" : "项目检查失败，请查看错误详情。",
          detail: JSON.stringify(result.envelope, null, 2),
        });
        return;
      }
      if (flow === "enable") {
        const result = await enablePreview({ projectRoot, agents });
        if (result.status === "completed") await startFusion(result.envelope, "project");
        else adoptPreview("enable", "enable-memory", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "ck") {
        const result = await ckPreview({});
        adoptPreview("ck", "install-context-keeper", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "recover") {
        const result = await recoverPreviewRpcCall({ journalPath: journalPath.trim(), action: recoverAction });
        adoptPreview("recover", "machine-recovery", result, setPhase, setShowPlan);
        return;
      }
      if (flow !== "onboard") { setPhase({ kind: "gate", message: "未知操作入口；请从 Command Center 重新选择。" }); return; }
      if (agents.length === 0) {
        const tools = await dependencyPreview({});
        if (tools.status !== "completed") { adoptPreview("dependency", "prepare-tool-assets", tools, setPhase, setShowPlan); return; }
        const detected = await detectAgents({});
        if (detected.status !== "completed") {
          setDetectionEvidence(JSON.stringify(detected.envelope, null, 2));
          setShowDetection(true);
          setAvailableAgents([]); setAgents([]);
          setDetectionDetail("安装探测失败，尚不能确定实际名单；请查看原始结果，再点击生成精确预览重试。");
          setPhase({ kind: "form" }); return;
        }
        const facts = record(record(detected.envelope.facts)?.agents);
        const installed = AGENT_CHOICES.filter(name => record(facts?.[name])?.status === "installed");
        setDetectionEvidence(JSON.stringify(facts ?? detected.envelope, null, 2));
        setAvailableAgents(installed); setAgents(installed);
        setDetectionDetail(installed.length ? "环境已就绪，请选择实际安装的 Agent。" : "本次未发现已安装的 Agent；请检查 CLI/App 安装后重试。");
        setPhase({ kind: "form" }); return;
      }
      const result = await bootstrapPreview({});
      if (result.status === "completed") {
        setPhase({ kind: "result", ok: true, message: "已安装，已接入。" }); return;
      }
      if (result.status === "already_prepared") {
        currentFlow.current = "machine";
        const machine = await machinePreview({ agents });
        if (machine.status === "completed") { await startFusion(machine.envelope, "user"); return; }
        adoptPreview("machine", machine.status === "approval_required" ? machine.planKind : "install-machine", machine, setPhase, setShowPlan);
        if (machine.status !== "approval_required") {
          setPhase(gateOutcome(machine));
        }
        return;
      }
      adoptPreview("onboard", result.status === "approval_required" ? result.planKind : "prepare-release-source", result, setPhase, setShowPlan);
    } catch (error) {
      setPhase({ kind: "result", ok: false, message: "RPC 中断，结果未知；请检查操作状态后恢复", detail: String(error) });
    } finally { previewLock.current = false; }
  }

  async function confirmPlan(action: "confirm" | "reject"): Promise<void> {
    if (phase.kind !== "preview" || confirmLock.current) return;
    confirmLock.current = true;
    currentFlow.current = phase.flow === "onboard" ? "bootstrap" : phase.flow === "uninstallRecover" ? "recover" : phase.flow;
    setCancelMessage("");
    setPhase({ kind: "busy", message: action === "confirm" ? "正在执行已确认计划…" : "已拒绝，清除待批计划…" });
    try {
      const input = { action, confirmationToken: phase.confirmationToken };
      let outcome;
      if (phase.flow === "fusion") outcome = await fusionConfirm(input);
      else if (phase.flow === "dependency") outcome = await dependencyConfirm(input);
      else if (phase.flow === "onboard") outcome = await bootstrapConfirm(input);
      else if (phase.flow === "machine") outcome = await machineConfirm(input);
      else if (phase.flow === "enable") outcome = await enableConfirm(input);
      else if (phase.flow === "uninstall") outcome = await uninstallConfirm(input);
      else if (phase.flow === "stagingCleanup") outcome = await stagingConfirm(input);
      else if (phase.flow === "uninstallRecover") outcome = await uninstallRecoverConfirm(input);
      else if (phase.flow === "ck") outcome = await ckConfirm(input);
      else outcome = await recoverConfirmRpcCall(input);
      if (outcome.status === "rejected") {
        setPhase({ kind: "result", ok: true, message: "已拒绝；未执行计划中的写入。" });
      } else if (outcome.status === "stale_plan" || outcome.status === "no_pending_plan") {
        setPhase({ kind: "gate", message: describe(outcome.status, outcome.detail) });
      } else if (outcome.status === "acquired") {
        const next = await machinePreview({ agents });
        if (next.status === "completed") await startFusion(next.envelope, "user");
        else adoptPreview("machine", "install-machine", next, setPhase, setShowPlan);
      } else if (outcome.status === "completed") {
        if (phase.flow === "fusion") {
          setPhase({ kind: "result", ok: true, message: fusionResult(outcome.envelope), detail: JSON.stringify(outcome.envelope, null, 2) });
        } else if (phase.flow === "machine" || phase.flow === "enable") {
          await startFusion(outcome.envelope, phase.flow === "enable" ? "project" : "user");
        } else if (phase.flow === "uninstall" || (phase.flow === "uninstallRecover" && outcome.envelope.status === "completed")) {
          const shown = uninstallResult(outcome.envelope);
          setPhase({ kind: "result", ...shown, continuation: externalSteps(outcome.envelope, JSON.parse(phase.planText)), detail: JSON.stringify(outcome.envelope, null, 2) });
        } else if (phase.flow === "stagingCleanup") {
          setPhase({ kind: "result", ok: true, message: "宿主暂存已外置并清理；继续整机卸载须另起预览和批准。", detail: JSON.stringify(outcome.envelope, null, 2) });
        } else if (phase.flow === "ck" && outcome.envelope.status !== "source_prepared") {
          setPhase({ kind: "result", ok: true, message: contextKeeperResult(outcome.envelope), detail: JSON.stringify(outcome.envelope, null, 2) });
        } else if (outcome.envelope.status === "tool_assets_ready") {
          await runPreview();
        } else if (outcome.envelope.status === "source_prepared") {
          const next = await ckPreview({});
          adoptPreview("ck", "install-context-keeper", next, setPhase, setShowPlan);
        } else {
          setPhase({ kind: "result", ok: true, message: "执行完成。", detail: JSON.stringify(outcome.envelope, null, 2) });
        }
      } else {
        setPhase({ kind: "result", ok: false, message: `执行失败：${outcome.code}`, detail: `${outcome.message}\n${JSON.stringify(outcome.envelope ?? {}, null, 2)}` });
      }
    } catch (error) {
      setPhase({ kind: "result", ok: false, message: "RPC 中断，结果未知；请检查操作状态后恢复", detail: String(error) });
    } finally { confirmLock.current = false; }
  }

  const picksAgents = flow === "onboard" || flow === "enable";

  const inputStyle = {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    minHeight: 48,
    padding: 14,
    color: theme.colors.foreground,
    backgroundColor: theme.colors.surface1,
  };

  return (
    <View style={styles.screen}>
      <FlowPage theme={theme} layout={layout} {...flowCopy(flow)} blocked={phase.kind === "gate"}
        stage={flowStage(phase.kind, phase.kind === "result" && phase.ok)}>

      {projectRoot.length > 0 ? <Details theme={theme} title="当前项目路径" text={projectRoot} /> : null}

      {phase.kind === "form" ? (
        <View style={{ gap: 12 }}>
          {flow === "uninstall" ? <View style={{ gap: 8 }}><Text style={styles.label}>全新外置备份目录（父目录须已存在）</Text><TextInput accessibilityLabel="全新外置备份目录" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={backupDir} onChangeText={setBackupDir} placeholder="/absolute/new-backup" /><Text style={styles.label}>归还当前公共记忆后删除机器资产；Paseo 插件本体需随后从独立终端移除。默认保留 Context Keeper。</Text></View> : null}
          {flow === "stagingCleanup" ? <View style={{ gap: 8 }}><Text style={styles.label}>已存在的独立外置证据父目录</Text><TextInput accessibilityLabel="外置证据目录" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={evidenceDir} onChangeText={setEvidenceDir} placeholder="/absolute/evidence-directory" /><Text style={styles.label}>单独预览与批准；只处理可证明终态的暂存。中断后保留现场与外置副本，不能把失败当清空。</Text></View> : null}
          {flow === "uninstallRecover" ? <View style={{ gap: 8 }}><Text style={styles.label}>外置 manifest 绝对路径</Text><TextInput accessibilityLabel="外置恢复清单路径" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={manifestPath} onChangeText={setManifestPath} /><View style={{ flexDirection: layout.compact ? "column" : "row", flexWrap: "wrap", gap: 8 }}>{(["restore", "resume"] as const).map(action => <Pressable key={action} accessibilityRole="radio" accessibilityState={{ checked: uninstallAction === action }} style={styles.chip(uninstallAction === action)} onPress={() => setUninstallAction(action)}><Text style={styles.detail}>{action === "restore" ? "恢复原状" : "继续卸载"}</Text></Pressable>)}</View></View> : null}
          {picksAgents ? (
            <View style={{ gap: 8 }}>
              <Text style={styles.detail}>选择参与共享的 Agent</Text>
              <Text style={styles.label}>{detectionDetail}</Text>
              <Text style={styles.label}>已选择 {agents.length} 家 · 请核对下方实际名单</Text>
              {detectionEvidence ? <Pressable accessibilityState={{ expanded: showDetection }} onPress={() => setShowDetection(!showDetection)}><Text style={{ color: theme.colors.accent }}>查看 CLI / App 安装证据</Text></Pressable> : null}
              {showDetection ? <JsonBlock theme={theme} text={detectionEvidence} /> : null}
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {availableAgents.map((name) => (
                  <Pressable
                    key={name}
                    accessibilityRole="checkbox" accessibilityState={{ checked: agents.includes(name) }}
                    style={styles.chip(agents.includes(name))}
                    onPress={() =>
                      setAgents((current: AgentName[]) => (current.includes(name) ? current.filter((item: AgentName) => item !== name) : [...current, name]))
                    }
                  >
                    <Text style={styles.chipText(agents.includes(name))}>{agents.includes(name) ? "✓ " : "+ "}{AGENT_LABELS[name] ?? name}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          {flow === "ck" ? <Text style={styles.label}>Context Keeper 帮助 Agent 在新会话接续项目进展、决策和经验。支持范围以当次上游安装计划为准；获取当前 main 来源与安装分别批准。</Text> : null}
          {flow === "recover" ? (
            <View style={{ gap: 8 }}>
              <Pressable style={styles.secondary} onPress={() => { return operations({}).then(records => {
                const pending = records.find(r => r.state === "unknown" && typeof r.journal === "string");
                if (pending) setJournalPath(String(pending.journal));
                else setPhase({ kind: "result", ok: false, message: "未找到可自动恢复的未知操作", detail: JSON.stringify(records, null, 2) });
              }).catch(error => setPhase({ kind: "result", ok: false, message: "读取未完成操作失败，请保留现场后重试。", detail: String(error) })); }}><Text style={styles.secondaryText}>查找未完成操作</Text></Pressable>
              <Text style={styles.label}>操作 journal 绝对路径</Text>
              <TextInput accessibilityLabel="未完成操作记录路径" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={journalPath} onChangeText={setJournalPath} placeholder="/absolute/path/to/journal.json" />
              <View style={{ flexDirection: layout.compact ? "column" : "row", flexWrap: "wrap", gap: 8 }}>
                {(["continue", "rollback"] as const).map((choice) => (
                  <Pressable key={choice} accessibilityRole="radio" accessibilityState={{ checked: recoverAction === choice }} style={styles.chip(recoverAction === choice)} onPress={() => setRecoverAction(choice)}>
                    <Text style={styles.chipText(recoverAction === choice)}>{choice === "continue" ? "继续完成" : "回滚"}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          <PrimaryAction theme={theme} label="生成精确预览"
            disabled={(flow === "enable" && agents.length === 0) || (flow === "recover" && !journalPath.trim()) || (flow === "uninstall" && !backupDir.trim()) || (flow === "stagingCleanup" && !evidenceDir.trim()) || (flow === "uninstallRecover" && !manifestPath.trim())}
            onPress={() => {
              if (flow === "enable" && agents.length === 0) return;
              if (flow === "recover" && journalPath.trim().length === 0) return;
              if (flow === "uninstall" && !backupDir.trim()) return;
              if (flow === "stagingCleanup" && !evidenceDir.trim()) return;
              if (flow === "uninstallRecover" && !manifestPath.trim()) return;
              return runPreview();
            }}
          />
        </View>
      ) : null}

      {phase.kind === "ckChoice" ? <View style={{ gap: 12 }}>
        <Text style={styles.detail}>{phase.prompt}</Text>
        <Text style={styles.label}>{phase.agents.map(name => AGENT_LABELS[name] ?? name).join("、")}</Text>
        {phase.choices.includes("安装") ? <Pressable style={styles.button} onPress={() => { currentFlow.current = "ck"; setPhase({ kind: "loading" }); return ckPreview({}).then(next => adoptPreview("ck", "install-context-keeper", next, setPhase, setShowPlan)).catch(error => setPhase({ kind: "result", ok: false, message: "Context Keeper 准备失败；公共记忆结果保留。", detail: String(error) })); }}><Text style={styles.buttonText}>安装 Context Keeper</Text></Pressable> : null}
        {phase.choices.includes("跳过") ? <Pressable style={styles.secondary} onPress={() => setPhase({ kind: "result", ok: true, message: "已跳过 Context Keeper；公共用户记忆结果保留。" })}><Text style={styles.secondaryText}>跳过</Text></Pressable> : null}
      </View> : null}

      {phase.kind === "fusion" ? <View style={{ gap: 16 }}>
        <Text style={styles.detail}>查看每项原文与来源，再按稳定编号选择。未选内容保留；查看或暂不融合不会修改记忆。</Text>
        <View style={{ padding: 16, borderRadius: 12, gap: 8, backgroundColor: theme.colors.surface2 }}>
          <Text style={{ color: theme.colors.foreground, fontSize: 15, fontWeight: "600" }}>完整融合方案与选择说明</Text>
          <Text selectable style={styles.detail}>{typeof phase.envelope.prompt === "string" ? phase.envelope.prompt : fusionResult(phase.envelope)}</Text>
        </View>
        <Text style={styles.label}>{fusionResult(phase.envelope)}</Text>
        {fusionGroups(phase.envelope).map(group => <View key={group.number} style={{ padding: 16, gap: 8, borderRadius: 12, backgroundColor: theme.colors.surface2 }}>
          <Text style={styles.detail}>{group.number}. {group.summary || "记忆条目"}</Text>
          <Pressable onPress={() => chooseFusion(`查看 ${group.number}`)}><Text style={{ color: theme.colors.accent, lineHeight: 22 }}>查看 {group.number} 完整原文与来源 →</Text></Pressable>
        </View>)}
        {phase.original ? <JsonBlock theme={theme} text={phase.original} /> : null}
        <Text style={styles.label}>共享编号或组合输入，例如 3、4 / 不共享 2 / 共享 3、4，不共享 2 / 按默认方案</Text>
        <TextInput accessibilityLabel="融合选择：按默认方案或输入稳定编号" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={selection} onChangeText={setSelection} />
        {fusionScope === "project" ? <><Text style={styles.label}>排除已有公共项时，先逐条确认保留位置（编号到已参与原生文件的 JSON，例如 {`{"1":"CLAUDE.md"}`}）</Text><TextInput accessibilityLabel="项目规则保留位置" placeholderTextColor={theme.colors.foregroundMuted} style={inputStyle} value={retentions} onChangeText={value => { setRetentions(value); setRetentionError(""); }} />{retentionError ? <Text accessibilityRole="alert" style={{ color: theme.colors.statusDanger, fontSize: 13, lineHeight: 22 }}>{retentionError}</Text> : null}</> : null}
        <Pressable style={styles.button} onPress={() => chooseFusion()}><Text style={styles.buttonText}>按此次选择执行</Text></Pressable>
        <Pressable style={styles.secondary} onPress={() => chooseFusion(undefined, true)}><Text style={styles.secondaryText}>保留现状，暂不融合</Text></Pressable>
      </View> : null}

      {phase.kind === "loading" ? <Text accessibilityLiveRegion="polite" style={styles.detail}>◌ 正在读取或准备当前步骤，请稍候…</Text> : null}
      {phase.kind === "busy" ? <View style={{ gap: 8 }}><Text accessibilityLiveRegion="polite" style={styles.detail}>◌ {phase.message}</Text>
        {cancelMessage ? <Text style={styles.label}>{cancelMessage}</Text> : null}
        <Pressable style={styles.secondary} onPress={() => { return cancelPending({ flow: currentFlow.current }).then(() => setCancelMessage("取消请求已发送，当前结果仍待核对。请等待操作返回，勿重复执行。")).catch(error => setCancelMessage(`取消请求未能确认：${String(error)}。请保留现场并核对操作状态。`)); }}><Text style={styles.secondaryText}>取消运行（完成前结果未知）</Text></Pressable>
      </View> : null}

      {phase.kind === "gate" ? (
        <View style={{ gap: 8 }}>
          <Text style={styles.detail}>! {phase.message}</Text>
          {flow === "uninstall" ? <View style={{ gap: 8 }}><Text style={styles.label}>若暂存阻断，先独立外置清理（已有证据父目录）</Text><TextInput accessibilityLabel="外置证据目录" placeholderTextColor={theme.colors.foregroundMuted} value={evidenceDir} onChangeText={setEvidenceDir} style={inputStyle} /><Pressable style={styles.button} onPress={() => { if (evidenceDir.trim()) return stagingPreview({ evidenceDir: evidenceDir.trim() }).then(result => adoptPreview("stagingCleanup", "host-staging-cleanup", result, setPhase, setShowPlan)).catch(error => setPhase({ kind: "result", ok: false, message: "RPC 中断，结果未知；请保留暂存与外置证据后核对", detail: String(error) })); }}><Text style={styles.buttonText}>预览宿主暂存清理</Text></Pressable></View> : null}
          {phase.needsConversion ? <>
            <Text style={styles.label}>请先核对适用的升级方案，再继续设置记忆共享。重复预览不会补齐转换方案。</Text>
            {phase.detail ? <Details theme={theme} title="原始错误详情" text={phase.detail} /> : null}
          </> : <Pressable accessibilityRole="button" style={styles.secondary} onPress={() => runPreview()}>
            <Text style={styles.secondaryText}>重新预览</Text>
          </Pressable>}
        </View>
      ) : null}

      {phase.kind === "preview" ? <PlanPreview theme={theme} summary={phase.summary} planText={phase.planText}
        planKind={phase.planKind} digest={phase.digest} expanded={showPlan} onExpandedChange={setShowPlan} onConfirm={() => setModalOpen(true)}>
        {phase.flow === "fusion" ? <View style={{ gap: 8 }}>
          <Text style={styles.detail}>完整修改清单：参与范围、选中编号、原文、来源、目标与逐阶段变化如下；确认后才修改。</Text>
          {fusionGroups({ approval_plan: JSON.parse(phase.planText) }).map(group => <View key={group.number}><Text style={styles.label}>{group.number}. {group.summary}</Text><JsonBlock theme={theme} text={group.original} /></View>)}
          <Pressable onPress={() => startFusion({ fusion: { automatic_continue: true } }, fusionScope).catch(error => setPhase({ kind: "result", ok: false, message: "融合预览中断，请保留现场。", detail: String(error) }))}><Text style={{ color: theme.colors.accent }}>返回选择（旧批准作废）</Text></Pressable>
        </View> : null}
      </PlanPreview> : null}

      {phase.kind === "result" && flow === "uninstall" && !phase.continuation ? <Pressable style={styles.button} onPress={() => runPreview()}><Text style={styles.buttonText}>继续卸载预览</Text></Pressable> : null}
      {phase.kind === "result" && currentFlow.current === "fusion" && !phase.ok ? <Pressable style={styles.secondary} onPress={() => { return startFusion({ fusion: { automatic_continue: true } }, fusionScope).catch(error => setPhase({ kind: "result", ok: false, message: "融合预览中断，请保留现场。", detail: String(error) })); }}><Text style={styles.secondaryText}>重新预览融合（旧计划作废）</Text></Pressable> : null}
      {phase.kind === "result" && !phase.ok && currentFlow.current !== "fusion" ? <Pressable style={styles.secondary} onPress={() => setPhase({ kind: "form" })}><Text style={styles.secondaryText}>返回填写并重试</Text></Pressable> : null}
      {phase.kind === "result" ? <OperationResult theme={theme} ok={phase.ok} message={phase.message} detail={phase.detail} rows={phase.rows}>
        {phase.continuation ? <JsonBlock theme={theme} text={phase.continuation} /> : null}
      </OperationResult> : null}
      </FlowPage>
      <PlanConfirmation theme={theme} layout={layout} open={modalOpen && phase.kind === "preview"} onOpenChange={setModalOpen}
        planKind={phase.kind === "preview" ? phase.planKind : ""} digest={phase.kind === "preview" ? phase.digest : ""}
        danger={flow === "uninstall" || flow === "stagingCleanup"}
        onConfirm={() => { setModalOpen(false); return confirmPlan("confirm"); }}
        onReject={() => { setModalOpen(false); return confirmPlan("reject"); }} />
    </View>
  );
}

type AdoptResult = { status: string; message?: string; detail?: string; continuation?: string; rows?: { label: string; value: string }[] };

function adoptPreview(
  flow: "dependency" | "fusion" | "onboard" | "machine" | "enable" | "uninstall" | "stagingCleanup" | "uninstallRecover" | "ck" | "recover",
  planKind: string,
  result: { status: string; planKind?: string; digest?: string; confirmationToken?: string; summary?: { label: string; value: string }[]; plan?: Record<string, unknown>; message?: string; detail?: string; envelope?: Record<string, unknown> },
  setPhase: (phase: Phase) => void,
  setShowPlan: (value: boolean) => void,
): void {
  if (result.status === "approval_required" && result.digest && result.confirmationToken && result.plan) {
    setShowPlan(false);
    setPhase({
      kind: "preview",
      flow: result.planKind === "prepare-tool-assets" ? "dependency" : result.planKind === "prepare-release-source" ? "onboard" : flow,
      planKind: result.planKind ?? planKind,
      digest: result.digest,
      confirmationToken: result.confirmationToken,
      summary: result.summary ?? [],
      planText: JSON.stringify(flow === "fusion" ? result.plan : publicPlan(result.plan), null, 2),
    });
  } else if (result.status === "completed") {
    setPhase({ kind: "result", ok: true, message: flow === "ck" ? contextKeeperResult(result.envelope ?? {}) : describe(result.status), detail: JSON.stringify(result.envelope ?? {}, null, 2) });
  } else {
    setPhase(gateOutcome(result));
  }
}

export type { Phase, AdoptResult };
