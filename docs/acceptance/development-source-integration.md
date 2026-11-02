# 开发源码整合候选（未发行）

本候选从本地工具提交 `2f739b4c8b3b7fa63f0e287093ff069f099513a5` 建立；该提交已经包含固定产品 R `ef742a2843edb3961d7bf3c71e8ca9cc921c5d1d`、独立 staging 退役工具 `368faca9d756a447bee25c202de02028f0023298`、两类历史备份严格识别和显式 DSH 单 token 归还路径转换，不重复移植这些差异。

统一六家顶部入口来自 `guaji-unified-layout-r2-udch2ny4/frozen-r2.json` 的十路径冻结增量，基线为上述 R；其中 operations 文档与工具文档均为基线末尾追加，整合保留双方全文。其他九路径保持布局冻结字节。历史 SOURCE/TARGET 合同不变，新 unified handler 的四文件 after_contract 必须继续等于冻结字节，不接受重算任意来源充当信任根。

源码态删除旧 `release/core-release.json` 和完整 `plugins/paseo/payload/`，release identity 使用当前生成器 `_identity_bytes('')`。尚无新版本、新 S/R 或正式载荷；不得以此候选替换现装同版产品。

## 发行闭包与独立工具

现有生成器的 `managed_source` 自动纳入所有已跟踪 `scripts/` 普通文件。因此 staging_retirement、uninstall_compat、entry_layout、user_entry_layout 模块和两个独立 CLI 都必须由 root 随源码提交，不能只提交路由或测试。当前规则无需扩大源码 gate 或修改生成器；完整 clean/pinned source gate 只能在 root 提交稳定候选后运行。

独立 CLI 的 `--tool-commit` 是调用者信任的外部固定工具 pin；发行 payload 携带工具代码不等于已安装 C 可冒充 clean Git 工具来源。继续使用公开 CLI 与真实安装身份/活动内核校验，不绕过绑定。将来 S 提交后再由 root 决定版本、统一完整回归与发行，不预造 handler 版本目标。

## 验收事实与剩余边界

现机完整核心卸载、五产品根 absent、固定 0.1.6 empty/fresh 新装的真实报告：
`/Users/vincent4j/qa-evidence/memsharing-approved-real-fresh-install-keeco1p2/report.md`。
该记录证明核心链及六家归还/用户正文/Context Keeper保全；没有将本候选布局应用到现机。

Claude 检测仍 unknown；Paseo 插件未重装，原 host completion metadata pending；原生新会话、页面与运行验收 pending。宿主另一个插件 paseo-cafe 版本/路径漂移尚未归因。不得将 source/static/临时 HOME 测试改称真机 runtime 通过。归还副本未自动导回 fresh 公共库。

主区用户与验收文档 dirty、Context Keeper 记录全部留原处，本候选不复制或改写；既有验收四文档与历史 9fdfaba 比对结果在外置交付证据中逐项列出。阶段经历由 root 核验后按已安装 Context Keeper Skill 统一安排，避免跨会话覆盖。

## root 下一次集中决定

核验本候选精确差异后，由 root 决定源码提交 pin、一次统一完整回归和后续发行版本/S/R。Claude/Paseo 恢复实际使用、章教授真实运行验收和发布清单分别进入后续阶段，本候选不执行这些真实写入。
