// Read-only environment snapshot; readiness does not establish memory connection.
import { useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { useRpc } from "@getpaseo/plugin/client";
import { envStatusRpc } from "../shared/contracts";
import { Action, Card, Details } from "./ui";

interface StatusValue {
  python: { status: string; pythonVersion?: string; selectedPath?: string; detail?: string };
  git: { status: string; version?: string; detail?: string };
  payload: { status: string; installerPath?: string };
  releaseIdentity: { status: string; detail: string };
  durableSource: { status: string; sourceManifestPath?: string; detail: string };
}
type StatusState = { kind: "loading" } | { kind: "ready"; value: StatusValue } | { kind: "error"; message: string };

export function StatusScreen({ theme, layout }: PluginScreenProps) {
  const status = useRpc(envStatusRpc);
  const [state, setState] = useState<StatusState>({ kind: "loading" });
  const [revision, setRevision] = useState(0);
  const [checkedAt, setCheckedAt] = useState("");
  const refreshing = useRef(false);
  useEffect(() => {
    let active = true;
    refreshing.current = true;
    setState({ kind: "loading" });
    void status({}).then((value: StatusValue) => { if (active) { setCheckedAt(new Date().toLocaleTimeString()); setState({ kind: "ready", value }); } })
      .catch((error: unknown) => { if (active) setState({ kind: "error", message: String(error) }); })
      .finally(() => { if (active) refreshing.current = false; });
    return () => { active = false; };
  }, [status, revision]);
  const c = theme.colors;
  const value = state.kind === "ready" ? state.value : undefined;
  const ready = value ? [value.python, value.git, value.payload, value.releaseIdentity].filter(item => item.status === "ready").length : 0;
  const groups: { title: string; rows: { title: string; state: string; detail?: string }[] }[] = value ? [
    { title: "运行环境", rows: [{ title: "Python", state: value.python.status, detail: value.python.pythonVersion }, { title: "Git", state: value.git.status, detail: value.git.version }] },
    { title: "插件与来源", rows: [{ title: "插件载荷", state: value.payload.status }, { title: "发行身份", state: value.releaseIdentity.status }, { title: "持久来源", state: value.durableSource.status }] },
  ] : [];
  return <ScrollView style={{ flex: 1, backgroundColor: c.surface0 }} contentContainerStyle={{ padding: layout.compact ? 16 : 32, paddingBottom: 48 }}>
    <View style={{ width: "100%", maxWidth: 820, alignSelf: "center", gap: 20 }}>
      <View style={{ gap: 8 }}>
        <Text style={{ color: c.accent, fontSize: 12, fontWeight: "600" }}>MEMORY SHARING & FUSION</Text>
        <Text accessibilityRole="header" style={{ color: c.foreground, fontSize: layout.compact ? 26 : 32, fontWeight: "700" }}>接入前，先看一眼状态</Text>
        <Text style={{ color: c.foregroundMuted, fontSize: 15, lineHeight: 24 }}>检查所选 Host 的运行环境、插件文件与持久来源。此页只读，不会修改记忆。</Text>
      </View>
      <Card theme={theme}>
        <Text style={{ color: state.kind === "error" ? c.statusDanger : c.foreground, fontSize: 20, fontWeight: "600" }}>
          {state.kind === "loading" ? "◌ 正在检查环境…" : state.kind === "error" ? "! 暂时无法读取状态" : ready === 4 ? "✓ 环境检查完成 · 4/4 就绪" : `! 环境检查完成 · ${ready}/4 就绪`}
        </Text>
        <Text style={{ color: c.foregroundMuted, fontSize: 14, lineHeight: 23 }}>环境就绪不代表记忆已接入。请从命令中心的“设置记忆共享”继续。</Text>
        <Action disabled={state.kind === "loading"} onPress={() => { if (refreshing.current) return; refreshing.current = true; setRevision(n => n + 1); }}
          style={{ alignSelf: "flex-start", paddingHorizontal: 18, borderRadius: 10, backgroundColor: c.accent }}>
          <Text style={{ color: c.accentForeground, fontWeight: "600" }}>{state.kind === "loading" ? "正在读取…" : state.kind === "error" ? "重新读取" : "刷新状态"}</Text>
        </Action>
        {state.kind === "ready" && checkedAt ? <Text accessibilityLiveRegion="polite" style={{ color: c.foregroundMuted, fontSize: 12, lineHeight: 20 }}>✓ 已更新 · 最近检查 {checkedAt}（本地时间）</Text> : null}
        {state.kind === "error" ? <Details theme={theme} title="错误详情" text={state.message} /> : null}
      </Card>
      <View style={{ flexDirection: layout.compact ? "column" : "row", gap: 16 }}>
        {groups.map(group => <View key={group.title} style={{ flex: 1, minWidth: 0 }}><Card theme={theme}>
          <Text accessibilityRole="header" style={{ color: c.foreground, fontSize: 17, fontWeight: "600" }}>{group.title}</Text>
          {group.rows.map(row => <View key={row.title} style={{ gap: 6, paddingVertical: 10, borderTopWidth: 1, borderColor: c.border }}>
            <Text style={{ color: c.foreground, fontSize: 14 }}>{row.title}{row.detail ? ` · ${row.detail}` : ""}</Text>
            <Text style={{ color: row.state === "ready" ? c.statusSuccess : row.title === "持久来源" && row.state === "missing" ? c.accent : c.foregroundMuted, fontSize: 13, lineHeight: 21 }}>
              {row.state === "ready" ? "✓ 已就绪" : row.title === "持久来源" && row.state === "missing" ? "○ 需要准备" : row.state === "missing" || row.state === "absent" || row.state === "not_prepared" ? "○ 未找到 · 查看详情" : row.state === "error" || row.state === "failed" ? "! 检查失败 · 查看详情" : `! 尚未就绪（${row.state}）· 查看详情`}
            </Text>
            {row.title === "持久来源" && row.state === "missing" ? <>
              <Text style={{ color: c.foreground, fontSize: 13, lineHeight: 22 }}>当前版本的共享来源尚未准备，可在“设置记忆共享”中继续。</Text>
              <Details theme={theme} title="来源检查详情" text={JSON.stringify(value?.durableSource, null, 2)} />
            </> : null}
          </View>)}
        </Card></View>)}
      </View>
      {value ? <Details theme={theme} title="路径、发行身份与完整检查结果" text={JSON.stringify(value, null, 2)} /> : null}
    </View>
  </ScrollView>;
}
