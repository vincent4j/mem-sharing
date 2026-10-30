# M4-10 tag 前发布清单（预备，未执行）

编写基线 `dc0b38f`；依据 [审计 §5.5](../../../plan/audit-rulings-20261030.md)、[裁定 §25—§26](../../../plan/decisions-m4.md)、[INSTALL](../../../../INSTALL.md) 与 [DESIGN](../../../../DESIGN.md)。本轮只备物料；下表待发布负责人逐项填写证据及 pass/fail/pending/blocked，当前均 **pending**。用户亲自 commit/tag/push，Agent 不执行。

| tag 前门禁 | 检查操作／命令模板 | 通过条件／停止条件 | 证据 |
|---|---|---|---|
| 冻结来源 | `git status --porcelain`；`git rev-parse HEAD`；记录 clean 候选 S 的完整清单 | 不用并行 dirty 工作区；实现 SHA、SemVer、schema=3、structure、来源 tree／清单哈希一致 | `release-source` |
| 版本一致性 | `rg -n 'product_code_version|schema_version|product_structure_version|version' scripts README.md INSTALL.md SKILL.md llms.txt`，逐项区分文档版本、封皮 schema 和产品版本 | SemVer 与候选发行／库存／批准计划／最终台账一致；文档 v1.x 不冒充代码号，封皮版本不机械换 3；不用试验 0.4.0／0.4.1 冒充正式号 | `versions` |
| §25 审计收口 | 主 Agent 逐项核销 B01—B08、T01—T06 与 D01—D05 | 用 §26 替代开发版转换链；T03 不再验产品 Skill；T04 一次确认绑定精确写集及依赖链，CK 独立同意；T06 缺家记 pending | `rulings-closure` |
| 正式升级承诺 | 检查冻结实现和 M4-09 用例 | 开发版／未知旧产品拒绝升级，旧 v1/v2 只读诊断保全；正式 T0→后续发行才承诺升级，故障恢复／回滚继续保留，不复活 P→改名版→v3 | `upgrade-contract` |
| 官方 URL | `rg -n 'github.com/vincent4j/(agent-group-memory|mem-sharing)' README.md INSTALL.md SKILL.md llms.txt scripts`；`git remote get-url origin` | 当前安装／获取入口为 `https://github.com/vincent4j/mem-sharing`；历史引用明确标历史；远程页面核验委派章教授，不以本地字符串证明远程可达 | `source-url` |
| LEGACY_OFFICIAL 处置 | `rg -n 'LEGACY_OFFICIAL|OFFICIAL' scripts`，审阅来源归一化及发行测试 | 基线安装器仍接受旧仓库 URL 为官方来源。发布前由负责人明确保留兼容别名或移除，并核对来源身份／清单测试；不得将 URL 别名兼容解释成开发版台账升级或旧标记迁移。未处置不勾选 | `legacy-official-decision` |
| 文档链接 | 检查 README／INSTALL／SKILL／llms／本目录的相对文件及 § 锚点；对实际打包产物重验 | checkout 和发行包都包含所需文档，大小写／相对路径正确；外链及远程 tag 可达性由章教授核验；只读静态链接存在不等于远程可达 | `links-checkout`、`links-package`、`links-remote` |
| 活动术语与菜单 | 核对上述文档、生成入口及实际菜单 | memSharing、R=`~/.mem-sharing`、C=`~/.local/share/mem-sharing`、`/mem-sharing` 一致；六项短路由一致；无产品 Skill 投影、R 无 skills/mcp；CK Skill 独立保留 | `docs-menu` |
| CK 与停用 | 按 §17—§19／§24／§25 复核案例和文案 | CK 用户级安装与首次项目激活分离；独立封皮、真回车、EOF 不同意、CK 失败不回滚主产品；remove-memory 与 --no-memory 的 disabled 两条语义分别有证据，显式恢复 | `ck-policy` |
| M4-09 | 对冻结 S 采用最终案例及所需单元／集成检查 | 结论对应最终实现；不使用旧用例数量证明新合同通过。本轮未跑测试 | `m4-09-final` |
| M4-10 分层 | 使用 [会话表](new-session-verification.md) 与 [首装表](isolated-install-checklist.md) | 首装、三家公共读取、项目规则、CK 激活、四会话接力、缺依赖路径分别判定；未做 pending，不统称全通过 | `m4-10-verdict` |
| v0 不受影响 | 获批真机窗口前后对 O=`~/.agents-group` 做精确类型／权限／原字节／链接清单比对；本轮不执行 | 只从 memories/references 复制到新 R，旧源索引不改，skills/mcp／旧脚本／状态不运行不接管，O 不作回滚目标；合成 v0 不能代替真实 v0 | `v0-before-after`，未执行时 pending |
| 开发机重建 | 审阅孤儿投影 keep／backup／clean／protect 逐项表及用户批准 | 旧标记漂移停止，保全后重装；只清所有权可证且获批的孤儿产品链接，独立／插件 Skill/MCP 保护；禁止先删后补备份 | `rebuild-plan`，本轮 pending |
| 恢复材料 | 固定恢复工具、journal、before／after 指纹、库存与批准绑定逐项核验 | 错账／中断不当首装，第三态停止，不自动清锁；V 已提交且全 after 只收尾。依赖和 CK 撤销不冒充产品回滚 | `recovery` |
| 用户发布 | 用户选择正式号并亲自提交／tag／push；之后只读核对精确 SHA 与发行清单 | 未授权不执行 Git 写操作。远程核验委派章教授，远程实际 tag 指向与本地候选一致后才宣称发布 | `tag-readback` |

放行单至少列：候选完整 SHA／版本、各门禁状态与证据、未验范围、用户是否接受限范围发布。本机 v0、WB 或四会话跳过均保持 pending，不因此扩写“三家项目经历已接力”。本地源码目录改名按 §23 与审计 §5.5 留到 M4-10 后，在引用旧 cwd 的会话结束后另给可逆计划；不在运行中移动。
