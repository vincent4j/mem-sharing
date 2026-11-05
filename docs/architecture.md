# 系统架构

本页只说明组件、数据和执行边界。用户操作在 [Skill](../SKILL.md)、[安装](../INSTALL.md)及[操作路由](operations.md)；需求真源是[模块 PRD（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/prd/README.md)，验证状态见[验收总览（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/acceptance/index.md)。

## 职责和数据

| 数据 | 唯一位置与管理者 |
| --- | --- |
| 公共用户规则、偏好与长期事实 | R 的 `memories/`；MEMORY.md 只保存读取、写入归属、项目触发及索引 |
| Agent 专属用户内容 | 各家原生用户文件，不自动搬入公共库 |
| 项目规则 | 当前项目根 AGENTS.md；各家原生入口引用它 |
| 项目经历 | Context Keeper 独立管理；memSharing 不实现其记录引擎 |

Agent 理解原文并提出语境/作用域分组，用户决定共享范围，小工具按精确字节计划修改。不得以摘要替换正文、凭相同标题合并语境，或将事故修复器变成日常必经步骤。多轮共享、原有重复次数、公共后续编辑及退出恢复都是正常能力，不能以一律拒绝代替实现。

## 安装布局与来源

| 位置 | 内容 |
| --- | --- |
| R：`~/.mem-sharing` | memories、references、backups、var |
| C：`~/.local/share/mem-sharing` | 持久安装核心与 Skill；原生薄入口指向这里，不指向临时 checkout |
| V：`~/.mem-sharing/var/registry.json` | schema 3 安装、受管对象、项目及来源状态 |
| `~/.local/share/mem-sharing-versions` | 已核验版本库存与完整指纹 |
| `~/.local/share/mem-sharing-sources` | 发行导出的持久源；不要求 direct clean-source 安装伪造 export |
| `~/.mem-sharing-install-<operation>` | 安装事务、staged registry、入口备份与恢复工具 |

固定源码与发行对象的身份、树、字节及模式须完整核验。摘要证明完整性，不自行证明来源。相同版本不同内容、缺来源、损坏的 export、未知前身及缺精确转换均不能静默回退或覆盖。用户数据不是缓存，不能随升级清理。

## 内核与适配器

- `scripts/agm.py`：项目启用、批量、检查以及兼容/卸载路由。
- `scripts/install.py`：机器安装、固定来源、追加 Agent、恢复与独立 Context Keeper 安装。
- `memory_share.py`、`project_share.py`：Agent 提案、选择、共享、归还与恢复；`user_rules_organize.py` 保留安装后整理路由。
- `paths.py`、`detect.py`、`user_entries.py`：六家路径、安装事实与原生入口。规则引用不等于 Skill 可发现；文件存在不等于模型读取成功。
- `transaction.py`、`registry.py`、安装/卸载恢复模块：锁、快照、精确写入、台账与恢复；不另造重复事务、日志或服务。
- Paseo 只作薄宿主适配，复用同一内核；公共 TypeScript 真源在 `plugins/shared/src`，生成副本不手改。细节见[Paseo 手册（源码仓库）](https://github.com/vincent4j/mem-sharing/blob/main/docs/plugin-adapters/README.md)。

## 所有权与事务

V 区分机器对象、项目对象与共享对象。创建、复用、消费者及原指纹是不同事实；whole-file fingerprint 不代表取得私文所有权。只处理已登记且可证明的精确产品块/import，未知同名文件、符号链接、未完成事务或漂移停止写入。

安装按选择接入；默认仅从检测为 installed 的六家中选择。仅有目录是 hint。首次新增 Agent 补原生 Skill 与记忆入口后，独立进入增量内容选择；重复已接入安装须零写且不重跑融合。检测与执行时的路径重定向保护保留在内核，不复制成常驻用户规则长文。

共享先保存公共完整原文并核验读取入口，再删批准的精确来源。相同语境、同字节正文可共用一份，每个来源的位置、次数和关系仍逐处记录。完整计划、真实选择、before/after、模式和备份受同一事务绑定；锁内重核，registry 最后提交。恢复不能扩大到未知路径或自动抢锁。

项目默认接入只对 Git 主 checkout 生效，disabled、非 Git、linked worktree 跳过。当前 Agent 只补自身项目入口，不预建其他家目录；Context Keeper 的政策、记录库与上游源码不受此状态控制。

退出使用同一完整卸载计划归还正文并拆除全部已安装 Agent 的受管资产。历史融合入口及已归还的 Claude 引用须由真实 committed producer 的精确前后链证明，不能按 marker 认领、手工洗 V 或要求先绕一次独立 return。实现边界见[卸载合同](uninstall-design.md)。

## 验证与维护边界

Python 仅标准库；Paseo 的 Node 检查按改动范围运行。源码、合成文件链、真实安装、原生发现、模型读取和发行分别报告。只为有活跃消费者的能力维护兼容；一次性事故工具及过程文档可退役，历史证据留 Git，不删 Context Keeper 工作记录。
