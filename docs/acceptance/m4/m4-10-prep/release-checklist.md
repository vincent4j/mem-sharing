# 发布清单与后续运行验收规格

2026-10-31 收尾整合。现行合同见 [DESIGN](../../../../DESIGN.md)、[INSTALL](../../../../INSTALL.md)、[系统架构](../../../architecture.md)与[操作手册](../../../operations.md)。历史裁定可用 `git show f06db31:docs/plan/decisions-m4.md`、`git show f06db31:docs/plan/audit-rulings-20261030.md` 追溯；旧 § 编号不作为已删除文件的本地链接。

**这是一份待办规格，不是执行授权。** 当前结论由[验收总览](../../index.md)、[M4-10 判定](../m4-10-runtime/verdict.md)及[本地收尾报告](../../release-review.md)承载。用户已暂停 WorkBuddy 新会话、CK 真实激活、自动入口及跨客户端接力。本轮不安装、不迁移、不发布、不启动真实执行器。

## 发布前核对

| 门禁 | 核对要求 | 放行边界 |
|---|---|---|
| 固定来源 | clean checkout 的完整 SHA、产品 SemVer、schema=3/structure=1、逐文件 hash 与清单一致 | 当前 dirty 收尾不是干净发行源；不将其称为已装 04c32e24 |
| 代码与测试 | 依据最终 diff 做必要回归，保留命令、退出码、实际数量 | 历史474/74只对应历史冻结版本，不替代改后验证 |
| 安装材料 | 核对发行集合、Python≥3.9、CLI help、批准 JSON 与安装文档；对安装产物检查文档引用 | checkout 链接存在不等于 C 内可读；不混入项目 CK、私人证据或临时文件 |
| 来源 URL | 当前获取为 `https://github.com/vincent4j/mem-sharing` | 旧官方 URL 仅作为精确来源别名归一化保留；不豁免 clean/pin/hash，不支持旧开发版升级。外链未在线核验 |
| 升级 | 正式发行精确转换、代码/入口分阶段、partial 后重预览、固定工具恢复 | 0.1.0→0.1.1 窄转换只支持审定前身；已安装0.1.1不能以同版新源码冒充幂等更新；未来发行须定新版本与精确转换 |
| 保全 | before/after、所有权、journal、固定恢复工具完整；检查私人正文和其他 Agent 对象未纳入写集 | 不清锁、不回放不明请求、不用整文件覆盖后续私人编辑 |
| 文档 | 一个事实一个当前权威来源；历史材料明确阶段；本地链接与证据 hash 核验 | CK 历史日志只追加，历史引用缺口单列，不偷偷重写日志 |
| 运行门禁 | 公共读取、项目规则、CK 尾步/首次激活、自动入口、四会话接力分别判定 | 未验保持 pending/blocked；静态 connected 不替代 runtime |
| 平台与依赖 | Windows/Linux、缺 Python/Git 自动准备、独立用户/VM 首装分别留证 | 未实测不宣传支持/通过 |
| Git/发布 | 用户明确授权后再提交/tag/push；最终核对候选 SHA、清单与实际 tag | 本轮无授权，不执行；网上核验只委派章教授 |

旧官方 URL 别名保留是本次删留裁定：它用于既有来源识别，删除会影响旧 clean checkout 身份；不属于无用兼容，也不授权迁移旧台账。未来取消应单独评估来源合同与回归。

## 隔离环境与合成项目

合成 HOME 的 Python 内核测试与独立 macOS 用户/VM 的真实首装分开。只改 HOME 不隔离系统目录解析、钥匙串、daemon 或登录态，不能当作真实客户端隔离。缺系统依赖准备仅在 VM/专用测试机验证。此前用户选择本机 v0 路线，不能改写为隔离首装已经通过。

恢复运行验收时先重新确认范围及环境，冻结干净来源、检查进程 UID/配置根/应用版本/独立 Git 主 checkout。登录、验证码和二次验证由用户处理，不复制日常凭据。所有页面操作只委派章教授；身份、窗口或提交状态不明时停止，结果未知不重发。

按当前任务建立独立合成主 checkout，不用本产品仓库或日常项目：

- **fresh：** 只有 `.git/`，无 AGENTS/CLAUDE/WB 原生目录/CK 库；验证默认启用与各执行器实际使用驱动，不能提前造原生目录冒充 App 行为。
- **legacy-agents：** 仅有合成 AGENTS 正文，例如纸卡排序后报告张数；验证原文逐字保留、短协议及幂等。
- **legacy-claude：** 仅有 Claude 专属合成正文，缺 import；验证默认启用不动它，Claude 实际使用或显式接入才追加引用；已有 import 另设样例。
- **legacy-workbuddy：** 已有合成原生目录和正文；只证明该形态的保全/补指针，真实 App 创建与加载另验。
- **CK/接力/负向：** 每项用独立项目。旧产品标记漂移与 CK 迁移门禁不能混成一个用例，不自创 CK 旧格式。

构造前后保存文件集合、类型、权限、字节/hash、链接原文与 Git 身份到私有证据目录。测试正文仅用无害合成内容，不把公共随机答案放进项目、prompt、manifest 或可自动注入历史。测试材料标记失效后可作证据，不能复用于盲测。临时目录与操作 ID 每次唯一；不得盲跑旧计划中的固定路径。

## 真实安装的逐层证据

在获准环境依次记录：范围与批准 → 环境身份 → 来源 SHA/清单 → 原件 before 快照 → Python/Git/installed 检测 → 五拍安装对话 → 无批准预览 → 精确批准执行 → keeper 独立选择及结果 → 文件/台账读回 → 各新会话验证 → 最终状态。

每步保留命令、UTC、退出码、真实确认来源和前后差异。异常先解释，不为凑通过删除旧现场或重复初始化。安装成功、keeper configured、项目建库及模型读取分别报告；缺家记 pending，执行器未安装不能伪造 installed。

v0 导入只复制获批 memories/references，旧源的 skills/mcp/脚本/状态原地保护。开发机重建须另有 keep/backup/clean/protect 清单与精确批准；本轮不重做前轮部署，不清已有孤儿链接或私人资料。

## 新会话公共与项目规则验证

使用新会话与各自独立项目；普通纸卡请求不提示公共路径、答案或库位置。公共主题放一次性随机规则，项目 AGENTS 放不同的独立标记。记录完整提示、session（不可见则说明）、入口→索引→主题的实际读取依据、项目规则依据、回答与文件保全。

| 层 | 通过要求 | 不足时 |
|---|---|---|
| 公共规则 | 入口加载、主题实读及随机规则应用俱全 | 只有自述/文件名/答案命中不证明完整来源 |
| 项目规则 | 实际读取依据、独立约定应用、原文字节保全 | 原生上下文注入与工具读取事件区分，行为证据注明限制 |
| 默认入口 | 进入前缺失，实际使用后按合同产生，重复不增生 | 预置 AGENTS 的只读测试不能替代 |
| CK 首次激活 | 首次命令前无库，按 keeper 授权建库，合成事实读回 | 只显示菜单/Skill 路径/configured 不足 |

Codex 核对用户入口与 AGENTS；Claude 核对用户 import、项目实际使用后的 `@AGENTS.md` 与原文保全；WorkBuddy 核对 App 项目/会话身份、公共入口、原生目录产生、顶部指针与 AGENTS。页面按 inspect → action → verify，窗口不可读即 blocked，不将不可见内容判为不存在。

不能关闭或隔离历史自动注入时，明确来源局限。公共临时主题在当前测试结束/阻断停止后按 before 原字节恢复，不无限等待；恢复前后 hash 与撤主题证据保留。

## 接力与负向门禁

完整闭环：Codex 经 CK 保存随机事实/待办 → Claude 普通续接并更新 → WorkBuddy 读取前两轮并追加 → Codex 新会话核对累积与来源。每轮无答案提示，留库 diff 和 session。三环读回、历史污染运行或另一版本证据不能替代本次四会话验收。

负向另验禁止保存零新增、CK 迁移门禁停读写、disabled 不受既有自动规则覆盖、默认重进不翻转、显式恢复精确批准。remove 撤入口保数据与 --no-memory 保入口禁自动经历分别记录。

发布结论须列出候选完整 SHA/版本、实际通过范围、blocked/pending、是否仅限范围交付；暂停不是通过，也不是恢复验收授权。

## 0.1.2 候选的精确升级请求

本节是提交完成后的离线清单生成方法，当前不执行安装。版本、前身、30文件树和逐文件hash的唯一候选快照在[收尾清单](../../release-review-files.json)的 `candidate`；理由与本地验证见[质量报告](../../release-review.md)。必须先获得本地提交授权并产生真实clean SHA；不能把测试的synthetic commit或当前dirty工作树塞进正式请求。两入口合同不变，使用 `entries=preserve`，不指定 `--agent`，不走0.1.0→0.1.1的专用入口转换。

后续获准冻结时，在源码仓库外私有目录生成request（只输出JSON、不读取或改写安装态）：

```sh
umask 077
CANDIDATE_REQUEST_DIR=$(mktemp -d)
python3 -B - '<干净源码绝对路径>' '<提交后实际完整SHA>' > "$CANDIDATE_REQUEST_DIR/request.json" <<'PY'
import importlib.util, json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location('release_installer', root/'scripts/install.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
from agm_core import user_install
candidate = json.loads((root/'docs/acceptance/release-review-files.json').read_text())['candidate']
source = cli.checkout_source(str(root), sys.argv[2], candidate['version'])
assert source['url'] == candidate['url'], 'Unexpected source origin'
canonical, files = user_install._source({'source': source})
assert files == candidate['release_files'], 'Candidate bytes/modes changed; review again'
assert canonical['tree_sha256'] == candidate['tree_sha256'], 'Candidate tree changed'
conversion = candidate['exact_conversion_draft']
assert conversion['after']['source']['commit'] is None, 'Draft identity unexpectedly filled'
conversion['after']['source']['commit'] = source['commit']
assert conversion['after']['source']['tree_sha256'] == canonical['tree_sha256']
print(json.dumps({'source': source, 'conversions': [conversion]}, ensure_ascii=False, indent=2))
PY
```

该request不是安装批准。仅当用户另行恢复真实升级授权时，使用新唯一operation-id预览：

```sh
UPGRADE012_OP="release012-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -B <干净源码>/scripts/install.py --request-file "$CANDIDATE_REQUEST_DIR/request.json" --operation-id "$UPGRADE012_OP"
# 核对真实现场后，完整approval_plan加真实UTC Z confirmed_at/reference，写入私有批准文件。
# 独立CK尾步不在本升级范围：非交互执行，不提供同意回车。
python3 -B <干净源码>/scripts/install.py --approval-file <批准文件绝对路径> < /dev/null
```

前身URL/完整commit/tree/版本、目标SHA/tree/版本、direction以及整个计划均须精确相符；两个入口合同文件必须保持审定hash。错配、漂移、缺失/重复转换、同版替换或未知前身停止；不得通过删账、篡改清单或改preserve语义放行。缺账、旧schema、旧产品标记不属于本候选升级路径。

中断使用该operation保存的固定recover.py/toolkit重新预览：V未提交可continue/rollback，rollback会撤掉新增3文档并恢复原27文件；V已提交时rollback拒绝，只能continue完成收尾。第三态停止。已经成功升级后的主动降级必须另有精确转换和批准，本节不提供。此清单不恢复用户暂停的WB新会话、CK激活、自动入口或接力。
