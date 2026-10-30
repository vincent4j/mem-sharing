# memSharing 全库代码改名交接(§23,基线 98af5d6+bb6066a;§26 范围缩减后)

执行者:突突兔。未 commit/push;未动真实 HOME;文档四件套(README/SKILL/INSTALL/llms.txt)与 m4-09 文档为并行方改动,未触碰;仓库根 AGENTS.md/CLAUDE.md 的旧标记块按裁定不动(M4-10 重建)。

## 改动文件

代码(18):`scripts/agents.json`、`scripts/agm.py`、`scripts/install.py`、`scripts/agm_core/{check,enable,entries,layout,legacy_import,migrate,paths,registry,remove,upgrade,user_entries,user_install,user_rules_organize,versions}.py`

测试(14):`tests/unit/{runtime_fixture,test_cli,test_m402_layout_registry,test_m403_migrate,test_m404_install,test_m405_user_entries,test_m407_upgrade,test_m408_installer,test_m408_organize}.py`、`tests/integration/{test_m207_cli_cycle,test_m404_install_process,test_m406_cli_lifecycle,test_m407_real_upgrade,test_m408_installer_cli}.py`

`scripts/registry.json` 与 `scripts/backups/` 为本仓 dogfood 历史数据,未改(真机 M4-10 重建)。

## 新命名套件

- 路径:R `~/.mem-sharing`(layout.root);C `~/.local/share/mem-sharing`;版本库存 `~/.local/share/mem-sharing-versions`(PRODUCT 拼装);bootstrap `~/.mem-sharing-install-<op>`;安装锁 `~/.mem-sharing-install.lock`;升级 guard `~/.mem-sharing-upgrade.json`。
- 标记串:`mem-sharing:rules` / `mem-sharing:memory-denied` / `mem-sharing:keeper-exception` / `mem-sharing:organized-<id>`(enable.py 三常量、entries/remove 字面量、user_rules_organize 正则与登记)。
- 枚举与身份:bridge_owner 值 `mem-sharing`(agents.json、paths.BRIDGE_OWNERS、check.BRIDGE_MARKERS 键);product_id `mem-sharing`(user_install/upgrade/versions PRODUCT、registry 校验、migrate journal/owner);菜单 `/mem-sharing 菜单`(模板与断言);`OFFICIAL = https://github.com/vincent4j/mem-sharing`(新增 `LEGACY_OFFICIAL` 旧 URL 仍记作官方来源,应对真机 origin 尚未改名的过渡期);痕迹探测串 `b'mem-sharing:'`。

## v0 源/目标分离(§23.3)

- `layout.legacy_root = ~/.agents-group`:v0 历史位置,只读源,产品永不写入。
- 判别:V 无台账时 R 非空→停止;R 空且 legacy_root 有内容(无产品痕迹)→v0;两者皆空→fresh。legacy_root 完整枚举进 observations(scene 绑定);`var`、`skills/agent-group-memory` 痕迹检查挂 legacy_root;入口痕迹检查排除 legacy_root;content_candidate 按 ROOTS 探 legacy_root(migration 路由同步)。
- `legacy_import.plan_import(source_root, target_root, op)` 双根:package/快照/归档全部在 R 下,源侧零写入(新索引是 R 下的新文件,旧 MEMORY.md 原地不动);`_content_scene` 简化为源树指纹不变;plan_install 增加源与 legacy_root 的重叠拒绝。

## 升级白名单(§26 注)

本轮已按改名后字节登记 after 哈希(登记于 upgrade.py,与 P 侧原值成对):

- P(27d6e26,不变):`scripts/agents.json` `24258be62f8e4d5fe260a1578fbda55c456a74a4a812bc154bdadcdcee48e396`;`scripts/agm_core/user_entries.py` `5cff6dfb0f21dc24b21b41b0b815bf4570cec3f795b41d7771054e52a191f789`
- 本发行(改名后):`scripts/agents.json` `50ca9e0e53bfc068a1b60efdf734a4be6e316a2ee3bffe4c4ceaa301700b4147`;`scripts/agm_core/user_entries.py` `a8fad5f078b5ac32a33edf40b4be159ba7b59fd7d0c40d8e22a266d2c4af2586`

配套改名语义(均属 §26 下轮整块删除清单):`_predecessor_whitelisted` / `_load_whitelisted_predecessor`(P 台账旧 product_id 内存规范化装载)、`_plan` 白名单分支的 product_id 迁移、`inspect_machine` 的白名单装载接入、`_code_matches` 接受 `{PRODUCT, LEGACY_PRODUCT_ID}` 集合、真链夹具把 P 落位预置到新名、两个专用真链用例。标记串改名后 P 时代旧块在 T 下按漂移处理(装配 preview 提出追加新块,执行被 registry 冻结防护拒绝、零写入)——该场景随白名单删除轮一并消失(真机无 P 升级机,M4-10 全量重建)。

## 有意保留的旧字面量(历史事实)

`legacy_import.py`/`user_install.py` 的 `skills/agent-group-memory`(v0 源内历史产品名目录检查);`migrate.py` 的 `b"agent-group-memory"`(历史源 SKILL.md 身份);`install.py` 的 `LEGACY_OFFICIAL`;`layout.py` 的 legacy_root `.agents-group`;测试中 P 侧路径、历史投影名与 dogfood 断言。

## 验证

全量 **446 单元(OK, exit 0)+ 72 集成(OK, exit 0)**;真链 `test_m407_real_upgrade` 6/6(含 P=27d6e26 真实链、白名单正/负例、六阶段恢复与逐文件窗口)。命令与退出码见 commands.txt,原始输出见 unit.log / integration.log。