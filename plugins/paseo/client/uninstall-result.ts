// Pure presentation helpers; no host mutation or automatic follow-up.
export function uninstallResult(envelope: Record<string, unknown>) {
  const complete = envelope.overall === "completed";
  return { ok: complete, message: complete ? "本次声明范围内卸载完成。" : "机器资产已处理；Paseo 插件移除尚未证实。",
    rows: ["scope", "machine_assets", "host_plugin", "overall"].map(key => ({ label: key, value: String(envelope[key] ?? "pending") })) };
}

const quote = (value: string): string => "'" + value.replace(/'/g, "'\\''") + "'";
export function externalSteps(envelope: Record<string, unknown>, plan: Record<string, unknown>): string {
  if (typeof envelope.manifest !== "string") return "未返回持久 manifest；保留现场，检查外置备份，不能继续 CK。";
  const runtime = plan.recovery_runtime as Record<string, unknown> | undefined;
  if (typeof runtime?.interpreter !== "string") return "从外置 manifest.plan.recovery_runtime.interpreter 读取解释器路径后继续；不能依赖已删除的产品代码。";
  const manifest = envelope.manifest;
  const runner = manifest.slice(0, manifest.lastIndexOf("/")) + "/recover.py";
  const base = `${quote(runtime.interpreter)} -I -S -B ${quote(runner)} --manifest ${quote(manifest)}`;
  const obligation = plan.host_obligation as Record<string, unknown> | undefined;
  if (!obligation) return `默认保留 Context Keeper（不写入）：\n${base} --ck-choice retain\n如选择卸载，另用 --ck-choice uninstall --ck-source '<独立CK源码绝对路径>' --ck-agent '<宿主>' 先预览，再独立精确批准。`;
  if (typeof obligation.plugin_id !== "string") return "宿主安装 ID 未绑定；保留插件与外置材料，不能继续 CK。";
  return `保留以下外置命令。CLI 路径须为真实可执行路径；daemonHome 必须指向当前插件所在 daemon，也可明确使用 --host endpoint。查询失败、disabled 或新 serverId 都不能解锁 CK。\n\n1. 插件仍在时绑定原宿主，预览后独立批准：\n${base} --bind-host-plugin --paseo-cli '<真实Paseo CLI绝对路径>' --paseo-home '<原daemonHome绝对路径>'\n同一命令追加 --host-binding-approval-file '<独立批准JSON绝对路径>'，成功后保留 host-binding.json。\n\n2. 独立终端移除准确安装 ID（remove 输出的 disabled 不是证明）：\n'<同一Paseo CLI绝对路径>' plugin remove ${quote(obligation.plugin_id)} --json --home '<同一daemonHome绝对路径>'\n\n3. 外置入口重查同一已绑定宿主完整列表：\n${base} --check-host-plugin\n仅 host_plugin=removed 才能进入卸载 CK。列表错误或未预绑定即移除，保持 pending。\n\n4. 默认保留 Context Keeper：\n${base} --ck-choice retain\n如明确选择卸载：\n${base} --ck-choice uninstall --ck-source '<独立CK源码绝对路径>' --ck-agent '<宿主>'\n先独立预览，再用 --ck-approval-file '<CK独立批准JSON绝对路径>'；不复用主批准、不隐式扩大宿主范围。失去 Skill 自动记录、续接、历史检索与经验整理能力，规则及历史数据保留。`;
}

export function publicPlan(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(publicPlan);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).filter(([key]) => !/hex$|^before_bytes$|^after_bytes$/.test(key)).map(([key, item]) => [key, publicPlan(item)]));
  return value;
}
