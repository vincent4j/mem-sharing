# Paseo 发行生成与只读 CI 检查

此目录只负责确定性发行与核验。Python 业务真源仍在 `scripts/`，公共 Node 真源在 `plugins/shared/src/`。当前范围仅 Paseo，不生成 Orca。这些工具不安装产品，不提交、推送、打 tag 或发布。

S 是实现与测试完成后的干净源码提交；R 是只加入或更新允许生成物的发行提交。内核身份绑定 S，获取来源绑定 R。产品版本必须由用户明确批准，通过 `--version` 传入；工具没有默认产品版本，不允许为新内容沿用已安装同版来替换。

## 任意 CI 均可调用的检查

需要可用的 Python 3.9+、Git 和支持 `--experimental-strip-types` 的 Node（本次合成验证使用 Node 22.22.3）。只使用本地源码和 Node 内置测试模块，不安装 npm 包、不联网，也不依赖某家远程 CI。

在对应 checkout 根目录运行，`S` / `R` 均为完整提交 SHA，`VERSION` 为已批准的产品版本。变量必须由调用者提供，不填示例 hash 或猜测版本。

```sh
# 源码 S：要求 HEAD=S、全树干净、生成 common 与真源一致、identity 为空哨兵；
# 旧 release 描述、旧 Paseo payload 或非空 identity 残留均拒绝，不冒充干净 S。
python3 -B tools/plugin-release/check.py source --source "$PWD" --commit "$S"

# 发行 R：同样检查 common，再调用既有 checkout_delivery 校验固定 R 与完整发行。
python3 -B tools/plugin-release/check.py release --source "$PWD" --commit "$R" --version "$VERSION"
```

退出 0 表示本阶段静态检查通过，失败退出 2；参数错误也退出 2。stdout 是 JSON，包含原 common 测试的 TAP 输出。`published: false` 表示此命令不证明发布状态；`runtime_acceptance: pending` 表示未验收真实宿主。

检查入口不运行写入型 sync 或 generate。它要求 sync 脚本、既有 sync 测试、identity、shared 真源、common 生成物、两份 `THIRD_PARTY_NOTICES.md` 与两个 `notices/` 目录中的许可文件受 Git 跟踪，且工作树字节/模式等于 pin 中的 blob；拒绝 notice 符号链接和额外未跟踪文件，隐藏在 `assume-unchanged` / `skip-worktree` 后的修改也不能冒充已核验输入。source 阶段在运行 Node 测试前先拒绝三类旧生成物残留：`release/core-release.json`、`plugins/paseo/payload/` 下任何跟踪文件，以及不等于空哨兵字节的 `release-identity.ts`（含隐藏在 `assume-unchanged` 后的工作树改动）；对 manifest 与 payload 还做不跟随链接的物理存在检查，被 `.gitignore`/`.git/info/exclude` 隐藏的残留（含空目录、普通/悬空链接）同样拒绝，Node 测试结束后再次复核同一源码态。开发 sync 测试允许非空 identity 匹配旧 manifest，不构成干净 S 的证据。随后复用 `plugins/paseo/test/sync.test.ts`：S 运行 common 两项、notice 同步和空哨兵共四项；R 运行 common 两项和 notice 同步共三项，排除开发空哨兵测试。检查预期测试实际运行，不能因全跳过而通过。转换算法不在 Python 中重复实现。

R 阶段继续复用 `scripts/agm_core/plugin_release.py::checkout_delivery`，核验 S 是 R 的祖先、S/R 受管文件集合/字节/模式一致、跟踪描述与 pin 一致、Paseo 载荷闭合、identity 精确等于 canonical manifest 摘要，以及 R 仅改允许生成路径。缺少正式 manifest/payload/identity 的开发树不能通过此阶段。

## 可审核的 S → R 操作

以下是未来获得提交与发行授权后的操作顺序，不是现在已经存在 S/R 产物或已经发布的声明。提交、推送、tag 和发布均由主 Agent 在相应授权后执行。不要在 dirty 主工作区生成正式载荷。

1. 在专门的源码 checkout 完成代码、文档和测试。维护者先运行 `node plugins/shared/sync-to-plugins.mjs` 更新 common；这是明确写操作，不是 CI 检查。开发 `plugins/paseo/server/shared/release-identity.ts` 保持空字符串哨兵，插件在此状态拒绝 bootstrap，不伪造摘要。将所有源码、common 生成副本、工具及开发哨兵纳入经授权的 S 提交。
2. 取得完整 S，确认 checkout 干净，再运行上面的 `check.py source`。八份受管文档（含 `docs/uninstall-design.md`）和 `scripts/` 必须在 S 中；未跟踪的新内核模块不能遗漏。上一轮的旧 `release/core-release.json`、旧 payload 树与具体 identity 常量在 S 准备时先删除/恢复空哨兵，残留会被 source 阶段拒绝。没有用户批准的产品版本，就停在源码检查。
3. 从干净 S 导出到**源码 checkout 外、尚不存在**的绝对目录 `OUTPUT`。父目录由调用者准备。官方来源清单不固化开发机路径；非官方 origin 的开发夹具会明确保留带本地路径的 `local-checkout:` 身份，不冒充官方来源。

   ```sh
   python3 -B tools/plugin-release/release.py generate \
     --source "$PWD" --commit "$S" --version "$VERSION" --output "$OUTPUT"
   ```

   现有生成器输出且仅输出：`release/core-release.json`、`plugins/paseo/payload/{core/,release.json}`、`plugins/paseo/server/shared/release-identity.ts`。摘要常量在 manifest 之外生成，不把最终 R 写进自己的产物，没有 hash 自引用。载荷包含八份受管文档和完整受管 `scripts/`，并保持模式。
4. 需要独立复查重生成零差异时，再指定另一尚不存在的外部目录 `OUTPUT_AGAIN`，重复相同 generate 命令后比较两棵输出（例如 `diff -r "$OUTPUT" "$OUTPUT_AGAIN"`）。这两个命令有明确外部输出写入，不属于只读 CI 入口；字节与模式的最终检查由下一步 release verifier 完成。不要将一次生成结果描述为已完成真实宿主验收。
5. 在**同一 clean S checkout** 中仅放回上述三个生成路径。下面的显式复制只面向该发行准备 checkout；若已有 payload，应在独立候选目录中逐项核对替换，不能把合并复制留下的旧文件混入载荷。

   ```sh
   set -eu
   test ! -e plugins/paseo/payload
   mkdir -p release plugins/paseo/server/shared
   cp "$OUTPUT/release/core-release.json" release/core-release.json
   # 首次发行要求目标 payload 尚不存在；后续发行先审查旧目录，再精确替换，禁止混合两版。
   cp -Rp "$OUTPUT/plugins/paseo/payload" plugins/paseo/payload
   cp "$OUTPUT/plugins/paseo/server/shared/release-identity.ts" plugins/paseo/server/shared/release-identity.ts
   git diff --stat
   git status --short
   ```

   common 已在 S 中与真源一致，R 不再运行 sync；手写 host/shared 源码也必须在 S 中。当前 Paseo 使用宿主支持的 TypeScript 入口，没有此工具生成的独立 Node build。若将来确需构建输出，先明确生成命令与只允许的输出目录，不能宣称当前已实现该步骤。
6. 主 Agent 审核差异：`scripts/` 和八份受管文档相对 S 不变；R 只能改 `release/core-release.json`、`plugins/paseo/payload/**`、`plugins/paseo/server/shared/**` 或已明确构建的 `plugins/paseo/dist/**`。不能把工具、说明文档、手写适配代码或顺手修复混进 R；需要修改就回到新的 S。主 Agent 获授权后仅提交生成物为 R，不在本工具中自动提交。
7. R 提交完成后，必须在 clean、完整 pin R 的 checkout 执行 `check.py release`。原来的窄核验命令仍可单独使用，但不额外检查公共 Node 副本：

   ```sh
   python3 -B tools/plugin-release/release.py verify \
     --source "$PWD" --commit "$R" --version "$VERSION"
   ```

   任何不一致都阻断候选。未生成或未提交的 R 不算发行可用；CI 通过也不等于真实安装、新会话加载或发布通过。依赖供应 URL/hash/许可与真实宿主批准通道未闭合时，保持阻断，不以合成已有解释器测试宣称“缺依赖机器即装即用”。

## 同仓两种安装入口

普通根安装继续使用原 Git 仓库及固定 R：`python3 -B scripts/install.py --source "$PWD" --commit "$R" --version "$VERSION"`。原有 clean/pin 不变；识别发行后先精确批准持久 export，再通过返回的 `source_manifest` 进入原机器安装批准。V 的内核来源记录 S，获取 R 的记录保留在 acquisition receipt。

Paseo 的目录入口是同一固定 R 下的 `plugins/paseo`。平台固定 ref/selector 的准确安装写法须在正式发布前按已核实宿主合同确认，不在这里拼造未验证语法。发行必须包含该子目录实际载荷和生成 identity；插件运行时不向父目录读取 `plugins/shared/src` 或仓库 `scripts/`。公共代码来自子目录内的 `server/shared/common`，Python 来源来自 `payload/core`，获批后转为 HOME 内独立持久 export，升级或卸载插件不应删除唯一恢复材料。

两个入口使用同一 S/版本/受管树身份、库存 marker 与 conversion 门禁。hash 证明完整性，作者来源信任来自已信任的固定 Git/插件安装渠道；RPC 传来的 pin/hash 不能自行成为信任根。运行时供应、真实宿主路径解析、精确确认和新会话加载仍须独立验收，未做就标 pending。
