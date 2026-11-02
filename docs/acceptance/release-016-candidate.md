# 0.1.6 源码候选准备

用户已明确批准“确认用0.1.6继续”。本记录绑定本轮发行输入版本 **0.1.6**，尚无正式 S/R、发布或真实升级结论。

产品版本沿用发行工具的唯一输入：`release.py generate --version 0.1.6`（该参数必填、无默认值），随后由生成 manifest 的 `source.version` 承载。不新增运行时默认版本，不修改 Paseo 插件 package 版本，不改历史版本、SOURCE/TARGET 或 0.1.4→0.1.5 专用 handler。

本轮从固定 R `417e1637e7ff172eb5651cd0cdd360559341b8db`、其父 S `542f248f35e9de8fb2e7566b6312e6f13d26cd41` 出发。0.1.5 内核 tree 为 `023bbaa275cd1290450ee7ac707f0b58d341d3e6064a09a6c24bfd6245f0d2e5`。已审 r3 的 `scripts/agm.py`、`scripts/agm_core/legacy_reconcile.py`、`tests/unit/test_legacy_import_reconcile.py`、`docs/operations.md` 字节保持冻结。

0.1.5→0.1.6 的 `agents.json` 与 `user_entries.py` 合同未变，使用既有外部精确 conversion，`direction=upgrade`、`entries=preserve`。before 是 schema3/structure1/version0.1.5 与上述固定 S/tree 的实际来源；after 的 version 为0.1.6，URL/S/tree 必须来自未来固定 S 生成并验证的 manifest/source export，不能填 R 或示例 SHA。不同 source、缺 conversion、同版异来源、入口合同漂移继续拒绝，不新增 handler。成功后 reconcile 与政策迁移仍是两个单独精确预览/批准操作。

源码态清理仅删除本独立区的 `release/core-release.json` 和 `plugins/paseo/payload/**`，`release-identity.ts` 用既有 `_identity_bytes('')` 规范生成；旧 manifest、37个待删除文件的 hash/mode 和允许集保存在外置私有证据。sync 执行并逐文件核对 common/notices 前后字节不变；不安装 npm 包。

定向测试 `tests/unit/test_release_016_upgrade.py` 从固定 Git 历史生成真正的0.1.2→0.1.3→0.1.4→0.1.5 临时 HOME 链，以实际固定0.1.5 producer/S/tree为前身，再升级到未发行0.1.6 fixture，验证 inventory、显式 rollback、再升级、入口/私文/CK保全、后续窄 reconcile 与普通 policy 只读预览。所有 HOME/探测/确认均为合成；0.1.6 fixture SHA不是正式 S，不复制生产私文，不用 moving HEAD 代替历史0.1.5。

后续由主 Agent 审核并提交源码候选 S，再在 clean pin 执行 `check.py source --source "$PWD" --commit "$S"` 和统一完整回归；本次 dirty 准备树不能冒称 source gate 已通过。通过后才另行按既有文档外置 generate/双份确定性核对/回填三个允许路径、提交 R 和 release verify。本轮不 generate、commit、push，也不升级/协调真实安装，不执行 policy、Claude unlink、Paseo、CK 或 daemon 操作。真实新会话/Host 仍 pending。
