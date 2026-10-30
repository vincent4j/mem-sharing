# M2-09 平台矩阵验收

状态:已完成。依据 docs/plan/tasks.md M2-09;前置 M2-08(两项目装配 second-run 部分通过)与
m2-matrix.md(M2-07 幂等与故障矩阵,含 2026-10-29 主 Agent 裁定)。本任务交付:平台矩阵、
本仓库真实卸载/重装/失败恢复演练证据、README/SKILL 发布前文档更新、全量测试。

- 交付者:突突兔(ZCode 会话)。任务消息:paseo `deddc255-fe9a-4329-bc69-0c12b28ab9fa`。
- 观测环境(见 [env.txt](m2-platforms/env.txt)):macOS 26.6.2(Build 25G83,Darwin 25.6.0 arm64),
  CPython 3.14.3(仅标准库),git 2.x;CLI 基线提交 `117b83a`。
- 全部演练在本仓库(agent-group-memory 主 checkout)以真实 CLI/真实文件执行;快照工具
  [snapshot.py](m2-platforms/snapshot.py) 只读,证据文件均在 [m2-platforms/](m2-platforms/) 目录。

## 1. 平台矩阵总表

| 平台 | 安装 | 重装 | 卸载 | 失败恢复 | 结论 |
|---|---|---|---|---|---|
| macOS(darwin,arm64) | passed | passed | passed | passed | 本机四项均有真实文件证据 |
| Windows | not-run | not-run | not-run | not-run | 无环境;不声称支持 |
| Linux | not-run | not-run | not-run | not-run | 无环境;不声称支持 |

Windows/Linux not-run 的依据:agents.json 平台表仅含 `darwin`(paths.py 对未知平台键直接拒绝,
CLI 在其他平台无法加载路径表);上游 context-keeper 的跨平台 symlink 策略未定(DESIGN §4.6、
开放问题 O8);本轮无对应环境,未做任何远程或容器内冒测。上述平台的一切能力均未验证,
不得从代码可移植性推断"支持"。

## 2. macOS 四项明细

### 2.1 安装 — passed

- M2-08 second-run:knowwind、poster-fit 两项目真实装配 `enable-memory --memory` 返回 0,
  真实上游 install/init 由 enable 驱动,既有业务文件与记录库 SHA/mtime 全部保持
  ([m2-08/README.md](m2-08/README.md) second-run 节;两项目 `second-run/` 下批准文件、
  装配输出、前后快照与 diff)。
- M2-07 矩阵 O-1/O-2:先 Group 后 Keeper、先 Keeper 后 Group 双安装顺序在隔离环境以真实
  文件断言([m2-matrix.md](m2-matrix.md) §3)。
- 本仓库自身装配史:M1-03 round3(登记见 `scripts/registry.json`,本机文件)。

### 2.2 重装 — passed

- M2-08 second-run:两项目装配后再次 enable 返回 0、`changes=[]`,前后树快照相等
  (idempotent.diff 为空)。
- 本任务重装演练(卸载后恢复,见 §2.3 的卸载后状态):预览返回 5 → 批准
  [enable-approval.json](m2-platforms/enable-approval.json) → 执行返回 0
  ([enable-applied.stdout.json](m2-platforms/enable-applied.stdout.json));
  随后无参数幂等重跑返回 0、`changes=[]`
  ([enable-idempotent.stdout.json](m2-platforms/enable-idempotent.stdout.json)),
  `check-memory` 返回 0、三执行器 skill/bridge 全 ready
  ([check-after-enable.stdout.json](m2-platforms/check-after-enable.stdout.json))。
- M2-07 矩阵 I-1..I-8:幂等矩阵(零字节/mtime 变化、一致修复免批准等)见
  [m2-matrix.md](m2-matrix.md) §2。

### 2.3 卸载 — passed(本仓库真实演练)

流程(先预览后批准,非交互执行):

1. 预演快照 [remove-before-snapshot.json](m2-platforms/remove-before-snapshot.json):
   10 个受管路径 + 记录库全树 + registry 各项目/共享段哈希。
2. 非交互无批准 remove → CLI 门禁返回 5,零变更
   ([remove-preview-gate.stdout.json](m2-platforms/remove-preview-gate.stdout.json));
   交互(pty)预览返回 5 并给出 8 项精确变更计划
   ([remove-preview.parsed.json](m2-platforms/remove-preview.parsed.json)):
   AGENTS.md/CLAUDE.md/.workbuddy MEMORY.md 三处 created 块摘除、4 个 created Skill 链接删除、
   registry 更新;同时声明保留 reused 对象与用户级共享入口(剩余消费者 2)。
3. 依预览构造批准文件 [remove-approval.json](m2-platforms/remove-approval.json)
   (reference 指向本任务消息),执行返回 0、8 项全部 applied
   ([remove-applied.stdout.json](m2-platforms/remove-applied.stdout.json))。
4. 事后快照 [remove-after-snapshot.json](m2-platforms/remove-after-snapshot.json) 核对:

| 核对项 | 结果 |
|---|---|
| 4 个 created Skill 符号链接 | 已删除(absent) |
| 三处 created 桥接块 | 按块字节精确摘除,块外字节保留([remove-entry-files-full.diff](m2-platforms/remove-entry-files-full.diff)) |
| reused 对象(AGENTS.md/CLAUDE.md 整文件、CLAUDE.md @import) | 未触碰(预览 warnings 逐项声明保留) |
| 记录库 `docs/context-keeper` 全树(11 文件) | 逐文件 SHA+mtime 完全一致 |
| 用户级共享入口 `~/.workbuddy/MEMORY.md` | 字节与 mtime 完全一致 |
| registry 中 knowwind/poster-fit 两项目段 | 哈希不变(不受影响) |
| 共享对象(O2) | 对象与 created 证据保留,consumers 3→2 |
| 卸载后 `check-memory` | 返回 1,skill/bridge 三执行器 missing、store unknown([check-after-remove.stdout.json](m2-platforms/check-after-remove.stdout.json)) |

### 2.4 失败恢复 — passed(真实 Transaction 崩溃 + recover_manifest)

驱动脚本 [crash_drill.py](m2-platforms/crash_drill.py)、崩溃子进程
[recover-scene/crash-child.py](m2-platforms/recover-scene/crash-child.py) 均使用本仓库真实
`agm_core.transaction`(无桩、无 mock);场景:文件更新(带真实 before 备份)、文件新建、
符号链接新建三项变更,子进程在第三个写前 `os._exit(9)` 硬崩溃(绕过一切异常处理)。

| 步骤 | 结果 | 证据 |
|---|---|---|
| 崩溃后现场 | manifest `status=applying`、前两项 attempted(第三项因"写前保守置位"也标记 attempted)、a.md 已改写、b.md 已写入、link.md 未写、`.lock` 目录残留 | [crash-scene.json](m2-platforms/crash-scene.json) |
| 锁在场时恢复 | `lock_conflict` 拒绝(不偷锁),现场零变化 | [crash-result.json](m2-platforms/crash-result.json) step `recover-refused-with-lock` |
| 操作员确认陈旧锁 | 子进程 rc=9 已退出、锁归属明确,rmdir 移除(记录裁定理由) | 同上 step `operator-removed-stale-lock` |
| `recover_manifest` 显式恢复 | before 备份指纹校验通过,三项 restoration=restored,manifest 置 `rolled_back`,目录回收 | 同上 step `recover-manifest` |
| 字节核对 | 恢复后现场与崩溃前快照完全一致(a.md 字节复原、b.md/link.md absent),锁已释放 | verdict=passed |

负向核对:用本仓库真实 committed manifest(重装演练产物)调用 `recover_manifest` 被拒
("manifest is not eligible for recovery"),manifest/备份原样、锁正常释放
([recover-committed-refusal.json](m2-platforms/recover-committed-refusal.json))。

说明:`recover_manifest` 是库级原语而非第四个 CLI 命令;真实 CLI 事务自身异常走进程内
回滚(M2-07 F-11 已测),本演练覆盖的是进程死亡后需要操作员显式恢复的路径。演练未对
生产 registry 制造崩溃(那会波及三项目共享登记),场景目录位于
`docs/acceptance/m2-platforms/recover-scene/`,输出全部在批准根范围内。

## 3. 卸载→重装全周期字节观察

演练前(remove-before)与重装后(enable-after)对比:

- 4 个 Skill 链接、用户级共享入口、`context-keeper.json`:**字节一致**(链接目标不变)。
- 记录库全树:**一致**(重装 init 对完整库零改写)。
- AGENTS.md/CLAUDE.md/.workbuddy MEMORY.md:受管块内容字节一致,但连接符换行重排
  ([cycle-entry-files.diff](m2-platforms/cycle-entry-files.diff)):append 场景的块尾 `\n`
  迁到块前;WorkBuddy MEMORY.md(top 场景)文件尾每次完整周期多一个 `\n`
  (2673→2674 字节,重复周期会累积)。这是 m2-matrix.md §5-4 已裁定接受的行为
  (字节精确性优先)在全周期下的具体表现,登记在此供发布文档引用;registry 重装后按
  新现场重算指纹,自洽无漂移。

## 4. 全量测试

- 基线(演练前,[tests-baseline.txt](m2-platforms/tests-baseline.txt)):unit 228 项 OK +
  integration 53 项 OK,共 281 项。
- 终态(全部文档与演练完成后):见 [tests-final.txt](m2-platforms/tests-final.txt)。

## 5. 未验收范围

- Windows/Linux:全项 not-run(§1);跨平台锁语义(fcntl 等)未做任何未验证声明。
- WorkBuddy 桥接运行时验收:M2-08 起保持未执行;操作单在手,不得以静态存在计通过。
- Claude 显式走 Skill/resume 的程序化验证、记录库迁移门禁(rc=3)真实触发:未在本轮范围
  (后者由 M1-07 隔离夹具与上游合同覆盖)。
- 本演练不构成发布、安装定时器或对上游回传(M3)的任何动作。
