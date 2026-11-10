// Read-only environment snapshot; readiness does not establish memory connection.
import { useEffect, useRef, useState } from "react";
import type { PluginScreenProps } from "@getpaseo/plugin/client";
import { useRpc } from "@getpaseo/plugin/client";
import { envStatusRpc } from "../shared/contracts";
import { Details } from "./ui";
import { StatusPage } from "./presentation";
import { PlatformScreen } from "./platform";

interface StatusValue {
  python: { status: string; pythonVersion?: string; selectedPath?: string; detail?: string };
  git: { status: string; version?: string; detail?: string };
  payload: { status: string; installerPath?: string };
  releaseIdentity: { status: string; detail: string };
  durableSource: { status: string; sourceManifestPath?: string; detail: string };
}
type StatusState = { kind: "loading" } | { kind: "ready"; value: StatusValue } | { kind: "error"; message: string };

export function StatusScreen(props: PluginScreenProps) {
  return <PlatformScreen screen={{ ...props, params: { ...props.params, flow: "status" } }}><MacStatusScreen {...props} /></PlatformScreen>;
}

function MacStatusScreen({ theme, layout }: PluginScreenProps) {
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
  const value = state.kind === "ready" ? state.value : undefined;
  const ready = value ? [value.python, value.git, value.payload, value.releaseIdentity].filter(item => item.status === "ready").length : 0;
  const groups: { title: string; rows: { title: string; state: string; detail?: string }[] }[] = value ? [
    { title: "运行环境", rows: [{ title: "Python", state: value.python.status, detail: value.python.pythonVersion }, { title: "Git", state: value.git.status, detail: value.git.version }] },
    { title: "插件与来源", rows: [{ title: "插件载荷", state: value.payload.status }, { title: "发行身份", state: value.releaseIdentity.status }, { title: "持久来源", state: value.durableSource.status }] },
  ] : [];
  return <StatusPage theme={theme} layout={layout} loading={state.kind === "loading"}
    error={state.kind === "error" ? state.message : undefined}
    headline={ready === 4 ? "✓ 环境检查完成 · 4/4 就绪" : `! 环境检查完成 · ${ready}/4 就绪`}
    guidance="环境就绪不代表记忆已接入。请从命令中心的“设置记忆共享”继续。"
    checkedAt={checkedAt} groups={groups} details={value ? JSON.stringify(value, null, 2) : undefined}
    onRefresh={() => { if (refreshing.current) return; refreshing.current = true; setRevision(n => n + 1); }}>
    {value?.durableSource.status === "missing" ? <Details theme={theme} title="持久来源准备说明"
      text={"当前版本的共享来源尚未准备，可在“设置记忆共享”中继续。\n" + JSON.stringify(value.durableSource, null, 2)} /> : null}
  </StatusPage>;
}
