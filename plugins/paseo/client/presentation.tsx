// Shared presentation for both daemon platforms. Controllers own RPCs and
// capabilities; page structure, actions and confirmation sequence live here.
import type { ReactNode } from "react";
import { ScrollView, Text, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { Modal } from "@getpaseo/plugin/client/ui";
import { Action, Card, Details } from "./ui";

type Screen = Pick<PluginScreenProps, "theme" | "layout">;
export type SummaryRow = { label: string; value: string };
export type StatusGroup = { title: string; rows: { title: string; state: string; detail?: string }[] };

export function Page({ theme, layout, title, description, children }: Screen & { title: string; description: string; children: ReactNode }) {
  const c = theme.colors;
  return <ScrollView style={{ flex: 1, backgroundColor: c.surface0 }} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: layout.compact ? 16 : 32, paddingBottom: 48 }}>
    <View style={{ width: "100%", maxWidth: 820, alignSelf: "center", gap: 20 }}>
      <View style={{ gap: 8 }}>
        <Text style={{ color: c.accent, fontSize: 12, fontWeight: "600" }}>MEMORY SHARING & FUSION</Text>
        <Text accessibilityRole="header" style={{ color: c.foreground, fontSize: layout.compact ? 26 : 32, fontWeight: "700" }}>{title}</Text>
        <Text style={{ color: c.foregroundMuted, fontSize: 15, lineHeight: 24 }}>{description}</Text>
      </View>
      {children}
    </View>
  </ScrollView>;
}

export function PrimaryAction({ theme, label, disabled, danger, onPress }: Pick<Screen, "theme"> & { label: string; disabled?: boolean; danger?: boolean; onPress: () => unknown }) {
  const c = theme.colors;
  return <Action disabled={disabled} onPress={onPress} style={{ minHeight: 44, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 10, backgroundColor: danger ? c.statusDanger : c.accent, alignSelf: "flex-start" }}>
    <Text style={{ color: c.accentForeground, fontWeight: "600" }}>{label}</Text>
  </Action>;
}

export function FlowPage({ theme, layout, title, description, stage, blocked, children }: Screen & { title: string; description: string; stage: string; blocked?: boolean; children: ReactNode }) {
  return <Page theme={theme} layout={layout} title={title} description={description}>
    <View style={{ padding: layout.compact ? 16 : 24, borderWidth: 1, borderColor: theme.colors.border, borderRadius: 16, backgroundColor: theme.colors.surface1, gap: 16 }}>
      <Text style={{ color: blocked ? theme.colors.statusDanger : theme.colors.accent, fontSize: 12, fontWeight: "600" }}>{stage}</Text>
      {children}
    </View>
  </Page>;
}

export function PlanPreview({ theme, summary, planText, planKind, digest, expanded, onExpandedChange, onConfirm, children }: Pick<Screen, "theme"> & {
  summary: SummaryRow[]; planText: string; planKind: string; digest: string; expanded: boolean;
  onExpandedChange: (value: boolean) => void; onConfirm: () => void; children?: ReactNode;
}) {
  const c = theme.colors;
  return <View style={{ gap: 8 }}>
    <Text style={{ color: c.foregroundMuted, fontSize: 13, lineHeight: 22 }}>请核对以下变更；完整计划可展开查看。</Text>
    {summary.map(row => <Text key={row.label} style={{ color: c.foreground, fontSize: 14, lineHeight: 24 }}>{row.label}：{row.value}</Text>)}
    <Action accessibilityState={{ expanded }} onPress={() => onExpandedChange(!expanded)}>
      <Text style={{ color: c.accent, fontSize: 13 }}>{expanded ? "收起完整计划" : "查看完整计划与技术详情"}</Text>
    </Action>
    {children}
    {expanded ? <View style={{ backgroundColor: c.surface2, padding: 16, borderRadius: 12 }}>
      <Text selectable style={{ color: c.foregroundMuted, fontSize: 12, lineHeight: 21 }}>{planText}</Text>
    </View> : null}
    <Details theme={theme} title="计划标识" text={`${planKind} · ${digest}`} />
    <PrimaryAction theme={theme} label="确认执行…" onPress={onConfirm} />
  </View>;
}

export function PlanConfirmation({ theme, layout, open, onOpenChange, planKind, digest, danger, busy, onConfirm, onReject }: Screen & {
  open: boolean; onOpenChange: (value: boolean) => void; planKind: string; digest: string; danger?: boolean; busy?: boolean;
  onConfirm: () => unknown; onReject: () => unknown;
}) {
  return <Modal title="确认执行精确计划" open={open} onOpenChange={value => { if (!busy) onOpenChange(value); }}>
    <Modal.Content><View style={{ gap: 12 }}>
      <Text style={{ color: theme.colors.foreground }}>{planKind} 将按已展示的精确计划执行。</Text>
      <Text style={{ color: theme.colors.foregroundMuted, fontSize: 12 }}>计划摘要 {digest.slice(0, 32)}…</Text>
      <View style={{ flexDirection: layout.compact ? "column" : "row", flexWrap: "wrap", gap: 12 }}>
        <PrimaryAction theme={theme} label={busy ? "正在执行…" : "确认执行"} danger={danger} disabled={busy} onPress={onConfirm} />
        <Action disabled={busy} onPress={onReject} style={{ paddingVertical: 12, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.surface1 }}>
          <Text style={{ color: theme.colors.foreground, fontWeight: "600" }}>返回并拒绝</Text>
        </Action>
      </View>
    </View></Modal.Content>
  </Modal>;
}

export function OperationResult({ theme, ok, message, detail, rows, children }: Pick<Screen, "theme"> & {
  ok: boolean; message: string; detail?: string; rows?: SummaryRow[]; children?: ReactNode;
}) {
  return <View style={{ gap: 8 }}>
    <Text accessibilityLiveRegion="polite" style={{ color: ok ? theme.colors.statusSuccess : theme.colors.statusDanger, fontSize: 15 }}>{ok ? "✓ " : "! "}{message}</Text>
    {rows?.map(row => <Text key={row.label} selectable style={{ color: theme.colors.foreground, fontSize: 14, lineHeight: 24 }}>{row.label}：{row.value}</Text>)}
    {children}
    {detail ? <Details theme={theme} title={ok ? "完整结果" : "错误详情与恢复线索"} text={detail} /> : null}
  </View>;
}

export function StatusPage({ theme, layout, loading, error, headline, guidance, checkedAt, onRefresh, groups, details, children }: Screen & {
  loading: boolean; error?: string; headline: string; guidance: string; checkedAt: string; onRefresh: () => unknown;
  groups: StatusGroup[]; details?: string; children?: ReactNode;
}) {
  const c = theme.colors;
  return <Page theme={theme} layout={layout} title="接入前，先看一眼状态" description="检查所选 Host 的运行环境、插件文件与持久来源。此页只读，不会修改记忆。">
    <Card theme={theme}>
      <Text style={{ color: error ? c.statusDanger : c.foreground, fontSize: 20, fontWeight: "600" }}>{loading ? "◌ 正在检查环境…" : error ? "! 暂时无法读取状态" : headline}</Text>
      <Text style={{ color: c.foregroundMuted, fontSize: 14, lineHeight: 23 }}>{guidance}</Text>
      <PrimaryAction theme={theme} disabled={loading} label={loading ? "正在读取…" : error ? "重新读取" : "刷新状态"} onPress={onRefresh} />
      {!loading && !error && checkedAt ? <Text accessibilityLiveRegion="polite" style={{ color: c.foregroundMuted, fontSize: 12, lineHeight: 20 }}>✓ 已更新 · 最近检查 {checkedAt}（本地时间）</Text> : null}
      {error ? <Details theme={theme} title="错误详情" text={error} /> : null}
    </Card>
    <View style={{ flexDirection: layout.compact ? "column" : "row", gap: 16 }}>
      {groups.map(group => <View key={group.title} style={{ flex: 1, minWidth: 0 }}><Card theme={theme}>
        <Text accessibilityRole="header" style={{ color: c.foreground, fontSize: 17, fontWeight: "600" }}>{group.title}</Text>
        {group.rows.map(row => <View key={row.title} style={{ gap: 6, paddingVertical: 10, borderTopWidth: 1, borderColor: c.border }}>
          <Text style={{ color: c.foreground, fontSize: 14 }}>{row.title}{row.detail ? ` · ${row.detail}` : ""}</Text>
          <Text style={{ color: row.state === "ready" ? c.statusSuccess : c.foregroundMuted, fontSize: 13, lineHeight: 21 }}>{row.state === "ready" ? "✓ 已就绪" : row.title === "持久来源" && row.state === "missing" ? "○ 需要准备" : row.state === "missing" || row.state === "absent" || row.state === "not_prepared" ? "○ 未找到 · 查看详情" : row.state === "error" || row.state === "failed" ? "! 检查失败 · 查看详情" : `! 尚未就绪（${row.state}）· 查看详情`}</Text>
        </View>)}
      </Card></View>)}
    </View>
    {children}
    {details ? <Details theme={theme} title="路径、来源与完整检查结果" text={details} /> : null}
  </Page>;
}
