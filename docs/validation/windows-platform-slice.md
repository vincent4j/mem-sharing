# Windows 平台安全切片验收记录

日期：2026-11-08。依据：[已批准 Windows PRD](../prd/windows-support.md)。本记录区分实现、合成测试和真实宿主证据，不是 Windows 发布声明。

## 当前收口判定（2026-11-09）

主 Agent 已独立验收当前冻结来源、任务计划和持久脱敏证据索引；这允许只读阶段按实际范围部分验收提交，不使 W01/W02 或 Windows 生产支持变为完成。诊断切片 6+1 exit 0；原生 r1 为 10/14、r2 为 **13/14、exit 1**。名称重查仅检出可观察漂移；元数据 share=0 排他假设被证伪，不能称旧基线或产品 bug。ACL 目前仅只读快照，实际安全写入/恢复/并发/崩溃事务尚未完成，隔离仍 partial。

后续入口：[剩余任务与独立工作区交接](../context-keeper/plans/2026-11-09-Windows剩余任务与独立工作区交接.md)、[持久脱敏证据索引](windows-evidence-summary.json)。JSON 留存 21 份既有原件的具体路径、SHA256、结论和三源码冻结指纹，不复制 SID/DACL 正文、凭据或配对链接。本次只读本地旧证据，不代表重新运行测试或刷新 Windows 当前环境。提交推送和新区创建仍待主 Agent 实际执行后另记。

以下按当时阶段保留历史判断、失败及限制；其中“未接入/仍运行/未开始”等当时描述不覆盖本节当前判定，旧失败不删改。

## 历史记录 A：最初诊断切片的范围与状态

- W00：完成本地接口和来源清单语义核实，消费章教授官方资料首批；固定客户端版本、Windows 现场事实仍待验，任务整体未关闭。
- W01：新增 `agm_core/platform_diagnostics.py`：纯 Windows 路径语法检查、lstat 节点分类、六家显式未准入诊断。语法合法不代表路径安全、节点身份或写入批准；分类不检查祖先链，不作为写入 guard。
- 诊断入口：`python3 -B scripts/agm.py diagnose-platform --json`。可重复传 `--windows-path`，仅检查字符串，不打开目标。不读用户配置/正文、不创建缓存/锁/目录、不执行 Git、不下载。输出系统、解释器版本、架构与 Git PATH 存在性；Git 可执行性/版本未核验。路径结果只输出序号和原因码，不回显路径或用户根。无语法问题退出 0，有问题退出 1；0 仅表示诊断完成。
- W08：准备 Mac/Windows、Python 3.9/3.13 安全切片 CI，仅跑本切片测试；未运行远端 CI，不代表全生命周期整合通过。
- CI 的 `windows-latest` 是托管 runner 标签，与目标 Windows 11 真机环境不同；即使将来 CI 通过，也不能替代 Windows 11 本机 NTFS、ACL、原生客户端及新会话验收。执行时必须另记 runner 实际系统信息，不凭标签推定具体 SKU/build。
- W02–W07、W09/W10：未实现/未验。保留 `user_install.plan_install` 和 `upgrade._plan` 的 darwin 限制；`agents.json` 无 Windows 生产配置。插件 payload、版本和发布身份未修改。
- Windows 目标存在，家中测试机需安装 app，连接详情以后提供，本轮不接入、不催问。真实 NTFS、ACL、节点身份、外置恢复、六家固定版本及新会话验证全部 pending。

## W00 本地事实

核验源码：`paths.select_platform/load_agents_table`、`transaction.read_snapshot/write_lock/Transaction.run`、`user_install.plan_install/_source`、`upgrade._plan`。路径表只有 darwin；Windows/Cygwin 名称映射不代表受支持。事务已有 mkdir 排他、同目录替换、备份和台账最后提交；这些不证明 Windows ACL/占用/断电语义。

`user_install._source` 当前 `tree_sha256` 是排序逐文件清单 `{path, sha256, mode}` 经 `legacy.encoded` 后的 SHA256，文件 SHA256 来自实际工作树字节；它不是 Git tree 对象 ID。当前还检查源码 HEAD 与受管文件 dirty 状态。这一格式本轮不改，Git for Windows 的 autocrlf/filter/模式差异与对象 blob 基准的兼容方案仍阻断生产来源准入。

## 官方资料与边界

由章教授于 2026-11-08 静态核查，原始摘要 `/tmp/memsharing-windows-official-20261108.md`。以下为该次资料来源，不代表本轮在 Windows 调用了这些 API：

- [Reparse points](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-operations)：检查 `FILE_ATTRIBUTE_REPARSE_POINT`；真正防跟随和竞态还需 handle-aware 检查。本切片只保守分类，未调用 Win32 写入接口。
- [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)：卷序列号和文件 ID 共同提供身份线索；当前未实现生产身份绑定。
- [ReplaceFile](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilea) 和 [文件安全](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)：DACL、继承、同卷和失败状态需单独验证；不能据此宣称 Python `os.replace` 满足恢复合同，未实施未经证实 ACL 接口。
- [Python pathlib](https://docs.python.org/3.14/library/pathlib.html)：`is_junction()` 自 3.12 新增；本实现保留 Python 3.9，不依赖该方法。[stat 属性](https://docs.python.org/3/library/stat.html#stat.FILE_ATTRIBUTE_REPARSE_POINT)用于保守识别；缺少 Windows 属性的 Mac 合成结果不替代 Windows 实测。
- [Git attributes](https://git-scm.com/docs/gitattributes)、[Git 对象](https://git-scm.com/docs/gitdatamodel)、[cat-file](https://git-scm.com/docs/git-cat-file)：工作树可能发生 CRLF/filter 转换；blob 原始内容可以作为未来设计依据，尚未改变发布清单协议。
- Codex 当前来源补核：[Windows](https://developers.openai.com/codex/windows)、[AGENTS.md](https://developers.openai.com/codex/guides/agents-md)、[Skills](https://developers.openai.com/codex/skills)。当前官方文档明确 Windows 及规则/Skills 能力，替代首批 cookbook/API CLI 线索作为依据；仍未取得目标固定版本、本机配置根与新会话实证，不准入。
- Claude 当前来源补核：[Setup](https://code.claude.com/docs/en/setup)、[Memory](https://code.claude.com/docs/en/memory)、[Skills](https://code.claude.com/docs/en/skills)。当前官方文档明确原生 Windows 安装与记忆/Skills 入口，替代旧 WSL/Git Bash 观察；优先级、导入、固定版本与实际加载仍待验，不准入。
- 其他线索：[OpenCode instructions](https://opencode.ai/docs/instructions/)、[OpenCode skills](https://docs.opencode.ai/docs/skills/)。这些 live 文档未固定目标版本。WorkBuddy、DSH、ZCode 的固定 Windows 发行/入口仍有缺口；六家均不准入，不凭文档路径配置生产 Agent。

## 验证证据

本机 Mac（Python 3.14.3）执行；仅合成数据，非真实用户记忆。2026-11-08 07:44 UTC 交主审时：定向 6 unit + 1 integration 通过；全量 unit/integration 已启动、仍运行，日志已有额外 E/F 标记，尚无完整 traceback/最终计数，不能仅用已定位版本断言概括所有失败。unit PID 64575（会话 77727）、integration PID 66618（会话 20489）与日志交主 Agent 继续收取终态；本切片不标全绿。

- 定向单元：`python3 -B -m unittest discover -s tests/unit -p test_platform_diagnostics.py`。
- 定向集成：`python3 -B -m unittest discover -s tests/integration -p test_platform_diagnostics_cli.py`。冷拷贝代码、显式合成用户根与最小环境，运行诊断前后核对整个测试根目录和文件 bytes，验证无缓存/输出文件产生，正文不进输出。
- 全量：`python3 -B -m unittest discover -s tests/unit`；`python3 -B -m unittest discover -s tests/integration`。日志：`/tmp/memsharing-windows-unit-20261108.log`、`/tmp/memsharing-windows-integration-20261108.log`。
- 首次集成全量发现同名 unit/integration 模块导入冲突；已将集成文件改为 `test_platform_diagnostics_cli.py`，未弱化保护。
- 全量 unit 首个 FAIL 已定点复现：`test_acceptance_fixes.AcceptanceFixes.test_core_version_fresh_checkout_without_version_and_conflict` 预期 `0.1.7`，实际 `0.1.11`；HEAD 中该断言相同，测试及版本文件本轮未改，保留失败。证据 `/tmp/memsharing-windows-unit-first-failure-20261108.log`。未为了通过而调整版本/发布身份或削弱断言。
- 集成零写快照最终覆盖测试根、目录、文件的 mode、mtime_ns、inode 与 bytes；最终定向复验 7 项通过。PRD Distill `check`：initialized，errors/warnings 均为空；`git diff --check` 通过。
- 本轮 CK `save-report` 通过；仓库总 `coverage` 仍报告未索引/断链等问题（`worklogs_unindexed=4`、`broken_links=43`），未扩大为本轮历史记录修复。
- 巴克转达的独立只读审查：无 P1/P2；CI runner 与 Windows 11 真机差异提示已补，最终结果仍待全量终态。未扩大路径字符禁集。
- 主审补充修正：移除真实“文件下子路径”固定判为 unreadable 的跨平台假设，改用明确 mock `NotADirectoryError`；保留 `PermissionError` 精确断言。生产分类语义未改；修后只重跑定向 6+1，通过，不重跑全量。

## 历史记录 B：第二段结果与失败分类（截止 08:01 UTC）

主 Agent 按阶段审核机制批准原执行者第二段，仅收取结果与必要分类，不新增功能、不重跑已充分验证的切片，不改旧版本断言；这不是用户新增明确授权。该第二段已结束，测试已停止，不再后台运行。

集成全量终态：**66 项，1 FAIL，退出 1，465.569 秒**。唯一失败 `test_m408_installer_cli.InstallerCLITests.test_context_keeper_route_is_independent_and_uses_synthetic_pinned_source`：预期 CK `skipped`，实际 `pending_selection`。固定 HEAD `9f4a0ba433085cab23016382c62b5bdec671276c` 的隔离导出在同一合成 HOME 下定点复现相同断言（1 项，4.034 秒），见 `/tmp/memsharing-windows-baseline-ck-route-20261108.log`。这是本轮前存在的失败，未修改 CK 行为或断言。

单元全量 **未完成并已停止**：discovery 总数 1063；07:59:44 UTC 停止前有 565 个完成标记，含 4 FAIL/9 ERROR，剩余 498 项未完成。向本人进程组 64574 发 SIGINT 后退出码 130，07:59:53 核对该组无残留。中断候选为 `test_m407_upgrade.UpgradeTests.test_repeated_successful_operation_is_readonly_noop`，不是挂起结论。停止证据 `/tmp/memsharing-windows-unit-stop-20261108.json` 及原单元日志；前文 07:44 的“仍运行/交接 PID”是历史状态，已由本段替代。已观察失败逐项分类如下，不概括为版本断言，也不宣称完整单元通过：

| 测试/数量 | 实际原因 | 基线证据 |
|---|---|---|
| `test_acceptance_fixes` 版本用例，1 FAIL | 旧断言要求 0.1.7，当前值 0.1.11 | 隔离 HEAD 定点同失败；`baseline-version` 日志 |
| `test_cli.InstallationHintTests.test_allowed_user_paths_single_agent`，1 FAIL | 实际允许名单含 WorkBuddy 原生 Skill 路径，断言只有记忆文件 | 当前区与 Git HEAD clone 同断言失败 |
| `test_explicit_public_reuse.ExplicitReuseTests`，4 ERROR | 历史 ed3 源码不能携带统一入口布局，`entry_layout_code_incompatible` | 当前区与 Git HEAD clone 同异常 |
| `test_fusion_claude_import` 的 projection/prompt 两用例，2 FAIL | 提示文案断言仍要求“记忆条目 1”“默认共享” | 当前区与 Git HEAD clone 同断言失败 |
| 同模块 terminal history 用例，1 ERROR | `No terminal transaction matches this exact fusion approval` | 当前区与 Git HEAD clone 同异常 |
| `test_legacy_fusion_exit.HistoricalExitTests`，4 ERROR | 历史固定来源预检被 `entry_layout_code_incompatible` 拒绝 | 当前区与 Git HEAD clone 同异常 |

除版本用例外，上表 12 项在当前区定点运行 28.380 秒、Git HEAD clone 运行 20.049 秒，均为 3 FAIL/9 ERROR，逐项结果与最终异常签名 **12/12 相同**。日志：`/tmp/memsharing-windows-current-extra-20261108.log`、`/tmp/memsharing-windows-baseline-git-extra-20261108.log`；结构化比较：`/tmp/memsharing-windows-baseline-comparison-20261108.json`。

隔离基线：本地 `git clone --shared --no-checkout` 后在 `/tmp/memsharing-windows-head-git-20261108` detached checkout 固定 HEAD；只使用合成 HOME，无网络 clone、commit、真实 HOME 修改。最初的无 `.git` archive 对依赖历史 Git 对象的 8 项产生“非 Git 仓库”错误，该批不作为这 8 项的基线证据；改用完整对象可读 clone 后才确认上述对应异常。原始无效基线日志也保留，未伪装为成功复现。

这只证明已分类失败在本轮前存在，不代表接受这些产品行为或豁免全量回归。尚未结束的用例和后续新增失败保持未验证，真实 Windows 仍 pending。

## 连接后独立测试路径（尚未执行）

先只读核验系统/build、普通测试账号、Python/Git 实际版本、独立源目录。由用户提供连接信息后再安排；不操作日常账号、记忆、daemon 或凭据，不自动安装客户端。

在已核验源码目录的 PowerShell 执行以下只读/合成入口；解释器名称需以现场核验为准：

```powershell
python -B scripts/agm.py diagnose-platform --json
python -B scripts/agm.py diagnose-platform --windows-path 'C:\Users\合成 测试\AGENTS.md' --json
python -B -m unittest discover -s tests/unit -p test_platform_diagnostics.py
python -B -m unittest discover -s tests/integration -p test_platform_diagnostics_cli.py
```

集成测试内部通过 `TemporaryDirectory(prefix='memsharing-platform-')` 创建独立根，下面仅有 `source/scripts` 与 `synthetic-home/synthetic-memory.txt`。子进程 HOME/USERPROFILE 只指该根；数据固定合成 UTF-8 BOM/CRLF。这只允许诊断与合成检查，不启动安装器，不因通过而开放生产写入。真实 NTFS/ACL/占用/恢复需后续专门实现和独立验收。


## 历史记录 C：真实 Windows 安全切片执行准备（2026-11-08）

用户明确要求准备独立测试目录、同步源码并运行 Windows 诊断与合成测试；这是一项新的真实 Windows 测试授权，不延长上轮被中断的全量回归。仅运行本切片 6 unit + 1 integration，不安装 memSharing/CK，不开放生产。

Paseo fleet 当前登记 `srv_GZ0PNW-HemHR`（4J-DELL-WIN），固定目标独立根 `D:\project\memsharing-windows-test\slice-20261108T133125Z`。原 e9e 执行者已 closed，恢复消息未执行；经主审允许单次替代，使用同真实 Profile zcode/GLM-5.3、yolo/high 的 Agent `245c329e-8546-4813-a2a0-f0655e732580`，同 workspace 串行执行，不触其他 WorkBuddy 任务。

Mac 源快照：40 个文件已与固定 HEAD 的 Git blob 原始 bytes 独立比对一致，另 4 个为精确未提交 overlay。44 文件 manifest SHA256 为 `4d1fdd818d08132ee3380ae954f5aee553e39c53c1c5908548ceecbc98d7a024`，不冒充 release/新 commit。传输暂存及本地证据 `/tmp/memsharing-win-transfer-20261108T133125Z/`，含 manifest.json、snapshot.json、source-verification.json、bundle.b64 和 transport-summary.json。远端必须按三层载荷 hash 与44文件 hash 全部验证后才允许测试。

截至 13:44 UTC，远端报告根已创建且在落盘四段载荷，但尚未收到完整根安全原始证据、44文件 hash 对照或7项测试结果。此阶段仅为准备进行中；Windows原生测试仍 pending，Mac校验不替代远端执行。主Agent此前核验的Win11Home build26200.7840、Python3.14.10 x64、Git2.56.0.windows.4和NTFS事实，需要在本测试证据中绑定；本记录不把传入环境信息当本轮已执行证明。


### 本轮真实 Windows 结果（13:59 UTC 收口）

官方程序化传输已闭合：采用本机同版 `@getpaseo/client` 的 `connectToDaemon` 正常本地认证，经 `openHostRoute/createHostChannelTransport` 到已登记 Windows host，仅在授权 evidence 下创建 `bundle.machine.b64`，以 `fs.file.write` 写原始 bytes，再 `readFile` 读回。33960 bytes 逐字节相同，SHA256 `f6022e6a13bf54297b23071b4432d7f6cda4095a3facbde1078b2646b67db904`。没有开监听、导出认证或写 Paseo 附件目录。错误手抄包保留，未经校验未执行。

| 维度 | 结果与证据边界 |
|---|---|
| 原生机器与根 | 原执行者原生命令回报 Win11 build26200.7840、C/D本地NTFS、祖先链普通目录无reparse；主Agent已有前置核验。本轮回收的三个诊断原始JSON均为 native_platform=win32、Python3.14.10。根为上述slice目录；不是VM/mock运行。Mac回收证据未包含单独preflight原始文件，不把reparse/ACL门宣称完整关闭。 |
| 固定源码 | 远端已对已有fetch checkout固定9f4a0ba并机器应用4 overlay，保留dirty形态。`verify44.json`的44个path/size/SHA256逐项与Mac manifest核对一致；Mac另经官方readFile独立读回四重点源码，hash全部匹配。没有伪造新commit/release。 |
| 单元 | `run_unit6.json`：6 tests，exit 0，unittest报告0.116s。 |
| 集成 | `run_integration1.json`：1 test，exit 0，unittest报告2.142s；冷拷贝与合成目录零写快照通过。 |
| 三组诊断 | 正常/中文空格/设备名分别exit 0/0/1；原始stdout的 `windows.production_write_enabled=false`、6家全部not_admitted，changes=[]；合法路径syntax_issue=null，设备名为reserved_device_name。 |
| 进程环境 | 已机器拉回并审计apply_and_test.py：HOME/USERPROFILE=根synthetic-home、TEMP/TMP=根tmp；仅子进程环境，-B及禁用字节码。未setx/重启daemon。精简PATH不含Git，诊断git_on_path=false是该环境事实，不能当Git未安装。 |
| 限定入口与代码快照 | ZCode/WorkBuddy四个被检查的规则/Skill文件实际全部不存在，before/after逐字节相同，仅证明未新建这些入口，不能称保全了已有正文。代码树快照前后逐字节同（SHA256 76faec633d91f78a0652fe83ee8c3699689b169e5e0ad60ef4645df9689561d8）。未扩大HOME扫描。 |
| 测试子进程 | 五份run记录均有结束时间和退出码，helper使用同步subprocess.run；执行者终报tasklist无python/git子进程、已停止。后续补查turn在调用API前报EADDRINUSE，未启动新测试。 |
| 写入隔离 | **部分通过/待处置**：测试子进程环境在独立根，但执行者申报Git Bash `/tmp/joined.b64`（33959B坏拼接副本）曾落范围外。补核其Windows绝对路径/metadata/hash时ZCode报 `EADDRINUSE Cannot connect to API`，未取得定位结果；没有重试/换Agent/删除。保留坏材料，不能写“所有写入仅独立根”或“零范围外写入”。Mac `/tmp/memsharing-win-transfer-20261108T133125Z` 则属于本轮明确授权暂存，两者不混同。 |

本轮证据原件位于 Windows slice根/evidence；Mac机器回收副本在 `/tmp/memsharing-win-transfer-20261108T133125Z/remote-evidence/`。`sdk-transfer-result.json`保存传输回执，`sdk-pull-result.json`保存证据hash及四重点源码独立readback结果，`reviewed-results.json`保存本执行者基于原始JSON的审核结果。重点原件：verify44.json、overlay_write.json、run_unit6.json、run_integration1.json、run_diag_{normal,cn_space,device}.json、home_snapshot_{before,after}.json、code_snapshot_{before,after}.json、apply_and_test.py。

证据投影限制：远端 `run_summary.json` 错从顶层读取production_write_enabled/agents，产生null/{}；审核改读三份原始run_diag的 `windows.*` 验证通过，不改源码、不重跑测试、不把错误摘要当真实诊断结果。四个源码SHA256与所有回收证据完整hash见本次sdk-pull-result.json。

本轮仅关闭“指定快照在此Windows上运行诊断与7项合成检查”的窄验收；ACL、节点身份、外置恢复、完整生命周期、六家客户端新会话仍未验。W00/W01/W08整体不done，生产Windows不准入；未commit/push/release，未安装memSharing/CK，未改版本/payload/上游CK。


## 历史记录 D：Win32只读底座续段（本地日期2026-11-09，UTC 2026-11-08 16:46前收口）

本轮唯一源码写入者新增 `scripts/agm_core/windows_native.py`、`tests/unit/test_windows_native.py`、`tests/integration/windows_native_probe.py`。标准库ctypes模块可在Mac导入，非win32调用明确拒绝。只读功能包括CreateFileW句柄、FILE_ID_INFO卷/128bit文件身份、全部祖先及叶节点reparse拒绝、GetFinalPathNameByHandleW规范名核对、固定盘与句柄NTFS查询、可选OWNER/GROUP/DACL安全描述符字节快照。描述符在复制后LocalFree，句柄异常路径finally释放；没有ACL写回、安装或写入批准。

API依据为章教授只读核实的 `/tmp/memsharing-win32-api-20261108.md`：Microsoft [CreateFileW](https://learn.microsoft.com/en-us/windows/desktop/api/fileapi/nf-fileapi-createfilew)、[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)、[FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)、[GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)、[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)。DWORD/BOOL固定32位，FILE_ID_INFO 24B、属性tag结构8B。class23本轮未得官方/SDK证据，已移除，结果明确case_sensitivity_checked=false，不能默认准入大小写敏感目录。

真实Windows独立根 `D:\project\memsharing-windows-test\native-20261108T161600Z`；原始证据在其evidence，Mac机器拉回位于 `/tmp/memsharing-native-20261108T161600Z/`。bootstrap.json记录win32/Python3.14.10 x64及D盘到新根父链无reparse。47文件候选为原固定HEAD+既有overlay+本轮3源码，非新release。source-manifest-r2.json与final-snapshot.json绑定最终候选；官方SDK逐文件读回47/47 SHA/size匹配。生产darwin保护、agents表、payload与版本身份均未修改。

| 证据层 | 实际结果 |
|---|---|
| Mac可移植 | unittest `test_windows_native.py` 5/5通过，非Windows拒绝、ABI、路径及身份对照；定点修复后仍5/5。 |
| Windows可移植 | 同套5项exit0，其中非Windows拒绝用例按平台skip1，即4过1跳过。 |
| Windows原生首轮 | native-result.json/run-result.json：14项10过4失败，exit1。真实os.replace在READ_ATTRIBUTES句柄持有期间仍成功；其后3项因同一fixture文件移走连带失败。保留原始反例，不改称旧基线。 |
| r2原始反例复验 | native-result-r2.json/run-result-r2.json：14项13过1失败，exit1。rename_allowed=true且named_recheck_detected=true；退出前重开名称+对照volume/fileID明确抛node_drift，fixture finally恢复。替换后新节点ID、172B只读权限快照重复一致、硬链接/大小写别名身份、中文NTFS、junction叶及祖先拒绝均通过。 |
| r2剩余失败 | `sharing_conflict_fails_closed`的“exclusive READ_ATTRIBUTES/share0必拒绝第二元数据打开”假设被实际证伪。不是旧基线或Windows产品bug，不更改断言凑绿，未承诺元数据句柄排他。 |
| 独立只读审查 | 单一突突兔837924f5审前后3冻结hash一致，无P1/P2；P3为junction异常cleanup完备性、硬链接多名称边界应明示、LocalFree返回值未观测。未跑重复测试，P3保留未修。 |
| 个人入口 | final-snapshot.json经只读metadata API核对ZCode/WorkBuddy4限定入口均missing，与前次观察同；未读正文、不称已有正文保全。 |
| 终态/传输限制 | 第一次SDK超时后有界重连成功，r2两源码写入读回匹配；长-c创建terminal worker超时。随后未观察到terminal/结果，不能绝对证明该请求从未执行。简化文件启动返回唯一terminal d67a8385-b963-4ea5-8934-ef298a0538b1并得到r2结果。两次尝试未做到fixture/结果前缀完全分离，迟到请求归属风险保留，不能用空列表排除；不再重复启动。最终本任务cwd listTerminals=[]，各有结果的同步子进程已终态，未观察到测试terminal。 |
| SDK取证清理 | 47/47、入口metadata、terminal状态已写final-snapshot.json后，关闭SDK时未处理的`Daemon client closed`使本机取证脚本exit1；快照原件保留，不能把该整条命令写exit0。其他本人SDK脚本均有终态，未新增后台daemon。 |

修复只是可观察漂移检测：READ_ATTRIBUTES句柄不保证rename排他；按名重开和句柄查询之间仍有竞态，不是原子相对句柄遍历、锁或后续安全写入批准，production_write_authorized与race_free始终false。硬链接可有多名字同一ID，身份相等不是路径唯一证明。W01/W02整体仅部分通过；case-sensitive、ACL恢复、权限拒绝注入、完整事务与客户端生命周期仍pending。

旧尾项已原生cygpath定位 `C:\Users\VINCEN~1\AppData\Local\Temp\joined.b64`，33959B、SHA256 `a0443c14d9aec65ecd3cfdcf7ab8adc40cfa8950d8ed9df965aa2cb21a87dee0`。与现有参考文件字节不符，不足以授权删除，保留不再泛查；隔离仍部分通过。

冻结SHA256：

- `scripts/agm_core/windows_native.py`：`ef3138c5778ab26807a22ad52769f12fb94bb8b2f41870b2715e896081da3f66`。
- `tests/unit/test_windows_native.py`：`c92cf6ab4ecd38ecdb445ff74df9a67a893cd98b394eec1834ad98b022c61467`。
- `tests/integration/windows_native_probe.py`：`974506be124e7799d76b29ca15616097f1f4797857d62402a54e1f350a607a95`。
