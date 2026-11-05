<!-- context-keeper: session-id=01a1ab40-2a89-7542-bd60-68aacd7ec374 -->
# 修复ContextKeeper固定版本与六家安装

## 追加记录 2026-11-05 18:33:10 +0800

- **用户需求：** 用户截图显示 OpenCode、DSH、ZCode 因固定上游不支持而跳过，要求解决安装；另质疑 Skill 安装为何仍向用户级 AGENTS.md 写入大段内容。
- **根因与证据：** 活动 memSharing `~/.local/share/mem-sharing/scripts/agm_core/ck_install.py` 固定旧 CK 695074ee，仅认旧三家；真实 Skill 链接也指向该旧持久来源。Context Keeper 主仓库当前 7a45d179 已支持六家并采用短入口。首次直接预览被旧源软链接保护拦截，没有强行绕过安装器。
- **本机修复：** 先备份六家规则文件与七个 Skill 位置的存在/链接状态至 `~/.local/share/context-keeper-backups/20261105-install-fix/`；本地 clone 当前 clean CK 至 `~/.local/share/context-keeper-sources/7a45d179e6243c02d5955a803ecb41f3c39fd8ca`，原旧 checkout 保留。核对来源后改接既有五个旧链接，预览并运行新版 `--all --approved`，补齐 DSH/OpenCode 链接与 ZCode/DSH/OpenCode 用户规则。新 checkout origin 设为官方 URL。
- **读回：** 七链接均指新源；六家文件用 `_verify_rule` 逐字节验证块外保全。Codex/Claude 的 CK 块 973→455 字符，WorkBuddy 1084→533；后三家新块455字符。只保留触发入口，细则在 Skill。没有触碰截图中的块外 `å`，没有初始化任何项目记录库。
- **源码修复：** Python CK pin、六家映射、输出排序及共享 Skill 路径去重；Paseo acquisition pin/名单同步；测试与安装 PRD、插件维护文档同步。活动产品核心未直接编辑或重新部署，源码尚未提交/推送，不能宣称后续旧 memSharing 安装入口已升级。Context Keeper 上游源码未改。
- **验证：** memSharing CK 定向35项通过；CK 自身安装器30项通过；真实7a45d179安装器经 memSharing plan/execute 在隔离HOME六家 configured（7唯一Skill路径）。Paseo定向首次21/22通过，一处旧三家名单断言失败，同步期望后22/22通过。`git diff --check`通过。无独立生效合同命中，按安装PRD验证；未执行类型检查、全量回归、客户端新会话或Paseo界面验收。
- **记录边界：** context-keeper 当前源码目录没有初始化记录库，record-path返回未初始化（退出2），未建库或询问；本项目既有获授权记录库保存本轮跨仓库修复事实。未新增编号经验，本轮只验证同一问题。
- **后续：** 等待本轮卸载相关回归完成；正式集成代码部署需按后续实际授权与固定来源流程执行；新会话运行效果仍待验。

## 追加记录 2026-11-05 18:33:50 +0800

- **最终补验：** 卸载CK两模块共16项，7项成功、7项在fixture setUp mkdir已存在目录处报错、2项跳过；取未修改HEAD的ck_install模块原字节在同一测试进程重跑一个失败用例，仍在相同setUp报FileExistsError，确认该夹具失败并非本轮CK适配引入；未扩修卸载模块。不能称卸载回归通过。
- **记录校验：** coverage输出worklogs_unindexed=4、missing_summary=40、missing_session=2、broken_links=55；save-report被memory-keeper中既有six-native-skill-distribution等失效链接阻断（退出2）。本轮日志及主题摘要已落盘，但校验未通过，不改写旧日志或批量修补旧链接。git diff --check仍通过。源码未提交/推送/部署，客户端新会话仍未验。

## 追加记录 2026-11-05 18:52:05 +0800

- **用户最终选择与授权：** 保留完整触发条件、执行细节放Skill，按最终版本提交并推送Context Keeper与memSharing，确保后续安装使用新版。
- **最终入口：** 原177字符入口遗漏触发风险，恢复完整触发并补用户记忆与记录不一致场景；Codex等入口最终345字符，WorkBuddy386字符。仅触发条件与无项目边界常驻，执行细节在Skill。
- **Context Keeper发布：** 修改Skill、安装模板、说明及测试；全量首次150项因manifest旧哈希出现4失败，运行package_skill.py同步manifest后150/150通过；构建ZIP校验通过。6文件提交86af15073c1da7fedddc34342eb10bba64062b73已推送main，不改版本号、不打tag。
- **本机来源同步：** 创建86af150持久clean Git来源并保留旧来源；七个已验证Skill软链接改指新来源，链接旧值备份在~/.local/share/context-keeper-backups/20261105-final-source-sync；避免以后调用旧Skill又生成455字符模板。用户规则正文此次未重写。准备来源时一次remote set-url误在父目录执行，Git以非仓库拒绝；随后在新checkout内正确设置官方origin，未改其他仓库。
- **memSharing最终集成：** Python pin、Paseo获取pin及相关文档/测试统一固定86af150；六家支持、上游顺序、共享Skill路径去重保留。原远端README提交45eb3189先ff合入，未覆盖内容。真实固定上游通过memSharing plan/execute在隔离HOME成功配置六家、七唯一Skill链接，并读回最终345/386字符块。Paseo定向22/22通过；Python35项定向补跑中，完成结果见后续追加。
- **提交前PRD收尾：** 使用PRD Distill；无独立生效合同命中，安装PRD与固定pin和六家路径/排序/去重一致；check initialized且errors/warnings为空，scan无inbox。无UI改动，不重装Paseo插件或修改活动memSharing产品核心；未来Git main源码新安装使用新pin，既有产品部署不会被Git推送自动替换。客户端新会话未验，旧卸载夹具失败仍保留原边界。

## 追加记录 2026-11-05 18:52:16 +0800

- **最终补跑结果：** CK安装定向35/35通过（62.663秒）。Python源码pin、Paseo pin、文档与相关测试均固定86af150；git diff --check与PRD结构检查通过。下一步按已明确授权提交推送本次11路径，随后以远端分支SHA核对推送结果。
