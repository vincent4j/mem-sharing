import { useEffect, useState, type ReactNode } from "react";
import { Text, View } from "react-native";
import { useRpc } from "@getpaseo/plugin/client";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { hostPlatformRpc } from "../shared/contracts";
import { WindowsStatusScreen, WindowsFlowScreen } from "./windows-preview";

// Route by the selected daemon, never React Native's client OS. A Windows
// application connected to a Mac daemon must retain the Mac product flow.
export function PlatformScreen({ screen, children }: { screen: PluginScreenProps; children: ReactNode }) {
  const info = useRpc(hostPlatformRpc);
  const [mode, setMode] = useState("loading");
  useEffect(() => {
    let active = true; setMode("loading");
    void info({}).then(result => { if (active) setMode(result.mode); }).catch(() => { if (active) setMode("error"); });
    return () => { active = false; };
  }, [info]);
  if (mode === "macos") return children;
  if (mode === "windows-preview") return screen.params.flow === "status" ? <WindowsStatusScreen {...screen} /> : <WindowsFlowScreen {...screen} />;
  return <View style={{ padding: 24, backgroundColor: screen.theme.colors.surface0, flex: 1 }}>
    <Text style={{ color: screen.theme.colors.foreground }}>{mode === "loading" ? "正在检查所选 Host…" : mode === "error" ? "无法确认 Host 平台，请重新打开页面。" : "此 Host 平台尚不支持记忆共享。"}</Text>
  </View>;
}
