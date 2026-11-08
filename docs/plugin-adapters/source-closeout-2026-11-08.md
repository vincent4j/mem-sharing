# 2026-11-08 源码收尾验收

本轮源码修复通过，允许按用户授权提交推送。正式新发行尚未生成；不能把当前源码提交当作新的可安装发行候选。

## 实现与审核

- Paseo 客户端统一状态和流程布局，完整融合方案及稳定编号可见，技术详情折叠。返回选择失败明确报错；保留位置输入错误不发送请求、不丢输入，查看/拒绝不受无效输入阻断。缺转换方案给出中文阻断提示，原始错误放详情。项目检查 gaps 不报成功，重复接入终态不再循环预览。
- 已审 CK 通用正文允许跨相邻协议块识别，真正嵌套、未知和变更正文仍保护。公共标题使用通用语境，来源 context 保留原值。
- 巴克收尾发现：卸载包装回放不识别新标题；多轮替代又过滤最早创建事务。现兼容旧、新公共渲染，历史 producer 仅加入包装证明，原生归还仍仅处理有效来源；完整 before/after、范围、正文哈希、absent 创建祖先和全部移除证明保留。用户预存同名标题不因名称删除。
- 最终审核无新增阻断；审核所列三个修复文件 SHA 与最后回归前后完全一致。未修改已安装核心、上游 Context Keeper 或真实用户文件。

## 验证与边界

| 证据 | 结果与限制 |
| --- | --- |
| 最后受影响 Python 回归 | 29/29，exit 0，零失败/跳过，153.626 秒；覆盖 CK 两模块、生成包装、普通融合卸载。源码冻结后运行，不是全量 unit/integration |
| 原反例重放 | 从修前函数重放同用例：两处断言失败；修后无失败，纯函数审计写入尝试 0 |
| 多轮共享/替代→卸载→独立恢复 | 单链通过；六家退出字节与同一安装共享前的退出预览一致，无新增通用空标题；恢复后隔离 HOME 全树精确一致。未修复既有退出布局的前导 LF |
| 插件自测复用 | 67/67 插件测试通过；后续局部修正另有 typecheck、9 项输入/RPC 和 6 项转换展示验证。本次仅核同字节证据，未重复整批，不称完整最终 UI/响应式验收 |
| 本机 CK 共享 | 用户明确选择后完成：公共正文一份，六家精确删重，来源和恢复备份保留。首轮错误章节曾正式归还纠正后重新共享，未隐藏该过程 |
| 新会话读取 | DSH 导出工具记录和 WorkBuddy 原生界面证明有引导的新会话沿用户入口读取公共规则并正确解释 CK 边界；不等同无提示自动触发、项目保存或其他客户端全验 |

首轮修复批次实际为 29 项中 1 失败，暴露历史 producer 过滤；随后保留失败断言并修复。最终通过不覆盖早期失败事实。

## PRD 与发行状态

未命中独立生效合同。安装、共享与卸载 PRD 的相关行为无需改写；PRD 结构检查 errors=0、warnings=0，两类 inbox 均空，受控入口无需修改。记录结构与链接检查通过。

0.1.11 的固定来源 S=`9b131917a18364888ede2d2f41ad98e97a800a39`、发行 R=`c40cc63ffeec1b7c95753924915fbe53a47c84b5` 已有独立门禁证据。本轮源码修复尚未进入下一版本载荷；当前提交不冒称通过下一版 source/release 门禁。新版本、生成物、安装、tag 和发布不在此次推送范围。

## 冻结功能文件

以下是本轮完整功能改动的 SHA-256（本次卸载返修只改其中三个文件）。

- `scripts/agm_core/memory_share.py`：`52d91b13378a6e8aa92c48833960a5eff7981aa07e4f64e8bb24e91e239b4263`
- `scripts/agm_core/user_rules_organize.py`：`7f82bc8f5a4fb7d624f827a50101f175c95baa8174791c9ba20e58a6216c3b0f`
- `tests/unit/test_ck_common_trigger.py`：`8378fd4002fb85a09adde1a5922262d81f811bea86c3176c3629faf9836520e9`
- `tests/unit/test_ck_common_trigger_chain.py`：`d0791ddda558f90ae8fb50aabe423bf57d76146b3c4374823b8213be737423ce`
- `plugins/paseo/client/flow.tsx`：`4e30ad8a582381487c522c5960638f435f914c63c2bbf51df7c8fd4c6c63edff`
- `plugins/paseo/client/status.tsx`：`688b81c9ada78c094aa37852c64f7caadac65696bacd8999ba9140b3ee63d021`
- `plugins/paseo/client/ui.tsx`：`96d7ce734d1fc881974ea639fd00a1bdfa36fe34ce80d46e9cd7db4e06c505e8`
- `scripts/agm_core/uninstall_memory.py`：`9613af3e93eff0968d0e37acd35afb08df048b8f55014a47415abaf583ccfb6a`
- `tests/unit/test_generated_wrapper_retirement.py`：`989074985e28d334e9c23765d655da9e89f5c9fade8f0199f5552ec538d6007a`

## 过程记录

- [CK 共享、失败反例、修复与最终验收](../context-keeper/worklogs/2026-11-08-Context-Keeper通用触发真实共享准备.md)
- [Paseo 界面、静态审查与真实界面范围](../context-keeper/worklogs/2026-11-07-Paseo页面体验改进与真实界面验收.md)

原始测试输出、冻结差异和独立审核报告留在本机证据目录，路径见上述日志。原生会话导出、用户记忆全文和安装备份不进入仓库。
