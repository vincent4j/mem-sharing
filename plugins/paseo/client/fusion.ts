// Pure display only: numbering, selection and migration policy come from CLI.
export function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}
export function fusionGroups(envelope: Record<string, unknown>) {
  const plan = record(envelope.approval_plan);
  const groups = Array.isArray(plan?.groups) ? plan.groups : [];
  return groups.map(record).filter((g): g is Record<string, unknown> => !!g).map(g => ({
    number: Number(g.number), summary: String(g.summary ?? ""),
    original: (Array.isArray(g.sources) ? g.sources : []).map(record).filter(Boolean)
      .map(s => `${String(s!.source ?? "")}\n${String(s!.text ?? "")}`).join("\n\n"),
  }));
}
export function fusionResult(envelope: Record<string, unknown>) {
  if (envelope.fusion_status === "declined") return "已保留现状，本次融合未修改记忆内容。";
  if (envelope.status === "viewed") return "只读查看原文；未选择、未执行。";
  if (envelope.fusion_status === "completed") return "记忆融合完成。";
  if (envelope.fusion_status === "unchanged") return "没有需要融合的内容，记忆内容未修改。";
  return "本次融合尚未修改记忆内容，请选择后查看完整修改清单。";
}
