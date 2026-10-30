# M4-10 合成项目物料规格（预备，未构造）

基线 `dc0b38f`；依据 [裁定 §16／§17／§24—§26](../../../plan/decisions-m4.md)、[审计 §5](../../../plan/audit-rulings-20261030.md)。这里只提供构造命令和预期，不创建项目、不运行执行器。不得使用当前产品仓库或日常项目作夹具。

## 共用构造方法

只在用户批准的独立测试用户／VM 内执行；`PREP_PROJECTS` 先填写该环境内不存在的绝对目录。`umask 077`；所有 Git 为独立主 checkout，不用 worktree，不设远端、不联网、不 commit/push、不装依赖。空仓库无需伪造提交；若冻结内核要求首次提交，则另记录该限制并由用户决定，不能偷偷改变规格。

```bash
umask 077
PREP_PROJECTS="<隔离环境内不存在的绝对目录>"
mkdir -m 700 "$PREP_PROJECTS"
git init "$PREP_PROJECTS/fresh"
git init "$PREP_PROJECTS/legacy-agents"
git init "$PREP_PROJECTS/legacy-claude"
git init "$PREP_PROJECTS/legacy-workbuddy"
```

每个项目先用 `git -C "<项目>" rev-parse --show-toplevel` 与 `git -C "<项目>" rev-parse --git-common-dir` 核对独立根；记 `git status --porcelain`，目录类型／权限、文件原字节、SHA-256、mtime、链接原文于私有 evidence。所有文本用 UTF-8；合成用户段不带产品或 CK 受管标记，避免误入旧块转换分支。不要把公共随机答案写入项目。

## 全新空项目形态

`fresh/` 只有 `.git/`，没有 AGENTS.md、CLAUDE.md、`.workbuddy/`、CK 库、项目 Skill 或产品状态。进入前证据证明这些不存在；默认启用后允许生成 AGENTS 骨架及短协议，CK 库仍无。Claude／WB 入口只按该执行器实际使用产生（§16）。

为每家首次进入和 CK 激活从空规格分别新建 `codex-fresh`、`claude-fresh`、`wb-fresh`、`codex-ck`、`claude-ck`、`wb-ck`，使用 `git init "<独立新路径>"`，不复制其他已启用项目的 `.git` 或入口。空结构验证后，证据操作者经批准在 AGENTS 用户段加入独立项目约定／随机标记，用于新会话规则实读；与公共主题标记分开保管。

## 旧形态一：已有 AGENTS.md

```bash
cat > "$PREP_PROJECTS/legacy-agents/AGENTS.md" <<'EOF'
# 合成项目规则

这里只处理本目录合成纸卡，不访问网络。
用户保留段：纸卡整理后报告总张数。
EOF
```

前置：无 CLAUDE、WB 目录和 CK 库。预期：保留全部用户原字节，只按批准追加受管短协议；Codex 实读并应用“总张数”。重复启用不重复追加，原段哈希不变。不得覆盖重写文件来制造统一格式。

## 旧形态二：已有 CLAUDE.md

```bash
cat > "$PREP_PROJECTS/legacy-claude/CLAUDE.md" <<'EOF'
# Claude 专属合成约定

用户保留段：说明结果时先报纸卡总张数。
EOF
```

前置：没有 AGENTS、没有 `@AGENTS.md`、没有 CK 库。预期：任一家默认启用可以建立 AGENTS，但只有 Claude 实际使用才补其缺失 import；保留 CLAUDE 全文，不把专属内容迁入公共主题。新生成导入为 `@AGENTS.md`，不嵌 CK 长模板；再次使用不重复。另建独立副本测试“已有 import”分支，勿修改已验现场凑第二用例。

## 旧形态三：已有 WorkBuddy 原生目录

```bash
mkdir -p "$PREP_PROJECTS/legacy-workbuddy/.workbuddy/memory"
cat > "$PREP_PROJECTS/legacy-workbuddy/.workbuddy/memory/MEMORY.md" <<'EOF'
# WorkBuddy 合成原生内容

用户保留段：纸卡任务仅输出合成数据，不查询外部信息。
EOF
```

该手工样例只用于已有目录保全／补指针的受控夹具，不证明真实 App 创建或加载。真机会话须另用 `wb-fresh` 由 App 实际使用产生原生目录并留证。已有目录本身不授权其他执行器抢先写 WB 指针。预期：实际使用驱动的指针仅引向项目 AGENTS，原生正文保持原字节；check 只报缺口不补写。

## 扩展与证据交付

以上四形态均默认无旧产品标记；若测 `agent-group-memory:*`，另建独立异常夹具，预期漂移停止并指引保全后重装，不迁移（§26）。CK 旧块 created/reused／漂移分支按冻结 CK 合同另建，不与旧产品标记混同。

停用、禁止保存、CK 迁移门禁及四会话接力分别使用新路径，构造 CK 旧库须采用 CK 当前文档，不自创格式。每例留构造命令、前后树／原字节哈希、使用执行器与会话、批准／报告／diff。真机执行完由用户决定保留／销毁隔离环境，不用批量删除重置已验现场。
