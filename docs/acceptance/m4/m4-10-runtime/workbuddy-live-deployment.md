# WorkBuddy 0.1.1 真机部署与静态读回

2026-10-31。用户授权按推荐流程完成，不再逐步追问；主 Agent 对精确计划作内部核验后执行。**正式升级和 WorkBuddy 入口装配完成，静态读回通过；新会话运行验收仍 pending，M4 不因此关闭。**

## 固定来源与验证

- 本地精确提交：`04c32e24b9ab9504514908f2368cddca4356e478`。未 push、tag 或远程发布。
- 独立干净 checkout 为本地 clone；目标 0.1.1，tree `15cd779745ab6ef80f3d966ef8c9850ee1e87abc48c314158a6502434127e179`，27 个产品文件。
- 窄合同转换处理器已完成：只允许固定 0.1.0 前身到 0.1.1、固定 user_entries 前后指纹及不变 agents.json；入口仍用精确批准事务。
- 冻结全量单元 474 项/98.095 秒、集成 74 项/105.438 秒，退出码均 0；定向 50 项/16.111 秒也通过（非额外不重复用例统计）。两位独立审查无阻断。原始全量结果见 [单元](workbuddy-contract-unit.log)、[集成](workbuddy-contract-integration.log)。

## 保全与精确写集

私有备份位置 `/Users/vincent4j/.mem-sharing-private-evidence/wb-fix-live-20261031-20261031T021405Z-94da86c3`，快照 UTC `2026-10-31T02:14:05.563951+00:00`；目录0700，文件0600。6份原始文件及snapshot仅留私有目录，不入Git：WB/Codex/Claude入口、公共索引、台账、C清单。部署前再次核对原件hash/权限。

精确计划含12条changes：C下INSTALL、ck_install、upgrade、user_entries、install与manifest共6更新；持久版本目录、registry、升级标记、旧版archive、固定toolkit/journal目录；唯一用户内容更新为WB MEMORY.md。正式事务另按计划生成锁、备份和激活收据。不改Codex/Claude入口、公共索引、上游CK或项目原生目录。

## 一次失败与更正后的实际执行

首个操作 `wb-public-index-011` 的批准时间使用真实UTC `+00:00`；外层CLI接受但内层registry仅接受Z，执行exit2/failed，`registry_invalid: expected UTC timestamp`。`upgrade.execute_upgrade` 在开锁/建journal前调用 `migrate._approval` → `registry._evidence` → `_time`，故失败发生在产品写入之前。现场验证bootstrap/archive/journal/版本槽/激活收据/guard/锁均未创建，6原件hash不变，recovery_required=false。保留原approval/execution，未重放。

主Agent明确放行输入格式修正及新唯一操作 `wb-public-index-011b`。新预览与旧计划除操作ID及其衍生路径/编码后registry/hash之外一致；采用实际UTC严格Z时间、真实用户授权说明与内部核验reference，执行一次supported CLI `--approval-file`。

结果：exit0、status=completed、entries=completed、WorkBuddy connected、connection_pending=false、runtime_acceptance=pending，stderr为空。批准与完整返回仅保留私有目录0600。新outer plan内部hash `9a0a1e180ee5d8357589b22a09a9c845e541e55024f1d0f07dd009a00aa9566d`。

## 独立读回

详见 [脱敏读回](workbuddy-live-readback.json)。

- C27文件逐一与清单/固定源hash匹配；台账0.1.1/commit/tree一致。
- WB由5788增至8174字节，旧5788字节逐字节作为前缀保留（包括原CK块），mode0644不变，最终hash `02adac0d139218402235cbb7a1860231e5bedc148895f8cd1078314ce948c272`。
- Codex/Claude入口和公共索引hash/权限不变；台账原agents/projects/shared_objects及已有对象保持，只新增WB受管对象。
- journal=committed；前后激活收据的operation/phase/journal/完整inventory/代码阶段registryhash相符，版本槽存在；升级guard及锁已清除。最终台账随后有合法入口事务，不能要求其hash仍等于代码阶段after receipt。
- 已安装C的Keeper `_scene`只读通过，agents为Codex/WorkBuddy；二者静态connected、runtime pending。未调用Keeper安装，不把前置校验通过说成尾步再次执行成功。

## 剩余范围

此前“升级无合同转换处理器”和“源码未部署”已由本轮实现与正式部署解除；历史记录保留。WorkBuddy新会话公共实读/项目标记仍需章教授取证，项目标记此前遗漏根因不由静态安装证明解决。CK首次激活、自动入口、跨执行器接力仍独立待验；M4维持部分通过。成功发行降级不在专用通道支持范围，中断恢复与已完成后撤回仍须分别按精确计划处理。

## 部署后运行时取证阻断

主Agent收到章教授的本轮反馈：Computer Use刷新绑定返回cgWindowNotFound；按已知文档对旧Raise尝试一次后返回element ID no longer valid，随即停止，没有发送测试提示。此次不是安装失败：已装入口及静态读回成立，运行时新会话仍blocked/pending。没有再次要求用户重复操作，也没有新增临时公共规则。

阶段时间按现存证据：阶段A全量单元98.095秒、集成105.438秒（可能并行，不相加当墙钟）；私有备份快照UTC02:14:05.563951，部署静态读回UTC02:23:47.212564，相隔约9分42秒，期间包括等待源码冻结、本地提交、预览、时间格式失败定位与成功部署，不等同于纯执行耗时。端到端墙钟起点由主Agent会话日志核对，本子任务不据上述区间杜撰总耗时。
