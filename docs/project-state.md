# 项目现状与后续工作

## 当前确认状态（2026-11-10）

- DELL Windows双端首次预览已限定主审通过：安装、两端原生新增/新会话跨端读取、退出保全；测试接入已撤，451B共享正文及备份保留。见[验收](windows-acceptance.md)。
- 只覆盖此机器/两家/普通本地NTFS/首次显式预览，不是完整Windows或一般六家支持。完整R2/W01/W02部分通过，旧ACL/CF失败与未知状态保持。
- 普通安装/升级仍保持darwin保护；本次只做源码与文档收尾，不发布、不重新安装、不改真实HOME/daemon/凭据或上游Context Keeper。
- 用户已明确授权巴克队长收尾验收、提交推送、合并main。文档归并时feature HEAD为58c47fd587de7208a891279cb425c2c819bb1925；Git结果待主审实际执行，不预填虚构commit。实际结果以git历史及远端读回为准。

## 本仓文档与记录约定

用户明确删除旧的validation、context-keeper、prd三目录，所有有效材料直接放docs根。入口是[文档索引](README.md)；本页维护当前进度，[项目历史](project-history.md)保留有用阶段结论，[经验边界](project-lessons.md)保留可复用判断。旧分阶段原件已在仓库外备份，不另建archive替身。

本仓已退出原目录布局的PRD Distill/Context Keeper自动初始化与桥接；不要运行init、ensure-bridge或旧save-report来重建目录。技能仍可用于整理和语义核对；工具返回not_initialized是本仓按用户要求退出后的预期，不冒称结构通过。不改全局Skill/上游CK，其他项目的默认经历库行为不变。

## 继承未闭合事项（旧记录快照，未在此次刷新环境）

以下仅保留有效未完范围及来源；旧版本/部署身份属于当时记录，不能直接充当今天宿主状态。已完成的小步骤不重新开工，重启相应任务时先核当前文件/版本和用户授权。

- 六家原生Skill客户端验收；状态：源码0456ed88已提交推送合入main并部署，文件/CLI层通过；触发：用户自行验收；完成：客户端发现调用、正式卸载再全新安装完成；证据：[部署记录](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/six-native-skill-distribution.md)。136受影响测试通过，三项旧升级测试基线已有失败，不称全量通过。
- 展示文案与命令名称真实宿主验收待办；状态：进行中（源码修改与静态核对完成，真实宿主显示待验）；触发：用户批准重新安装插件并开展真实宿主验收时；完成：真实 Paseo 加载后展示文案、macOS 说明、原理图与九个命令名称显示有证据；证据：[展示文案日志](project-history.md)、[补齐日志](project-history.md)。
- 正式发行与跨平台/新会话验证；状态：未开始；触发：用户另行批准新发行或重新安装；完成：固定发行输入、目标平台和真实客户端验收有证据；证据：[收口日志](project-history.md)。本轮本机卸载、六家归还纠正及源码合入 main 已完成，不再占卸载待办。
- Paseo 插件即装即用补齐；状态：0.1.11本地S/R提交及插件替换running完成；S=9b131917、R=c40cc63f，source/release门禁和双生成通过，49核心文件闭包一致，其余8插件未变、未推送；触发：继续真实业务验收时；完成：新候选UI、融合/新会话、缺依赖首装、卸载恢复分别有证据，上架独立处理；证据：[执行日志](project-history.md)。
- 双桌面端原生运行补证；状态：本轮交付结束，等待用户回到电脑前人工验收；0.1.3真实升级及双端接入完成、五家静态connected、586/74测试与私文/幂等通过；CUA双端绑定超时，原生验收blocked/pending；触发：用户主动恢复并人工操作；完成：两款原生新会话用户/项目规则读回、只读Skill实际加载有独立证据；证据：[交接日志](project-history.md)、[人工接手说明](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/desktop-agent-contracts.md#人工接手与本轮收口)。
- 公共记忆分层与独立执行器接入；状态：源码/合成验证及本机0.1.1→0.1.3迁移已完成；触发：用户已批准实现；完成：新安装与已有用户迁移、无 Codex 组合、私人内容保全及恢复验证通过；证据：[实施日志](project-history.md)。
- M4-10 真实运行补证；状态：暂停（用户明确暂停）；触发：用户恢复对应范围后；完成：WorkBuddy 新会话、CK 实际尾步/首次激活、自动入口、四会话接力各有独立证据；证据：[当前判定](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/m4/m4-10-runtime/verdict.md)。0.1.1 已部署和静态通过不替代这些验证。
- 发行冻结与发布；状态：0.1.2候选成果已进入提交0f690ef，本轮另做公共记忆分层开发；触发：新合同实现和验收完成后；完成：固定新候选来源及精确升级请求，提交、push/tag/部署按各自授权执行；证据：[本轮核验日志](project-history.md)、[上一轮发布清单](https://github.com/vincent4j/mem-sharing/blob/4fb22c0988426c06183d9f4faa71b7b00747a546/docs/acceptance/m4/m4-10-prep/release-checklist.md)。本机已由ea55373升级0.1.3；旧清单待提交措辞是上一轮状态，本轮未打tag或发布。
- M2-08 两项目复制与新会话验收；状态：进行中（部分通过）；触发：用户恢复真实验收后；完成：审核 WorkBuddy 实际读回证据后关闭三家验收；证据：[重跑日志](project-history.md)。
- M2 收官遗留（M2-09 后）；状态：待办；触发：后续迭代或用户要求；完成：各子项随后续里程碑处置或由用户裁定的取消；范围：Claude 显式走 Skill/resume 的程序化验证、卸载/重装周期换行重排的可选打磨（AGENTS/CLAUDE 块尾换行迁移、WorkBuddy MEMORY.md 每周期 +1 换行）、AGENTS.md 构建/测试占位文案补充、Windows/Linux 环境具备后的平台扩展；证据：[M2-09 日志](project-history.md)、平台矩阵（原路径 ../acceptance/index.md；原件见外部备份）。
- M1 整体验收补证；状态：阻断；触发：取得 WorkBuddy N1/N2 运行证据并另行安排标准无污染接力；完成：三家负向齐备及 P2/P3 流程缺口关闭；证据：[收口日志](project-history.md)。

## 继续顺序与授权边界

先完成本次文档归并、主审提交/推送/main合并；之后若用户需要可日常安装的Windows预览交付，再固定发行输入/打包/安装说明，并明确保留安装使用。其他客户端、升级旧安装、迁移融合及特殊目录需独立范围，不能自动追加。发布和真实部署另行授权。

当前测试导出：`C:\Users\vincent4j\.mem-sharing-preview-exports\cd34775d-58b4-47ed-b976-7d3a1fd42236\MEMORY.md`。四个真实native入口原先均不存在，当前恢复不存在；BOM/CRLF既有私文恢复是合成证据，不扩大为真实私文内容验收。
