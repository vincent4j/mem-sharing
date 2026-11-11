# memSharing Windows 双端预览

本包仅用于已验证的 DELL Win11 x64 / 本地 NTFS / ZCode 3.17.2.9661 / WorkBuddy 5.9.3.0 首次接入。以 `preview-manifest.json` 的 `core_version + preview_revision` 标识构建；不代表一般 Windows、升级、迁移或自动融合支持。不需要管理员，不修改系统 PATH。

## 安装

1. 使用交付时提供的 SHA256 核对 ZIP（`Get-FileHash -Algorithm SHA256`），解压到自己可长期保留的新目录。不要覆盖已有目录。hash只证明完整性；来源须为已信任的固定仓库/交付渠道。
2. 用本机实际 Python 3 解释器完整路径替换下面的 `C:\path\python.exe`；`C:\path\preview` 是解压目录，`C:\path\plans` 是你已创建的本地计划目录。计划与备份可能含私文，不上传或放进待删除代码目录。

```powershell
& 'C:\path\python.exe' -I -S -B 'C:\path\preview\scripts\windows_preview.py' plan --home $env:USERPROFILE --source 'C:\path\preview' --output 'C:\path\plans\install.json'
```

3. 核对输出方案中的两家入口、公共路径和备份位置；`exit 5 / approval_required` 表示预览成功。只有明确同意该精确方案，才把返回的 `plan_sha256` 填入执行命令：

```powershell
& 'C:\path\python.exe' -I -S -B 'C:\path\preview\scripts\windows_preview.py' apply --home $env:USERPROFILE --plan 'C:\path\plans\install.json' --plan-sha256 '<方案返回的完整摘要>'
```

4. `exit 0 / committed` 后在 ZCode、WorkBuddy 各开新会话读取公共记忆。明确要求新增时，客户端读取 mem-sharing Skill 并执行其中的 `add`；原私有记忆不迁移。首次空公共文件是正常状态。

已有安装、同名 Skill、链接、非普通目录或外部修改会拒绝；不要删目录、重装或改回执绕过。上次预览退出留下的空目录也不能自动当作新安装，需先核实原事务及允许范围。

## 校验解压后的文件

在解压目录的 PowerShell 中逐文件核对 manifest：

```powershell
$m = Get-Content -LiteralPath '.\preview-manifest.json' -Raw | ConvertFrom-Json
$m.files.PSObject.Properties | ForEach-Object {
    $p = Join-Path $PWD $_.Name
    if ((Get-Item -LiteralPath $p).Length -ne $_.Value.size -or (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -ne $_.Value.sha256) { throw '文件校验失败' }
}
```

## 退出与恢复

日常使用不需要退出。需要撤接入时先生成新方案，确认后再 apply；不会自动融合/归还旧记忆：

```powershell
& 'C:\path\python.exe' -I -S -B 'C:\path\preview\scripts\windows_preview.py' exit-plan --home $env:USERPROFILE --output 'C:\path\plans\exit.json'
& 'C:\path\python.exe' -I -S -B 'C:\path\preview\scripts\windows_preview.py' apply --home $env:USERPROFILE --plan 'C:\path\plans\exit.json' --plan-sha256 '<退出方案返回的完整摘要>'
```

公共正文先导出到用户目录 `.mem-sharing-preview-exports/<退出UUID>/MEMORY.md` 并回读；备份在 `.mem-sharing-preview-backups/`，都留在代码目录外。外部编辑或未知内容保留并停止，不自动覆盖或递归删除。

中断时保留程序返回的 manifest 路径，用此解压包中仍保留的入口执行 `recover --home <原HOME> --manifest <原manifest>`。未知锁不自动抢占；先由操作人确认原进程和锁归属。不修私文、不删除备份，也不要通过重新安装掩盖恢复失败。
