# 当前用户全卸载→固定来源全新安装：只读准备与阻断计划

时间窗口：2026-11-04 04:58:59–05:13:59 UTC。本阶段只读核查、正式预览与计划，不执行删除、迁移、安装，不制作批准文件。真实产品与六家入口未修改，未调模型，未触碰凭据、当前 Paseo daemon/会话或 CK；无 commit/push。用户已授权本机测试，开始本身不再询问；删除仍须先展示具体完整计划再批准。

**当前结论：卸载正式预览被阻断，尚无可批准执行的完整删除计划。下面的删除根是已核实候选清单，不是成功卸载计划；不能批准本报告摘要来替代产品完整预览。**

## 现场身份与只读证据

| 对象 | 本次实测 |
| --- | --- |
| 源码 | 开始时工作树干净，HEAD 与 origin/verify/skill-first-runtime 均为 `2b239f045c55f38fe08b041a284fb7e8b83a451e`；后续只新增本报告。 |
| 已装 C | `~/.local/share/mem-sharing`，版本 0.1.7；来源 `8f3c43e30674dc2769559c6aab3010fb6df62dbd`，受管树 `99f96abd7e95487c6684077c7e7083677d466c7fba23fd31dc68e82134759b2f`；46/46 文件哈希一致，无额外文件、无 pycache。 |
| V | schema 3，installation_status=complete，installation_id=`20261103T104014Z-d486dc450a1d4a898f1f95e10c7a71db`。台账无已登记项目，七个机器受管单元的实际指纹全等。 |
| 六家原生用户文件 | Codex、Claude、WorkBuddy、DSH、ZCode、OpenCode 均为 live connected；runtime_acceptance 仍 pending。私文未输出到仓库。 |
| 原生 Skill 当前状态 | Codex 与 Claude 的 `skills/mem-sharing/SKILL.md` 当前均不存在；记忆指针 connected 不等于原生 Skill 已安装。新固定代码只自动分发这两家的原生 Skill，其余四家本阶段检查用户规则入口，不能宣称六家 slash 均可用。 |
| 当前公共文件 | 仅 MEMORY.md 与 user-rules.md，无《使用约定》。前者 SHA256=`7d5afd358db918982cb51ebc0842c8b1062a531ba6f04253f31357b64e757d01`，1353 bytes；后者 SHA256=`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`，1848 bytes。正文是用户数据，不写入本报告。 |
| 固定新源 | 官方 checkout_source 和 _source 已核验 49 个受管文件；版本按既有授权保持 0.1.7，来源 `2b239f045c55f38fe08b041a284fb7e8b83a451e`，规范含 mode 的受管树摘要=`20efa354c23763ea3f30e9b21857449363f16d1606d5011dbef7b63b9f305273`。这不是已安装或已发布证明。 |
| 当前安装事实 | 本次固定代码重新检测六家均 installed。OpenCode 分面 CLI=verified、desktop=verified；其他五家本输出没有分面字段，不据 null 推断缺失。 |
| 本地 Codex | CLI 0.166.0，help 实证支持 `--sandbox`、`--ask-for-approval`、`--cd`；未启动模型、App 或新会话。 |

临时诊断证据根（0700）：`/var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-real-reinstall-gj8nbjkp`。文件均设 0600；可能含原始预览/本地安装元数据，不发布到仓库。

- `baseline.json`：六家文件+V+两公共 md，共九目标，记录 hash/bytes/mode/inode/dev；各次预览后哈希均全等。
- `product-preservation-inventory.json`：仅四个明确产品根，205 文件、31 目录，无 symlink/特殊节点；逐文件 sha/mode/inode，未复制正文、未创建真实备份根。清单摘要 `c61950387ac8a475e654f88b65749dc4169da362aa4934e2ea5efcee539a9046`。
- `installed-uninstall-preview.json`、`installed-policy-preview.json`、`fixed-install-existing-preview.json`：实际 CLI 输出，保留失败。
- `fixed-source.json`、`fixed-source-verified.json`：固定来源与逐文件清单。之前诊断打印的 `e380…` 是 files 映射摘要，不是产品规范 tree_sha256；以表中 `20efa…` 为准。
- `host-target-evidence.json`、`live-agent-detection.json`：本次宿主与安装事实证据，不包含完整配置或凭据。

## Paseo 宿主范围

官方 `paseo status --json`→`paseo plugin ls --json`→status，前后同 home、serverId=`srv_snTWUoI0EgfS`、PID=3231、startedAt=`2026-11-02T03:40:50.467Z`，localDaemon=running、connectedDaemon=reachable。完整列表共八条，逐条读取其 `paseo-plugin.json`，八份均可读且无 manifest id=memsharing；名称/ID/路径/来源亦无目标匹配。完整列表摘要 `64f24805b50419c237a9178f50cad6bc1fd4604f9fc551a0b137549552561b5d`。

这证明**当前指定 daemon** 没有该插件，不是“所有 daemon/历史文件均无残留”。执行前必须对同一目标重查；若出现任何目标 alias、disabled 记录、来源不明或查询失败，停止并按宿主义务重新计划。现状无需 remove 任何插件；八个其他插件、daemon 与会话均保留，不重载、不改配置。

## 实际正式预览与阻断

1. 已核验旧 C 的命令：

```sh
python3 -B /Users/vincent4j/.local/share/mem-sharing/scripts/agm.py uninstall-machine --backup-dir /Users/vincent4j/.mem-sharing-review-backups/real-reinstall-20261104T050000Z --json
```

实际 rc=2，status=failed，code=uninstall_conflict：`Active/ambiguous product dependency; preserve and review required`。只读诊断不改变检查结果，定位到 `~/.mem-sharing/memories/MEMORY.md`，展开正文仍含 C 绝对路径。旧 C 不认识主按用户审阅修改的新索引；这是兼容衔接遗漏，不是用户错误。该备份路径尚不存在。

2. 已核验旧 C 的 `python3 -B <C>/scripts/agm.py migrate-policy`：实际 rc=2，`Unknown/customized public contract; preserve: /Users/vincent4j/.mem-sharing/memories/MEMORY.md`。现有机制只接受固定旧模板，不是通用用户文稿退休许可。

3. 固定新源的正式安装预览（source-manifest 取自上述私有证据根）：

```sh
python3 -B /Users/vincent4j/.paseo/worktrees/0p9qz2xa/skill-first-runtime/scripts/install.py --source-manifest <证据根>/fixed-source.json
```

实际 rc=2，code=machine_route_future，信息 `no supported source conversion`。同为 0.1.7、来源不同，覆盖被拒绝；不加 conversions 或换版本绕过。完整卸载成功并核为空后才能重新生成真实 fresh 安装预览。

**实际提示可用性问题：** 第一条没有具体文件和可行动下一步；第二条有文件；第三条内部 future 标签易让用户误解为版本高低。外层必须保留原始失败并明确解释“当前索引未被旧执行器识别”“同版异源覆盖不受支持”，不能润色后假称原 CLI 如此显示。真实成功、进度、融合和 slash 输出尚未产生。

## 最小合法解阻：独立兼容工具，不覆盖升级旧 C

首选是另行实现、审查并固定一个外置兼容工具提交 K（**K 目前不存在，不编 hash，不自动部署**），仍让安装目标保持用户指定的 2b239f04。

1. 在 `scripts/agm_core/uninstall_compat.py` 增加一个独立且窄的 0.1.7 profile。不要直接放宽 `staging_retirement.installed()`：该旧函数同时承载固定 0.1.6 staging 权限。新 profile 必须绑定本表 installation_id、0.1.7、8f3c43e3、99f96abd…、V hash、C 的完整 46 文件/mode/闭包，复用当前严格 active C 校验；错版本/错来源/多文件/活跃事务拒绝。
2. 当前兼容入口通过 `staging_retirement.installed()` 只认固定 0.1.6，host_scene 只认 `memsharing-synthetic-dev`。两者都不适用于本机，不能传假 ID 或假 absent。新 profile 绑定上文真实 daemon 的 full-list/八份 manifest 缺席证明，执行时重查 PID/serverId/startedAt/其他插件摘要；发现目标则切换真实 host binding/remove 合同，不伪造 removed。
3. 在独立工具与 `uninstall_memory` 的正式分类接口中增加**显式产品控制退休子计划**。对这份已批准索引按完整 before 字节/sha 及精确 span 分类：读取/保存归属/索引维护/自动接入/操作入口属于本次明确展示的产品常驻规则；user-rules.md 六条个人规则作为完整用户主体归还。不能仅按路径、关键词、标题或一份自报 approval 就删内容；所有已知控制片段须完整匹配审阅模板变体，分类必须无遗漏/重叠。任何新增或未知正文 fail closed，重新展示计划；不删读不到的文件、不回滚审定稿。
4. 该子计划纳入原全机卸载一个精确批准：本地展示完整原文、退休片段、六家最终正文、删除清单、恢复材料；先外置保全本次现稿及原始字节，再归还、读回、最后删产品。恢复直接还原本次批准时的审阅稿，不退回此前旧版，也不覆盖第三态私文。主已有审阅备份 `~/.mem-sharing-review-backups/20261104T033449718586Z` 只保留佐证，不把“有备份”当删除权。
5. 实现阶段仅在隔离 HOME 重放：准确 0.1.7+当前模板正例；任一字节/来源/mode/额外文件/索引新增私文/缺主题/源指纹/锁/daemon/alias 改变负例必须零写；六家私文、CK、重复次数与 restore/resume 保全。完成后在可信干净 K 下重新正式只读预览，生成真实完整计划，再由主展示给用户批准。**本阶段没有做这些源码修改。**

备选 `migrate-policy` 仅在增加同等严格的精确审阅稿转换机制后才可能解阻，但会先写真实 R，额外增加一次转换与批准，而且不能单靠它绕过同版新源门禁；不优先。手改删绝对路径、退回用户旧稿、将新代码覆盖 C、篡改台账、移动历史备份、临时 monkeypatch 通过检查均不可选。

## 具体保全、执行与恢复顺序（待正式计划批准）

- 候选删除根：`~/.mem-sharing`、`~/.local/share/mem-sharing`、`~/.local/share/mem-sharing-versions`、`~/.local/share/mem-sharing-sources`。按未来预览逐对象枚举，不能用本表递归 rm。
- 保留六家原生用户文件并原地精确写入归还后的用户正文；当前项目登记为 0，不额外扫描仓库。项目 AGENTS/独立 CK、当前 Paseo 会话/daemon、其他 Skills/插件、源码/worktree均保留。
- 三个既往安装证据容器由正式库存标为 retained：`.mem-sharing-install-20261103T091034Z-5d499c40808346f0a1c80052d9bd9883`、`.mem-sharing-install-20261103T094051Z-3fe45da1871c4aaa8e84ee6fed7726f5`、`.mem-sharing-install-20261103T104014Z-d486dc450a1d4a898f1f95e10c7a71db`；审阅备份与既往 QA 证据也不自行删。
- 计划中的全新外置备份根为上述 `real-reinstall-20261104T050000Z`，现有父目录 mode=0755，不 chmod 原目录；获批准后新根设 0700，私有文件 0600。完整 before、六家 byte/mode/inode、R/C/V、受管来源、恢复引擎及必要独立 Python均须在具体清单内，先验证可独立读取/恢复，再改入口。现阶段只准备元数据清单，未创建该根或复制真实正文。
- 卸载执行失败立即保留证据；恢复始终独立预览+精确批准，保护第三态内容。成功后按同 daemon 重核目标缺席及其他插件不变，确认四根与受管依赖确实清理，再进入 fresh；不以机器资产成功冒充宿主成功。
- 新安装目标固定为 2b239f04/0.1.7，默认范围为本次已核实 installed 的六家，可在正式安装请求用六个重复 --agent 明确绑定。安装完整计划必须已含六家入口、Codex/Claude Skill 及代码/台账/恢复范围，不能写完代码再补一次本应包含的入口批准。
- 本报告新增会使完整工作树有非产品文档 dirty。`fixed-source.json` 生成时全树干净；正式 source-manifest 路径会重核 HEAD 与全部受管文件。若重新用 --source/独立工具 clean_checkout，必须使用真正干净的固定 checkout，不隐藏 dirty、不冒写固定 commit。不得在卸载前把新 export/插件装入待删产品根。
- fresh 安装成功不等于公共规则已融合：旧公共主体会先归还六家私文，新公共索引允许没有 user-rules。随后展示增量整理默认/待选与完整内容清单，独立批准后才把共通六条迁回一份公共正文；安装批准不代替内容融合批准。CK 是独立可选尾步，选择保留，不自动安装/初始化/卸载。

## 用户可见信息逐步验收表

每一步保存实际 CLI JSON（私有 0600）、外层实际会话文本与状态，逐项对照；本表是期待与执行准则，不是已显示的结果。

| 步骤 | 必须正确显示/行为 | 当前证据层 |
| --- | --- | --- |
| 检测与范围 | 六家实测 installed、分面限制；默认或实际选择的六家一致，不拿旧台账替代 live 检测。 | 本段真实只读检测已留；未来安装呈现待验。 |
| 卸载前状态 | 当前已装 0.1.7/8f3c43e3，公共库仍存在；明确当前失败且没有删除。 | 三份实际错误 JSON 与本次外层说明已留。 |
| 全部修改清单 | 完整归还/退休/保全/删除/宿主/恢复范围；私文只能在用户私有界面展示，仓库仅摘要哈希。 | 正式计划被阻断，待兼容工具重预览。 |
| 精确批准 | 只对已展示计划批准，source/scene/内容漂移使批准失效；不自填批准。 | 未生成批准。 |
| 卸载进度 | 备份验证→六家读回→删产品；机器/宿主/overall 分列，不把进度当成功。 | 未执行，故障分支引用既有合成证据。 |
| fresh 安装 | 真实四根清空后才显示 fresh，不把 source/下载/export acquired 当安装 completed。 | 当前覆盖预览已拒绝；fresh 待真实卸载后预览。 |
| 入口接入 | 安装前完整计划一次包含六家；Codex/Claude 原生 Skill 与四家用户入口分别说明。 | 尚未安装。 |
| 重复安装 | 实际 rc/status/changes=[]，明确“已安装，已接入”，九目标及新增代码/Skill清单前后零写，不重启融合。 | 待执行，不能用源码文案冒充实际显示。 |
| 首次新增/内容整理 | 默认共享/由你选择是否共享两块、空块暂无、稳定编号；查看零写，完整最终清单，独有未选保留。 | 本机待验；不复用安装批准。 |
| 安装与融合状态 | 安装成功可同时融合 pending/declined/blocked，不能写“全部记忆已完成”。 | 本机待验。 |
| CK 可选 | 实际可选提示；不自动安装/初始化，用户保留 CK 不影响主流程。 | 本阶段无 CK 操作。 |
| 收尾 | 写真实版本/固定来源/接入者/公共主题数/零写证据及未验项；不输出凭据和原始私文。 | 完成后据真实输出填，不预报成功。 |

## 代表 Codex 原生 Skill 验证方案

执行批准且新安装读回后，先核本机 `.codex/skills/mem-sharing/SKILL.md` 为受管文件、frontmatter 和持久 C 指向正确；这是文件层，不能称 slash 可用。

再用本机 Codex 0.166.0 **全新交互会话**，非 resume，cwd 为本次独立非 Git 临时目录，使用已核实支持的 read-only sandbox/approval 选项；保持登录和 Paseo 当前会话/daemon不动。通过原生技能菜单列举并实际尝试用户要求的 `/mem-sharing`，记录菜单发现、原生选择/绑定和只读“展示菜单”执行输出。若当前 CLI 只提供其他原生选择语法，先据实际界面记录差异；`/mem-sharing` 未识别就标该项失败/pending，不用 `$`、普通自然语言或显式 cat 当作 slash 成功。只调用这一个代表模型，不向六家发模型请求，不触发安装/整理写入。

验收分别标：CLI JSON、外层 Agent 呈现、原生技能发现、字面 slash 命令与原生执行；每层均需实际证据。仅显式读取 SKILL.md、目录存在或本轮计划不能证明原生调用。执行后再核六家、公共文件和受管代码/Skill指纹，确认代表测试未写用户记忆。当前这些层全部尚未执行。

### 结束前复核

05:12:04 UTC，旧 C 的 46 个文件逐一与本仓库 Git 固定提交 `8f3c43e30674dc2769559c6aab3010fb6df62dbd` 的 blob 原始字节比较，46/46 一致，不只依赖自报 manifest；证据 `old-git-source-proof.json`。九个基线目标再次全等，拟用真实外置备份根仍不存在。当前仓库唯一新增为本报告，未改源码、测试、CK 或真实记忆。

## 用户取消兼容并直接授权手工清理后的实际节点（05:27 UTC）

用户明确取消兼容开发，并直接授权只清理已核实四产品根与六家产品自有引用。本段已停兼容测试：组合 runner exit143，外置恢复单项 exit0；未完成的兼容源码不作正式工具交付、不提交，保留待主收口。新增写集为 uninstall.py、uninstall_compat.py、uninstall_recovery.py 与 test_uninstall_reviewed_017.py；没有混入下述固定安装源。

实际已完成一次性手工清理，**不是旧卸载器验收通过**：

- 外置备份根（0700）：`/Users/vincent4j/.mem-sharing-review-backups/manual-clean-20261104T052626Z`。四根 205 文件/31 目录及六家原生文件逐个复制后核 sha/mode，审阅两 md 另存 `reviewed-public/`；完整恢复映射、原 before 与六家精确产品 span 在私有 `manual-manifest.json`。
- 六家仅删除 V 指纹验证通过的产品 marker span，以及 Claude 唯一完整 import 行中的产品 token；其余原字节不重排，文件 inode/mode不变。写前重核各文件，读回新 hash；删除前再次核整个原库存没有新增/漂移。
- 四产品根按已验证清单逐文件 hash/unlink、空目录 rmdir；四根均不存在。未递归吞未知文件，未删六家文件、CK、其他 Skills、八个其他插件、Paseo daemon/会话、历史安装容器和旧外置证据。
- 六条用户规则原文保存在 `reviewed-public/user-rules.md`，原 sha=`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`。后续 fresh 完成后恢复此用户数据并加真实主题链接一次；不把整个旧 MEMORY 覆盖新模板。恢复当前审阅稿所需原文仍完整保留。
- 真正干净的 detached 固定 checkout 已建在备份根的 `fixed-checkout`：HEAD=`2b239f045c55f38fe08b041a284fb7e8b83a451e`，git status为空。取消兼容的 dirty 代码完全不在其中。
- 从该固定 clean checkout 正式运行 fresh 安装预览：rc5、approval_required=true、channel=fresh、六家 effective、75 条 changes、无 errors。私有完整输出为备份根的 `fresh-install-preview.json`；没有自造安装批准或执行安装，四根仍全部不存在。

已停在“备份验证+手工清理完成、真实 fresh 精确预览可审”节点，交主审核并续接安装。未发模型，原生 slash 未测；后续用户提示验收表继续有效。清理脚本与实际 stdout 保存在 `/tmp/msf-manual-clean.py`、`/tmp/msf-manual-clean.log`，均不是产品兼容工具。主后续应保留本次恢复备份直到 fresh 与六家数据验收闭合。

## 用户明确继续后的真实 fresh 安装与验收（2026-11-04 05:32–05:39 UTC）

主展示完整75项清单后，用户明确回复“继续”；本次批准引用主消息 `faf0cfd8-1564-4dea-9630-d2ec73c71333`，确认时间记录为 `2026-11-04T05:32:09Z`。未声称更早批准。执行前以原 operation_id 重跑正式预览，approval_plan 与展示版本逐对象完全相等，内置 plan_sha256=`3fcb3851eebf540f4c18f2ceaf642df8579631e6f55df7fd0ac21e66ad8fa6ab`。clean checkout 无 dirty、四旧根不存在、六家文件与清理后 baseline 全等，然后才执行实际批准文件。

实际命令来自备份内干净 `fixed-checkout/scripts/install.py`，参数为同一 `--source <备份>/fixed-checkout --commit 2b239f045c55f38fe08b041a284fb7e8b83a451e --version 0.1.7 --operation-id 20261104T052720Z-20e588140d2d4f9aabe6b0cb94398deb --approval-file <备份>/fresh-install-approval.json`。当前工作树取消兼容的 dirty 未部署。正式执行退出码0、status/message=completed；六家 connected，connection_pending=false。此链是**授权手工清理后 fresh 安装**，不是旧正式卸载器通过。

### 身份、数据与重复安装

- schema3、product complete、版本0.1.7，source commit 为固定2b239f04，tree_sha256=`20efa354c23763ea3f30e9b21857449363f16d1606d5011dbef7b63b9f305273`。C manifest49文件逐一内容校验通过。
- 六家原生用户文件的安装前事务备份逐一等于手工清理后的 baseline。逐字节 diff 全部只含 insert，无 delete/replace；文件权限均保留。新V共9受管对象，含两个原生 Skill 文件、六家规则与 Claude import。Codex/Claude Skill frontmatter及持久C引用已实读；其他四家仅规则入口，不称四家都有 native slash。
- 已审阅 `reviewed-public/user-rules.md` 原字节恢复一次到新公共目录，六个编号仅一份，sha256=`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`。保留新生成 MEMORY模板，仅添加真实 user-rules 链接一次，未用旧 MEMORY 覆盖。公共文件集仅 MEMORY.md、user-rules.md，没有使用约定主题。
- 固定源正式重复安装 rc0，实际 message=`已安装，已接入。`、changes=[]、approval_plan=null、fusion=null。114相关文件（R/C/V/六家/两个Skill）的内容sha、mode、mtime_ns、inode前后完全相同。原生模型测试及只读查看后再次比较亦相同。
- 外置完整备份与映射继续保留，不自动清理；Paseo daemon PID3231/serverId/启动时间保持，8插件列表序列化sha仍为 `64f24805b50419c237a9178f50cad6bc1fd4604f9fc551a0b137549552561b5d`。未操作凭据、CK、其他Skills或插件。

### 真实用户可见输出分层

| 层/步骤 | 实际结果 | 裁定 |
| --- | --- | --- |
| 预览与批准 | 75项、fresh、effective六家；现场重算plan完全相同，使用本次真实继续引用。 | 通过；外层展示清单由主完成。 |
| 完成输出 | CLI completed、六家connected；外层明确“安装完成、融合待选择”。 | 安装成功，不等于全部记忆融合完成。CLI不是进度条，未虚构中间进度。 |
| 私文增量整理 | 自动尾步只生成零变更preview，pending_selection，default_numbers=[]、single_numbers=[1..6]。未批准或执行正文搬移。 | 状态分离通过；私文融合执行、最终内容修改清单保持未验。 |
| 默认/待选提示 | 实际prompt写默认暂无、由你选择是否共享暂无，但底部仍有6单家编号，没有可读摘要列表。 | **呈现缺口**，不能称整段提示验收通过。原始私文仅在私有输出，不复制报告。 |
| 查看编号 | 实际 `organize-user-rules --selection '查看 1'` rc0、status=viewed、plan.view=1、changes=[]，114文件不变。 | 只读查看零写通过；未将查看视为选择批准。 |
| 重复安装 | 正式“已安装，已接入。”、changes=[]、不再融合、114文件不变。 | 通过。 |
| CK可选 | 输出context_keeper.status=skipped、reason=non_interactive、独立next_action。 | 未安装/初始化CK；CLI未实际展示交互选择器，不以next_action冒充用户已选择。 |
| 收尾 | 固定版本来源、六家规则接入、2 native Skill、6规则恢复与未验项分开列出。 | 本报告据实际输出记录；不称6家原生运行均通过。 |

### Codex 新原生会话结果

实用本机 `codex-cli 0.166.0 --sandbox read-only --ask-for-approval never --no-alt-screen --cd /tmp/msf-native-skill-check`，新建非Git目录，非resume，未更改模型/账号。TERM=dumb有启动警告，接受继续；启动另有4条宿主警告，未修改插件/配置消除它们。

1. **字面 `/mem-sharing`失败**：界面实际回报 `Unrecognized command '/mem-sharing'. Type "/" for a list of supported commands.`，不能用后续成功覆盖该结论。
2. **原生Skill发现通过**：输入 `$mem-sharing`，原生picker出现 `mem-sharing [Skill]`及该入口description，选择绑定后发送“仅展示菜单、只读、禁止安装/卸载/融合/接入/写入”的请求。不是让外层显式cat冒充发现。
3. **原生Skill只读运行通过**：该代表模型实际读取 `.codex/skills/mem-sharing/SKILL.md`及持久C/SKILL.md，显示添加Agent、批量接入、整理用户记忆、健康检查、项目规则、统一卸载六菜单，并列实际路径。唯一代表模型回合，Worked22s，原始会话最后event=task_complete；PTY随后Ctrl-D exit0。未发六家模型调用。界面原生语法为 `$mem-sharing`，不是slash成功。
4. 实测后114文件sha/mode/mtime/inode保持，未触发项目自动接入（非Git）、融合或CK写入。Claude原生发现/执行及其余四家新会话仍未验。模型会话自身的正常会话记录/宿主hooks材料与产品记忆写入分开，不称整机零写。

### 私有证据与停止状态

同一0700备份根保存：fresh-recheck.json、fresh-install-approval.json、fresh-install-actual.json/.stderr、post-install-verification.json、repeat-install-actual.json、repeat-install-verification.json、fusion-view-1.json、fusion-view-verification.json、native-codex-pty.log、native-host-verification.json（私有文件0600）。Codex仅本次新会话ID=`01a1a50f-153a-7c90-810e-c5db65e3a2ae`，精确原始记录确认task_complete，不读取其他会话正文。Paseo官方host读回临时证据在 `/tmp/msf-host-final-status.json` 与 `/tmp/msf-host-final-plugins.json`。

本轮未修改产品源码或测试，未继续取消的兼容开发，无commit/push；唯一仓库新增更新为本报告。安装/查看命令均已退出，代表模型回合已完成、PTY退出，无本轮未收齐测试进程。数据恢复及安装验收完成；**字面slash和上述融合提示呈现未通过，新增私文融合未执行**，不得总体宣称全部用户体验验收通过。

## Claude 常驻入口短句任务（2026-11-04 07:20 UTC 起）

本次授权为源码短句/Skill合同/相关测试，以及可保持重复安装与卸载有效前提下的本机受管块同步；不含版本变更、安装卸载、来源manifest改写或新增兼容机制。保留此前取消兼容dirty，未触碰其三源码及测试。

### 已实现源码

`CLAUDE_FALLBACK_TEXT`改为用户指定精确一句：

> 首次使用已接入项目时，先读取 mem-sharing Skill，再按其流程补齐项目 CLAUDE.md 对 AGENTS.md 的引用。

`SKILL.md`的自动项目接入节承接详细执行约束：仅当前项目、先核台账且disabled跳过、显式当前claude执行器、沿精确预览/批准、缺失文件仅创建引用行、保留原文字节/权限、有效引用不重复、不得改其他项目/其他Agent入口。未改变项目接入核心命令行为，未修改其他Agent模板。

相关测试保留原有漂移/未知正文拒绝断言，新增短模板安装→正式重复零写→卸载只读预览；匹配短模板指纹也不能骗过旧模板reader；已登记项目首次Claude使用只补当前CLAUDE、重复零写、其他项目不动、disabled缺失入口不重建。详细保护断言从常驻长文本移到Skill合同测试，未将保护功能删除。

### 本机同步不可直接执行的已证实原因

真实安装C仍固定2b239f04。其 `scripts/agm_core/user_entries.py`机器已登记Claude分支，在actual指纹等于V trusted之后，还要求actual等于该C的旧模板desired（约477–480行）；否则`entry_semantics_missing`整单拒绝。其 `_claude_fallback_block_intact`也按标记内完整字节精确比旧模板（约835行）。已实际调用这个真实旧C函数，以纯合成短句块和该短句的匹配sha作为输入，结果False；没有使用真实私文作为诊断输出。

因此只换native+V不成立：保持旧hash将漂移拒绝，换为短句hash仍因旧C模板不符而拒绝。也不能直接改C及重算manifest冒充原固定来源。现有`upgrade._conversion`还明确拒绝same-version替换，changed-entry合同只支持既有冻结发行组合；不能仅另给一个新commit便称现有正式升级路径可用。**本轮保持真实CLAUDE/V/C/manifest不变，不把已授权的同步先做成损坏状态。**

最小收口是先交付源码修正，待主固定审核源码并裁定真实部署路径；若继续要求当前同版固定核心、禁安装升级、禁新增转换机制，真实同步这部分无法同时满足重复零写合同，应明确留待处理，不编造可执行升级命令。本报告不授权任何下一轮真实变更。

### 另行发现的既有本机台账阻断

首轮读取即发现真实V的8个created对象共同依赖下列manifest，但该文件已不存在：

`/Users/vincent4j/.mem-sharing-install-20261104T052720Z-20e588140d2d4f9aabe6b0cb94398deb/entry-backups/20261104T053459Z-e5763e3544444adb849bc626928136e5/manifest.json`

原`.mem-sharing-review-backups`父目录本次也已不在，不能复用上一阶段“仍存在”的断言。本轮没有删除这些路径，也没有调查或断言删除者。

在独立真实现存临时parent下，实际旧C正式卸载只读预览rc2、`registry_invalid: created backup manifest is unavailable`，目标backup未创建；实际旧C无参正式重复安装也rc2同因。因此这两项在本次未改本机短句之前就已阻断，不能记为短句引入回归，也不能宣布本机同步/重复零写/卸载通过。第一次预览使用已不存在的历史backup父路径，先返回`Backup must be a new directory in an existing real parent`；换合法parent后才定位上述独立台账错误，原始错误证据均保留。

私有证据只在本地：`/tmp/msf-claude-short-real-baseline.json`记录5个相关真实文件sha/mode/mtime/inode、真实C短句识别False与预览结果；`/tmp/msf-claude-short-real-uninstall-preview.json`、`/tmp/msf-claude-short-real-uninstall-preview-valid-parent.json`、`/tmp/msf-claude-short-real-repeat.json`保存实际输出，0600。五文件后复核与初始快照完全一致。未伪造/重建缺失备份，未洗V指纹；修复缺失历史材料属于独立待裁定事项。

### 本次验证终态与写集（07:31 UTC 前安全停）

- 最后冻结实现后组合执行：`PYTHONPATH=tests/unit:scripts python3 -B -m unittest test_install_idempotency_cleanup test_m405_user_entries test_m204_enable test_policy_retirement`，**86项/48.425秒，全部通过**，原始日志 `/tmp/msf-claude-short-final-86.log`。
- 另一次独立历史迁移套件 `test_public_layout.py` **71项/258.825秒通过**，日志 `/tmp/msf-claude-short-final.log`。其运行前后7文件指纹相同。随后唯一改动是下述policy测试断言；实现、Skill、public_layout测试及其他相关测试指纹与该轮相同。两轮分开报告，不称单次全量157项运行。
- 同日志中的policy套件首次15项有1失败：旧断言强制Claude入口常量包含“历史停用登记”。用户已要求细节归Skill，该断言过时；改为常量必须先读Skill且Skill含disabled跳过，保留历史Git blob逐字节识别和禁止旧政策句。修后15项独立通过，又纳入最后86项通过；未删除漂移/未知正文/旧字节断言。旧失败证据保留。
- 测试清单157个不同test ID（其中86最后组合、71独立），在 `/tmp/msf-claude-short-test-ids.json`，不是完整Python suite。最终源码/测试hash绑定及真实5文件不变结果：`/tmp/msf-claude-short-final-evidence.json`；原迁移前后hash：`/tmp/msf-claude-short-final-hashes.json`。`git diff --check`通过。
- 本次新增写集仅：`scripts/agm_core/user_entries.py`、`SKILL.md`、`tests/unit/test_m405_user_entries.py`、`tests/unit/test_m204_enable.py`、`tests/unit/test_install_idempotency_cleanup.py`、`tests/unit/test_policy_retirement.py`，以及本报告追加。无真实产品写，无版本变更，无commit/push，无模型/新Agent调用。
- 所有本轮runner均已退出（首组7、34、30，迁移71/退役15及修后15、最后组合86均有终态），无待收进程。真实短句同步、真实修改后重复零写及卸载验收均**未完成**；此前缺失备份与旧C模板约束已交主裁定，未用合成通过代替真实交付。

## 用户批准固定短句源码后再次清理与 fresh（2026-11-04 07:41:35–07:52 UTC）

用户同意完整方案并说“开始吧”，授权引用主消息 `bf163429-4f6a-4df8-8f27-e9793629d9f7`，时间 `2026-11-04T07:41:35Z`。主已将6个短句相关文件固定为本地提交 `f3b2524e537f1b19dc8ea4ba038c28c8bf7cebaf`，本轮未push。执行者未commit/push，也未带入取消兼容dirty。

### 固定源与当前数据保全

- 新外置根为 `/Users/vincent4j/.mem-sharing-review-backups/short-claude-20261104T0743Z`，0700，须保留至主验收及以后另行裁定，未自动删除。其内`fixed-checkout`为真正干净detached f3，git status空。
- 在该干净源上重新执行短句安装→正式重复零写→卸载预览，以及Claude当前已登记项目首次接入/disabled、已有私文保留三个定向测试，3/3、3.344秒通过。日志`/tmp/msf-clean-f3-tests.log`。这证明关键链不依赖当前工作树取消兼容dirty，不宣称干净源完整suite通过。
- 本次现场库存为106文件、17目录，sources根已absent；按3个实际存在根完整复制，第四根记absent，不伪造已缺失旧树。另备份6家原生文件、2 native Skill和审阅公共两md，覆盖V、C及现有版本库存。每文件sha/mode、目录mode核对，恢复映射在新`manual-manifest.json`；旧review备份不存在这一事实保留，不将新备份冒充旧历史。
- Claude整文件import receipt与当前文件不符，但当前文件sha与07:23基线相同，不能称本轮出现新的私文变化。只对唯一首行精确`@公共MEMORY` token，以及指纹匹配且完整字节为旧模板的fallback块证明归属；其他受管块均指纹匹配。按此次直接手工清理授权只移除这些可证片段及两份完整已验证native Skill，不洗V，也不扩大为整文件删除。其余原文字节和mode/inode保留。
- 完整备份后再核库存及每个原生文件快照，逐文件写前重核；四产品根仅按精确库存逐文件unlink与空目录rmdir。清理完成后四根均不存在。此前缺失的历史entry-backups没有被伪造。本链仍是**手工清理后fresh**，不是旧正式卸载通过。脚本`/tmp/msf-short-clean.py`和日志`/tmp/msf-short-clean.log`保留。

### 实际 fresh、恢复及正式读回

正式fresh预览来自新clean checkout，75项、六家effective、两份native Skill、channel=fresh，内置plan_sha256=`4939591c374c6fb83ffcd92f1777a41f7872375590e493af97311aed70c445f8`。范围与用户批准的完整方案相符后，以本次真实“开始吧”引用和07:41:35Z确认记录创建精确批准文件，没有借用更早批准。

正式执行rc0、status/message=completed、六家connected、connection_pending=false；fusion.status=pending_selection，CK.status=skipped（non_interactive）。未批准或执行新私文融合，未安装/初始化CK。旧六条审阅user-rules按本次备份原字节恢复一次，sha仍`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`；保留新MEMORY模板，仅登记一个有效链接。公共仅两md，不生成使用约定。

- 新V：schema3、complete、0.1.7、source commit=f3，tree_sha256=`c64f16866c9d2080d6b52643496beaba2b5e24e6dd88fa50543454e26846689e`；C49逐个文件sha匹配。新安装ID=`20261104T074452Z-a398ee803afe43209876d7f555a2b45d`。
- 六家安装事务before备份与清理后baseline逐项全等；实际字节diff仅insert，无delete/replace，权限保留。两native Skill指向新持久C，9个受管对象归属完整。
- 真实`~/.claude/CLAUDE.md`仍以`@/Users/vincent4j/.mem-sharing/memories/MEMORY.md`首行开头；原marker保留，块内精确为用户指定一句短句。全部私文由上述字节差异证明保留，正文不进报告。
- 正式重复安装rc0，实际“已安装，已接入。”、changes=[]、approval_plan=null、fusion=null。114相关文件sha/mode/mtime_ns/inode前后全等。
- 正式卸载**只读预览**rc5、status=approval_required、无errors，预览目标backup未创建；新9对象所需entry-backups manifest均实际存在。未执行卸载。该项在新安装上通过，不反向抹去旧安装missing backup失败。
- Paseo daemon PID/server/startedAt前后相同，8插件列表前后完全相同；未操作账号、凭据、其他Skill、真实业务项目或CK。

实际用户可见信息按层记录：预览和完整范围见`fresh-install-preview.json`；真实批准见`fresh-install-approval.json`；成功与融合待选择分开见`fresh-install-actual.json`；正式“已安装，已接入。”见`repeat-install-actual.json`；卸载仅待批准见`uninstall-preview-actual.json`。外层在每个节点准确说明当前状态。先前提示待选摘要呈现缺口未在本次扩大修复，不宣称所有文案分支通过。

### Claude模型运行验证：因HTTP502阻断，三个场景仍待验

主认可真实Claude进程保留当前用户账号及入口，仅执行器临时HOME/台账隔离，**不是整个Claude进程隔离**。本机Claude Code为2.1.295。临时根与三个Git项目路径仅存私有`claude-runtime-fixture.json`：alpha已登记而缺CLAUDE；beta有合成私文及有效引用；gamma在隔离台账disabled。隔离C使用真实新固定C字节，产品身份从新V投影；隔离V无其他业务项目、无私文，fixture准备不作为模型行为通过证据。

模型提示仅给三个普通README任务、临时HOME/根范围安全边界及已授权精确操作范围，让模型自行读取已加载规则/Skill判断行为；没有给三个场景的预期动作，也没有给逐条执行命令。禁止真实HOME产品写、账号/CK操作和其他Agent/模型调用。实际使用一次新的`claude -p`会话，dontAsk、限定内建tools/临时写路径、禁MCP；未换模型/账号。提示原文和实际stream分别保存`claude-runtime-prompt.txt`与`claude-runtime-actual.jsonl`，仅本地0600。

该会话实际连续6次HTTP502 api_retry，没有assistant回复、没有任何tool_use。为避免无效重试已TERM本次精确Claude PID34385，进程exit143，未发第二次模型请求、未升级或切provider。因此**原生加载触发、缺失引用补齐、已有引用幂等及disabled跳过的真实模型行为均未通过/仍待验**；不能用准备fixture或前述3合成通过替代。

读回alpha仍无CLAUDE、beta与gamma全文件内容不变；真实114文件sha/mode/mtime/inode及真实V与模型调用前相同。实测结果`claude-runtime-verification.json`；所有本轮执行命令和模型进程已有终态，无未收齐运行进程。

### 交回与证据保留

新外置根内的`product-inventory.json`、`manual-manifest.json`、`products/`、`native/`、`reviewed-public/`、clean checkout与fresh/重复/卸载/模型输出均保留；私有JSON/log为0600。`post-install-verification.json`、`repeat-install-verification.json`保存精确指纹核对。本轮仓库唯一写入是本报告追加；不改产品源码/版本/测试、CK、取消兼容dirty，不commit/push。窗口07:56:35前安全停交主审核：**安装/短句/数据保全/重复零写/卸载只读预览通过，Claude模型运行因服务HTTP502待验。**

### 交回前补核：无参安装入口的独立缺口

上述正式重复零写通过的是**与本次批准一致的显式固定源参数**（`--source <新备份>/fixed-checkout --commit f3... --version 0.1.7`）。另补跑已装C的`python3 -B <C>/scripts/install.py`无参入口，实际rc2、`release_invalid: Missing release manifest`，原始输出为新备份`repeat-installed-noargs.json`。本次direct-clean-checkout安装未生成`active_source()`要求的标准sources根中的release.json；sources在清理前即absent，未伪造旧树或补造发行receipt。新clean checkout和完整备份仍保留，可继续使用已核验显式固定源入口。

因此最终结论进一步限定：显式固定源安装及重复零写通过，**无参安装便利入口未通过**；不可笼统称全部安装入口均可用。本轮不扩大为发行导出/来源兼容修复，已交主裁定。读回安装状态、公共数据和卸载预览仍保持上文已证实结果。

## 两项剩余缺陷与取消改动清理（07:57 UTC 续行）

取消兼容3源码的原diff与新测试已逐hash备份到现有保全根的`cancelled-compat-evidence/`（0700，patch/test0600）；重核无并发变化后精确还原3tracked为HEAD，移除仅该新测试，保留本报告。没有撤掉正式f3修复。

无参入口修复：`active_source()`仅当该版本export目录真正absent时，复用已严格核验的活动C；固定commit/版本/tree来自V，完整C树/mode须匹配manifest，原安装版本库存的release/complete/code也须全量验证。目录存在但坏receipt不fallback、不捏造release。upgrade仅放行根恰为C且目标等于当前已核库存的noop，其他runtime重叠及活动C不同版本目标继续拒绝。

提示根因：真实安装尾步仍调用`user_rules_organize.continuation → present`；它只渲染optional_numbers，把single_numbers藏在尾部列表。此次仅改呈现：single与optional在“由你选择是否共享”下按原编号显示，标“单家内容，默认不共享”；选择集合/批准计划不变。Agent可沿既有summaries提供完整阅读后的语义摘要；CLI无摘要时明确显示忠实原文摘录（长文本截取160字带省略），不把摘录冒充模型摘要。查看仍零写，不增加配置或新融合子系统。

新测试覆盖direct-source安装后真正无参子进程noop、无export伪receipt、库存漂移拒绝、present坏export拒绝、活动C换版拒绝、C字节漂移拒绝及未选Claude入口不新增；单家待选编号/摘录/默认不选/查看零写。早期诊断日志保留于`/tmp/msf-last-fixes-target*.log`；其中fixture曾误混宿主App发现，现按既有CLI_DETECTION_BOOTSTRAP与隔离PATH修正，不改变实际默认接入范围。

本机落地准备（未执行）：待主固定审核后的新提交，建立新0700外置根并将新pin真正干净detached到其`fixed-checkout`；用`/tmp/msf-final-fixes-clean-ready.py <新备份根>`逐项备份当前数据后按可证owned片段/精确库存手工清理，脚本硬停界限08:10:15、旧C身份严格f3。然后用新clean checkout同六家75项fresh预览/本次用户明确“赶紧干完”引用执行，恢复本次备份的六规则原字节一次及新索引单链接；正式已装C**无参**重跑、查看零写、卸载仅预览、全相关指纹和六家私文保全读回。不得直接部署当前dirty或改C伪造manifest；当前f3及上轮完整备份保留，模型/Claude账号测试禁止。

### 本段终态与新增常驻精简（08:10 UTC）

两缺陷冻结快照的四套定向回归实际**68项、309.869秒通过**，日志`/tmp/msf-last-fixes-regression.log`；未跑全量。库存损坏、存在坏export、活动C换版与C字节漂移负例均在该轮，均拒绝且零写。原5文件hash在`/tmp/msf-last-fixes-source-hashes.json`，之后未改这5文件实现/测试。

用户截图新增DSH常驻技术说明精简：等68轮真正退出后才将`DSH_FALLBACK_TEXT`和`OPENCODE_FALLBACK_TEXT`置空。Codex/ZCode原已空；Claude短触发、WorkBuddy专属必要触发保留。新装4家native常驻块只生成公共读取指针；不删DSH私有Skill入口/私文。Skill原有按需环境重定向合同仍在，执行器环境/路径/漂移检查函数未改。

新增模板轮`test_m405_user_entries + test_opencode_adapter + test_desktop_adapters` **62项、15.379秒通过**，日志`/tmp/msf-resident-short-tests.log`；再加精确4家“marker+公共指针、无额外内容”断言单项0.175秒通过，日志`/tmp/msf-resident-short-final-assert.log`。68与后62是不同源码快照，不拼作单轮全量通过；后续真实安装须使用包含本次新增模板的新固定pin。所有runner均终态，`git diff --check`通过。

交主固定的写集共7文件：install.py、agm_core/upgrade.py、agm_core/user_rules_organize.py、agm_core/user_entries.py；test_install_idempotency_cleanup.py、test_memory_fusion.py、test_m405_user_entries.py。report另保留。取消兼容已外置移除，无commit/push、无Claude/模型调用，无真实产品/私文/CK/Paseo写入。本机仍f3，普通修复落地未完成；待主新固定来源后由原人沿已准备的精确备份/清理/fresh执行，不部署dirty。当前准备脚本时间阈值已过，后续只能在主审核续行窗口内明确更新该执行时限，不能偷偷绕时限运行。

## 新固定 bce 本机最终收口（08:12:46–08:19 UTC）

主审核并固定`bce32565baf0d3bd130d487928e7cecd240e0caa`后授权继续；未push，本执行者未commit/push。外置新0700根`/Users/vincent4j/.mem-sharing-review-backups/final-fixes-20261104T0813Z`保留真正干净detached checkout。其上三关键定向（direct-source真无参noop、Claude短模板安装/重复/卸载预览、single待选/查看零写）3/3、4.294秒通过，日志`/tmp/msf-final-clean-source-tests.log`。

当前四根、六家原生文件、两native Skill、公共两md及V/C/版本库存已新备份逐文件sha/mode和目录mode校验；sources原本absent照实记录。写前再次核本次库存/原生快照，精确产品片段与owned Skill/产品根清理后四根absent，私文不重排、不删文件，权限/inode保留。脚本只将经主审核的清理硬阈值改为08:23:00，于界限前完成；没有伪造旧正式卸载。新旧全部备份和clean源继续保留，交回前又逐项校验保存副本与原映射相符。

正式fresh预览：75项、六家、2 native Skill、channel=fresh；plan_sha256=`7ebd18c45f26c5ce3540bca86777dcd163a6037cc3ce43b675848ba5844afba4`，同operation重预览逐对象全等。批准记录引用用户07:57“赶紧干完，我来验收”及主08:12:46对新固定来源审核续行，未捏造新用户表态。实际执行rc0/completed，六家connected，融合pending_selection、CK skipped；未将安装批准用于内容融合。

真实核验全部通过：

- C49全文件hash匹配，V schema3/complete/0.1.7，source commit为bce、tree=`2d6eac546b20daafa8aa90b98b75f8c31f6328e00049854be2c16eae94958c48`。9受管对象指纹全匹配，所需新backup manifest全部存在。
- DSH/OpenCode受管块精确为marker+公共MEMORY读取指针，无环境技术说明；Claude块精确为已审短句，公共import仍首行。所有六家原生事务before备份等于本次清理后baseline，实际diff只有insert，私文原字节及mode保留；两native Skill持久C指向正确。没有删DSH私有Skill入口。
- 本次备份六条规则原字节一次恢复，sha仍`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`；新MEMORY仅加单链接，公共文件仍只有两md。
- **已装C无任何额外参数**：`python3 -B ~/.local/share/mem-sharing/scripts/install.py`实际rc0，message=`已安装，已接入。`、changes=[]、approval_plan=null、fusion=null。114相关文件sha/mode/mtime_ns/inode前后全等，真实修复旧无参入口缺口；未创建/捏造export receipt。
- 实际`organize-user-rules`输出default=[]、optional=[]、single=[1..6]，待选块完整显示6个稳定编号、逐项忠实原文摘录及“单家内容，默认不共享”，不再“待选暂无+尾部裸编号”；逐项摘录与原始source文本归一空白/截断规则核对一致。无一single被默认选择，无正文写入。退出rc5表示pending_selection，与status=completed/无changes并存，按当前CLI合同如实报告，不能当失败或内容融合完成。
- 实际“查看1”rc0/viewed、changes=[]，组及源编号稳定；真实114文件及完整文件集不变。正式卸载仅预览rc5/approval_required、无errors，预览backup目标未创建，**未执行卸载**。9对象新恢复材料可用。
- Paseo daemon身份/启动时间与8插件列表完全不变；CK/账号/其他Skill/业务项目未动。无Claude/Codex模型调用；依用户边界本轮不做账号或模型验收，不把旧502阻断混入本轮CLI通过结果。

全部实际输出与指纹存新0700根，文件0600：fresh-install-preview.json、fresh-install-approval.json、fresh-install-actual.json、post-install-verification.json、repeat-install-actual.json、repeat-install-verification.json、fusion-prompt-actual.json、fusion-view-actual.json、uninstall-preview-actual.json、final-verification.json、host-backup-verification.json；原文不入repo。清理/读回脚本在`/tmp/msf-final-bce-clean.py`、`/tmp/msf-bce-postverify.py`、`/tmp/msf-bce-final-checks.py`，只为本轮验收，不是产品兼容机制。

收口：本轮授权的三项常规问题与新增常驻精简均已落到当前机器，CLI/文件层可以交用户验收。没有实际批准/执行新的私文融合，没有跑全量或新增原生模型测试；不声称这些层通过。所有执行/验证进程已终态，无待收进程；源码和clean checkout未改，仓库仅本报告untracked，所有保全备份不清理。

## 卸载后导航残留修复（2026-11-04 09:43–09:58 UTC）

用户自行卸载后，观察到四产品根不存在，六家文件各残留一次`## 用户记忆 / - user-rules.md`，规则正文仍在；未发现正式执行receipt，不凭preview宣称完整卸载状态。先前误报“六家与旧preview完整after匹配”已立即纠正：真实JSON仅DSH/ZCode/OpenCode三家匹配，另三家不匹配，原因不推断。用户恢复的six-native备份中，公共index/rules字节hash与当时0456部署快照精确相等；用固定0456 kernel重算旧public_body，导航+完整六规则连续anchor在producer输出与每家当前文件各唯一匹配。范围证明不是同名标题搜索，不扩大其他私文读取。

根因是generic Markdown link展开保留label及原bullet，当前完整受管索引的“用户记忆”导航节也未退役。源码仅识别完整当前producer index前缀+纯规范同名topic导航，内联各正文、去该导航；任意用户同名标题、说明、自定义label不适用此分类，重复生成导航拒绝。Markdown fence及CK原字节保护，fence中的例子不按导航/import执行；绝对产品路径仍保留既有依赖拒绝。6初始合成全过，新增完整正式卸载/归还/恢复后，最终21项49.038秒通过（/tmp/msf-uninstall-nav-focused.log），未跑全量。

首轮诊断42项32 errors日志保留（/tmp/msf-uninstall-nav-regression.log）：既有native-return fixture假设新装自动存在topics，文件写入先于产品逻辑即失败；另一次误指定不存在的test_uninstall_recovery模块。仅补fixture创建其自用topics目录，不改产品生成逻辑、不删保护断言，正确恢复验证由原native-return恢复用例及新增端到端用例执行。

精确本机候选/tmp/msf-uninstall-navigation-cleanup-plan.json经主005607f2审核，0700完整备份位于`~/.mem-sharing-review-backups/uninstall-navigation-cleanup-20261104T0954Z`。六wholefile副本逐sha/mode验证后，写前重核prehash/mode/inode和唯一span；每家仅去33bytes，fsync读回posthash等计划，其他字节/权限/inode不变，规则sha保留`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`。映射、批准计划、每项before/after与状态在backup/cleanup-manifest.json、approved-plan.json（0600）。当前六文件小修已完成，不是重新卸载/重装，也不是正式执行receipt恢复。

本轮源码写集为uninstall_memory.py、test_uninstall_navigation.py及原native-memory测试fixture一行；本报告追加。无commit/push、模型/GUI、CK或其他文件修改。所有runner已终态；源修复未提交/发行，本机只做已审窄清理。
