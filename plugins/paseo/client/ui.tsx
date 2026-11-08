import { useEffect, useRef, useState } from "react";
import type { ComponentProps, ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import type { PluginTheme } from "@getpaseo/plugin";

type ActionProps = Omit<ComponentProps<typeof Pressable>, "onPress"> & {
  onPress?: () => unknown;
};
// Keep every action reachable by touch and announce real selection/disabled state.
export function Action({ onPress, disabled, accessibilityRole = "button", accessibilityState, style, ...props }: ActionProps) {
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [pending, setPending] = useState(false);
  const blocked = Boolean(disabled || pending);
  return <Pressable {...props} accessibilityRole={accessibilityRole} disabled={blocked}
    accessibilityState={{ ...accessibilityState, disabled: blocked, busy: pending }}
    style={[{ minHeight: 44, justifyContent: "center" }, typeof style === "function" ? undefined : style, blocked ? { opacity: 0.45 } : null]}
    onPress={async () => {
      if (locked.current || blocked) return;
      locked.current = true;
      try { const result = onPress?.(); if (result && typeof (result as Promise<unknown>).then === "function") { setPending(true); await result; } }
      finally { locked.current = false; if (mounted.current) setPending(false); }
    }} />;
}

export function Details({ theme, title = "技术详情", text }: { theme: PluginTheme; title?: string; text: string }) {
  const [open, setOpen] = useState(false);
  return <View style={{ gap: 8, minWidth: 0 }}>
    <Action accessibilityState={{ expanded: open }} onPress={() => setOpen(value => !value)}>
      <Text style={{ color: theme.colors.accent, fontSize: 13, lineHeight: 20 }}>{open ? "− 收起" : "+ 查看"} {title}</Text>
    </Action>
    {open ? <View style={{ backgroundColor: theme.colors.surface2, padding: 14, borderRadius: 12 }}>
      <Text selectable style={{ color: theme.colors.foregroundMuted, fontSize: 12, lineHeight: 20, flexShrink: 1 }}>{text}</Text>
    </View> : null}
  </View>;
}

export function Card({ theme, children }: { theme: PluginTheme; children: ReactNode }) {
  return <View style={{ borderWidth: 1, borderColor: theme.colors.border, borderRadius: 16, padding: 20, gap: 14, backgroundColor: theme.colors.surface1, minWidth: 0 }}>{children}</View>;
}

export const AGENT_LABELS: Record<string, string> = {
  codex: "Codex", claude: "Claude Code", workbuddy: "WorkBuddy", dsh: "DeepSeek Harness", zcode: "ZCode", opencode: "OpenCode",
};
