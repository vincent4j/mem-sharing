# M4-06 主 Agent 验收判定

日期:2026-10-30。判定人:主 Agent(独立复核)。

## 结论:通过(含两次授权扩展,均合规)

## 独立验证记录

1. 全量:387 单测 + 62 集成通过,退出 0;定向 27 项 M4-06 新回归 OK;
2. R1 反转(yes→no 撤权):DECLINE 原始输出 authorization=no、created_bridges_removed=true、denial_guard=true(受管停用 guard 在位)、store_preserved=true、plan_changes=6(精确撤销计划)——修复前账本改 no 但桥接/触发指令字节原样生效;
3. R4 反转(check 假 ready):SOURCE 原始输出 source_status=missing、gap_codes=[source_missing,source_missing]——修复前同现场返回 completed/ready/gaps=[];
4. 生命周期:AGENTS 非桥接自由编辑+永不删文件;新建纯 CLAUDE 引用单元可删、用户正文保留;旧 reused 不追认 created;WorkBuddy 原生目录不预建(native_pending/blocked 报告);项目 remove 保留机器安装;默认执行器=installed 过滤、显式未安装整单停;
5. CLI 封皮接线(授权①):字段矩阵 enable 扩展五字段/remove 零扩展/check 无批准入口,未知字段与畸形扩展拒绝,rebuild_confirmation 双哈希精确绑定;7 条 CLI 新回归;
6. 旧夹具更新(授权②):8 个既有测试文件改动与"改动点→冻结条款"清单逐条对应,核对 git status 与清单一致;故障/授权/事务/资产保护断言未放宽;
7. 写集合规:生产文件恰为授权六文件(agm.py+entries/enable/remove/check/registry)。

## 未验收范围

真实执行器新会话是否遵守停用 guard(受控指令合同,静态证据不能替代,M4-09/10);完整机器卸载、升级执行(M4-07)、README/SKILL 文档同步(M4-08)。
