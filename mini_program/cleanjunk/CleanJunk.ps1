Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# 在打包后的 exe 中运行时自动提权：若不是管理员，用自身重新以管理员身份启动（ps1 源码模式由 bat 提权，跳过）
$selfExe = $null
try {
    $pn = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if ($pn -and ([System.IO.Path]::GetExtension($pn) -eq '.exe') -and ([System.IO.Path]::GetFileName($pn) -notmatch 'powershell|pwsh')) {
        $selfExe = $pn
    }
} catch {}
if (-not $isAdmin -and $selfExe) {
    try {
        Start-Process -FilePath $selfExe -Verb RunAs -ErrorAction Stop
        exit
    } catch {
        # 用户取消提权或无管理员权限：继续以普通权限运行，需管理员的项目会置灰跳过
    }
}

$LVL_SAFE    = '绝对安全'
$LVL_CONSIDER = '可以考虑'
$LVL_RISKY    = '删了会影响使用'
$levelColor = @{ $LVL_SAFE=[System.Drawing.Color]::ForestGreen; $LVL_CONSIDER=[System.Drawing.Color]::DarkOrange; $LVL_RISKY=[System.Drawing.Color]::Firebrick }
$levelRank  = @{ $LVL_SAFE=0; $LVL_CONSIDER=1; $LVL_RISKY=2 }

# ---------------- 工具函数 ----------------
function Get-DirSizeMB {
    param([string]$path)
    if (Test-Path $path) {
        $sum = (Get-ChildItem $path -Force -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        if ($sum) { return [math]::Round($sum / 1MB, 1) } else { return 0 }
    }
    return 0
}

function Get-RecycleBinMB {
    try {
        $shell = New-Object -ComObject Shell.Application
        $rb = $shell.Namespace(0xA)
        $size = 0
        foreach ($i in $rb.Items()) { $size += [double]$i.ExtendedProperty('Size') }
        return [math]::Round($size / 1MB, 1)
    } catch { return 0 }
}

function Get-ThumbCacheMB {
    $p = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
    if (-not (Test-Path $p)) { return 0 }
    $sum = (Get-ChildItem $p -Force -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'thumbcache_*.db' -or $_.Name -like 'iconcache_*.db' } | Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
    if ($sum) { return [math]::Round($sum / 1MB, 1) } else { return 0 }
}

function Get-BrowserCacheMB {
    param([string]$userDataBase)
    $total = 0
    foreach ($sub in @("$userDataBase\Default\Cache", "$userDataBase\Default\Code Cache")) {
        $total += Get-DirSizeMB $sub
    }
    return [math]::Round($total, 1)
}

function Get-TargetSizeMB {
    param($t)
    if ($t.IsRecycle)   { return Get-RecycleBinMB }
    if ($t.IsThumb)     { return Get-ThumbCacheMB }
    if ($t.IsBrowser)   { return Get-BrowserCacheMB $t.Paths[0] }
    $total = 0
    foreach ($p in $t.Paths) { $total += Get-DirSizeMB $p }
    return [math]::Round($total, 1)
}

# 自动扫描 AppData 下所有已安装软件的缓存子目录（缓存/日志/临时，最多下探 2 层）。
# 不写死软件清单：以后新装的软件只要按标准方式放缓存，就会被自动检测到。
$appScanExclude = @('Microsoft','Packages','assembly','Temp','Google','pip','npm-cache','Yarn','JetBrains','QoderCN','InstallShield Installation Information','WPFLauncher')

function Scan-AppDataCaches {
    $grouped = @{}
    foreach ($root in @("$env:LOCALAPPDATA", "$env:APPDATA")) {
        if (-not (Test-Path $root)) { continue }
        foreach ($appDir in @(Get-ChildItem $root -Directory -Force -ErrorAction SilentlyContinue)) {
            if ($appScanExclude -contains $appDir.Name) { continue }
            $cacheDirs = @(
                Get-ChildItem $appDir.FullName -Directory -Recurse -Depth 2 -Force -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match '^(Cached.*|.*Cache$|SharedClientCache|logs|temp|ShaderCache|DXCache|GLCache|Crashpad|cache2)$' } |
                    Select-Object -ExpandProperty FullName
            )
            if ($cacheDirs.Count -eq 0) { continue }
            if (-not $grouped.ContainsKey($appDir.Name)) { $grouped[$appDir.Name] = @() }
            $grouped[$appDir.Name] = @($grouped[$appDir.Name] + $cacheDirs)
        }
    }

    $result = @()
    foreach ($key in $grouped.Keys) {
        $all = @($grouped[$key] | Sort-Object -Unique)
        $risky = $false; $consider = $false
        foreach ($d in $all) {
            $leaf = Split-Path $d -Leaf
            if ($leaf -match '^(Cached.*|SharedClientCache)$') { $risky = $true }
            elseif ($leaf -ieq 'temp') { $consider = $true }
        }
        if ($risky) { $level = $LVL_RISKY }
        elseif ($consider) { $level = $LVL_CONSIDER }
        else { $level = $LVL_SAFE }

        $desc = '自动检测的软件缓存，删除后自动重建'
        if ($level -eq $LVL_RISKY) { $desc = '含 CachedData/扩展缓存，删后需重新下载或重建索引' }
        elseif ($level -eq $LVL_CONSIDER) { $desc = '含 temp 临时目录，可能存有进行中数据，清理前请确认' }

        $result += @{ Name=($key + ' 缓存'); Paths=@($all); Admin=$false; Level=$level; Desc=$desc; Size=0 }
    }
    return $result
}

# ---------------- 扫描目标 ----------------
$targets = @()
# --- 绝对安全：删了自动重建，无任何影响 ---
$targets += @{ Name='用户临时文件';       Paths=@("$env:LOCALAPPDATA\Temp");    Admin=$false; Level=$LVL_SAFE;     Desc='临时文件，删除后自动重建';                  Size=0 }
$targets += @{ Name='Windows 更新缓存';   Paths=@('C:\Windows\SoftwareDistribution\Download'); Admin=$true; Level=$LVL_SAFE; Desc='已安装的更新包残留';            Size=0; IsUpdate=$true }
$targets += @{ Name='交付优化缓存';       Paths=@('C:\Windows\SoftwareDistribution\DeliveryOptimization'); Admin=$true; Level=$LVL_SAFE; Desc='Windows 更新传输缓存';         Size=0; IsUpdate=$true }
$targets += @{ Name='CBS 更新日志';       Paths=@('C:\Windows\Logs\CBS');       Admin=$true;  Level=$LVL_SAFE;     Desc='Windows 更新日志';                       Size=0 }
$targets += @{ Name='pip 缓存';           Paths=@("$env:LOCALAPPDATA\pip");     Admin=$false; Level=$LVL_SAFE;     Desc='下载过的安装包缓存，下次自动重下';        Size=0 }
$targets += @{ Name='npm 缓存';           Paths=@("$env:LOCALAPPDATA\npm-cache"); Admin=$false; Level=$LVL_SAFE;   Desc='npm 包缓存';                             Size=0 }
$targets += @{ Name='yarn 缓存';          Paths=@("$env:LOCALAPPDATA\Yarn\Cache"); Admin=$false; Level=$LVL_SAFE;  Desc='yarn 包缓存';                            Size=0 }
$targets += @{ Name='Chrome 缓存';        Paths=@("$env:LOCALAPPDATA\Google\Chrome\User Data"); Admin=$false; Level=$LVL_SAFE; Desc='只清 Cache，不动书签/历史/密码'; Size=0; IsBrowser=$true }
$targets += @{ Name='Edge 缓存';          Paths=@("$env:LOCALAPPDATA\Microsoft\Edge\User Data"); Admin=$false; Level=$LVL_SAFE; Desc='只清 Cache，不动收藏/历史/密码'; Size=0; IsBrowser=$true }
$targets += @{ Name='缩略图缓存';         Paths=@("$env:LOCALAPPDATA\Microsoft\Windows\Explorer"); Admin=$false; Level=$LVL_SAFE; Desc='缩略图，自动重建';                    Size=0; IsThumb=$true }
$targets += @{ Name='错误报告 WER';       Paths=@("$env:LOCALAPPDATA\Microsoft\Windows\WER"); Admin=$false; Level=$LVL_SAFE; Desc='程序错误日志';                         Size=0 }
$targets += @{ Name='应用商店缓存';       Paths=@("$env:LOCALAPPDATA\Packages\Microsoft.WindowsStore_8wekyb3d8bbwe\LocalCache"); Admin=$false; Level=$LVL_SAFE; Desc='Microsoft Store 缓存'; Size=0 }
# --- 可以考虑：删除会失去可恢复内容或无法回滚 ---
$targets += @{ Name='回收站';             Paths=@('RECYCLE'); Admin=$false; Level=$LVL_CONSIDER; Desc='清空后文件永久删除，无法从回收站恢复'; Size=0; IsRecycle=$true }
$targets += @{ Name='旧版 Windows 文件';  Paths=@('C:\Windows.old'); Admin=$true; Level=$LVL_CONSIDER; Desc='删除后无法回滚旧系统（不存在则不显示）'; Size=0 }
# --- 删了会影响使用：删除后需重新下载/重新索引 ---
$targets += @{ Name='QoderCN IDE 缓存';   Paths=@(
    "$env:APPDATA\QoderCN\SharedClientCache",
    "$env:APPDATA\QoderCN\CachedData",
    "$env:APPDATA\QoderCN\CachedExtensionVSIXs",
    "$env:APPDATA\QoderCN\Cache",
    "$env:APPDATA\QoderCN\GPUCache",
    "$env:APPDATA\QoderCN\logs"
); Admin=$false; Level=$LVL_RISKY; Desc='扩展需重新下载、索引重建，首次打开变慢'; Size=0 }

# --- 软件缓存：自动扫描 AppData 下所有软件的缓存子目录（不碰聊天记录/下载文件/账号配置等用户数据） ---
$targets += Scan-AppDataCaches
# 已下载的安装程序残留不属于某软件缓存，单独保留为已知安全项
$targets += @{ Name='安装器残留'; Paths=@("$env:LOCALAPPDATA\Downloaded Installations"); Admin=$false; Level=$LVL_SAFE; Desc='已下载的安装程序残留'; Size=0 }

# ---------------- 扫描 ----------------
function Update-Sizes {
    foreach ($t in $targets) { $t.Size = Get-TargetSizeMB $t }
}

# ---------------- 清理 ----------------
function Invoke-Clean {
    param($t)
    $before = $t.Size

    if ($t.IsUpdate) {
        Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
        Stop-Service bits -Force -ErrorAction SilentlyContinue
    }

    if ($t.IsRecycle) {
        try { Clear-RecycleBin -Force -ErrorAction SilentlyContinue } catch {}
    }
    elseif ($t.IsThumb) {
        $p = $t.Paths[0]
        Get-ChildItem $p -Force -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'thumbcache_*.db' -or $_.Name -like 'iconcache_*.db' } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
    elseif ($t.IsBrowser) {
        $base = $t.Paths[0]
        foreach ($sub in @("$base\Default\Cache", "$base\Default\Code Cache")) {
            Get-ChildItem $sub -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    else {
        foreach ($p in $t.Paths) {
            Get-ChildItem $p -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    if ($t.IsUpdate) {
        Start-Service wuauserv -ErrorAction SilentlyContinue
        Start-Service bits -ErrorAction SilentlyContinue
    }

    $t.Size = Get-TargetSizeMB $t
    return [math]::Round($before - $t.Size, 1)
}

# ---------------- GUI ----------------
$script:form = $null
$script:list = $null
$script:topLabel = $null
$script:selLabel = $null

function Update-Top {
    $free = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
    $hint = ''
    if (-not $isAdmin) { $hint = '   未以管理员运行，带 [需管理员] 的项无法清理' }
    $topLabel.Text = "C 盘可用: $free GB$hint"
}

function Update-SelLabel {
    $total = 0.0
    foreach ($i in $list.Items) {
        if ($i.Checked -and $i.Tag) { $total += $i.Tag.Size }
    }
    $selLabel.Text = ("已选 {0} 项 / {1} MB" -f $list.CheckedItems.Count, [math]::Round($total, 1))
}

function Refresh-List {
    $list.BeginUpdate()
    $list.Items.Clear()
    $sorted = $targets | Sort-Object @{Expression={$levelRank[$_.Level]}}, @{Expression={$_.Size}; Descending=$true}
    foreach ($t in $sorted) {
        if ($t.Size -le 0.1) { continue }
        $item = New-Object System.Windows.Forms.ListViewItem($t.Name)
        $item.SubItems.Add(("{0:N1} MB" -f $t.Size)) | Out-Null
        $item.SubItems.Add($t.Level) | Out-Null
        $sub = $t.Desc
        if ($t.Admin) { $sub += ' [需管理员]' }
        $item.SubItems.Add($sub) | Out-Null
        $item.Tag = $t
        $item.SubItems[2].ForeColor = $levelColor[$t.Level]
        if ($t.Admin -and -not $isAdmin) { $item.ForeColor = [System.Drawing.Color]::Gray }
        $list.Items.Add($item) | Out-Null
    }
    $list.EndUpdate()
    Update-SelLabel
}

function Do-Clean {
    $selected = @($list.Items | Where-Object { $_.Checked -and $_.Tag } | ForEach-Object { $_.Tag })
    if ($selected.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('请先勾选要清理的项目。', '提示', 'OK', 'Information')
        return
    }
    $totalSel = ($selected | ForEach-Object { $_.Size } | Measure-Object -Sum).Sum

    $riskyNames = @($selected | Where-Object { $_.Level -eq $LVL_RISKY } | ForEach-Object { $_.Name })
    $warn = ''
    if ($riskyNames.Count -gt 0) { $warn = "`n`n!! 注意 !! 以下项删除会影响使用：$($riskyNames -join '、')`n请确认是否真的需要清理。" }

    $r = [System.Windows.Forms.MessageBox]::Show(
        "确认清理选中的 $($selected.Count) 项（约 $([math]::Round($totalSel,1)) MB）？$warn`n`n提示：被占用/锁定中的文件会自动跳过，不影响使用。",
        '确认清理', 'YesNo', 'Question')
    if ($r -ne 'Yes') { return }

    $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    $results = @()
    $freedTotal = 0.0
    foreach ($t in $selected) {
        if ($t.Admin -and -not $isAdmin) {
            $results += "$($t.Name): 需要管理员权限，已跳过"
            continue
        }
        $freed = Invoke-Clean $t
        $freedTotal += $freed
        $results += ("{0} [{1}]: 释放 {2} MB" -f $t.Name, $t.Level, $freed)
    }
    $form.Cursor = [System.Windows.Forms.Cursors]::Default

    $free = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
    [System.Windows.Forms.MessageBox]::Show(
        ($results -join "`n") + "`n`n本次共释放 $([math]::Round($freedTotal,1)) MB`nC 盘当前可用: $free GB",
        '清理完成', 'OK', 'Information')
    Refresh-List
    Update-Top
}

function New-Form {
    $script:form = New-Object System.Windows.Forms.Form
    $form.Text = '系统垃圾清理 - 作者：隼蝶.'
    $form.Size = New-Object System.Drawing.Size(760, 560)
    $form.StartPosition = 'CenterScreen'
    $form.MinimumSize = New-Object System.Drawing.Size(700, 480)
    $form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9)

    $script:topLabel = New-Object System.Windows.Forms.Label
    $topLabel.Dock = 'Top'
    $topLabel.Height = 34
    $topLabel.Padding = New-Object System.Windows.Forms.Padding(10, 8, 0, 0)
    $topLabel.Text = '正在扫描垃圾文件，请稍候...'

    $script:list = New-Object System.Windows.Forms.ListView
    $list.Dock = 'Fill'
    $list.CheckBoxes = $true
    $list.View = 'Details'
    $list.FullRowSelect = $true
    $list.GridLines = $true
    $list.MultiSelect = $false
    $list.Columns.Add('项目', 165) | Out-Null
    $list.Columns.Add('大小', 90) | Out-Null
    $list.Columns.Add('安全等级', 120) | Out-Null
    $list.Columns.Add('说明', 320) | Out-Null

    $bottom = New-Object System.Windows.Forms.Panel
    $bottom.Dock = 'Bottom'
    $bottom.Height = 48
    $bottom.Padding = New-Object System.Windows.Forms.Padding(10, 8, 10, 8)

    $script:selLabel = New-Object System.Windows.Forms.Label
    $selLabel.Text = '已选 0 项 / 0 MB'
    $selLabel.AutoSize = $true
    $selLabel.Location = New-Object System.Drawing.Point(12, 18)

    $btnAll = New-Object System.Windows.Forms.Button
    $btnAll.Text = '全选'
    $btnAll.Size = New-Object System.Drawing.Size(68, 30)
    $btnAll.Location = New-Object System.Drawing.Point(330, 9)
    $btnAll.Add_Click({ foreach ($i in $list.Items) { $i.Checked = $true }; Update-SelLabel })

    $btnNone = New-Object System.Windows.Forms.Button
    $btnNone.Text = '全不选'
    $btnNone.Size = New-Object System.Drawing.Size(68, 30)
    $btnNone.Location = New-Object System.Drawing.Point(406, 9)
    $btnNone.Add_Click({ foreach ($i in $list.Items) { $i.Checked = $false }; Update-SelLabel })

    $btnClean = New-Object System.Windows.Forms.Button
    $btnClean.Text = '清理选中项'
    $btnClean.Size = New-Object System.Drawing.Size(100, 30)
    $btnClean.Location = New-Object System.Drawing.Point(500, 9)
    $btnClean.Add_Click({ Do-Clean })

    $btnClose = New-Object System.Windows.Forms.Button
    $btnClose.Text = '关闭'
    $btnClose.Size = New-Object System.Drawing.Size(68, 30)
    $btnClose.Location = New-Object System.Drawing.Point(610, 9)
    $btnClose.Add_Click({ $form.Close() })

    $bottom.Controls.Add($selLabel)
    $bottom.Controls.Add($btnAll)
    $bottom.Controls.Add($btnNone)
    $bottom.Controls.Add($btnClean)
    $bottom.Controls.Add($btnClose)

    $form.Controls.Add($list)
    $form.Controls.Add($bottom)
    $form.Controls.Add($topLabel)
}

# ---------------- 启动 ----------------
New-Form
$form.Add_Shown({
    $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    Update-Sizes
    Refresh-List
    Update-Top
    $form.Cursor = [System.Windows.Forms.Cursors]::Default
})
$list.Add_ItemChecked({ Update-SelLabel })
[System.Windows.Forms.Application]::Run($form)
