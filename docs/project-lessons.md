# 可复用的验收与恢复边界

从旧项目经历中提炼，原件在仓库外快照；这些经验只在已证范围内有效，不赋予真实环境写入授权。

## CK-PASEO-001：running不等于业务闭环

已验证范围为既有macOS/Paseo0.13.2开发候选与memSharing0.1.4接入。CJS loader曾丢失源码位置，ready时payload仍missing；修复后活动旧CLI又拒绝preview。应先查实际持久payload/编译期摘要，再由真实插件生成项目预览确认所调用程序支持批准合同，按精确升级处理旧版，不去掉预览或改台账冒充成功。接入后另启新会话读用户/项目记忆。全新机器缺依赖、其他provider/平台与未来loader版本均未由此证明。现行插件分层结果见[插件验收](plugin-adapters/acceptance.md)。

## CK-WIN-001：恢复组件不等于恢复全部metadata

仅Windows本地NTFS合成夹具及后续设计参考：DACL/owner/group字节相同而AUTO_INHERITED control仍异；CF注销S_OK后目录attrs异于原像；独立按句柄属性补救达到attrs16、身份/security/tag/tree同，但ChangeTime变化。写前须明确可设置组件、可复算原像和恢复归属，按阶段存ID/security/attrs/tag/tree/四时间；API返回、组件回读与整体承诺分别判断。缺原像不猜值，不改断言洗失败；另行有界补救需绑定具体节点/原像/源码并审核，系统自动更新字段单列。不能据此宣称任意ACL/control位可还原、真实HOME写安全或一般Windows准入。证据见[Windows验收](windows-acceptance.md)与[合并指纹](windows-evidence.json)。

## 跨阶段共通边界

- 语义由Agent理解、范围由用户选择、执行器做精确修改；保存、接入、配置、模型读取和业务验收不混为同一完成状态。
- 冻结来源与当前进程/真实版本核验后采用旧经验。错误、限流或unknown保留边界，不盲重试、重启daemon、提权或清理陌生进程。
- 私文按字节保全；BOM/CRLF或模式差异不能靠重编码和放宽fingerprint掩盖。backup/receipt/producer链不足或第三态编辑停止恢复。
- 固定批准范围内连续完成，不把可验产品目标扩成所有底层能力的穷举认证；产品收敛必须同时写清更窄承诺和仍未验证项。
