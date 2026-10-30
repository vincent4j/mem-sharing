# M4-10 隔离首装执行清单（预备，未执行）

编写基线：`dc0b38f`；实际执行前重新冻结 clean 候选发行 S。依据 [审计 §5](../../../plan/audit-rulings-20261030.md)、[裁定 §21—§26](../../../plan/decisions-m4.md)、[安装剧本](../../../../INSTALL.md) 与 [设计定位及安装章节](../../../../DESIGN.md)。冲突采用后续裁定；§26 已撤销开发版升级承诺。

本文件仅备操作与判定，不授权现在执行。**本机真实 HOME 不受触碰**：不安装、不迁移、不清旧链接、不复制个人配置或凭据。M4-10 实际时机、隔离环境与本机 v0 迁移由用户拍板。以下命令只供届时已批准的测试环境使用，尖括号必须先替换；不得整页盲跑。

## 环境预置与合成 HOME

两层分开验收：A 为合成 HOME 安装内核演练，不启动真实执行器；B 为独立 macOS 标准测试用户或可回滚 VM 中的真实首装与新会话。仅设置 HOME 不隔离系统用户目录解析、钥匙串、daemon、配置和日志，A 不能代替 B。缺依赖自动安装只在 VM／专用测试机验证；独立用户仍共享系统依赖。

| 步骤 | 命令／动作 | 预期及停止条件 | 证据落点（私有，不进 Git） |
|---|---|---|---|
| 0 门禁 | 审阅 M4-09 最终结论、§25 核销表、§26 重构结果；用户确认环境和范围 | 候选来源、恢复工具、待测接口已冻结；未完成则 pending，不安装当前并行工作区 | `00-scope.md`：批准引用、候选完整 SHA、SemVer、schema/structure、清单哈希 |
| 1 身份 | 在独立测试用户／VM 终端运行 `id -u`、`id -un`、`printf '%s\n' "$HOME"`、`dscl . -read /Users/"$(id -un)" NFSHomeDirectory`、`pwd -P` | UID 与系统 home 属于测试身份；日常 HOME 不挂载、不链接进测试环境；身份不明停止 | `01-identity.txt`，环境／VM 快照编号；仅留测试身份 |
| 2 构造 A | 在上述隔离终端执行下方命令 | 创建私有空 HOME；不复制日常 `.codex`、`.claude`、`.workbuddy` 或 auth；不伪造 installed 信号 | `02-home.md`：绝对路径、权限、空树记录 |
| 3 准备 B | 测试用户自行安装／登录执行器；核验其版本、help、实际配置／缓存／日志路径和进程 UID | 不复用日常 daemon／钥匙串；登录验证由用户完成；不能合法使用则 blocked。页面操作委派章教授，inspect → action → verify | `03-executors.md`：三家版本、installed/absent/unknown、配置根依据 |

```bash
# 仅在已批准隔离终端中构造 A；不 export HOME，不改变当前登录会话。
umask 077
PREP_RUN=$(mktemp -d /private/tmp/mem-sharing-m4-10.XXXXXX)
PREP_HOME="$PREP_RUN/home"
PREP_EVIDENCE="$PREP_RUN/evidence"
mkdir -m 700 "$PREP_HOME" "$PREP_EVIDENCE"
printf '%s\n' "$PREP_HOME" "$PREP_EVIDENCE"
ls -ld "$PREP_RUN" "$PREP_HOME" "$PREP_EVIDENCE"
```

A 的每条产品命令须使用 `env -i HOME="$PREP_HOME" PATH="<已核验的最小PATH>" TMPDIR="$PREP_RUN" PYTHONDONTWRITEBYTECODE=1 <绝对Python路径> ...`，不用继承的执行器根重定向变量。执行前只读核验冻结实现是否还解析系统 home／绝对用户路径；不能约束写集就停止 A，转为待批准的 VM 路线。A 无真实安装执行器时如实记录无目标／pending，不能造目录模拟三家通过。

## 安装、检查与证据

以下命令模板以 B 的隔离登录 HOME 为准；A 使用上方每命令包装。`PREP_EVIDENCE` 在 B 中须另建于测试用户私有目录，`PREP_SOURCE` 指已提供的 clean 冻结 checkout。所有重定向仅写私有证据目录，保留退出码；非零先解释报告，不自动重跑。

| 步骤 | 命令／动作 | 预期与判定 | 证据落点 |
|---|---|---|---|
| 4 来源 | `git -C "$PREP_SOURCE" status --porcelain`；`git -C "$PREP_SOURCE" rev-parse HEAD`；`git -C "$PREP_SOURCE" remote get-url origin` | clean、完整 SHA 与批准 S 一致；官方 URL 为 `https://github.com/vincent4j/mem-sharing`。获取网络材料委派章教授，本物料不下载 | `04-source.txt`、发行逐文件清单与哈希 |
| 5 前置树 | `ls -ld "$HOME/.mem-sharing" "$HOME/.local/share/mem-sharing" "$HOME/.mem-sharing/var/registry.json" "$HOME/.local/share/mem-sharing-versions" "$HOME/.agents-group"` | 全新分支应不存在；不存在的退出码留证。已存在、symlink、旧标记／旧账先停，不删后重装凑首装 | `05-before.txt`；获批用户入口 before 字节／类型／权限／哈希清单 |
| 6 运行时 | `python3 --version`；`git --version`；按现场核验的三家版本命令检查 | Python ≥3.9；汇总依赖和已安装名单。版本检测不代表接入成功 | `06-environment.txt` |
| 7 外层对话 | 向安装 Agent 提交 INSTALL 的安装请求，限定当前冻结 S 与测试身份 | 检查→已知写集一次真实确认→静默执行→极简报告；依赖补装纳入同一确认。外层入口仍未冻结则 pending，不能用直接 Python 成功替代 | `07-dialogue.md`：完整脱敏对话、确认引用、实际依赖准备结果 |
| 8 内核预览 | `python3 -B "$PREP_SOURCE/scripts/install.py" --source "$PREP_SOURCE" --commit "<完整SHA>" --version "<SemVer>"` | 按冻结 help 复核参数后执行；取得 approval_plan，验证来源／目标／Agent／before/after／恢复材料。未知冲突停止 | `08-plan.json` 与退出码 |
| 9 批准执行 | 将完整计划连同真实 `confirmed_at/reference` 写为私有批准文件；`python3 -B "$PREP_SOURCE/scripts/install.py" --approval-file "$PREP_EVIDENCE/install-approval.json"` | 封皮绑定步骤 7 的同一真实确认，不再逐项询问、不伪造确认；报告实际成功／partial。计划变更停止重审 | `09-result.json`、journal、固定恢复工具路径和指纹 |
| 10 CK 尾步 | 按 INSTALL 固定话术另问；同意后使用冻结 help 确认的 `--context-keeper` 路由，封皮 `command=install-context-keeper` | 真回车才同意，n 跳过，EOF 不同意；全部已接入者用户级安装。接口未落地则 pending，不杜撰完整 argv。失败不回滚主产品 | `10-ck.md`：独立选择／封皮／结果、各家落位；此时无项目库 |
| 11 读回 | `python3 -B "$HOME/.local/share/mem-sharing/scripts/agm.py" check-memory --project "<合成主checkout>"`；与获批 after 和 before 清单比较 | check 只读，前后哈希／mtime／节点相同；未启用项目报缺口可以，但不能代替修复。R/C/V、入口、schema=3 与发行一致，R 不建 skills/mcp，无产品 Skill 投影 | `11-check.json`、前后元数据、精确差异 |
| 12 会话验收 | 按 [新会话验证](new-session-verification.md) 执行 | 安装、公共读取、项目规则、CK 激活分别记；未做全部 pending | `12-sessions/` |
| 13 收尾 | 对照步骤 0 的目标逐项出具 pass/fail/pending/blocked 和证据引用 | 不清锁、不删账、不强制重跑；中断保留同 op，按固定恢复工具另预览批准。依赖／CK 撤销不由主产品回滚冒充 | `13-verdict.md`、隔离快照保留策略 |

## 本机 v0 与开发机重装预约项

此分支当前 **pending，禁止执行**。依据审计 §5.3、裁定 §23／§25／§26，届时另交精确计划：确认旧 O=`~/.agents-group` 的 v0 身份；只复制 memories/references，skills/mcp／脚本／状态保留且不运行；库存、台账和旧产品安装与 v0 内容导入分别识别。旧 v1/v2 仅只读诊断保全，开发版不升级；`agent-group-memory:*` 旧标记漂移即停，不能自动迁移。

开发机重装前先盘点旧用户入口、旧产品台账、孤儿产品投影链接（路径、链接原文、类型、归属、目标、before 哈希／权限），把保留／备份／获批清理／新建逐项列出。孤儿只限产品所有权可证者，独立与插件管理的 Skill/MCP 不动。清理安排在获批真机重建窗口，不提供批量删除命令。旧源 O 永不成为写入或回滚覆盖目标，结束核对原字节与链接未变。旧写者暂停范围、恢复条件、快照和固定恢复工具先就绪；不得凭零字节锁推断无写者。新 R 与旧 O 双目录导入保留；本地仓库目录改名在 M4-10 后另议。
