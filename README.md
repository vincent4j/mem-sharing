<div align="center">

# 多 Agent 记忆融合 · Multi-Agent Memory Fusion

给多个 AI 编程 Agent 装上同一份项目记忆。

**周一用 Codex,周二用 WorkBuddy,同一个项目,同一份记忆。**

[为什么需要](#-为什么需要-multi-agent-memory-fusion) ·
[快速上手](#-快速上手) ·
[三命令](#-三命令与退出码) ·
[设计理念](#-设计理念)

</div>

---

<a id="为什么需要"></a>
## 💡 为什么需要 Multi-Agent Memory Fusion?

你同时使用多个 AI Agent 时,是不是也遇到过这些问题?

- 🔄 **换个工具,记忆清零?** → 周一用 Codex 把方案定了、坑踩完了,周二换 Claude Code 或 WorkBuddy 接手,它什么都不知道,你又得从头交代。
- 🧩 **规则写了三份,越写越散?** → Codex 读 `AGENTS.md`,Claude 读 `CLAUDE.md`,WorkBuddy 只认自己的记忆文件——同一个项目,三处规则各自漂移。
- 🔁 **装配靠手,坏了没人知道?** → 手工给每个 Agent 配入口,配完就忘;哪天被重置或误改,静默失效。

**难道每次换工具,都得你来交接进度、同步规则、检查配置?**

Multi-Agent Memory Fusion 一条命令,把「**项目规则单一源 + [context-keeper](https://github.com/vincent4j/context-keeper) 记忆库**」装配到三个执行器:规则三家同读,记忆三方共写,谁来了都接着干。

### ✅ 在你用之前,你可能想知道

| | |
|---|---|
| ⚡ **会多花 Token 吗?** | 规则文件里只追加几个指针块;记忆本体在项目内,由 context-keeper 规则按需读取,不全量注入。 |
| 📝 **需要自己维护吗?** | 装配、巡检、修复、卸载由命令完成;记忆的记录与整理由 context-keeper 驱动 Agent 执行,你不手写日志。 |
| 🔒 **会动我的文件吗?** | 只触碰声明的受管对象,**块外字节一字不动**;指纹漂移即拒绝写入(实测:poster-fit 的未提交文件字节级保留)。 |
| 🤖 **支持哪些 Agent / 平台?** | Codex、Claude Code、WorkBuddy;macOS 安装/重装/卸载/失败恢复四项已验收,Windows/Linux 不声称支持。 |
| 🧹 **想撤掉怎么办?** | `remove-memory` 只撤销本工具创建的对象;你的记录库与既有规则永不删除。 |

---

<a id="能帮你做什么"></a>
## 🎯 能帮你做什么?

| 你遇到的问题 | Multi-Agent Memory Fusion 怎么处理 | 你得到什么 |
|---|---|---|
| 换工具就失忆,交接全靠你 | 把 context-keeper 记录库装配到三个执行器,新会话自动续接 | 周一 Codex、周二 WorkBuddy 无缝接力 |
| 规则三处各写一份 | 项目根 `AGENTS.md` 单一规则源;CLAUDE.md 放 `@AGENTS.md` 引用;WorkBuddy 桥接由上游接管 | 一份规则,三家同读 |
| 装完不知道坏没坏 | `check-memory` 只读巡检:入口漂移、缺口、`AGENTS.override.md` 劫持全部报告 | 一条命令看健康,不修复只说实话 |
| 配置被重置/误改 | `enable-memory` 幂等补装:现场与登记一致时免重新批准,一键复原 | 坏了自己发现,修了不留痕 |
| 不想要了 | `remove-memory` 按所有权精确卸载 | 只拆自建的,你的东西分毫不动 |

---

<a id="记忆融合如何发生"></a>
## 🧠 记忆融合是如何发生的?

**三套系统各管一层,边界一次说清:**

| 层 | 归属 | 管什么 |
|---|---|---|
| 用户级 | `~/.agents-group`(已独立建成) | 跨项目、跨执行器的个人规则与共享 Skills |
| 项目记忆 | [context-keeper](https://github.com/vincent4j/context-keeper)(独立产品) | 记录库本体:保存/继续/查找、按证据自我进化 |
| 编排层 | **本工具** | 谁在什么时机被装上、被触发:装配、巡检、授权记账、所有权卸载 |

**装配四态**:源码可用 → Skill 安装 → 桥接装配 → 记录库授权。没有用户批准,第四态不会发生;**写入永远走精确批准文件**(逐路径前后指纹),幂等补装除外。

**WorkBuddy 桥接已回传上游**:context-keeper 的安装器正式接管 `--workbuddy` 入口,本工具的私有模板已删除——**桥接的终局是消失**。

---

<a id="快速上手"></a>
## 🚀 快速上手

**方式一(推荐):对 Agent 说人话。** 把下面这段话复制给任一已装本工具的执行器:

```text
请用 Multi-Agent Memory Fusion 给这个项目装配跨执行器记忆:先预览,把精确计划给我确认后再执行。
```

**方式二:直接 CLI。** 在目标项目里执行(路径填本仓库 checkout):

```bash
# 1) 预览(只读):返回 5 时,stdout 的 next_action 就是待确认的精确计划
python3 /path/to/agent-group-memory/scripts/agm.py enable-memory --project <目标项目Git根> --memory

# 2) 把 next_action JSON 存成文件,补上 confirmed_at(UTC,以 Z 结尾)与 reference,即为批准文件
python3 /path/to/agent-group-memory/scripts/agm.py enable-memory --project <目标项目Git根> \
    --memory --approval-file plan.json
```

### 三命令与退出码

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `enable-memory` | 经授权装配/补装规则基座与记忆档 | `--project` `--agent codex\|claude\|workbuddy…`(缺省三家)`--memory\|--no-memory` `--approval-file` |
| `check-memory` | 只读巡检现场状态与缺口,不修复 | `--project`(缺省当前)或 `--all`(全部已登记项目) |
| `remove-memory` | 仅撤销本工具创建的对象;记录库永不删除 | `--project` `--approval-file` |

| 退出码 | 含义 |
|---|---|
| 0 | 完成(check 全绿 / 幂等无变更) |
| 1 | check 发现缺口(只报告,不修复) |
| 2 | 参数、schema、路径冲突、执行或恢复失败 |
| 3 | context-keeper 迁移门禁:立即停止读写,先看迁移预览 |
| 5 | 待授权:需要批准文件(或在交互终端确认) |

stdout 恒为单个 JSON envelope,stderr 是人读摘要。

---

<a id="项目里会新增什么"></a>
## 📁 项目里会新增什么?

```text
你的项目/
├── AGENTS.md                  # 规则唯一源(已有则只追加桥接块,块外字节不动)
├── CLAUDE.md                  # 仅一行 @AGENTS.md 引用 + 桥接块
├── .workbuddy/
│   ├── skills/context-keeper  # Skill 符号链接(本机装配,gitignore)
│   └── memory/MEMORY.md       # 顶部桥接块(上游 --workbuddy 维护)
├── .agents/skills/ · .codex/skills/ · .claude/skills/   # Skill 链接(本机)
└── docs/context-keeper/       # 记忆本体:memory-keeper / plans / worklogs / evolution(提交进 Git)
```

| 产物 | 性质 |
|---|---|
| `AGENTS.md` / `CLAUDE.md` / WorkBuddy 桥接块 | 项目资产,随 Git 分发 |
| `docs/context-keeper/` 记录库 | 项目资产,随 Git 分发——**worktree 天然继承、多设备天然同步** |
| Skill 符号链接、`registry.json`、备份 | **本机装配状态**(gitignore):新机器重新 `enable-memory` 即可 |

---

<a id="设计理念"></a>
## 🧭 设计理念

**记忆跟着仓库走,装配跟着机器走。**

- **不重复造轮子。** 项目记忆的一切归 context-keeper;本工具只做编排——边界判据:*记忆的内容与结构归 Keeper,谁在什么时机被装上、被触发归本工具,跨项目用户规则归 `~/.agents-group`*。
- **每一层只有一个真源。** 规则在 `AGENTS.md`,记忆在记录库,用户规则在公共源;宁可要指针,不要副本。
- **静态配置不算数。** 一切装配以新会话运行时验收为准(见 `docs/acceptance/` 的四执行器接力证据)。
- **漂移即停,人工核对。** 指纹不一致就拒绝写入,不猜、不自动覆盖;批准文件也不能越过这道保护。
- **桥接的终局是消失。** WorkBuddy 桥接已回传 context-keeper 上游,本工具不留第二真源。

### 已知限制

- created 对象被外部改动无自动修复:需人工还原,或批准 remove 后重装;
- remove→重装周期中块间换行会重排(受管块内容不变);
- WorkBuddy 真机新会话接力验收待做(装配与上游接管已验证);
- registry 与备份是本机文件,换机器/新 clone 须重新 `enable-memory`;
- 用户级 `~/.agents-group` 独立运行,不在本仓库范围;本期不做 Skills/MCP 管理。

### 文档与开发

设计:[DESIGN.md](DESIGN.md) · 实现合同:[docs/plan/architecture.md](docs/plan/architecture.md) ·
裁定记录:[docs/plan/decisions-m2.md](docs/plan/decisions-m2.md) ·
任务书(已收官):[docs/plan/tasks.md](docs/plan/tasks.md) ·
全部验收证据:[docs/acceptance/](docs/acceptance/)

```bash
python3 -m unittest discover -s tests/unit          # 228 项
python3 -m unittest discover -s tests/integration   # 53 项
```

Git 提交与发布由用户亲自执行,本工具不主动 commit/push。
