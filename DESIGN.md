# memSharing 设计总纲

文档版本 v2.1，2026-10-31。这里只保留现行产品合同；历史裁定与旧 § 编号见 Git `f06db31:docs/plan/decisions-m4.md`。机制详见[系统架构](docs/architecture.md)，操作详见[操作手册](docs/operations.md)，实际完成状态以[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)为准。

## 定位与边界

memSharing（多 Agent 记忆共享与融合，Multi-Agent Memory Sharing & Fusion）是跨执行器的规则共享与经历编排层，覆盖 Codex、Claude Code、WorkBuddy。纯文件、零服务，使用 Python 标准库；当前实证平台为 macOS，Windows/Linux 未验证。

不增加向量库、界面、模型配置、数据库或通用 provider 框架。不管理共享 Skills/MCP，不投影 memSharing 自身 Skill，不写各执行器的自动私有记忆库。其他记忆工具可独立共存，本产品不集成或管理其服务端。

## 三种记忆与唯一来源

| 名称 | 唯一来源 | 职责 |
|---|---|---|
| 用户记忆 | `~/.mem-sharing/memories/` | 跨项目公共规则与偏好，跟人走 |
| 项目记忆 | 项目根 `AGENTS.md` | 项目构建、约束与工作规则，随 Git 走 |
| 项目经历 | Context Keeper 管理的项目记录库，默认 `docs/context-keeper/` | 进度、事实、日志与经验，随 Git 走 |

Context Keeper 是可选的项目经历引擎；不装它仍可共享用户记忆和项目规则。其记录格式、保存、续接、查找、迁移与首次建库授权归 keeper 自身，本产品不复制其逻辑、不修改上游。

用户记忆采用 L0 索引恒读、L1 主题开头概要按需读、L2 全文与 references 必要时读。索引每主题一行，含主题名、当前结论、链接，最多 200 行/25KB；概要手写，不自动生成。按索引精确查找，不增加语义搜索机制。

## 机器安装与升级

R 为 `~/.mem-sharing`，仅包含 memories/references/backups/var；C 为 `~/.local/share/mem-sharing`；V 为 `R/var/registry.json`。版本库存独立位于 `~/.local/share/mem-sharing-versions`。布局、台账、事务和恢复协议的权威说明见[系统架构](docs/architecture.md)。备份没有自动到期删除机制。

安装首先判别全新、经确认的 v0 内容复制、有效产品升级/同版幂等、异常停止四类通道。旧 v0 源 `~/.agents-group` 原地只读保留，只复制 memories/references；skills/mcp、旧脚本与状态不复制、不运行、不接管。未知身份、坏账、缺账或中断不自动当成首装。

活动台账 schema=3，产品结构版本=1，代码版本由精确发行清单绑定，三者分开。旧 schema1/2 只作诊断与保全，不提供开发版迁移或逆 schema 转换。支持的正式升级必须匹配明确的前后发行、来源和转换，不按版本大小推测兼容。

用户安装对话、依赖检查、一次确认、静默执行与 keeper 独立尾步以 [INSTALL](INSTALL.md) 为唯一操作合同。Python ≥3.9；缺 Python/Git 的准备由外层 Agent 编排，Python CLI 不自行装依赖。后装执行器仅由用户主动请求接入，不自动发现或提示。

`installed` 只证明探测到应用；`connected` 证明入口登记、指纹与读取语义静态成立；真实会话读取另行验证。不能把主安装成功或静态接入当作三家运行成功。

## 项目入口与生命周期

进入未登记的 Git 主 checkout 时，规则驱动默认启用；不是后台监听。建立缺失的 AGENTS 骨架与项目经历短协议，已有正文完整保留。非 Git 目录及 linked worktree 不触发；路径复用必须重新核对 Git common-dir。

| 执行器 | 项目入口 | 创建与保全边界 |
|---|---|---|
| Codex | `AGENTS.md` | 首次实际使用时按默认启用条款补缺失骨架 |
| Claude Code | `CLAUDE.md` 中 `@AGENTS.md` | 默认启用完全不触碰；由 Claude 实际使用兜底，或显式 `--agent claude` 接入；保留已有正文 |
| WorkBuddy | `.workbuddy/memory/MEMORY.md` 顶部指针 | 原生目录由实际使用产生后补指针，不预建；原生正文原字节保留，运行时未验限制单列 |

短协议只说明经历库位置、`/context-keeper` 入口与职责。默认启用不调用 keeper 安装、不装项目级 Skill、不创建记录库；首次 `/context-keeper` 按 keeper 流程处理。旧桥接 created/reused/漂移必须按精确计划和所有权分别处理，不能拿旧标记当任意替换授权。

项目写入前核对身份、受管单元与精确计划；陌生内容或受管漂移停止。AGENTS 正文可自由编辑，工具不据骨架创建取得整文件删除权。复用单元不取得删除权；纯薄入口仅在容器创建与全部单元所有权证据齐备、没有其他正文时可删除。keeper 记录库、安装及用户独有内容保留。

`remove-memory` 撤允许撤销的入口并登记 disabled；`enable-memory --no-memory` 保留入口但禁止自动项目经历记录与初始化。两者都不会被默认启用或批量启用恢复；解除须显式 `--memory` 并批准精确计划。该政策约束 Agent，不能冒称 keeper 脚本具有硬拒写接口。

项目规则的子目录要求留在相应规则文件；经历仍集中于 keeper 记录库，以主题区分来源。WorkBuddy 子目录可见性有限，对它重要的要求放根规则摘要。现有子目录薄入口未经运行验证不自动删。

## 公共与独有内容治理

公共内容只写 R/memories 指定文件；Agent 独有内容永不并入公共、永不自动删除。归属不明保留。整理只读扫描后提出逐条计划，允许批准前改判，一次确认完整清单和原文指纹；程序分类不是语义事实。

用户规则整理 API 及六项菜单由 [SKILL](SKILL.md) 路由，[操作手册](docs/operations.md) 给出执行步骤。项目存量规则/经历的人工整理不冒充现有自动 CLI；涉及扩大 Git 可见性须明确说明并获准，不把私有材料放入仓库。

## WorkBuddy 修复与恢复边界

用户级入口修复保留私人全文，精确批准后追加公共索引与项目规则指针；登记旧块仅在指纹吻合时批准更新。未登记旧块不自动收编；与当前模板完全相同的块可登记 reused。共享 user scope 对象仍归原治理路径。完整语义见[操作手册](docs/operations.md#workbuddy-用户入口的接入边界)。

0.1.0 → 0.1.1 仅支持固定前身与固定入口合同的 `workbuddy-public-index-v1` 转换，目标 commit/tree 由外部清单绑定；不得借 `preserve` 放行任意合同变化。代码事务与入口事务分别读回，入口失败报告 partial；固定恢复工具只恢复代码阶段，不证明入口完成。成功发行降级、机器卸载不在该通道承诺范围。精确操作以[转换手册](docs/operations.md#010--011-的-workbuddy-入口合同转换)为准。

恢复保留 journal、固定工具、before/after 和所有权；第三态停止，不自动偷锁、回放不明请求或覆盖外部修改。文件原子替换不等于跨文件原子事务，对非协作写者的最终检查仍存在竞争窗口；不扩大为操作系统级并发保护。

## 验收与发布

安装、静态入口、公共主题实读、项目规则应用、keeper 尾步、项目首次激活、自动入口、跨客户端接力分别判定。配置与测试只能支持其实际覆盖层。

完整接力在获授权的合成记录库进行：Codex 保存随机事实/待办 → Claude 普通续接并更新 → WorkBuddy 读取前两轮并追加 → Codex 新会话核对累积结果。四轮提示不带答案或库位置，保留各次 session、来源和库 diff。禁止保存与迁移门禁另做负向测试，不关闭或清空执行器自己的自动记忆来虚构边界。

当前证据与未验范围集中在[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)和[M4-10 判定（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/m4/m4-10-runtime/verdict.md)。发布准备见[发布清单（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/m4/m4-10-prep/release-checklist.md)；这份设计不构成发布授权。
