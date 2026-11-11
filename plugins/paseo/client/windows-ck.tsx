import { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";
import { useRpc, type PluginScreenProps } from "@getpaseo/plugin/client";
import { windowsCkPlanRpc, windowsCkConfirmRpc, windowsCkCancelRpc, windowsCkStatusRpc } from "../shared/contracts";
import { FlowPage, PlanPreview, PlanConfirmation, OperationResult, PrimaryAction } from "./presentation";
import { flowCopy, flowStage } from "./presentation-model";
import type { PreviewReply } from "./windows-preview-model";

export function WindowsCkScreen({ theme, layout }: PluginScreenProps) {
  const preview = useRpc(windowsCkPlanRpc), confirm = useRpc(windowsCkConfirmRpc), cancel = useRpc(windowsCkCancelRpc), status = useRpc(windowsCkStatusRpc);
  const [pending, setPending] = useState<PreviewReply>();
  const [reply, setReply] = useState<PreviewReply>();
  const [busy, setBusy] = useState(false), [expanded, setExpanded] = useState(false), [modal, setModal] = useState(false);
  const lock = useRef(false), generation = useRef(0);
  useEffect(() => {
    generation.current++; const epoch = generation.current;
    setPending(undefined); setReply(undefined); setBusy(true); lock.current = true;
    void status({}).then(result => {
      if (epoch === generation.current) setReply(result.status === "idle" ? undefined : result);
    }).catch(() => {
      if (epoch === generation.current) setReply({ status: "unknown", message: "未取得 Context Keeper 状态，请刷新后核对；不要重复执行。" });
    }).finally(() => { if (epoch === generation.current) { lock.current = false; setBusy(false); } });
    return () => { generation.current++; };
  }, [preview, confirm, cancel, status]);
  useEffect(() => {
    if (reply?.status !== "running") return;
    let active = true; let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const result = await status({});
        if (active) setReply(result);
        if (result.status !== "running") return;
      } catch { /* A read timeout never replays the confirmed operation. */ }
      if (active) timer = setTimeout(poll, 1000);
    }
    timer = setTimeout(poll, 1000);
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [reply?.status, status]);
  async function run(work: () => Promise<PreviewReply>) {
    if (lock.current || reply?.status === "running") return;
    lock.current = true; setBusy(true); const epoch = generation.current;
    try {
      const result = await work(); if (epoch !== generation.current) return;
      if (result.status === "approval_required") { setPending(result); setReply(undefined); setExpanded(false); }
      else { setPending(undefined); setReply(result); }
    } catch { if (epoch === generation.current) { setPending(undefined); setReply({ status: "unknown", message: "操作结果未知，请保留 Context Keeper 备份与操作记录并核对现场。" }); } }
    finally { if (epoch === generation.current) { lock.current = false; setBusy(false); } }
  }
  const working = busy || reply?.status === "running";
  const prepared = reply?.status === "source_prepared", ok = prepared || reply?.status === "committed" || reply?.status === "rejected";
  const planKind = pending?.operation === "prepare" ? "获取 Context Keeper 官方 main 源码" : "安装 Context Keeper（ZCode / WorkBuddy）";
  const summary = pending ? [
    { label: "操作", value: planKind }, { label: "源码位置", value: String(pending.source) },
    ...(pending.backup_root ? [{ label: "备份位置", value: String(pending.backup_root) }] : []),
    { label: "参与 Agent", value: String(pending.agents) }, { label: "跳过的 Agent", value: Array.isArray(pending.skipped) && pending.skipped.length ? pending.skipped.join("、") : "无" },
    ...(Array.isArray(pending.skill_entries) ? pending.skill_entries.map(value => ({ label: `Skill 入口 ${String(value)}`, value: String(value) })) : []),
    ...(Array.isArray(pending.changes) ? pending.changes.map((item: { path: string }) => ({ label: `规则或回执 ${item.path}`, value: item.path })) : []),
  ] : [];
  const shown = pending ? { ...pending, confirmationToken: undefined } : {};
  return <FlowPage theme={theme} layout={layout} {...flowCopy("ck")}
    stage={flowStage(working ? "loading" : pending ? "preview" : reply ? "result" : "form", ok)} blocked={false}>
    {working ? <Text style={{ color: theme.colors.foreground }}>正在处理 Context Keeper，请等待结果…</Text> : pending ?
      <PlanPreview theme={theme} summary={summary} planText={JSON.stringify(shown, null, 2)} planKind={planKind} digest={String(pending.digest)} expanded={expanded} onExpandedChange={setExpanded} onConfirm={() => setModal(true)} /> : reply ? <View style={{ gap: 16 }}>
        <OperationResult theme={theme} ok={ok} message={prepared ? "官方源码已获取，尚未安装。请继续预览安装计划。" : reply.status === "committed" ? "Context Keeper 已安装，原有共享记忆保留。" : reply.status === "rejected" ? "已拒绝本次计划，未执行安装。" : String(reply.message ?? "结果待核对")}
          detail={JSON.stringify(reply, null, 2)} />
        {prepared ? <PrimaryAction theme={theme} label="生成安装预览" onPress={() => run(() => preview({ operation: "install" }))} /> : null}
        {reply.status === "rejected" ? <PrimaryAction theme={theme} label="重新预览" onPress={() => setReply(undefined)} /> : null}
      </View> : <View style={{ gap: 16 }}>
        <Text style={{ color: theme.colors.foreground, lineHeight: 24 }}>为此 DELL 的 ZCode、WorkBuddy 独立安装 Context Keeper。先预览并确认获取官方 main 最新源码，再核对安装计划并确认。Skill 从同一独立源码目录加载；保留原有记忆，不创建项目记录库。</Text>
        <PrimaryAction theme={theme} label="生成精确预览" onPress={() => run(() => preview({ operation: "prepare" }))} />
      </View>}
    <PlanConfirmation theme={theme} layout={layout} open={modal && Boolean(pending)} onOpenChange={setModal} planKind={planKind} digest={String(pending?.digest ?? "")} busy={working}
      onConfirm={() => { setModal(false); return run(() => confirm({ confirmationToken: String(pending?.confirmationToken) })); }}
      onReject={() => { setModal(false); return run(() => cancel({})); }} />
  </FlowPage>;
}
