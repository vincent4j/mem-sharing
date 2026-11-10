# Windows 分层验收与保留反例

## 当前产品结果

此DELL Win11 x64、本地NTFS、ZCode3.17.2.9661/WorkBuddy5.9.3.0首次显式预览闭环限定主审通过。当前测试接入已撤销；451字节共享记忆和事务备份保留。一般Windows生产安装/升级、六家、完整R2/W01/W02及发布仍未通过。

导出：`C:\Users\vincent4j\.mem-sharing-preview-exports\cd34775d-58b4-47ed-b976-7d3a1fd42236\MEMORY.md`，SHA256 `899f7b101e4414a41ddeebd0e340bc79b20edbeeb7af0575e7ef8c67d07f63ae`。

| 层次 | 已观察结果 | 不能据此宣称 |
| --- | --- | --- |
| 源码/普通平台 | 保留darwin生产保护；只增显式preview路由；冻结11源码，当前业务源码未随文档整理改变 | 普通Windows安装已开放 |
| Mac | preview定向11/11、原事务21/21 exit0 | 替代Windows文件语义 |
| DELL合成HOME | 定向11/11；源入口和安装后入口生命周期各8项字节/备份/导出/撤销通过；实际硬进程退出恢复，父链junction拒绝 | 任意ACL/metadata恢复或无竞态 |
| 真实安装 | 固定计划摘要2c8077e1…单次apply exit0/committed，14文件逐项回读一致；安装入口显式seed add成功 | 目录存在即客户端加载 |
| 原生客户端 | 用户手动新空项目/新会话，两端先读同词；两端再经Skill/add各写随机记录，另一端全新会话读取；截图词hash、来源、两份committed journal、seed→Z→W指纹及prefix链核对一致 | 原生add内部exit已捕获、完整工具trace已展开、一般六家支持 |
| 真实退出 | 新精确plan单次apply exit0/committed；14原目标absent+1唯一导出，451B逐字节等于退出前和计划后像，主审独立复核通过 | 当前仍安装、正式发布、真实已有私文正文恢复 |

源码/新会话/用户界面/事务原件分层保留，外层PTY退出状态unknown不补造。Windows详细有效需求在[预览PRD](windows-preview.md)，完整未来目标在[平台PRD](windows-support.md)。

## 完整路线阶段与反例

| 阶段 | 保留事实与边界 |
| --- | --- |
| 最初Win32只读 | 历史原生首轮10/14、r2为13/14且exit1；metadata READ_ATTRIBUTES/share0不能保证排他，rename_allowed与named_recheck_detected只证明观察到漂移，race_free=false。历史失败不洗绿。 |
| R1修复 | GENERIC_READ共享冲突正反例和metadata观察分开；junction finally cleanup、硬链接多名称边界及LocalFree返回检查修复。原生17项通过，unit首轮失败/后轮依赖修正分别保留。只读句柄不是写锁。 |
| R2最小只读门 | Mac/Win单测15项、原生7项通过；flags/number_of_links、范围/身份/重查等仅必要条件。SDK编译不是已通过。 |
| 重叠与严格CF门 | 批量ID/祖先覆盖冲突、持有组及独立overlap5/5通过。严格CF轮exit1：1pass/6fail/1unavailable；0x80070001保守未知拒绝，不当非云负例。 |
| 统一拒绝/有界诊断 | 单测7项与C/D共20格诊断记录；unknown/present/inferred/provider未知/未检路径不能整体放行。诊断成功不是Cloud Files能力通过。 |
| 大小写/短名 | DELL敏感目录prepare0→1、普通token拒绝、restore1→0及ID/security/empty回读闭环限定通过；真实短名同ID且被拒绝。不是一般管理员写入原子保证或ACL恢复。 |
| 临时盘符 | v1真实同ID/路径别名拒绝/EXACT清理及preimage恢复限定通过；v2效应后中断缺口修复仅合成8项，不能沿用v1真机身份称v2已实测。映射非进程私有，未清陌生定义。 |
| ACL拒绝失败 | deny READ_ATTRIBUTES未挡metadata open，DACL/owner/group组件同而control8004→8404，native needs_inspection/restore_complete=false；失败根只读保场，不猜RA原因、不补改控制位。 |
| CF v2/v3 | 注册/归属nonce识别及registered_root_refused正例、Register/Unregister各S_OK；v2初始attrs未持久化，不推断原值。v3阶段16→16→0x400030→0x400030→48→48→48，最终空树/ID/security/tag同但attrs不同，原轮needs_inspection保持。 |
| 普通对照/属性补救 | 无CF普通目录建删child三帧16/16/16限定通过，不能回填旧CF缺失baseline或证明旧因果。独立v3补救48→16、身份/security/tag/空树同，ChangeTime变化；仅属性目标通过，不称fullmetadata/CF/R2通过。 |
| SDK/权限研究 | ctypes x64 ABI预检、官方声明核查不等于SDK编译；Mac Windows-target首轮缺excpt.h失败。固定WDK资产下载完成但转产品范围后停止后续编译/RC实验，不自动安装工具链。 |
| 预览首轮依赖失败 | 最初bundle遗漏paths.py，unit exit1；失败独立根保留，补齐后新UUID验证11/11。 |
| 旧安装器回归 | unit21/22、integration4/5；fusion completed与pending_selection、CK pending_selection与skipped两旧断言在HEAD旧installer同样失败。原断言保留，不算全绿，不为此重新开启长链实验。 |

## 原件与可复算性

23份原结构化索引合并到[windows-evidence.json](windows-evidence.json)：每阶段保留原文件名、原始size/SHA256和完整JSON内容，包括失败与unknown。其中旧路径是原证据身份，不是当前路由。三目录的106文件（含当时untracked、原始CK日志/计划/经验）在仓库外全量字节备份，清单机器回读通过：

`/tmp/memsharing-docs-flatten-94cd7dce-a55f-4811-a986-f81a8b561252/before`

主审已核预览11源码与最终29原件、实际截图及hash/前缀链；预览私有原件根：`/tmp/memsharing-windows-preview-d324e408-6f4c-4b32-a490-af1121598e20`。截图、raw SD/SID、私有原文及测试值不搬进仓库；证据索引只存指纹/有限观察。仓库外临时文件可能被系统清理，原tracked文档也可按git历史追溯；不声称临时路径是长期远端存储。

## 后续门

只有选定完整Windows适配、更多客户端或正式发行时再开对应任务，不把已停止的SDK/RC/CF研究作为预览完成前置。旧失败夹具和未知temp不在文档清理中处理。提交、合并、发布、部署分别记录，不用Git成功充当新客户端验收。
