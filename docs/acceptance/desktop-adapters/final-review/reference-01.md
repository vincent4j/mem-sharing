# 01 号独立审查：原生入口与配置边界

结论：有非阻断建议。未发现本范围内阻断默认根、默认 coding cordis preset 适配的缺陷。该结论仅针对静态合同与下述合成验证，不代表真机安装或桌面新会话验收通过。

候选 HEAD：e6603730304de7352f4c6caef1615adb2ad74e97。
manifest SHA-256：0067dd93ef04b7b2a3bcb84b92217e532f6a8560f0258552706b3cb553f65fc2。
本轮重新计算 manifest 哈希，并对全部 106 个快照文件逐个核对 SHA-256，无不一致。以 candidate.diff 区分新增逻辑；没有改候选源码。

## 已确认

- scripts/agents.json 的 dsh 与 zcode 用户入口分别为 ~/.dsh/AGENTS.md、~/.zcode/AGENTS.md；项目原生 AGENTS.md，项目 Skill 根为各自隐藏目录及 .agents/skills，runtime_status=pending。
- 本轮直接只读解码本机 DeepSeek Harness.app 的 app.asar：dsh-home-paths/lib/index.js:55–125 确认默认根、显式配置优先于环境变量、空白视为未设置；agent-instructions/lib/index.js:646–674 确认用户与项目候选；skill-filesystem/lib/index.js:149–179 确认项目及用户两根。
- 实际完整包内 web 路径为 dsh/node_modules/@deepseek-ai/dsh-web-app/cordis.patch.yml 与其 presets/cordis.patch.yml。web 覆盖层 519–520、578–579 禁用基础 Skill/指令插件，cordis preset 18–21 与 122–126 重新注册。合同把支持限定至该 preset 是必要而准确的。
- 本轮直接读取 ZCode.app/Contents/Resources/glm/zcode.cjs 的约 2208400–2213300、4257195–4258800 字符片段，确认用户 .zcode/AGENTS.md、项目首个 AGENTS.md、用户与项目合并，以及 .zcode/skills、.agents/skills 根。ZCode 指令根使用 HOME/USERPROFILE 后备 homedir，Skill 根使用 homeDirectory option 后备 homedir；不能将 ZCODE_HOME 当作规则根。
- 两份 Info.plist 版本与文档一致：DSH 0.2.1-rc.5、ZCode 3.16.3/3.16.3.8992。未重跑签名有效性验证。
- user_entries.py 的 DSH_HOME guard 在用户入口规划前执行；两家有各自 fallback 文本，未错误复用 Codex 专属称谓。

## 非阻断建议

### F01 / P3：DSH_HOME 的 `~\` 前缀兼容遗漏（本次引入）

位置：scripts/agm_core/user_entries.py:592–608，dsh_home_redirected，尤其 606。

触发：DSH_HOME 的字面值为 `~\.dsh`（单个反斜杠）。本机上游 dsh-home-paths/lib/index.js:70–73 明确同时接受 `~/` 与 `~\`，该值被解析为默认 ~/.dsh；候选仅接受 `/`。

实际：在隔离合成 HOME 中调用 dsh_home_redirected 返回 True；安装规划据此拒绝默认入口。
预期：既然应用解析后仍是默认根，应返回 False 并允许继续规划。
影响：少见合法路径写法被过度拒绝，无错误写入或隐私泄露；不阻断正常默认根或 `~/.dsh`。

本轮最小复现：在 /tmp 合成目录中，以 patch.dict(os.environ, {'DSH_HOME': '~\\.dsh'}) 设置变量，再调用 dsh_home_redirected(Path(tmp))，输出 `tilde_backslash_default_rejected=True`。实际读取的上游函数为：`if (path.startsWith("~/") || path.startsWith("~\\")) return join(homedir(), path.slice(2));`。

建议：按上游对支持的 tilde 前缀展开，并保留其余非空字符语义；不要简单全量替换路径反斜杠。
所需验证：添加 `~\`、`~\.dsh`、`~\other` 定向用例，确认默认根放行、其他根仍拒绝且不回显变量原值。

### F02 / P3：DSH_AGENTS_HOME 检测承诺与运行输出不完全一致（本次引入，文档/诊断建议）

位置：docs/acceptance/desktop-agent-contracts.md:59；docs/operations.md:168；scripts/agm_core/user_entries.py:_plan / dsh_home_redirected。

触发：DSH_HOME 未覆盖，DSH_AGENTS_HOME 指向非默认共享根。
实际：源码中没有 DSH_AGENTS_HOME 检查。本轮使用 DesktopInstallTests 合成夹具，显式 agents=['dsh']，设置该变量后 plan 的 effective_agents=['dsh']，序列化计划不包含 DSH_AGENTS_HOME 诊断。
预期：文档所称“应展开、规范化并比对”及“检查仅报告是否偏离默认”，应明确哪些检测当前实现，哪些只是静态合同要求；也可补充值脱敏的共享根诊断。
影响：用户可能误以为工具已经核对共享 Skill 根。这里不认定用户入口接入失败：DSH_HOME 默认时 ~/.dsh/AGENTS.md 仍被读取，memSharing 也未创建 Skill 或宣称桌面实际加载通过，因此不应为共享根覆盖阻断有效规则入口。

建议：最小改法是在操作文档明确目前仅自动拒绝 DSH_HOME 重定向，DSH_AGENTS_HOME 属于尚未自动检测的 Skill 能力边界；或添加只报告布尔状态的诊断。保留真实环境及自定义配置未验证声明。
所需验证：默认/空白/等价路径/非默认共享根用例；证明诊断不回显原值、规则入口继续有效、Skill 能力保持 pending。

## 实际执行与未验证范围

读取：snapshot/AGENTS.md、manifest.json、candidate-identity.json、candidate.diff、scripts/agents.json、user_entries.py、desktop-agent-contracts.md；相关路径/状态调用点与测试夹具；本机上述应用包源码片段及 Info.plist。公共规则索引按任务要求读取；历史索引仅作检索线索，未把旧路径结论当作当前证据。

执行：全部快照哈希核对；仅运行 DesktopInstallTests.test_redirect_stops_whole_install_without_echoing_private_value 与 test_dsh_root_resolution_matches_relative_and_tilde_contract，2/2 通过（0.004s）；另运行 F01/F02 的局部合成实验。所有实验均用 /tmp 临时目录、清空并替换子进程 HOME/TMPDIR，Python -B，未写快照。没有重复全量测试，也未把旧 578/74 日志当作本轮通过证据。

一次按文档缩写路径读取 web 配置得到 KeyError；随后只遍历 app.asar 的文件目录，定位完整包内路径并成功读取，无改路线或联网。

未验证：真实安装、当前桌面环境及插件配置、用户真实 preset、桌面原生新会话规则读回、Skill 实际加载、完整运行初始化调用链、非 macOS、其他审核编号负责的生命周期逻辑。未读用户凭据/聊天，未启动客户端，未联网，未修改主仓、快照、配置、版本或其他报告。本文是唯一持久产出。
