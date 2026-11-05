---
name: mem-sharing
description: 多 Agent 记忆共享与融合，给你的每一个 AI Agent 同一份记忆。
---

# memSharing

当前 Agent 理解原文，用户决定共享范围，小工具按确认清单精确修改字节。设计合同见[共享 PRD（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/prd/sharing.md)和[架构与保护边界](docs/architecture.md)。

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
4. **选择即执行。** 展示两块方案时说明参与者、原文查看入口、公共目标、删源范围、保留内容、必要入口与备份安排。把本次 `approval_plan` 保存在本地；用户回复“按默认方案”或明确编号即授权，不再问“确认执行”。按实际选择构建完整计划，绑定真实选择消息；不得伪称用户另行批准。示例：

   ```bash
   python3 -B scripts/memory_share.py share-user-memory --agent codex --agent claude --proposal-file /绝对路径/proposal.json --selection '按默认方案' --selection-plan-file /绝对路径/已展示计划.json --selection-reference '实际用户选择消息'
   ```

   安装后 `organize-user-memory` 同样使用 `--selection`、`--selection-plan-file`、`--selection-reference`。`--approval-file` 保留为内部精确批准接口，批准证据直接来自本次选择。现场或编号实质变化才停止并重新展示；查看零写、不生成执行批准。执行后简报实际迁移、保留及备份结果。

   执行批准时不混入 `--agent`、`--selection`、`--proposal-file`；HOME、来源、公共正文和入口漂移均使旧批准失效。顺序为公共完整原文→全部原生入口→核验→精确删源，复用同一 Transaction 备份/恢复。同语境且完全同字节的同组来源可共用一份公共正文，每处来源、位置和次数仍在 manifest 顶层可选 `operation_metadata` 中逐处记录；格式变体逐份保留。原文不摘要替换。条目之间只补足一个空行，原生剩余字节不重排。

脚本输出 JSON；退出码 0 为本命令完成/只读查看，5 为待用户选择或内部精确批准，2 为失败或需恢复。`--home /绝对临时HOME` 仅用于隔离合成验证，不能把真实用户操作悄悄转到别处。静态入口核验与真实新会话读取分别报告。

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
| 当前项目规则接入与共享 | 项目记忆四步与用户记忆同一薄 CLI：`python3 -B scripts/memory_share.py share-project-memory --project <项目绝对路径>`（预览/提案/选择/批准同用户四步；归还 `return-project-memory`，恢复 `recover-memory-share --manifest`）。仅 Git 主 checkout，独立文件去重计票；AGENTS 既有公共项默认保留并只整理其他文件重复，不进待选；排除既有项必须逐项绑定本项目原生文件去向；Claude 补 `@AGENTS.md`、WorkBuddy 补项目桥块并核验后才删源；disabled 历史登记 fail closed 跳过；事务材料在 `<项目>/.mem-sharing/backups/`。合同见 [项目 PRD（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/prd/project-rules.md) 与[当前验收（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)。 |
| 批量接入、健康检查 | `scripts/agm.py enable-memory-batch`、`check-memory`，参数见操作手册；检查只读。 |
| 明确“卸载 memSharing／mem-sharing”“不想用这个共享记忆工具了，帮我卸载” | 立即进入[整机卸载合同](docs/uninstall-design.md)的零写预览。核实旧安装代码与台账，外置恢复路径和精确批准后才卸载；自然语言意图不代替完整计划确认。目标含糊先澄清。 |
| 旧迁移、staging、旧卸载恢复 | 按[兼容操作路由](docs/operations.md#保留的历史兼容入口)读取对应兼容文档；不删除未知备份或绕过恢复门禁。 |

项目经历由 Context Keeper 独立管理，记录库、协议及上游源码不参与本流程。AGENTS 项目基座和有效原生项目桥接按既有治理保留。未经单独授权，不提交、推送、安装、卸载或修改真实宿主。

## 原生入口与增量接入

六家执行器的原生 `skills/mem-sharing/SKILL.md` 由安装器按选择补齐，读取持久安装核心；记忆引用本身不等于 Skill 可发现。新增 Agent 先补入口且保留其原文，再展示增量整理方案，由实际选择授权执行；已有公共同语境同字节正文复用，不重复搬入旧 Agent 内容。已接入 Agent 重装零写，不再提示融合。任意入口提出卸载均走同一全机卸载核心，处理全部受管 Agent；不存在仅卸载当前 Agent 的产品分支。WorkBuddy 的 WORKBUDDY_CONFIG_DIR、CODEBUDDY_CONFIG_DIR、数据目录名或实例号使用户根偏离默认值时停止接入，不回显环境原值。

## 自动项目接入

首次进入未登记的 Git 主工作目录，先读取本 Skill 并核对项目台账；非 Git、linked worktree 和历史 disabled 项目跳过，不恢复已停用项目。用本 Skill 所在持久代码目录 C 的命令 `python3 -B <C>/scripts/agm.py enable-memory --project <项目绝对路径> --agent <当前执行器>` 接入；创建缺失的 AGENTS.md 并追加项目经历协议，完整保留已有正文。遇漂移、归属不明、覆盖或迁移要求，按对应精确预览/批准合同停止或处理，不用默认接入绕门禁。

项目已接入后，当前 Agent 首次实际使用时仅补自身缺失的专属入口；不因检测到其他 Agent 已安装就预建其入口。用户明确要求全体或批量接入时沿用相应命令范围。项目经历由 Context Keeper 独立管理，不随默认接入安装、初始化或创建其记录库；历史 disabled 不代表 Context Keeper 停用。

Claude Code 首次使用已接入项目时，仅处理当前项目：先核对台账，历史 disabled 项目跳过；按上述命令显式指定 `--agent claude`，沿精确预览与批准流程补齐项目 `CLAUDE.md` 对 `AGENTS.md` 的引用。`CLAUDE.md` 缺失时创建仅含 `@AGENTS.md` 引用行的文件；已有文件完整保留原文字节和权限，只追加缺失的引用行。已有有效引用时不重复添加，重复执行不改字节；不改其他项目或其他 Agent 的专属入口。

## /mem-sharing 菜单

| 用户意图 | 操作入口 |
| --- | --- |
| 添加 Agent | [安装与增量接入](INSTALL.md)，显式 --agent 限定；重复已接入者零写。 |
| 批量接入项目规则 | [操作手册](docs/operations.md)，指定扫描目录并预览范围。 |
| 整理用户记忆 | 本 Skill 的用户记忆四步；先提案、再逐项批准。 |
| 健康检查 | [操作手册](docs/operations.md)，只读 check-memory。 |
| 接入项目规则 | 本节自动接入合同及[操作手册](docs/operations.md)。 |
| 卸载 memSharing | [完整卸载合同](docs/uninstall-design.md)，全机统一预览与批准，不按当前 Agent 缩小范围。 |

新装不生成《使用约定》主题或菜单副本；旧格式仅按已核验来源兼容识别，不无批准改删用户文件。

## 安装对话收尾

检查后集中确认一次安装范围，静默安装；成功后展示公共用户记忆的默认共享/由你选择两块。选定直接执行并简报，或用户暂不整理后结束该阶段，最后才询问 CK。已有有效公共读取块时不另加 memory-index；仅精确归并已证明的产品重复指针，空用户规则章节随同一事务清理，保留未选正文。
CK 提示：为了让 Agent 在新会话中记住项目进度、决策和经验，接着上次的工作继续，需要另外安装 Context Keeper。是否为本机已安装的〈实际检测名单〉安装？回复“安装”或“跳过”。名单独立于本次 memSharing 选择；CK 单独授权，回车不算同意。当前固定上游只支持三家，其余明确报告不支持，不传未知 flags、不改上游。

### 显式复用既有公共片段

标题不同但 Agent 完整阅读后确认适用语义等价时，不改写来源标题或取消语境保护。为 `organize-user-memory --public-reuse-file /绝对路径/reuse.json` 提供 JSON 列表：每项包含 `source/start/end/source_context`、`public_start/public_end/public_context`、`text_sha256`、Agent 实际完整读取时的 `source_basis/public_basis` SHA256、`equivalent: true` 和非空 `reason`。context 使用实际的 `[标题深度, 标题原文, 同级出现次数]` 列表；公共目标必须是已证明、同字节的既有片段。同组需要逐处声明，不能用一处判断扩大其他来源。

先展示含理由、源/目标范围的完整预览，再按实际选择执行；查看零写。没有声明仍按原语境保护，不自动建立永久标题别名。来源 context、位置和次数保持原样记录，归还与卸载仍使用已有协议。
