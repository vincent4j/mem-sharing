# Windows 双端首次预览 PRD

## 产品目标与验收状态

让此DELL上的ZCode、WorkBuddy在不搬迁旧记忆的前提下，读取同一份用户明确新增的公共记忆，并可撤销本次接入、保全新增内容。此预览安装→两端原生新增/新会话跨端读取→退出导出已限定主审通过。

仅实证DELL Win11 x64、本地NTFS、Python3.14.10、ZCode3.17.2.9661、WorkBuddy5.9.3.0。测试接入现已撤销，14个目标文件恢复为安装前不存在状态；451字节共享记忆导出保留。不是正式发行、通用Windows或完整R2/W01/W02通过。边界及旧失败见[Windows完整目标](windows-support.md)和[验收结果](windows-acceptance.md)。

## 范围

- 仅当前用户、两家、首次显式预览；仅新增公共内容和带标记的接入，不迁移、融合、删除旧记忆。
- 不升级旧安装、不覆盖未知安装/同名Skill，不支持其他客户端、Linux/WSL、网络/云盘、链接/reparse/硬链接、大小写敏感目录、特殊权限或自定义配置根。
- 保留普通生产安装/升级darwin保护和原平台表；版本/payload不因预览修改。没有一切同步软件均不存在的机器证明，也不将支持声明翻译成provider验证通过。
- 不自动修改项目规则、初始化Context Keeper、登录客户端、提权、注册云根或改卷策略。它复用字节编辑和事务原语，不复制融合引擎。

## 用户流程

1. 只读核实际客户端版本、配置根、文件与父链、安装占用及固定源码依赖。目录存在不能代替客户端安装或新会话读取证据。
2. 生成包含HOME、源码hash、解释器、每项原像/目标字节、允许路径和外置备份位置的精确计划。显式输出计划文件；无批准不改目标。
3. 用户/已授权执行者批准计划摘要。执行前重算来源和现场，漂移拒绝重新预览；不覆盖、不重试安装。
4. 写入持久核心、两家普通薄Skill及入口、公共文件和最后回执；原私有字节保持为前缀。逐文件回读，备份/journal留代码目录外。
5. 用户明确要求新增时由原生客户端读取mem-sharing Skill，并通过预览add追加公共文件、同步回执hash。公共正文发生外部漂移时保留并拒绝覆盖。
6. 两家独立空项目/全新会话读取；每家显式新增后，另一家全新会话再读取。测试值不放读者提示或继承历史；模型手动猜测、Paseo直接读文件不能替代原生证据。
7. 退出先导出当前公共正文并回读，再撤本次入口/代码/回执；原像不存在则恢复不存在，原文件存在则按字节恢复。外部编辑或陌生文件保全并拒绝；不自动融合归还或删导出。

## 固定数据与允许路径

| 对象 | 位置/含义 |
| --- | --- |
| 公共正文 | `<home>/.mem-sharing/memories/MEMORY.md`；显式新增按UUID章节追加 |
| 预览回执 | `<home>/.mem-sharing/preview-receipt.json`；schema `mem-sharing-windows-preview-1`，绑定HOME/安装UUID/源码hash/四入口原像/installed hash/公共hash |
| 用户入口 | `.zcode/AGENTS.md`与`.workbuddy/MEMORY.md`，只追加唯一`mem-sharing:windows-preview`受控块；BOM/CRLF及私文原字节保留 |
| Skill | `.zcode/skills/mem-sharing/SKILL.md`与`.workbuddy/skills/mem-sharing/SKILL.md`，普通文件而非联接；只提供读取、显式add和精确退出，无融合/升级菜单 |
| 自有代码 | `<home>/.local/share/mem-sharing/scripts/`下固定8文件：wrapper、agm_core的__init__/entries/transaction/windows_preview/windows_native/platform_diagnostics/paths |
| 备份 | `<home>/.mem-sharing-preview-backups/<事务ID>/`；原始字节、前后fingerprint和manifest |
| 导出 | `<home>/.mem-sharing-preview-exports/<退出UUID>/MEMORY.md`；先写先核，内容与退出前公共正文逐字节一致 |

原像和计划可能包含私有正文，应留在用户批准的本地位置，不进仓库或聊天。源码与公共数据之外出现未知文件/目录时不递归删。空目录、备份、导出及外置冻结源码保留。

## 接口与失败行为

显式入口是`python.exe -I -S -B scripts/windows_preview.py`；完整源码入口也可用`scripts/install.py --windows-preview`。使用实际已核解释器完整路径，不假定python3/PATH，参数以argv传递。

| action | 主要参数 | 行为 |
| --- | --- | --- |
| plan | `--home --source --output` | 首次安装精确预览；显式计划文件，exit5/approval_required |
| apply | `--home --plan --plan-sha256` | 校批准摘要并重生成方案，完全一致才执行；成功exit0/committed，失败exit2且返回manifest定位 |
| add | `--home --text` | 用户显式新增动作；非空UTF-8，最多64KB；不修改旧原文；回执最后提交 |
| exit-plan | `--home --output` | 校源码/四入口和回执，唯一新UUID导出+精确撤销 |
| recover | `--home --manifest` | 仅同HOME预览事务，校备份/前后态/路径；未知漂移保场，不自动抢占旧锁 |

事务是合作writer lock和逐文件替换/快照复核，不是OS原子CAS，不保证任意metadata逐位恢复。硬崩溃恢复使用代码外冻结入口；操作人须先确认原进程退出和原锁身份，再显式处理旧锁。异常回滚只接受已记录before/after；第三态不覆盖。恢复失败留下manifest、原始错误和定位，不用重装抹平。

## 必需验收标准与当前证据

- 计划批准、源/现场漂移、未知Skill/旧安装、父链链接及外部编辑均拒绝且原内容保留。
- BOM/CRLF/私文、导出失败、KeyboardInterrupt、真实子进程硬退出和回放恢复有实际字节断言。Mac/DELL定向各11项通过，原事务回归21项通过。
- Windows源入口和实际安装后入口分别完成CLI生命周期；新增、退出使用安装后的程序并成功撤销自身文件，各8项读回通过。
- 实际安装14项逐文件与批准一致。原生两家初始读取和两方向新增/全新会话读取由用户截图及真实committed add journal、词hash、连续旧文前缀链复核。native add内部exit未捕获，未称全量工具trace。
- 实际退出apply exit0/statuscommitted；15路径逐项核：14原目标absent、唯一451B导出；导出与退出前公共bytes及计划后像逐字节相等。四native原先缺失，不把它说成真实已有私文恢复；私文原像恢复属合成证据。
- 外层PTY exit未知如实保留；检查通过不等于已发布。首轮依赖闭包遗漏paths.py的失败和两个旧安装器回归失败均保留，不改旧断言追绿。

详细来源、指纹和失败在[Windows验收](windows-acceptance.md)与[合并证据](windows-evidence.json)。普通平台全量、六家、迁移/升级和特殊环境不从本预览结果推定通过。
