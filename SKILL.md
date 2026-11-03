---
name: mem-sharing
description: memSharing，多 Agent 记忆共享与融合。提供公共用户记忆共享、项目记忆接入、检查、整理与整机卸载路由；支持明确自然语言卸载意图，项目经历由 Context Keeper 独立管理。
---

# memSharing

当前 Agent 理解原文，用户决定共享范围，小工具按确认清单精确修改字节。设计合同见[记忆共享与融合 PRD](docs/memory-sharing-fusion-prd.md)和[已批准模块去向](docs/retrospectives/2026-11-03-module-disposition-review.md)。

## 用户记忆：四步入口

用户输入 `/mem-sharing` 或明确要求共享用户记忆时，执行以下四步。不以安装、registry 或发行状态作为新主线前置条件。当前已实现切片为 macOS 六家：Codex、Claude Code、WorkBuddy、DeepSeek Harness（DSH）、ZCode、OpenCode，各自按路径表使用真实原生用户文件与读取机制；Claude 的 @ 引用只属于 Claude，其余各家（含 WorkBuddy 的 MEMORY.md）为原生文件内受管指针块，不互相泛化。环境边界：DSH_HOME 重定向 DSH 用户规则根时拒绝本次操作（~/ 与 ~\ 前缀按目标 HOME 展开，等于默认根不算重定向；DSH_AGENTS_HOME 只影响 Skill 根，不阻断用户入口）；OpenCode 配置根被 XDG_CONFIG_HOME/OPENCODE_CONFIG_DIR/OPENCODE_CONFIG 重定向或覆盖时拒绝，fail closed 且不回显环境原值；ZCode 规则根只由 HOME/USERPROFILE 后备 homedir 决定，ZCODE_HOME 不是规则根。项目共享仍沿既有能力单独处理。真实模型对话和原生新会话加载仍待验。

1. **确认共享位置和参与者。** 默认公共位置为当前用户 `~/.mem-sharing/memories/`；核实用户实际使用者与原生文件读取依据，显式传每个 `--agent`。用户未确认建立目录时保持只读；最终共享事务可以创建所需目录。遇旧安装未完成事务、旧迁移或归属不明先停下，读取对应兼容文档，不用新路径覆盖旧现场。
2. **完整读取原生记忆。** 从已核验源码根执行以下薄 CLI。输出 `participants` 包含各来源状态与完整 `text`，`segments` 只是候选定位线索，`basis` 绑定当前字节。缺失、空、未知分开报告；未知不能算无内容或全覆盖。不把文件存在当作实际安装或原生已读取的证明。

   ```bash
   python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude
   ```

3. **Agent 提议，用户选编号。** 当前 Agent 阅读完整原文及上下文，在用户指定的临时工作位置写提案 JSON（不写原生或公共记忆）。沿用输出的完整 `basis`，每组写一句忠实摘要、`same_content` 和各处 UTF-8 原文的精确字节范围；同文件重复项逐处列出。`same_content=true` 是 Agent 已核实语境与作用域后的判断，标题相同不足以证明；仅语义类似或冲突项写 false。独有项默认留原处，CK、Agent 专属及受保护协议不可迁。工具分段不是语义裁决，必要时可提供未预切的完整原文范围，不能截断字符或跨受保护块。

   ```json
   {"schema_version":1,"basis":{"/实际来源绝对路径":"步骤2返回的sha256"},"groups":[{"summary":"依据实际原文写一句摘要","same_content":true,"items":[{"agent":"codex","start":0,"end":实际字节末位},{"agent":"claude","start":0,"end":实际字节末位}]}]}
   ```

   上面是字段示意，`实际字节末位` 须替换为整数，不能直接执行。用真实提案预览：

   ```bash
   python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude --proposal-file /绝对路径/proposal.json
   python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude --proposal-file /绝对路径/proposal.json --selection '查看 1'
   python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude --proposal-file /绝对路径/proposal.json --selection '共享 3，不共享 2'
   ```

   展示返回 `prompt` 的“默认共享”“由你选择是否共享”两块，空块写“暂无”；保持全局稳定编号，不能把 CLI 占位当实际摘要。N≥2 且全参与者同内容才默认推荐，部分覆盖默认不选。用户可输入待选编号、`不共享 2`、组合选择、`按默认方案`、`查看 3`、`暂不整理`。查看只返回完整原文与来源，零写，不选择、不批准；暂不整理零写。换提案或来源漂移后须重新展示，不复用旧编号含义。
4. **确认完整清单后执行。** 展示 `final_list` 及完整 `approval_plan.changes`：参与者、稳定编号、每处原文和来源范围、公共目标、删源片段、保留内容、入口改动、恢复位置。用可读文本解码 `after_hex`，不能只展示摘要或 hash。用户确认此清单后，将完整 `approval_plan` 原样加真实 `confirmed_at`、`reference` 写入批准文件；Agent 不得伪造确认。然后执行：

   ```bash
   python3 -B scripts/memory_share.py share-user-memory --approval-file /绝对路径/approval.json
   ```

   执行批准时不混入 `--agent`、`--selection`、`--proposal-file`；HOME、来源、公共正文和入口漂移均使旧批准失效。顺序为公共完整原文→全部原生入口→核验→精确删源，复用同一 Transaction 备份/恢复。完全同字节的同组来源可共用一份公共正文，每处来源、位置和次数仍在 manifest 顶层可选 `operation_metadata` 中逐处记录；格式变体逐份保留。原文不摘要替换。条目之间只补足一个空行，原生剩余字节不重排。

脚本输出 JSON；退出码 0 为本命令完成/只读查看，5 为待最终批准，2 为失败或需恢复。`--home /绝对临时HOME` 仅用于隔离合成验证，不能把真实用户操作悄悄转到别处。静态入口核验与真实新会话读取分别报告。

## 当前正文归还与中断恢复

归还不等于整机卸载。Agent 读取当前公共正文、各家当前原生正文和本次 HOME 下已提交共享 manifest 的 `operation_metadata.share_user_memory.migrations`，给出明确精确计划：

- `schema_version:1`，`basis` 至少含当前公共主题绝对路径与 sha256，建议含全部目标基线。
- `items` 每处指定 `ref`（共享 manifest 父目录名）、`migration`（该 manifest 的迁移数组下标）、当前 `public_span:{start,end,text_hex}`、`target:{path,mode}`。未漂移原来源可用 `mode:in_place`；当前原生内容已编辑时必须用 `mode:insert_at,insert_at:当前字节偏移`，不能默认文末追加。多个偏移均针对本次当前文件，由工具从后往前执行。
- 公共新增用 `additions:[{start,end,text_hex,action:"move",target:{path,insert_at}}]` 明确目标；要保留公共则 `action:"keep_public"`。历史迁移也可明确 `action:"keep_public"`；它保留读取依赖，不构成完整退出。
- `remove_entries:true` 仅在迁移全部处置、无保留公共迁移时使用。只移除本次精确公共目标入口，其他引用和 CK 不动。分隔空白默认保留；需移动的其他当前公共正文也须明确列入新增范围。

```bash
python3 -B scripts/memory_share.py return-user-memory --agent codex --agent claude --return-plan-file /绝对路径/return.json
python3 -B scripts/memory_share.py return-user-memory --return-plan-file /绝对路径/return.json --approval-file /绝对路径/return-approval.json
python3 -B scripts/memory_share.py recover-memory-share --manifest /当前HOME/.mem-sharing/backups/事务目录/manifest.json
python3 -B scripts/memory_share.py recover-memory-share --manifest /当前HOME/.mem-sharing/backups/事务目录/manifest.json --approval-file /绝对路径/recovery-approval.json
```

归还先展示完整 `approval_plan` 的目标、当前位置和解码后的完整字节变化，用户确认后完整加 `confirmed_at/reference` 执行；归还本次 manifest 记录消费引用，不改删历史 manifest。恢复先只读检查并展示计划，按输出的完整 `approval_plan` 加真实确认执行。陈旧锁不会自动抢占：先由操作员核实进程已结束和现场，再处置本次确实陈旧的两层锁，不把删锁做成普通成功路径。失败或未知不得报完成。

## 既有外围与兼容入口

新用户记忆主线与旧安装/卸载各自保持范围。以下只在用户明确需要相应能力时读取；不为共享重新安装产品或生成发行包。

| 意图 | 路由 |
| --- | --- |
| 安装、升级、添加 Agent | [INSTALL.md](INSTALL.md)；按既有精确计划和批准，不把六家安装支持当成本切片验收。 |
| 当前项目规则接入与共享 | 项目记忆四步与用户记忆同一薄 CLI：`python3 -B scripts/memory_share.py share-project-memory --project <项目绝对路径>`（预览/提案/选择/批准同用户四步；归还 `return-project-memory`，恢复 `recover-memory-share --manifest`）。仅 Git 主 checkout，独立文件去重计票；AGENTS 既有公共项默认保留并只整理其他文件重复，不进待选；排除既有项必须逐项绑定本项目原生文件去向；Claude 补 `@AGENTS.md`、WorkBuddy 补项目桥块并核验后才删源；disabled 历史登记 fail closed 跳过；事务材料在 `<项目>/.mem-sharing/backups/`。合同见 [PRD](docs/memory-sharing-fusion-prd.md) 与[项目链验收](docs/acceptance/skill-first-project-chain.md)。 |
| 批量接入、健康检查 | `scripts/agm.py enable-memory-batch`、`check-memory`，参数见操作手册；检查只读。 |
| 明确“卸载 memSharing／mem-sharing”“不想用这个共享记忆工具了，帮我卸载” | 立即进入[整机卸载合同](docs/uninstall-design.md)的零写预览。核实旧安装代码与台账，外置恢复路径和精确批准后才卸载；自然语言意图不代替完整计划确认。目标含糊先澄清。 |
| 旧迁移、staging、旧卸载恢复 | 按[模块去向评审](docs/retrospectives/2026-11-03-module-disposition-review.md)读取对应兼容文档；不删除未知备份或绕过恢复门禁。 |

项目经历由 Context Keeper 独立管理，记录库、协议及上游源码不参与本流程。AGENTS 项目基座和有效原生项目桥接按既有治理保留。未经单独授权，不提交、推送、安装、卸载或修改真实宿主。
