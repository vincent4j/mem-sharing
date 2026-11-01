// memSharing Paseo plugin — one-time flow screen.
// Opened from Command Center items with string params. Runs one preview,
// shows the exact plan summary (and the full plan JSON on demand), and asks
// for an explicit confirm/reject press in a host Modal. Confirm sends only
// the plan digest — the server holds the plan and builds the approval file.
// The modal closes after confirm or reject; this is not a management page.

import { useMemo, useState, useRef } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import type { PluginTheme } from "@getpaseo/plugin";
import { useRpc } from "@getpaseo/plugin/client";
import { Modal } from "@getpaseo/plugin/client/ui";
import {
  cancelPendingRpc,
  operationStatusRpc,
  bootstrapPreviewRpc,
  bootstrapConfirmRpc,
  machinePreviewRpc,
  machineConfirmRpc,
  projectCheckRpc,
  projectEnablePreviewRpc,
  projectEnableConfirmRpc,
  projectRemovePreviewRpc,
  projectRemoveConfirmRpc,
  ckPreviewRpc,
  ckConfirmRpc,
  recoverPreviewRpc,
  recoverConfirmRpc,
} from "../shared/contracts";

type Phase =
  | { kind: "form" }
  | { kind: "loading" }
  | { kind: "preview"; flow: "onboard" | "machine" | "enable" | "remove" | "ck" | "recover"; planKind: string; digest: string; confirmationToken: string; summary: { label: string; value: string }[]; planText: string }
  | { kind: "gate"; message: string }
  | { kind: "busy"; message: string }
  | { kind: "result"; ok: boolean; message: string; detail?: string };

const AGENT_CHOICES = ["codex", "claude", "workbuddy", "dsh", "zcode"] as const;
type AgentName = (typeof AGENT_CHOICES)[number];

function JsonBlock({ theme, text }: { theme: PluginTheme; text: string }) {
  return (
    <ScrollView style={{ maxHeight: 220, backgroundColor: theme.colors.surface1, borderRadius: 8 }}>
      <Text style={{ color: theme.colors.foregroundMuted, fontSize: 11, padding: 8 }}>{text}</Text>
    </ScrollView>
  );
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

function titleFor(flow: string): string {
  if (flow === "onboard") return "memSharing 接入本机";
  if (flow === "check") return "memSharing 检查当前项目";
  if (flow === "enable") return "memSharing 启用当前项目";
  if (flow === "remove") return "memSharing 停用当前项目";
  if (flow === "ck") return "memSharing 可选安装 Context Keeper";
  if (flow === "recover") return "memSharing 恢复未完成操作";
  return "memSharing";
}

export function FlowScreen({ params, theme, layout }: PluginScreenProps) {
  const flow = params.flow ?? "onboard";
  const projectRoot = params.projectRoot ?? "";
  const bootstrapPreview = useRpc(bootstrapPreviewRpc);
  const bootstrapConfirm = useRpc(bootstrapConfirmRpc);
  const machinePreview = useRpc(machinePreviewRpc);
  const machineConfirm = useRpc(machineConfirmRpc);
  const projectCheck = useRpc(projectCheckRpc);
  const enablePreview = useRpc(projectEnablePreviewRpc);
  const enableConfirm = useRpc(projectEnableConfirmRpc);
  const removePreview = useRpc(projectRemovePreviewRpc);
  const removeConfirm = useRpc(projectRemoveConfirmRpc);
  const ckPreview = useRpc(ckPreviewRpc);
  const ckConfirm = useRpc(ckConfirmRpc);
  const recoverPreviewRpcCall = useRpc(recoverPreviewRpc);
  const recoverConfirmRpcCall = useRpc(recoverConfirmRpc);

  const [phase, setPhase] = useState<Phase>({ kind: "form" });
  const [showPlan, setShowPlan] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [memoryChoice, setMemoryChoice] = useState<"preserve" | "enable" | "disable">("preserve");
  const [agents, setAgents] = useState<AgentName[]>(["codex", "claude", "workbuddy"]);
  const cancelPending = useRpc(cancelPendingRpc);
  const operations = useRpc(operationStatusRpc);
  const currentFlow = useRef<"bootstrap" | "machine" | "enable" | "remove" | "ck" | "recover">("bootstrap");
  const [journalPath, setJournalPath] = useState("");
  const [recoverAction, setRecoverAction] = useState<"continue" | "rollback">("continue");

  const styles = useMemo(
    () => ({
      screen: { flex: 1, padding: layout.compact ? 16 : 24, gap: 12, backgroundColor: theme.colors.surface0 },
      title: { color: theme.colors.foreground, fontSize: layout.compact ? 18 : 22, fontWeight: "600" as const },
      label: { color: theme.colors.foregroundMuted, fontSize: 12 },
      detail: { color: theme.colors.foreground, fontSize: 14 },
      button: { paddingVertical: 10, paddingHorizontal: 16, borderRadius: 8, backgroundColor: theme.colors.accent, alignSelf: "flex-start" as const },
      buttonText: { color: theme.colors.accentForeground, fontWeight: "600" as const },
      chip: (active: boolean) => ({
        paddingVertical: 6,
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

  async function runPreview(): Promise<void> {
    currentFlow.current = flow === "onboard" ? "bootstrap" : flow === "check" ? "enable" : flow as "enable" | "remove" | "ck" | "recover";
    setPhase({ kind: "loading" });
    try {
      if (flow === "check") {
        const result = await projectCheck({ projectRoot });
        setPhase({
          kind: "result",
          ok: result.status !== "failed",
          message: `check-memory：${result.status}`,
          detail: JSON.stringify(result.envelope, null, 2),
        });
        return;
      }
      if (flow === "enable") {
        const result = await enablePreview({ projectRoot, agents, memory: memoryChoice === "preserve" ? undefined : memoryChoice });
        adoptPreview("enable", "enable-memory", result, setPhase, setShowPlan);
        return;
      }
      if (flow === "remove") {
        const result = await removePreview({ projectRoot });
        adoptPreview("remove", "remove-memory", result, setPhase, setShowPlan);
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
      const result = await bootstrapPreview({});
      if (result.status === "already_prepared") {
        currentFlow.current = "machine";
        const machine = await machinePreview({ agents });
        adoptPreview("machine", machine.status === "approval_required" ? machine.planKind : "install-machine", machine, setPhase, setShowPlan);
        if (machine.status !== "approval_required") {
          setPhase({ kind: "gate", message: describe(machine.status, "message" in machine ? machine.message : "detail" in machine ? machine.detail : undefined) });
        }
        return;
      }
      adoptPreview("onboard", result.status === "approval_required" ? result.planKind : "prepare-release-source", result, setPhase, setShowPlan);
    } catch (error) {
      setPhase({ kind: "result", ok: false, message: "RPC 中断，结果未知；请检查操作状态后恢复", detail: String(error) });
    }
  }

  async function confirmPlan(action: "confirm" | "reject"): Promise<void> {
    if (phase.kind !== "preview") return;
    currentFlow.current = phase.flow === "onboard" ? "bootstrap" : phase.flow;
    setPhase({ kind: "busy", message: action === "confirm" ? "正在执行已确认计划…" : "已拒绝，清除待批计划…" });
    try {
      const input = { action, confirmationToken: phase.confirmationToken };
      let outcome;
      if (phase.flow === "onboard") outcome = await bootstrapConfirm(input);
      else if (phase.flow === "machine") outcome = await machineConfirm(input);
      else if (phase.flow === "enable") outcome = await enableConfirm(input);
      else if (phase.flow === "remove") outcome = await removeConfirm(input);
      else if (phase.flow === "ck") outcome = await ckConfirm(input);
      else outcome = await recoverConfirmRpcCall(input);
      if (outcome.status === "rejected") {
        setPhase({ kind: "result", ok: true, message: "已拒绝；未执行计划中的写入。" });
      } else if (outcome.status === "stale_plan" || outcome.status === "no_pending_plan") {
        setPhase({ kind: "gate", message: describe(outcome.status, outcome.detail) });
      } else if (outcome.status === "acquired") {
        setPhase({
          kind: "result",
          ok: true,
          message: "持久来源已就绪；继续机器安装预览。",
          detail: JSON.stringify(outcome.envelope, null, 2),
        });
      } else if (outcome.status === "completed") {
        if (outcome.envelope.status === "source_prepared") {
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
    }
  }

  const picksAgents = flow === "onboard" || flow === "enable";

  const inputStyle = {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    padding: 10,
    color: theme.colors.foreground,
    backgroundColor: theme.colors.surface1,
  };

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>{titleFor(flow)}</Text>
      {projectRoot.length > 0 ? <Text style={styles.detail}>{projectRoot}</Text> : null}

      {phase.kind === "form" ? (
        <View style={{ gap: 12 }}>
          {picksAgents ? (
            <View style={{ gap: 8 }}>
              <Text style={styles.label}>拟接入的执行器（实际用户文件以精确预览为准）</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {AGENT_CHOICES.map((name) => (
                  <Pressable
                    key={name}
                    style={styles.chip(agents.includes(name))}
                    onPress={() =>
                      setAgents((current: AgentName[]) => (current.includes(name) ? current.filter((item: AgentName) => item !== name) : [...current, name]))
                    }
                  >
                    <Text style={styles.chipText(agents.includes(name))}>{name}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          {flow === "enable" ? <View style={{ gap: 8 }}>
            <Text style={styles.label}>项目记忆政策（实际变更以原内核完整计划为准）</Text>
            {([
              ["preserve", "保留现状"],
              ["enable", "启用项目记忆"],
              ["disable", "禁用自动记忆（保留共享规则）"],
            ] as const).map(([value, label]) => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ checked: memoryChoice === value }} style={styles.chip(memoryChoice === value)} onPress={() => setMemoryChoice(value)}><Text style={styles.chipText(memoryChoice === value)}>{label}</Text></Pressable>)}
          </View> : null}
          {flow === "ck" ? <Text style={styles.label}>Context Keeper 为可选独立安装，仅支持 Codex、Claude Code、WorkBuddy。需要获取来源时，先确认固定来源与目标目录，再单独确认安装计划。</Text> : null}
          {flow === "recover" ? (
            <View style={{ gap: 8 }}>
              <Pressable style={styles.button} onPress={() => { void operations({}).then(records => {
                const pending = records.find(r => r.state === "unknown" && typeof r.journal === "string");
                if (pending) setJournalPath(String(pending.journal));
                else setPhase({ kind: "result", ok: false, message: "未找到可自动恢复的未知操作", detail: JSON.stringify(records, null, 2) });
              }); }}><Text style={styles.buttonText}>查找未完成操作</Text></Pressable>
              <Text style={styles.label}>操作 journal 绝对路径</Text>
              <TextInput style={inputStyle} value={journalPath} onChangeText={setJournalPath} placeholder="/absolute/path/to/journal.json" placeholderTextColor={theme.colors.foregroundMuted} />
              <View style={{ flexDirection: "row", gap: 8 }}>
                {(["continue", "rollback"] as const).map((choice) => (
                  <Pressable key={choice} style={styles.chip(recoverAction === choice)} onPress={() => setRecoverAction(choice)}>
                    <Text style={styles.chipText(recoverAction === choice)}>{choice === "continue" ? "继续完成" : "回滚"}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          <Pressable
            accessibilityRole="button"
            style={[styles.button, picksAgents && agents.length === 0 ? { opacity: 0.4 } : null]}
            onPress={() => {
              if (picksAgents && agents.length === 0) return;
              if (flow === "recover" && journalPath.trim().length === 0) return;
              void runPreview();
            }}
          >
            <Text style={styles.buttonText}>生成精确预览</Text>
          </Pressable>
        </View>
      ) : null}

      {phase.kind === "loading" ? <Text style={styles.detail}>正在生成精确预览…</Text> : null}
      {phase.kind === "busy" ? <View style={{ gap: 8 }}><Text style={styles.detail}>{phase.message}</Text>
        <Pressable style={styles.button} onPress={() => { void cancelPending({ flow: currentFlow.current }); }}><Text style={styles.buttonText}>取消运行（完成前结果未知）</Text></Pressable>
      </View> : null}

      {phase.kind === "gate" ? (
        <View style={{ gap: 8 }}>
          <Text style={styles.detail}>{phase.message}</Text>
          <Pressable accessibilityRole="button" style={styles.button} onPress={() => void runPreview()}>
            <Text style={styles.buttonText}>重新预览</Text>
          </Pressable>
        </View>
      ) : null}

      {phase.kind === "preview" ? (
        <View style={{ gap: 8 }}>
          <Text style={styles.label}>计划类型 {phase.planKind}</Text>
          {phase.summary.map((row: { label: string; value: string }) => (
            <Text key={row.label} style={styles.detail}>
              {row.label}：{row.value}
            </Text>
          ))}
          <Pressable accessibilityRole="button" onPress={() => setShowPlan(!showPlan)}>
            <Text style={{ color: theme.colors.accent, fontSize: 13 }}>{showPlan ? "收起完整计划" : "展开完整计划 JSON"}</Text>
          </Pressable>
          {showPlan ? <JsonBlock theme={theme} text={phase.planText} /> : null}
          <Text style={styles.label}>确认即按此精确计划执行；计划摘要 {phase.digest.slice(0, 16)}…</Text>
          <Pressable accessibilityRole="button" style={styles.button} onPress={() => setModalOpen(true)}>
            <Text style={styles.buttonText}>确认执行…</Text>
          </Pressable>
        </View>
      ) : null}

      {phase.kind === "result" && flow === "onboard" ? <Pressable style={styles.button} onPress={() => void runPreview()}><Text style={styles.buttonText}>继续接入预览</Text></Pressable> : null}
      {phase.kind === "result" ? (
        <View style={{ gap: 8 }}>
          <Text style={{ color: phase.ok ? theme.colors.statusSuccess : theme.colors.statusDanger, fontSize: 15 }}>{phase.message}</Text>
          {phase.detail ? <JsonBlock theme={theme} text={phase.detail} /> : null}
        </View>
      ) : null}

      <Modal title="确认执行精确计划" open={modalOpen} onOpenChange={setModalOpen}>
        <Modal.Content>
          <View style={{ gap: 12 }}>
            <Text style={{ color: theme.colors.foreground }}>
              {phase.kind === "preview" ? phase.planKind : ""} 将按已展示的精确计划执行。
            </Text>
            <Text style={{ color: theme.colors.foregroundMuted, fontSize: 12 }}>
              计划摘要 {phase.kind === "preview" ? phase.digest.slice(0, 32) : ""}…
            </Text>
            <View style={{ flexDirection: "row", gap: 12 }}>
              <Pressable
                accessibilityRole="button"
                style={[styles.button, { backgroundColor: theme.colors.accent }]}
                onPress={() => {
                  setModalOpen(false);
                  void confirmPlan("confirm");
                }}
              >
                <Text style={styles.buttonText}>确认执行</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                style={[styles.button, { backgroundColor: theme.colors.statusDanger }]}
                onPress={() => {
                  setModalOpen(false);
                  void confirmPlan("reject");
                }}
              >
                <Text style={styles.buttonText}>拒绝</Text>
              </Pressable>
            </View>
          </View>
        </Modal.Content>
      </Modal>
    </View>
  );
}

type AdoptResult = { status: string; message?: string; detail?: string };

function adoptPreview(
  flow: "onboard" | "machine" | "enable" | "remove" | "ck" | "recover",
  planKind: string,
  result: { status: string; planKind?: string; digest?: string; confirmationToken?: string; summary?: { label: string; value: string }[]; plan?: Record<string, unknown>; message?: string; detail?: string },
  setPhase: (phase: Phase) => void,
  setShowPlan: (value: boolean) => void,
): void {
  if (result.status === "approval_required" && result.digest && result.confirmationToken && result.plan) {
    setShowPlan(true);
    setPhase({
      kind: "preview",
      flow: result.planKind === "prepare-release-source" ? "onboard" : flow,
      planKind,
      digest: result.digest,
      confirmationToken: result.confirmationToken,
      summary: result.summary ?? [],
      planText: JSON.stringify(result.plan, null, 2),
    });
  } else {
    setPhase({ kind: "gate", message: describe(result.status, "message" in result ? result.message : "detail" in result ? result.detail : undefined) });
  }
}

export type { Phase, AdoptResult };
