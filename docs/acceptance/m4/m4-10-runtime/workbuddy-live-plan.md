# WorkBuddy 修复真机精确变更计划（只读准备，尚不可执行）

> 历史阶段材料，保留原始观察及计划；其中状态仅指当时。当前有效判定统一见 [verdict.md](verdict.md)。

2026-10-31。本轮只读盘点实际机器、运行安装器 help/无批准 preview，并在本仓库写此计划；没有部署、改真实用户规则/台账/C，也没有提交。以下指纹只代表本次观察；执行前必须重新预览，不能直接沿用旧批准。

## 1. 结论与实际阻断

**当前正式升级路径不能部署这次修复。提交代码、把版本改成 0.1.1 仍不够。**

1. 当前修复是基于 `51ecf55ea3847ef71866892ca45b46fed1b0f154` 的未提交工作树，不是此 SHA 的内容。`install.checkout_source` 要求干净且 HEAD 等于完整固定 commit。本轮真实只读命令返回 exit 2 / `source_drift`：`Dirty checkout: preserve it and supply a clean verified source`。
2. 同版换源码不是升级：`upgrade._conversion` 明确拒绝旧版本 >= 目标版本的 upgrade。不能以 0.1.0 覆盖旧代码，再手工改台账。
3. 高版本也必须提供精确发行 conversion（before/after/direction/entries）。现实现只接受 `entries='preserve'`。
4. `upgrade._ENTRY_CONTRACT_NAMES` 包含 `scripts/agents.json` 与 `scripts/agm_core/user_entries.py`；后者正是本次修复文件。`upgrade._plan` 无条件比较旧/新文件指纹，变更即拒绝：`Conversion has no handler for changed entry contract`。这是代码静态核对结论，未伪造发行 commit/清单去绕过预览。

依据：`scripts/install.py:78`（checkout_source）、`scripts/agm_core/upgrade.py:31`（合同文件）、`:81`（conversion）、`:168`（合同门禁）。不删除这些门禁、不改写旧发行清单、不将未提交 tree 冒充 commit、不重装/清空用户数据。

## 2. 当前机器状态（仅元数据）

| 项目 | 当前观察 |
|---|---|
| 代码 C | `/Users/vincent4j/.local/share/mem-sharing` |
| 公共源 R | `/Users/vincent4j/.mem-sharing` |
| 台账 | `/Users/vincent4j/.mem-sharing/var/registry.json`，schema 3 |
| 已安装产品 | 0.1.0 / structure 1 / complete |
| 已装来源 commit | `4cfe7bedfde695b0bd4085ccc453afd3ef161711` |
| 已装来源 tree_sha256 | `5af4e9208884560741ce05081d157cfa57d42789b3d87cd6554491cb951e875b` |
| 当前操作 ID | `20261030T183458Z-33746607ff5d4465a8728d7dd347437b` |
| 台账 SHA256 | `64e0c17179825b2bc0a2a189560a82cfbc6afd4be27294261f00d7e943bf3ddf` |
| C 清单 SHA256 | `f0581485a4bafbd44c0ba90d1b159b5d0a17dc1add7ae9daceecf681e746e169` |
| C 完整性 | `_code_matches` 校验通过；清单共 27 个受管文件 |
| 执行器 | Codex 与 WorkBuddy installation=installed；原台账 static=unknown、runtime=pending |
| 机器入口对象 | 仅 Codex 1 个；WorkBuddy 0 个 |
| 修复版静态只读核验 | Codex connected；WorkBuddy pending / entry_not_registered；均不宣称 runtime 通过 |

WorkBuddy 用户文件 `/Users/vincent4j/.workbuddy/MEMORY.md`：5788 字节、mode 0644、SHA256 `eea8c118937a73af6414e2a71f8f2e95734f522dca854d86f72fa2cf5263e8a0`。存在 CK 自有块；没有 mem-sharing 用户受管块，没有公共索引绝对路径指针。没有输出私人正文。

## 3. 本次已测工作树与 C 的差异

27 个受管文件中，仅以下 4 个字节有差异。文档/验收记录不因位于仓库就全部复制到 C。

| 拟更新 C 下相对路径 | 当前 C SHA256 | 本次工作树 SHA256 |
|---|---|---|
| `INSTALL.md` | `3f693f5f719d801867c11b69293b0587aaaaab5f7c64df9856d2a0b3fe2d38bf` | `892e499d597e45986722669ff044d30d8a0b79891dc584fd40c9d6bc08d7eebd` |
| `scripts/agm_core/ck_install.py` | `1c386f310851c5934fd4dd62cd40d7b7cc88e8ddcf4c804f88722d36c8485314` | `a1e67cc504796e2ffd144c8ea5579935266a8180bff3112bff5841db2bf73d7d` |
| `scripts/agm_core/user_entries.py` | `155eba8df9b14ccb96e017bc19e3975930be544019fdb1d3aaa17f3aa563be44` | `eda73b02e99d8092f6f587d786d163efd4d8bbc72340e79de0ad1ffabd25c85a` |
| `scripts/install.py` | `52c3a3e381ce06904aea2e7d8fe0e0900df7cd281b811ef95874a8dc2f815b6f` | `91281509b4bf647d5ce4bf52bb401556c65f0209730338d0795327b56a1c1ee7` |

这是**工作树文件指纹清单**，不是可发行的 Git 源身份。支持升级合同的后续代码尚未实现，上表不能作为未来完整部署清单；实现后必须重算并展示新增受管路径。

## 4. 用户入口子计划（已真实只读预览，未应用）

调用当前源码 `user_entries.run_user_entries`，参数 home 为真实 HOME、agents=['workbuddy']、interactive=False，结果 `approval_required`，无错误。此结果只证明入口装配子计划可预览，不替代机器正式升级门禁，也不授权从未发行源码直接执行子计划。

唯一内容变更目标：`/Users/vincent4j/.workbuddy/MEMORY.md`。

- 原 5788 字节保留为新文件完全相同的前缀；CK 块与私人正文不改。
- 末尾追加 2386 字节受管块，本次无需补分隔换行；新文件 8174 字节，mode 保持 0644。
- 新块 SHA256：`c7dceaf2aac616a9172ddc487327b758b8e020d0c48810e71e6a7ce96aa1dc40`。
- 新文件 SHA256：`02adac0d139218402235cbb7a1860231e5bedc148895f8cd1078314ce948c272`。
- 块明确要求读取 `/Users/vincent4j/.mem-sharing/memories/MEMORY.md`，保留项目 AGENTS 约定，包含治理、实际使用兜底及菜单文本。
- 台账仅新增机器对象 `/Users/vincent4j/.workbuddy/MEMORY.md#convention`，登记受管块指纹/created 所有权/事务备份引用；不取得整个用户文件所有权。本次 machine_agents 无更新。
- 不创建项目 `.workbuddy/memory/`，不改公共索引、主题、Codex/Claude 用户入口、CK 文件/安装链接或其他 Agent 私人内容。

## 5. 解阻后预计写入路径与保护范围

以下是正式机制的范围图，**尚非完整可执行批准封皮**。目标 commit、目标 tree、转换处理器未固定，不能捏造 after_registry 指纹或版本目录。

| 路径 | 计划作用/保护要求 |
|---|---|
| `C/INSTALL.md` 及 §3 三个 Python 文件 | 正式升级逐文件原子替换；禁止直接 cp 三文件后改台账 |
| `C/.agm-code-manifest.json` | 正式生成目标来源与全部 27 个文件（后续若增文件则完整列出）清单 |
| `R/var/registry.json` | 正式升级最后提交产品版本/来源/操作 ID；入口事务再提交 WB 对象；保留全部既有项目/对象 |
| `/Users/vincent4j/.workbuddy/MEMORY.md` | 仅 §4 批准追加；原始全文受保全，不公开备份正文 |
| `/Users/vincent4j/.mem-sharing-install-wb-fix-live-20261031/` | 固定恢复工具、源码暂存与 journal；不得与已存在操作复用 |
| `R/backups/upgrade-wb-fix-live-20261031/` | 旧完整 C 与 registry-before 只读存档 |
| `/Users/vincent4j/.local/share/mem-sharing-versions/<版本>/<tree>/` | 前/后发行代码及收据；版本与 tree 待固定 |
| `/Users/vincent4j/.local/share/mem-sharing-versions/activations/wb-fix-live-20261031-{before,after}.json` | 正式激活收据 |
| `/Users/vincent4j/.mem-sharing-upgrade.json` | 未完成升级保护标记；完成后按内核清理 |
| `R/backups/<UTC>-<uuid>/manifest.json` 与对应 `*.before` | 入口事务生成，绑定真实用户文件及台账的改前字节；目录0700、备份0600；不公开正文 |
| `/Users/vincent4j/.mem-sharing-install.lock`、`R/var/.agm.lock`（含 transaction） | 运行时互斥锁，按内核生命周期创建/清理，不手工偷锁 |

R/memories、R/references、旧 v0 阅读包、项目记录库、真实用户私人正文、CK 上游源码及其 Skill 链接均为保护对象，不作为本轮迁移、重装或清理目标。若后续生成的精确计划超出范围，停止重新审阅。

## 6. 两阶段最小路线与命令边界

### 阶段 A：尚未实施的窄范围处理器

建议下一项开发仅实现**固定前后发行的用户入口合同转换支持**：绑定当前 0.1.0 的确切来源、目标新版本确切来源和两份合同文件指纹；转换本身保持用户对象/正文，入口追加仍走已有精确批准事务。`scripts/agents.json` 必须保持原字节，不在本次允许变更范围。不得泛化为“任意合同改变都允许 preserve”，也不得降低当前漂移/恢复门禁。必须覆盖升级中断恢复、前后对象/私人字节保持、入口失败 partial、回退边界。此方案需单独批准，实现与回归后再提交部署精确计划。

### 阶段 B：处理器通过后才能生成真机批准计划

阶段 A 未实现，当前不能生成有效完整机器 approval_plan。目标 after_registry、发行 tree、版本目录、转换恢复/完成后回退语义尚须处理器实现和验证后确定；§4 的实际子计划不是完整机器批准。

随后需要用户明确授权主 Agent 提交（不必 push 才可本地部署），得到干净 pinned Git 来源；建议新版本 0.1.1，版本号及 commit 仍待批准/生成。无须把无关脏改动强行混入：可使用精确文件清单提交已审查修复，并以干净的提交导出/独立 checkout 为发行来源。不能将未提交修复配上旧 SHA 做 `--source-manifest`。

以下均为已有正式 CLI 形状，含占位符的命令目前**不可执行**，且合同处理器实现前不会放行：

```sh
# 只读机器升级+WB入口预览；request 文件含精确 before/after conversion
python3 <干净固定来源>/scripts/install.py --source <干净固定来源> --commit <完整目标SHA> --version 0.1.1 --request-file <精确发行转换JSON绝对路径> --agent workbuddy --operation-id wb-fix-live-20261031

# 用户批准该次完整 approval_plan，加真实 confirmed_at/reference 后才能执行
python3 <干净固定来源>/scripts/install.py --approval-file <完整精确批准JSON绝对路径>

# 升级中断：先只读生成恢复计划
python3 <固定恢复来源>/scripts/install.py --recover /Users/vincent4j/.mem-sharing-install-wb-fix-live-20261031/journal.json --action rollback
# 另行批准恢复计划后执行，不能直接以旧安装批准替代
python3 <固定恢复来源>/scripts/install.py --recover /Users/vincent4j/.mem-sharing-install-wb-fix-live-20261031/journal.json --action rollback --approval-file <恢复批准JSON绝对路径>
```

完成后的发行降级与中断 rollback 不是同一操作：前者还需已成功安装收据与反向精确 conversion；当前合同文件变化同样不受支持。不能承诺“成功升级后可用一条命令降回0.1.0”。入口事务失败会按其 manifest 回滚；成功追加后若要撤回，要用精确块/指纹批准计划与保全备份，不能整文件覆盖后加的私人正文。本次不新增机器卸载。

## 7. 真机执行后的验收条件

1. 读取 C 清单，逐个实际文件比对目标来源；产品台账 complete、目标版本/commit/tree 与最终激活收据一致，不以文件复制完成当成安装成功。
2. WB 旧5788字节与保护备份逐字节一致；仅追加目标块，实际新块指纹与对象登记一致；旧 CK 块不变。若期间用户文件变化，旧计划失效，重新预览。
3. 修复版报告 WB 静态 connected；runtime 仍 pending。CK 只读前置可核验，不再次安装/覆盖已有 CK。
4. 再做独立新会话无答案泄漏验收，公共主题实读和项目标记分别取证；只读提取由章教授负责。本计划不提前宣告 M4 关闭。

当前状态：**入口子计划具体可审阅；正式部署因源码身份与入口合同升级支持缺失阻断。请先选择是否批准上述窄范围升级支持开发；这份文档不是部署授权。**
