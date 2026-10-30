# 手动收口入库的格式与验证边界

授权：本轮派工明确要求“按 M1-05 的先例（手动写入+格式合规说明）”完成一条 worklog 并挂 memory-keeper 入口；同时禁止修改用户级文件。本轮按此具体要求执行，不创建 guard 缓存、不动态 monkeypatch 上游、不重新建立写后基线。

| 要求 | 本轮落点 |
|---|---|
| 一条本会话新日志、保留旧记录 | `docs/context-keeper/worklogs/2026-10-29-M1负向验证与收口.md`，新建一次；旧 worklogs/evolution/plans 未改 |
| 来源与时间 | 头部来源为“主 Agent 收口汇总”，关联任务消息及实际 +08:00 时间；session marker 使用稳定任务标识，明确不是宿主 UUID |
| 事实、方法、观察、判断、后续与证据 | 日志涵盖 N1/N2、各任务结果、四环、P2/P3 偏差、P4 后续纠正、M2 进展及未完成事项；所有历史来源可定位 |
| 旧日志只追加、不覆盖 | 本轮不修改任何旧日志；旧 P4 未执行文字作为历史保留，在新收口日志明确后续实测结果 |
| memory-keeper 入口 | 只添加收口当前主题、阻断待办与最新时间线，原有行逐字保留；不另写经验、不修旧接力条目 |
| 状态诚实 | M1/M1-07 部分通过；两家限定运行通过不代表 WorkBuddy，静态装配不代表完整接力；M2 进度不冒充本轮测试 |

本会话首次 Skill 补桥仅只读预览，输出 project/unchanged，无需变更。首次保存前已运行上游 `status --root .`，rc=0。用户指定的手动先例优先于 Skill 标准 record-path/guard 流程，因此 **record-path、record-guard、save-report 均未运行**；不能声称标准历史基线缓存/会话保护已通过。没有改源码或把缓存移到其他位置来制造标准调用成功。

写后运行一次只读 coverage，原始输出和退出码见 `closeout-coverage.*`。coverage 是结构检查，不证明事实正确或完整会话保护；既存 legacy 日志缺 session-id 保持原状，missing_summary 只作提示，不为通过校验重写历史。

最终真实库全树文件清单/SHA 为 `store-after-closeout.json`；旧文件保护前后原始指纹见 `old-protected-{before,after}.json` 与系统 diff。库相对 Git 的完整差异见 `closeout-store.diff`，新 worklog 全文单独见 `closeout-new-worklog.diff`。实际改动只有新 worklog 与 memory-keeper 收口入口；前后指纹不能代替 OS 访问审计，也不承诺未观察区间不存在瞬时改后还原。

入口指纹覆盖六个明确列出的项目/用户入口，未作全用户目录审计；CLI 运行元数据不属于被测项目库零差异范围。本轮未修改、提交或推送并行代码。
