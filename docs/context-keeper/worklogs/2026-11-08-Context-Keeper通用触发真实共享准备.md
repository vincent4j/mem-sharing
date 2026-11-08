<!-- context-keeper: session-id=01a1b6c2-5160-7ab2-b367-e681477433b2 -->
# Context-Keeper通用触发真实共享准备

## 用户纠正与核实

- 用户截图指出DSH原生AGENTS.md仍留完整Context Keeper触发正文，并质疑此前‘解决’。当前公共user-rules.md确无该正文。历史记录/源码证据只证明通用正文共享能力与隔离验证，未证明真实迁移；此前1.11升级明确无公共记忆迁移。主Agent承认本机落地与源码完成口径混淆，并继续准备真实共享，未修改上游CK。
- 用户随后质疑项目检查页路径，后明确理解为当前项目记忆检查。核实index.client.tsx传workspace.directory，仓库root正是/Users/vincent4j/Tools/Source/mem-sharing，无开发路径硬编码。只读check-memory真实gaps为project_unregistered及Claude项目CLAUDE.md缺@AGENTS.md引用，无写入。不自动启用项目；gaps绿色勾误报已在client/flow.tsx修为非成功并给中文提示，typecheck及reload通过。

## 新反例与最小源码修复

- 六家均有精确729字节CK通用正文，SHA e58e12c8…；五家候选识别通过，WorkBuddy recognize通过却candidate为false。其mem-sharing块与CK块直接相邻，_protected_spans用start<=end合并半开区间，产生0..1340大保护范围，误判为嵌套。未通过插空行或移动真实正文绕过保护。
- 仅把memory_share._protected_spans合并条件由<=改<，保留真正重叠/嵌套合并，独立相邻协议保留边界。新增六家相邻规则块/引用、真实嵌套私有块仍拒绝的回归用例。CK相关19项通过，普通memory_share16项通过，插件typecheck通过，diff --check通过。未部署或覆盖已装0.1.11核心、未commit/push，源码与真实执行仍分层。

## 真实HOME零写共享预览

- 使用已审当前源码CLI生成organize-user-memory六家预览，sandbox-exec拒绝HOME所有写入，-B/DEVNULL。退出5/approval_required，errors=[]；六原生文件+公共索引/正文/registry前后hash/mode/mtime一致。证据根 /var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-ck-preview-tqle26e4。
- approval-plan.json SHA4daa9181dabe9e81beeddb9cb917388fe95edb0c79c791eb0727a0b5bab0b6ed，默认及selected_numbers均仅[1]，第1项完整CK通用正文含六真实来源，7个其余单家候选均不选。完整prompt.md与原始preview.stdout/stderr、command.json、zero-write.json、scope-check.json、source-fingerprints.json均保留。
- 精确计划：public user-rules.md保全1854既有字节为前缀，增加783字节（标题/分隔+完整729B正文），该正文由0份变1份；六家各精确删除729字节，after完全等于before删该body的拼接，其余标题/marker/空白/入口字节完全不变。MEMORY.md无需改动。仅Claude现有import机器对象整文件指纹做验证后的registry rebind；六source迁移元数据保全以供归还，非正文迁移。
- 实际迁移尚未执行、无真实共享事务备份生成。下一步展示稳定编号方案，用户明确共享1/按默认方案后，用同一源码工具、--selection-plan-file及实际选择reference执行，先核对工具指纹、场景/基线锁内复验。真实HOME与已安装核心不因源码回归通过而冒称已完成。源码边界修复后续发行单独处理。

## 追加记录 2026-11-08T01:30:05+08:00

- 用户明确选择“共享 1”，按绑定计划执行真实迁移。首轮生成章节误继承Claude专属标题，不能以命令成功冒称归属正确；使用正式归还事务恢复六家原文件，再通过标准事务仅清除新增54字节错误标题。修正生成器：公共CK章节使用通用标题，来源context与归还证据保留原值。随后在同一选择授权范围重新共享，未迁移其他候选。四个事务均保留备份，详见final-acceptance.json的correction_history。
- 最终公共user-rules.md在“Context Keeper 通用触发”下仅有一份729字节完整正文，原1854字节用户规则保留为精确前缀。六家原生文件分别只移除对应729字节，其余字节、标题、协议壳与入口不变；Claude import指纹按真实结果更新。当前6条有效来源记录，旧6条已由正式归还消费，六家connected。
- 最终事务 /Users/vincent4j/.mem-sharing/backups/20261107T172513Z-13383cda260d4bcab9a57fd4afe0bfe0/manifest.json committed；mandatory reader、shared_span生产者证明与终态恢复证据通过。最后只读归还预览可逐字节恢复六家原文件，没有实际执行该最终归还。首轮纠错归还已真实执行，二者明确区分。
- 新增私有来源标题反例验证公共通用标题及真实来源context保留；修正后CK19项通过（16.969s）。此前普通memory_share16项通过。证据根 /var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-ck-preview-tqle26e4，核心验收final-acceptance.json、最终归还预览final-return-preview.json。没有修改已安装0.1.11核心或上游CK，未commit/push。源码修复尚未正式发行，六家新会话模型实际读取仍待验。

## 追加记录 2026-11-08T12:14:35+08:00

- 用户“继续”后仅推进当前收尾。未命中独立生效合同；按installation.md原生文件/模型读取分层验收。在中性临时目录启动原生新CLI会话，不向prompt提供公共路径或正文。Claude Code只用Read读取user-rules.md，索引由原生import注入，正确复述触发条件与无项目边界；exit0，14.39s。Codex首次嵌套sandbox_apply失败，不计通过；保留失败后以外层sandbox保护产品目录、取消重复内层沙箱再验，实际cat读取MEMORY.md和user-rules.md，正确复述，exit0，39.56s，第二轮前后被检查的保护文件零变更。两者属于有引导的新CLI读取，不冒称自动触发或桌面通过。
- OpenCode真实新CLI已完成公共索引、user-rules.md读取并加载CK Skill，但120s内无最终回答而超时；保留partial，不重试。WorkBuddy/DSH/ZCode保持本轮桌面待验，未人工改写runtime_acceptance。
- 外层sandbox拒绝项目、公共记忆、持久核心、上游CK和六家原生入口写入。14564个原有文件最终比对，现有产品文件hash/mode/mtime未变；memory-keeper.md由主Agent修链；两个Git FETCH_HEAD元数据另有并发变化，来源未归因，不能称全树零写。首次验收脚本预期仅索引变化的断言因此失败，已如实区分产品文件和Git元数据，不触发产品重试。证据 /var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-native-read-xz9qelqa，acceptance-summary.json保留原始输出/退出码定位与边界。
- 当前索引8个已删除历史目标均先验证4fb22c09内Git对象存在，再改为固定版本URL；旧历史日志不覆盖。save-report结构与链接检查通过；35KB索引有30KB压缩提示，未自动压缩。进度CLI因progress插件缺zod无法运行，未扩修其他插件。
- 当前7个源码/测试/UI文件已导出delivery.patch（含未跟踪ui.tsx）与SHA清单，加载UI三文件均匹配工作区。复用此前CK19/普通共享16/插件67及增量类型与定向验证证据，本轮未改源码、未重复整批。未改版本/payload、未生成正式候选、未commit/push/publish。

## 追加记录 2026-11-08T12:29:24+08:00

- 用户上传DSH原生会话session-9c049c65-0357-420f-b154-635c9630ec10的zip，主Agent只读解析session.v4.jsonl。原生用户规则实际注入，read结果行47/48/53分别成功取得DSH入口、公共索引和user-rules正文，最终turn completed，触发与无项目边界回答正确。该引导读取项通过；其23步/35工具的跨宿主与历史探查超出本次必要范围。空CK块为共享后保留壳，不能以独立安装器current=False推断迁移损坏，也不补回重复正文。未凭导出会话自述宣称全机字节零写。
- 用户明确“验收一个就可以了”，本轮验收以DSH收口；随后又单独要求补验WorkBuddy。通过CUA原生WorkBuddy新建任务，使用默认设置与既有模型，发送不含公共文件路径的有界只读提示；禁止跨宿主/历史扫描及安装/补桥/保存。未切工作空间或修改权限。
- WorkBuddy原生界面可见读取过程“查看文件：MEMORY.md”及对公共user-rules.md的grep。最终界面显示已完成1m3s，正确列出三类CK触发、先读Skill/读取失败停止、无项目不自动记录/查状态/询问建库、cwd不等于项目；实际来源列出.workbuddy/MEMORY.md → .mem-sharing/memories/MEMORY.md → user-rules.md。只沿当前入口读取，未误判空原生桥壳为损坏。本项为新原生UI中有引导的规则读取验收通过，不冒称无提示自动触发、项目保存或全机零写。未运行任何本机安装/补桥/迁移命令、未改运行台账runtime_acceptance；仅追加项目结果记录。
- 依据用户收窄范围，本轮新会话验收关闭，不再把ZCode/OpenCode进一步验收作为本轮阻塞项；源码提交与正式发行仍待各自明确授权，未commit/push。

## 追加记录 2026-11-08T14:37:20+08:00

- 巴克收尾审核发现P2：通用公共标题生成后，uninstall_memory仍按旧原生context回放，生成空标题被当正文带回。用户明确要求修复。只修改uninstall_memory.py、test_generated_wrapper_retirement.py，并扩充既有test_ck_common_trigger_chain.py的断言；UI及其余源码不动。未命中独立生效合同，受影响PRD为uninstall-recovery.md生成包装完整producer证明、无新增空标题、用户同名标题保护及原生归还次数，源码/隔离范围均通过。
- 先复现单次CK/普通与CK混合新标题反例，再加入每个append producer的新旧渲染回放；审定kind/hash、真实source context、完整before/after、offset与absent祖先证据不变。首轮29项实际1失败（129.773s），暴露多轮CK替代把最早公共创建producer过滤。保留失败日志，新增wrapper_producers只补公共包装证明所需历史，原生归还与排序仍仅活跃来源，不重复归还。
- 新增最初literal逐字节断言还发现既有退出leading LF；未顺手修改产品布局。测试改为在共享前获取同安装只读退出after作独立baseline，之后多轮共享/替代/正式卸载需六家逐字节匹配该baseline，另保留通用空标题不存在、正文1份和CK完整块断言；standalone recover仍全树精确。不能声称修复既有LF或安装前literal完全一致。单链最终1test OK、40.574s（实际工具session26743回执记录，不伪称原始stderr）。
- 最终同一冻结3文件29项定向回归全部通过、零跳过，实际exit0、153.626s；测试前后SHA相同且与巴克最终复核三SHA逐一匹配。覆盖CK2模块、generated wrapper、普通fusion uninstall。纯原函数AST重放before2失败/after0失败，audit写尝试0。没有重跑插件67或扩大客户端验收。
- 巴克原审核、首次delta失败、最终delta代码认可三报告均保留；最终放行条件为同指纹定向测试通过，现已满足，P2关闭、本轮源码修复可交付。正式发行仍未完成，未commit/push/tag/生成payload/改版本/真实HOME卸载或回滚/上游CK。证据根 /var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-ck-wrapper-fix-212dbkvn；final-summary.json、final-tests-command.json、final-tests.stdout/stderr/result/exit、final-tested-files.json、final-probe.stdout、buck-final-delta-review.md、delivery.patch与9文件SHA清单。

## 追加记录 2026-11-08T14:43:01+08:00

- 用户明确调用“$context-keeper 推送”，授权主Agent保存、提交并推送当前已审核成果。已fetch origin/main，无远端新增，main领先两个本轮授权0.1.11 S/R提交；本次将同本轮最终源码增量一起推送，不生成新版本/tag/payload，不改真实安装。
- 9个已审核源码/测试/客户端文件与冻结delivery SHA全部一致，复用最终29项与UI既有检查，不重跑。补充脱敏长期验收摘要docs/plugin-adapters/source-closeout-2026-11-08.md，列出实现、原失败与修复、29项结果、审核SHA及真实验收/正式发行边界；不纳入原生会话包、用户记忆全文、临时日志或安装备份。PRD check initialized/errors0/warnings0，两inbox空，相关PRD/入口无需改写。实际commit与远端身份以本轮Git回执为准。
