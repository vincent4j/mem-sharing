# M4-05 主 Agent 验收判定

日期:2026-10-30。判定人:主 Agent。

## 执行经过(如实记录)

任务原派突突兔(GLM),其中断于 GLM 每周限额(2026-11-05 重置);用户指示主 Agent 亲自接手。突突兔遗留:agents.json/paths.py 扩展、detect.py、user_entries.py、两套测试(56 项中 3 处失败)。主 Agent 完成:①修复 skill_projection 创建投影未登记 machine 对象的缺陷(幂等失效根因);②补"复制目录占用投影位"的前置明确冲突(否则落 read_snapshot 的笼统 path_conflict);③修测试三处自身缺陷(子场景现场清理、backups 断言改为前后一致、收敛态二次预览应直接 completed);④test_cli 老夹具适配新表 schema(user_skill_roots 必填+各家独立 skill 根+allowed_user_paths 新预期)。

## 结论:通过

## 独立验证记录

1. 定向:test_m405_detect + test_m405_user_entries 共 56 项 OK;
2. 全量:单元 335、集成 57 全部 OK(含 M4-03 并行改动与新 C 落位 layout);
3. 关键语义抽查:仅 Codex 夹具的计划不含 Claude/WorkBuddy 任何路径;残留 ~/.claude 目录→unknown 只报告;显式指定未安装执行器整单停止零写入;同标记二次规划不重复;受管块漂移整单停写;异目标链接/复制目录冲突 entry_conflict;产品 Skill 投影指向 layout.code(已随裁定切至 ~/.local/share/agent-group-memory),同目标链接复用不 repoint;预览只读、执行锁内重规划、台账最后提交。

## 未验收范围(留后续)

模块尚未接入 CLI/安装器(按任务书由 M4-08 编排,M4-06 做生命周期兼容);真实机器三态探测结果未采样(M4-09/M4-10);新会话读取用户级指针未验证(runtime pending)。
