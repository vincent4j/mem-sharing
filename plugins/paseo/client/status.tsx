// memSharing Paseo plugin — on-demand status screen.
// Shows the dependency / payload / durable-source snapshot from the daemon
// side. Opened from a Command Center item only; no persistent sidebar entry.

import { useEffect, useMemo, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { useRpc } from "@getpaseo/plugin/client";
import { envStatusRpc } from "../shared/contracts";

// Structural view of envStatusRpc's output; the runtime value is validated
// by the shared Zod contract on both sides.
interface StatusValue {
  python: { status: string; pythonVersion?: string; selectedPath?: string; detail?: string };
  git: { status: string; version?: string; detail?: string };
  payload: { status: string; installerPath?: string };
  releaseIdentity: { status: string; detail: string };
  durableSource: { status: string; sourceManifestPath?: string; detail: string };
}

type StatusState =
  | { kind: "loading" }
  | { kind: "ready"; value: StatusValue }
  | { kind: "error"; message: string };

export function StatusScreen({ theme, layout }: PluginScreenProps) {
  const status = useRpc(envStatusRpc);
  const [state, setState] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    status({})
      .then((value: StatusValue) => {
        if (active) setState({ kind: "ready", value });
      })
      .catch((error: unknown) => {
        if (active) setState({ kind: "error", message: String(error) });
      });
    return () => {
      active = false;
    };
  }, [status]);

  const styles = useMemo(
    () => ({
      screen: { flex: 1, padding: layout.compact ? 16 : 24, gap: 10, backgroundColor: theme.colors.surface0 },
      title: { color: theme.colors.foreground, fontSize: layout.compact ? 18 : 22, fontWeight: "600" as const },
      section: { color: theme.colors.foregroundMuted, fontSize: 12, marginTop: 6 },
      row: { color: theme.colors.foreground, fontSize: 14 },
      ok: { color: theme.colors.statusSuccess, fontSize: 14 },
      bad: { color: theme.colors.statusDanger, fontSize: 14 },
    }),
    [theme, layout.compact],
  );

  return (
    <ScrollView style={styles.screen}>
      <Text style={styles.title}>memSharing 状态</Text>
      {state.kind === "loading" ? <Text style={styles.row}>读取中…</Text> : null}
      {state.kind === "error" ? <Text style={styles.bad}>状态读取失败：{state.message}</Text> : null}
      {state.kind === "ready" ? (
        <View>
          <Text style={styles.section}>Python</Text>
          <Text style={state.value.python.status === "ready" ? styles.ok : styles.bad}>
            {state.value.python.status}
            {state.value.python.pythonVersion ? `（${state.value.python.pythonVersion}）` : ""}
            {state.value.python.selectedPath ? ` ${state.value.python.selectedPath}` : ""}
          </Text>
          {state.value.python.detail ? <Text style={styles.row}>{state.value.python.detail}</Text> : null}

          <Text style={styles.section}>Git</Text>
          <Text style={state.value.git.status === "ready" ? styles.ok : styles.bad}>
            {state.value.git.status}
            {state.value.git.version ? `（${state.value.git.version}）` : ""}
          </Text>

          <Text style={styles.section}>插件载荷</Text>
          <Text style={state.value.payload.status === "ready" ? styles.ok : styles.bad}>{state.value.payload.status}</Text>

          <Text style={styles.section}>发行身份</Text>
          <Text style={state.value.releaseIdentity.status === "ready" ? styles.ok : styles.bad}>
            {state.value.releaseIdentity.status === "ready" ? "就绪" : "缺失（开发源码）"}
          </Text>

          <Text style={styles.section}>持久来源</Text>
          <Text style={state.value.durableSource.status === "ready" ? styles.ok : styles.bad}>
            {state.value.durableSource.status === "ready" ? state.value.durableSource.sourceManifestPath : "未准备（首次接入时创建）"}
          </Text>
        </View>
      ) : null}
    </ScrollView>
  );
}
