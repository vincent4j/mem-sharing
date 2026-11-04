# 六家原生 mem-sharing Skill 分发

范围：源码与临时HOME合成；不写真实HOME、不启动模型/GUI。已装bce仍为旧两家分发与旧描述，不能称本轮已部署。

| 执行器 | 安装默认路径 | 本次发现依据 |
| --- | --- | --- |
| Codex | ~/.codex/skills/mem-sharing/SKILL.md | 沿用已实现与此前Codex原生picker证据；本轮不重跑模型。 |
| Claude Code | ~/.claude/skills/mem-sharing/SKILL.md | 沿用既有原生Skill目录合同；本轮不启动Claude。 |
| WorkBuddy | ~/.workbuddy/skills/mem-sharing/SKILL.md | 本机app.asar公开main/app-instance.js把用户目录传为CODEBUDDY_CONFIG_DIR；公开cli/dist/codebuddy-lite-wb.mjs的resolveCliHomeDir、PathUtils.getHomeSkillsDir、getSkillScanDirs(user)及SKILL.md/frontmatter解析。默认根由桌面配置解析为.workbuddy；重定向拒绝。 |
| DSH | ~/.dsh/skills/mem-sharing/SKILL.md | 本机DeepSeek Harness.app app.asar的@deepseek-ai/dsh-home-paths/index.js（defaultDshHome/resolveDshHome）与dsh-skill-filesystem/index.js（roots:join(dshHome,skills)、SKILL.md/YAML解析）。DSH_AGENTS_HOME影响另一共享根，不影响此自有根。 |
| ZCode | ~/.zcode/skills/mem-sharing/SKILL.md | 本机Resources/glm/zcode.cjs：resolveDefaultSkillRoots(Dpo)默认homedir；skillRootsForBase(ySn)组合.zcode/skills；scanSkillFilesUnderRoot(Lpo/Q4e)扫描SKILL.md。 |
| OpenCode | ~/.config/opencode/skills/mem-sharing/SKILL.md | 章教授本轮核[官方V1](https://opencode.ai/docs/skills)、[V2](https://opencode.ai/v2/docs/skills)：全局config目录；两字段兼容，不推断同名覆盖优先级。 |

上述为静态发现合同与分发依据，不是四家真实新会话已发现/运行证明。仅把路径写进记忆引用不算原生Skill。WorkBuddy本机公开源证据与DSH摘取的公共包模块只暂存/tmp/msf-*-asar-index.json、/tmp/msf-dsh-dsh-*-index.js；未读取私文、凭据或历史会话。

实现复用现有事务/台账：固定六家自有根经paths.native_skill_path统一供allowed_user_paths、user_entries及uninstall使用；薄入口frontmatter name=mem-sharing、description为用户指定句，正文指向持久C/SKILL.md。按selected分发；默认仍选择经核实installed全集。未选不预建，不写共享.agents/skills。后装只补选中入口，公共文件不重建/重复融合；私文整理仍单独提案批准。未知同名、受管漂移、父/叶链接拒绝且零写。整机卸载遍历台账撤全部owned薄Skill，私文和其他Skill保全；既有恢复引擎处理文件与目录，不增加恢复协议。

边界：DSH_HOME/OpenCode既有默认根保护保留。WorkBuddy的WORKBUDDY_CONFIG_DIR、CODEBUDDY_CONFIG_DIR非默认根、非默认数据目录名或实例号拒绝，不回显原值；明确默认绝对根可用。自定义产品配置根与各宿主实际环境仍不承诺。ZCode本次所核Skill根由homedir构造，不从ZCODE_HOME推断。

合成验证：test_six_native_skills覆盖默认六家/未选择、Codex先装后五家逐个增量（含所漏四家）、公共字节/mtime不变、重复changes[]/fusion=null、未知同名/链接/漂移零写、WorkBuddy重定向不泄露值、全机卸载保私文且撤六Skill，以及after_entries故障后的正式回滚恢复。相关旧用例把“不得创建DSH/OpenCode skills目录”改为核验真实受管薄文件；未登记WorkBuddy规则块测试移除干扰的fixture薄Skill后仍要求原始entry_layout_conflict，不弱化拒绝语义。

首次相关67测试3F/1E日志/tmp/msf-six-native-regression.log保留：两项为旧“无Skill”预期，一项是fixture未登记薄Skill先行拒绝，一项是新增恢复测试调用签名/异常断言写错。修正后的终态结果见下方追加，不拼接为单轮全量。真实分发/原生发现/实际调用均待用户后续验收。

本窗口终态：修后六家/原有入口相关67项41.905秒全过，日志`/tmp/msf-six-native-regression-fixed.log`；registry相关54项4.636秒全过，日志`/tmp/msf-six-native-registry-regression.log`。安装幂等+entry-layout组合18项59.190秒，**1F/2E，未全过**（日志`/tmp/msf-six-native-transaction-regression.log`）：LegacyUpgradeTests两项被现有冻结旧→新合同拒绝（no exact supported release conversion），另一项断言候选当前user_entries.py必须等于旧冻结hash，因本轮源变更不相等。未删除或重算冻结保护来宣称通过，需主审核后补明确候选合同/fixture衔接，不能以拒绝代替支持完成。

主审核指出链接分支只有assertRaises，尚缺不跟随symlink的前后快照；因此当前链接拒绝已证实，链接场景零写仍缺断言，不以其他冲突快照冒充。未知同名/受管漂移的前后零写、公共保全、整机卸载与六入口回滚已通过。全量未跑；源码与合成尚有上述收尾，真实安装/发现/调用均未验。到08:51:40安全停，无运行进程待收、不commit/push。

## 第二段：历史失败归因及链接闭环

干净基线28b5508a的user_entries.py sha=`5c7418f888ebf03541bc32bd442b5ef913db45bd78c8ceab79592f4c94f02246`，本就不是UNIFIED_ENTRY_AFTER冻结的`8e22f8876c8437a806ecd1cdc0fa8308c05c317a348e01166a3a0a37b95c62d4`。在独立clean基线checkout原样运行LegacyUpgradeTests，3项5.672秒复现同一1F/2E；不是本次六家Skill引入。

找到固定历史候选`76d3fc50f42d4ad77597a65217d51e9ff95ac4aa`，agents.json/user_entries.py/user_entry_layout.py/entry_layout.py四个Git原始blob全部等于原安全合同。该历史clean checkout原样运行同3项，9.452秒全过，包含旧转换正向、篡改后重hash拒绝、篡改运行kernel拒绝。证明旧保护及当时支持路径未损坏；不能据此声称当前可变源码支持此旧转换。采取明确隔离基线3项的方案，不改产品历史白名单、不动态洗hash、不删/skip旧断言，不新建升级兼容。精确证据`/tmp/msf-native-legacy-candidate-evidence.json`及两份log；历史和基线临时checkout路径在该JSON/`/tmp/msf-native-baseline-path`。

新增四家叶子链接和父目录链接：os.walk(followlinks=False)+lstat记录HOME完整节点类型/mode/mtime/inode和链接文字，拒绝前后逐项相等；链接指向的HOME外文件还单独比较bytes/mtime，避免跟随链接的快照掩盖目标写入。单项7.064秒通过（`/tmp/msf-six-native-link-zero-write.log`）。这补齐首轮声明缺口；没有放宽文件/目录链接保护。

本段仅修改新增测试的快照断言，生产源码沿用首段；当前新功能与原有非Legacy布局/台账的单轮冻结回归正在收终态。冻结10文件hash `/tmp/msf-six-native-round2-before.json`，运行期间未改源码或测试；后续结果单列，不拼成完整unit全绿。

最终当前快照受影响回归：**136项、100.248秒全部通过**，`/tmp/msf-six-native-final-affected.log`。136个不同test ID、10个冻结实现/测试/产品文档文件运行前后hash完全一致，证据`/tmp/msf-six-native-round2-final-evidence.json`。覆盖六家新分发、原用户入口、DSH/OpenCode适配、安装幂等、非历史布局、台账及本轮故障回滚。排除的仅为已在基线同样失败且在固定历史候选通过的LegacyUpgradeTests三项；未声称全量unit/integration通过，也未跳过/修改其测试代码。生产历史转换合同及白名单逐字节未修改。

第二段收口：新功能和当前受影响范围通过，可交主审核源码；当前仓库仍28b5508a+本次dirty，真实安装bce未改变，本轮不部署。原生文件分发为合成证据，四家真实发现/新会话调用仍未验。所有runner均已终态、无待收进程；不commit/push、不模型/GUI/真实产品写入。基线与历史只读临时checkouts和证据保留供复核。

## 已批准真实部署（2026-11-04 09:10–09:20 UTC）

本节更新前述“尚未部署”边界。用户明确要求提交、推送、合并main及部署；主完成固定并推送`0456ed888dffdc8763cdc4ccd03489ff38bf6f6b`，执行者仅部署，不commit/push。新0700长期保全根：`/Users/vincent4j/.mem-sharing-review-backups/six-native-20261104T0911Z`，clean detached固定checkout及全部旧备份保留。该clean源关键分发/增量测试2项15.683秒通过（`/tmp/msf-six-native-deploy-clean-tests.log`），不是重跑全量。

部署前核现机bce C完整树与owned对象：Claude reused import整文件receipt漂移，原因未知；canonical公共import为唯一首行且fallback span精确匹配登记。主再次确认仅按这些已证产品片段处理，完整备份当前bytes/mode、副本逐hash校验、写前重读一致后才清理；未将整文件视为产品所有权，也未改旧V指纹。四新增Skill目标absent且祖先真实，备份后、写前再次复核；无同名覆盖。六家私文其余字节/mode/inode保留。四产品根按精确库存清理，sources原absent照实记录；这是授权手工清理后fresh，不是旧正式卸载成功。所需恢复副本与映射在新manual-manifest.json，交回前再次逐一核sha/mode。

正式fresh预览79项、六家effective、六个原生Skill文件，内置plan_sha256=`84b796a503ff87dca7d6315cf2be804c558d8ce3ab8ee37a5675ef649a2f6b59`。同operation重预览逐对象全等，按本次真实部署授权及主对漂移片段审查引用执行精确批准文件；未借用内容融合授权。实际rc0/completed，六家connected，fusion=pending_selection，CK=skipped。未执行新增私文融合/卸载/CK操作。

真实读回结果：

- C49文件逐一hash匹配；V schema3/complete/0.1.7，source=0456，tree=`c3691f4f794bdc033890d6792bd9fcef230a63d582ec69c2c822f354cb963121`。13受管对象指纹全匹配，需要恢复manifest的对象均有实际材料。
- 六家native Skill全文均等于预期：name=`mem-sharing`，description=`多 Agent 记忆共享与融合，给你的每一个 AI Agent 同一份记忆。`，正文指向持久`~/.local/share/mem-sharing/SKILL.md`，无临时checkout引用。当前文件分发层已落地，四家不再只是公共记忆指针。
- 六家原生文件安装事务before备份逐一等于本次清理后baseline，actual diff仅insert；私文与权限保留。公共六规则按本次备份原字节恢复一份，sha仍`86d780999196a539882b7c985b9a36622afec00548d361d21f20b8f16db79d4c`；新MEMORY只加有效单链接，未用旧控制模板覆盖，公共仍两md。
- 正式**已装C无参**重复安装rc0，实际“已安装，已接入。”、changes=[]、approval_plan=null、fusion=null；118相关文件sha/mode/mtime_ns/inode前后相同，完整相关文件集亦相同。卸载预览后再次复核118文件全同。
- 正式卸载仅preview：rc5/approval_required、无error，六个Skill各有detach→absent行动（摘要after精确等于absent结构的hash），所需backup闭合、目标backup未创建；没有执行卸载，留用户验收。
- Paseo daemon身份/启动时间及8插件列表前后全等；CK、其他Skill、账号/凭据与业务项目未改。无模型或GUI调用。原生客户端新会话发现/实际调用仍由用户后续验收，不用文件存在或静态合同代替。

私有证据均在新0700根且文件0600：product-inventory.json、manual-manifest.json、products/native/reviewed-public、fresh-install-preview/approval/actual.json、post-install-verification.json、repeat-install-actual/verification.json、uninstall-preview-actual.json、six-native-deploy-verification.json。该最后证据含六文件路径/hash、13对象指纹、六项absent-detach覆盖、118零写与文件集、Paseo不变及保存副本重核。辅助脚本/log在`/tmp/msf-six-native-deploy-*`，不是新增产品协议。所有命令/runner终态，无待收进程；本轮唯一仓库写为本说明追加，未改源码或部署旧/dirty源。
