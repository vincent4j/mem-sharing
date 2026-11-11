# Paseo 插件更新工作流

适用于维护者发布 Memory Sharing & Fusion 新版，以及用户更新已安装插件。官方商店地址：<https://paseo.sh/plugins/vincent4j/memsharing>；注册表 ID 为 `vincent4j/memsharing`，默认运行 ID 为 `memsharing`。

本文是操作说明，不表示已执行新版发布或真实机器更新。提交、推送、打标签、发布和真实 Host 部署按当次用户授权执行；只要求编写文档时不执行这些操作。

## 一、准备新版

1. 明确改动、目标版本、支持的 Paseo 版本和平台范围。插件更新不等于已安装的 memSharing 产品升级，也不升级 Context Keeper。Windows 限定预览不能因插件更新扩大为一般 Windows 支持。
2. 在独立源码 checkout 完成代码、当前文档及上架说明。需要时更新 `OVERVIEW.md`、翻译、manifest 和截图；下载来源、确认步骤及支持限制必须与实现一致。Context Keeper 说明应列明官方仓库、获取 `main` 及再次确认后执行安装的行为，不修改上游源码。
3. 按改动范围运行检查。插件代码至少运行：

   ```sh
   npm --prefix plugins/paseo run typecheck
   npm --prefix plugins/paseo test
   ```

   内核改动运行相应 Python 检查；需要全量回归时按仓库规则执行。分别说明源码测试、合成测试和真实 Host/客户端验证，不将类型检查或 `running` 当作全部功能通过。
4. 按[发行工具说明](../../tools/plugin-release/README.md)完成干净源码 S、生成发行 R、source/release 门禁及确定性核验。不要从上次已生成的发行树直接手改 payload 或摘要；受管文档变化也要纳入新来源。Windows 预览候选另按[Paseo 维护手册](paseo.md#windows-预览接线与候选准备)准备与核验，不能混用 Mac 身份或遗漏预览载荷。
5. 在获准的测试 Host 核验准确候选及受影响核心流程，保留既有记忆和恢复来源。需要部署时先确定目标 Host、安装来源、运行 ID、当前提交及必要备份；不以卸载记忆、重装 Context Keeper或重启 daemon 作为常规更新步骤。
6. 完成审核后，由主 Agent 在授权范围内推送发行提交、创建新标签和 GitHub Release。读取远端标签、资产和摘要，确认与批准候选一致；不移动旧标签，不覆盖旧版本来交付新内容。

## 二、申请更新商店版本

当前插件通过 Git 来源上架。推送 `main` 或创建 GitHub Release 不会自动更新商店审核版本，Git 更新需要手动提交。

1. 在 [Paseo 插件提交表单](https://github.com/getpaseo/plugins/issues/new?template=submit-plugin.yml)提交新版，明确是更新已有 `vincent4j/memsharing`。Source 填 GitHub 源码目录和新 ref，不将注册表 ID 当作源码；也可向官方注册表提交更新现有记录的 PR。
2. 提供以下内容，不复用示例版本或旧 SHA：

   ```text
   Plugin: Memory Sharing & Fusion
   Existing registry ID: vincent4j/memsharing
   Source: https://github.com/vincent4j/mem-sharing/tree/<新标签>/plugins/paseo
   Git ref: <新标签>
   Commit: <已核验的完整发行提交 SHA>
   Plugin path: plugins/paseo
   Changes: <本次变更及兼容范围>
   Validation: <实际完成的测试与宿主验收，列明待验边界>
   Media: <当前真实界面图的公开 HTTPS 地址，若需要更新>
   ```

3. 跟进新审核 PR，按实际反馈修正来源或素材。界面变化时更新真实截图，隐藏私密信息；首图作为商店缩略图，原理图仅作补充。媒体链接应直接返回 HTTP 200 和对应图片类型。
4. 审核通过、PR 合并后，核对[在线注册表记录](https://plugins.paseo.sh/plugins/vincent4j/memsharing.json)：`artifact.commit`、`artifact.pluginPath`、上架介绍及图片与批准内容一致。再检查商店页面；审核合并与在线目录更新分别确认，缓存未刷新时不要称新版已可安装。

## 三、用户更新插件

先在需要更新的 Host 上检查现有安装。以下命令使用默认运行 ID；若安装时指定过别名，替换为实际 ID。远程 Host 在 `plugin` 前加 `--host <目标地址>`，不要操作到另一台电脑。

```sh
paseo plugin ls memsharing
```

根据结果选择对应路径：

| 安装来源 | 更新行为 |
| --- | --- |
| 官方商店 `vincent4j/memsharing` | 跟随注册表批准的版本；先确认新版已进入在线注册表 |
| 直接 Git 来源 | 普通更新检查远端默认分支 HEAD，不受初次安装标签约束；先核对候选是否为目标发行提交，不将其视为商店审核更新 |
| 本地目录 | `update` 跳过目录来源；维护者准备并核验新目录内容后使用 `reload`，不要在真实安装目录随意 `git pull` 或混合两版文件 |

商店安装先检查更新，不执行替换：

```sh
paseo plugin update memsharing --check
```

核对当前/目标提交及审核信息后，再执行并按提示确认：

```sh
paseo plugin update memsharing
paseo plugin ls memsharing
```

要求目标提交与商店批准提交一致，状态为 `running` 且无加载错误。打开同一 Host 的插件状态页，核对原有共享状态；按变更范围验证核心操作，涉及写入时重新预览并批准。插件重载后不能复用旧确认计划。

本地目录在完成受控内容替换和检查后执行：

```sh
paseo plugin reload memsharing
paseo plugin ls memsharing
```

直接 Git 安装若确需指定新版，先独立核验完整发行提交，再按官方 CLI 的 `--ref` 流程更新；显式 `--ref` 会直接应用而不再次询问，不作为普通商店用户的默认步骤。不要承诺应用内已有手动版本审核功能，当前官方文档以 CLI 更新审核为准。

## 四、失败与恢复

- 没有发现新版：核对安装来源、目标 Host 和在线注册表提交；缓存可能延迟新 pin。不要通过反复重装或切到默认分支绕过审核。
- 下载、准备或激活失败：Paseo 保留原安装，先读取实际状态和 `paseo plugin logs memsharing`，核实旧版是否仍运行，再处理原因。
- 更新后业务异常：停止新的业务写入，保留日志、备份和恢复来源。插件代码回退与产品数据恢复分别处理；已提交产品状态不能靠换回旧插件自动降级。
- 存在 busy、unknown 或未闭合事务：先按[Paseo 维护手册](paseo.md#所有权取消与恢复)核对事务，不抢锁、不复用批准、不删除记忆或操作日志来强行更新。

## 完成条件

维护者只有在发行提交已核验、审核通过且在线记录指向新提交后，才报告商店更新完成。用户只有在目标 Host 已安装准确提交、插件正常运行且受影响流程核验后，才报告该机器更新完成。未操作的机器和未验证的功能保持待验。

## 官方依据

- [发布与 Git 更新提交](https://paseo.sh/docs/plugins/publishing#plugin-registry)
- [CLI 更新、确认及失败保留规则](https://paseo.sh/docs/plugins/reference#cli-reference)
- [安装来源](https://paseo.sh/docs/plugins/reference#plugin-sources)
- [注册表协议与缓存](https://github.com/getpaseo/plugins/blob/main/PROTOCOL.md)
