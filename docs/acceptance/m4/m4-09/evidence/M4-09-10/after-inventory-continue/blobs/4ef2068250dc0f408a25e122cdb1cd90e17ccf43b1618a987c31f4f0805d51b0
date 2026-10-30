# M4-02 主 Agent 验收判定

日期:2026-10-30。判定人:主 Agent(独立复核,不采信执行者自报数字)。

## 结论:通过(经一轮退回修复)

## 独立验证记录

1. 全量测试复跑:单元 252、集成 53,均 OK、退出 0(含执行者新增 18+2 项定向测试);
2. 零写入抽查:空 HOME(临时目录)下 `--help` 与 `check-memory` 零持久写入(fake HOME 内除夹具项目外无任何新建条目);
3. 未安装现场语义:`check-memory` 返回 status=gaps、errors=[]、rc=1(缺口),建议走 enable,不自动建账、不写 var/;
4. 退回项已修复并复核:`validate_paths` 原对父链含符号链接组件的 HOME(所有 macOS `mktemp` 目录)误报
   `runtime_path_conflict`;修复后改为仅检查 HOME 以下受管链路的逐段符号链接。复测 `HOME=$(mktemp -d)`
   下 check-memory 返回 gaps/errors=[],零写入;定向回归 2 项纳入套件。

## 验收范围与未验收范围

- 通过:layout 统一、registry schema=2 严格模型、三命令接线、HOME/layout 注入测试、旧 schema=1 拒绝(不静默重建);
- 未验收(按任务书留后续):账本迁移执行(M4-03)、首装/判别/v0 复制(M4-04)、新会话运行时、Windows/Linux。

## 遗留注意事项

- M4-03 迁账落地前,禁止在真实 HOME 下运行项目命令(三命令已定位 `~/.agents-group/var/`,而本机 v0
  目录尚无台账;真实运行会向 v0 目录写入 var/,属未批准操作)。
