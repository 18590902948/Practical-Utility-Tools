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

function Get-TargetSizeMB {
    param($t)
    if ($t.IsRecycle)   { return Get-RecycleBinMB }
    if ($t.IsThumb)     { return Get-ThumbCacheMB }
    $total = 0
    foreach ($p in $t.Paths) { $total += Get-DirSizeMB $p }
    return [math]::Round($total, 1)
}

# 自动扫描 AppData 下所有已安装软件的缓存子目录（缓存/日志/临时，最多下探 2 层）。
# 不写死软件清单：以后新装的软件只要按标准方式放缓存，就会被自动检测到。
$appScanExclude = @('Microsoft','Packages','assembly','Temp','Google','pip','npm-cache','Yarn','JetBrains','QoderCN','InstallShield Installation Information','WPFLauncher',
    # 浏览器数据目录一律不扫：保护书签/收藏、登录信息、密码等用户数据
    'Mozilla','BraveSoftware','Opera Software','Vivaldi','360Chrome','360SE','SogouExplorer','Maxthon3','CentBrowser','Chromium','Yandex','TorBrowser','Waterfox')

# 判断路径是否位于浏览器数据目录下（书签/收藏、登录信息、密码所在的目录结构）。
# 命中即视为浏览器数据，自动扫描一律跳过，确保绝不清理浏览器内容。
function Test-BrowserDataPath {
    param([string]$path)
    $segContain = @('browser','firefox','vivaldi','sogou','maxthon','brave','opera','chromium','chrome','360se','mozilla','yandex','liebao')
    foreach ($seg in ($path -split '\\')) {
        $s = $seg.ToLower()
        foreach ($p in $segContain) {
            if ($s -match [regex]::Escape($p)) { return $true }
        }
        if ($s -in @('user data','profiles','bookmarks','login data')) { return $true }
    }
    return $false
}

function Scan-AppDataCaches {
    $grouped = @{}
    foreach ($root in @("$env:LOCALAPPDATA", "$env:APPDATA")) {
        if (-not (Test-Path $root)) { continue }
        foreach ($appDir in @(Get-ChildItem $root -Directory -Force -ErrorAction SilentlyContinue)) {
            if ($appScanExclude -contains $appDir.Name) { continue }
            $cacheDirs = @(
                Get-ChildItem $appDir.FullName -Directory -Recurse -Depth 2 -Force -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match '^(Cached.*|.*Cache$|SharedClientCache|logs|temp|ShaderCache|DXCache|GLCache|Crashpad|cache2)$' } |
                    Select-Object -ExpandProperty FullName |
                    Where-Object { -not (Test-BrowserDataPath $_) }
            )
            if ($cacheDirs.Count -eq 0) { continue }
            if (-not $grouped.ContainsKey($appDir.Name)) { $grouped[$appDir.Name] = @() }
            $grouped[$appDir.Name] = @($grouped[$appDir.Name] + $cacheDirs)
        }
    }

    $result = @()
    foreach ($key in $grouped.Keys) {
        $all = @($grouped[$key] | Sort-Object -Unique)
        $risky = $false; $hasTemp = $false
        foreach ($d in $all) {
            $leaf = Split-Path $d -Leaf
            if ($leaf -match '^(Cached.*|SharedClientCache)$') { $risky = $true }
            elseif ($leaf -ieq 'temp') { $hasTemp = $true }
        }
        # 注意：自动扫描到的缓存默认按"可以考虑"处理，不替用户打包票"绝对安全"。
        # 只有不影响任何使用的才会判 SAFE，否则一律需要用户确认后再删。
        if ($risky) {
            $level = $LVL_RISKY
            $desc = '含 CachedData/扩展缓存，删后需重新下载或重建索引'
        }
        else {
            $level = $LVL_CONSIDER
            if ($hasTemp) {
                $desc = '含 temp 临时目录，可能存有进行中数据，清理前请确认'
            }
            else {
                $desc = '自动检测的软件缓存，删除后可能需重建或重新登录，清理前请确认'
            }
        }

        # code 类编辑器（VS Code/Cursor/Windsurf/Trae 等）缓存按"删了会影响使用"+二次确认处理，与 JetBrains/QoderCN 一致
        $needConfirm = $false
        if ($key -match '(?i)(^code($| - )|vscodium|cursor|windsurf|trae|zed|void|sublime|lapce|axon|idx)') {
            $needConfirm = $true
            $level = $LVL_RISKY
            $desc = 'IDE 缓存，删后需重建索引/重下扩展，首次打开变慢'
        }

        $result += @{ Name=($key + ' 缓存'); Paths=@($all); Admin=$false; Level=$level; Desc=$desc; Size=0; NeedsSecondConfirm=$needConfirm }
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
$targets += @{ Name='缩略图缓存';         Paths=@("$env:LOCALAPPDATA\Microsoft\Windows\Explorer"); Admin=$false; Level=$LVL_SAFE; Desc='缩略图，自动重建';                    Size=0; IsThumb=$true }
$targets += @{ Name='错误报告 WER';       Paths=@("$env:LOCALAPPDATA\Microsoft\Windows\WER"); Admin=$false; Level=$LVL_SAFE; Desc='程序错误日志';                         Size=0 }
$targets += @{ Name='应用商店缓存';       Paths=@("$env:LOCALAPPDATA\Packages\Microsoft.WindowsStore_8wekyb3d8bbwe\LocalCache"); Admin=$false; Level=$LVL_SAFE; Desc='Microsoft Store 缓存'; Size=0 }
# --- 可以考虑：删除会失去可恢复内容或无法回滚 ---
$targets += @{ Name='回收站';             Paths=@('RECYCLE'); Admin=$false; Level=$LVL_CONSIDER; Desc='清空后文件永久删除，无法从回收站恢复'; Size=0; IsRecycle=$true }
$targets += @{ Name='旧版 Windows 文件';  Paths=@('C:\Windows.old'); Admin=$true; Level=$LVL_CONSIDER; Desc='删除后无法回滚旧系统（需夺权，删不掉会如实提示）'; Size=0; IsWindowsOld=$true }
# --- 删了会影响使用：删除后需重新下载/重新索引 ---
$targets += @{ Name='QoderCN IDE 缓存';   Paths=@(
    "$env:APPDATA\QoderCN\SharedClientCache",
    "$env:APPDATA\QoderCN\CachedData",
    "$env:APPDATA\QoderCN\CachedExtensionVSIXs",
    "$env:APPDATA\QoderCN\Cache",
    "$env:APPDATA\QoderCN\GPUCache",
    "$env:APPDATA\QoderCN\logs"
); Admin=$false; Level=$LVL_RISKY; Desc='扩展需重新下载、索引重建，首次打开变慢'; Size=0; NeedsSecondConfirm=$true }
$targets += @{ Name='JetBrains 缓存'; Paths=@("$env:LOCALAPPDATA\JetBrains"); Admin=$false; Level=$LVL_RISKY; Desc='IDE 索引与缓存（不含用户设置），删后需重建索引，首次打开项目变慢'; Size=0; NeedsSecondConfirm=$true }

# --- 软件缓存：自动扫描 AppData 下所有软件的缓存子目录（不碰浏览器数据/聊天记录/下载文件/账号配置等用户数据） ---
$targets += Scan-AppDataCaches
# 已下载的安装程序残留不属于某软件缓存，单独保留为已知安全项
$targets += @{ Name='安装器残留'; Paths=@("$env:LOCALAPPDATA\Downloaded Installations"); Admin=$false; Level=$LVL_SAFE; Desc='已下载的安装程序残留'; Size=0 }

# ---------------- 扫描（后台 Runspace，避免界面冻结） ----------------
# 在独立 Runspace 里逐项算大小，UI 线程只负责用 Timer 轮询进度并刷新标签。
# 不在单文件粒度上 DoEvents（那会让 Temp 这种几万文件的目录慢上百倍）。
$script:scanState     = [hashtable]::Synchronized(@{ Index=0; Count=0; Done=$false })
$script:scanRunspace  = $null
$script:scanPS        = $null
$script:scanHandle    = $null
$script:scanning      = $false
$script:lastShown     = 0

function Start-Scan {
    $list.BeginUpdate(); $list.Items.Clear(); $list.EndUpdate()
    $script:lastShown = 0
    $script:scanState = [hashtable]::Synchronized(@{ Index=0; Count=$targets.Count; Done=$false })
    $script:scanRunspace = [runspacefactory]::CreateRunspace()
    $script:scanRunspace.ApartmentState = 'STA'
    $script:scanRunspace.Open()
    $script:scanRunspace.SessionStateProxy.SetVariable('targets', $targets)
    $script:scanRunspace.SessionStateProxy.SetVariable('state', $script:scanState)
    $script:scanPS = [System.Management.Automation.PowerShell]::Create()
    $script:scanPS.Runspace = $script:scanRunspace
    [void]$script:scanPS.AddScript({
        function Get-DirSizeMBInner {
            param([string]$path)
            if (Test-Path $path) {
                $s = (Get-ChildItem $path -Force -Recurse -ErrorAction SilentlyContinue |
                      Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                if ($s) { return [math]::Round($s / 1MB, 1) }
            }
            return 0
        }
        for ($i = 0; $i -lt $targets.Count; $i++) {
            $t = $targets[$i]
            if ($t.IsRecycle) {
                try {
                    $sh = New-Object -ComObject Shell.Application
                    $rb = $sh.Namespace(0xA); $sz = 0
                    foreach ($x in $rb.Items()) { $sz += [double]$x.ExtendedProperty('Size') }
                    $t.Size = [math]::Round($sz / 1MB, 1)
                } catch { $t.Size = 0 }
            }
            elseif ($t.IsThumb) {
                $p = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
                $sz = 0
                if (Test-Path $p) {
                    $sz = (Get-ChildItem $p -Force -File -ErrorAction SilentlyContinue |
                           Where-Object { $_.Name -like 'thumbcache_*.db' -or $_.Name -like 'iconcache_*.db' } |
                           Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                }
                $t.Size = if ($sz) { [math]::Round($sz / 1MB, 1) } else { 0 }
            }
            else {
                $tot = 0
                foreach ($p in $t.Paths) { $tot += Get-DirSizeMBInner $p }
                $t.Size = [math]::Round($tot, 1)
            }
            $state.Index = $i + 1
        }
        $state.Done = $true
    })
    $script:scanHandle = $script:scanPS.BeginInvoke()
    $script:scanning = $true
}

function Stop-Scan {
    $script:scanning = $false
    try { if ($script:scanHandle) { $script:scanPS.EndInvoke($script:scanHandle) } } catch {}
    try { if ($script:scanPS) { $script:scanPS.Dispose() } } catch {}
    try { if ($script:scanRunspace) { $script:scanRunspace.Close() } } catch {}
}

# ---------------- 清理（后台 Runspace，支持暂停/取消/进度） ----------------
$script:cleanState    = [hashtable]::Synchronized(@{ Selected=@(); Index=0; Count=0; FreedTotal=0.0; Paused=$false; Cancel=$false; Done=$false; Results=@() })
$script:cleanRunspace = $null
$script:cleanPS      = $null
$script:cleanHandle  = $null
$script:cleaning     = $false

function Start-Clean {
    param($confirmed)
    $script:cleanState = [hashtable]::Synchronized(@{
        Selected=$confirmed; Index=0; Count=$confirmed.Count; FreedTotal=0.0; Paused=$false; Cancel=$false; Done=$false; Results=@()
    })
    $script:cleaning = $true
    foreach ($t in $confirmed) { $t.CleanStatus = '等待中' }

    $script:cleanRunspace = [runspacefactory]::CreateRunspace()
    $script:cleanRunspace.ApartmentState = 'STA'
    $script:cleanRunspace.Open()
    $script:cleanRunspace.SessionStateProxy.SetVariable('state', $script:cleanState)
    $script:cleanRunspace.SessionStateProxy.SetVariable('isAdmin', $isAdmin)
    $script:cleanPS = [System.Management.Automation.PowerShell]::Create()
    $script:cleanPS.Runspace = $script:cleanRunspace
    [void]$script:cleanPS.AddScript({
        # 注意：后台 Runspace 看不到主作用域的函数，大小重算逻辑必须内联在这里
        function Get-Size {
            param($t)
            if ($t.IsRecycle) {
                try {
                    $sh = New-Object -ComObject Shell.Application
                    $rb = $sh.Namespace(0xA); $sz = 0
                    foreach ($x in $rb.Items()) { $sz += [double]$x.ExtendedProperty('Size') }
                    return [math]::Round($sz / 1MB, 1)
                } catch { return 0 }
            }
            if ($t.IsThumb) {
                $p = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
                if (-not (Test-Path $p)) { return 0 }
                $sz = (Get-ChildItem $p -Force -File -ErrorAction SilentlyContinue |
                       Where-Object { $_.Name -like 'thumbcache_*.db' -or $_.Name -like 'iconcache_*.db' } |
                       Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                return if ($sz) { [math]::Round($sz / 1MB, 1) } else { 0 }
            }
            $tot = 0
            foreach ($p in $t.Paths) {
                if (Test-Path $p) {
                    $s = (Get-ChildItem $p -Force -Recurse -ErrorAction SilentlyContinue |
                          Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                    if ($s) { $tot += $s }
                }
            }
            return [math]::Round($tot / 1MB, 1)
        }
        for ($i = 0; $i -lt $state.Selected.Count; $i++) {
            if ($state.Cancel) {
                for ($j = $i; $j -lt $state.Selected.Count; $j++) { $state.Selected[$j].CleanStatus = '已取消' }
                break
            }
            $t = $state.Selected[$i]
            $t.CleanStatus = '清理中...'
            while ($state.Paused -and -not $state.Cancel) { Start-Sleep -Milliseconds 200 }
            if ($state.Cancel) { $t.CleanStatus = '已取消'; continue }

            $before = $t.Size
            if ($t.IsUpdate) {
                $wuaR = ((Get-Service wuauserv -ErrorAction SilentlyContinue).Status -eq 'Running')
                $bitsR = ((Get-Service bits -ErrorAction SilentlyContinue).Status -eq 'Running')
                if ($wuaR)  { Stop-Service wuauserv -Force -ErrorAction SilentlyContinue }
                if ($bitsR) { Stop-Service bits -Force -ErrorAction SilentlyContinue }
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
            elseif ($t.IsWindowsOld) {
                foreach ($p in $t.Paths) {
                    if (-not (Test-Path $p)) { continue }
                    & takeown /f $p /r /d y 2>$null | Out-Null
                    & icacls $p /grant "*S-1-5-32-544:F" /t /c /q 2>$null | Out-Null
                    Get-ChildItem $p -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                    Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            else {
                foreach ($p in $t.Paths) {
                    Get-ChildItem $p -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            if ($t.IsUpdate) {
                if ($wuaR)  { try { (Get-Service wuauserv -ErrorAction SilentlyContinue).Start() } catch {} }
                if ($bitsR) { try { (Get-Service bits -ErrorAction SilentlyContinue).Start() } catch {} }
            }
            $t.Size = Get-Size $t
            $freed = [math]::Round($before - $t.Size, 1)
            $state.FreedTotal += $freed
            $note = ''
            if ($before -gt 1 -and $freed -lt 0.1) { $note = '（未清理）' }
            $t.CleanStatus = if ($freed -ge 0.1) { "已清理 $freed MB" } else { "已跳过$note" }
            $state.Results += ("{0} [{1}]: 释放 {2} MB{3}" -f $t.Name, $t.Level, $freed, $note)
            $state.Index = $i + 1
        }
        $state.Done = $true
    })
    $script:cleanHandle = $script:cleanPS.BeginInvoke()

    # 切到清理模式界面
    $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    $btnAll.Visible = $false; $btnNone.Visible = $false; $btnClean.Visible = $false; $btnRefresh.Visible = $false
    $progressBar.Value = 0; $progressBar.Visible = $true
    $btnPause.Text = '暂停'; $btnPause.Visible = $true
    $btnCancel.Visible = $true
    $script:cleanTimer.Start()
}

function Stop-Clean {
    $script:cleaning = $false
    try { if ($script:cleanHandle) { $script:cleanPS.EndInvoke($script:cleanHandle) } } catch {}
    try { if ($script:cleanPS) { $script:cleanPS.Dispose() } } catch {}
    try { if ($script:cleanRunspace) { $script:cleanRunspace.Close() } } catch {}
}

# ---------------- 清理 ----------------
function Invoke-Clean {
    param($t)
    $before = $t.Size

    if ($t.IsUpdate) {
        $wuaRunning = ((Get-Service wuauserv -ErrorAction SilentlyContinue).Status -eq 'Running')
        $bitsRunning = ((Get-Service bits -ErrorAction SilentlyContinue).Status -eq 'Running')
        if ($wuaRunning)   { Stop-Service wuauserv -Force -ErrorAction SilentlyContinue }
        if ($bitsRunning)  { Stop-Service bits -Force -ErrorAction SilentlyContinue }
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
    elseif ($t.IsWindowsOld) {
        # Windows.old 归 TrustedInstaller 所有，普通管理员删不动，先夺权再删
        foreach ($p in $t.Paths) {
            if (-not (Test-Path $p)) { continue }
            & takeown /f $p /r /d y 2>$null | Out-Null
            & icacls $p /grant "*S-1-5-32-544:F" /t /c /q 2>$null | Out-Null
            Get-ChildItem $p -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    else {
        foreach ($p in $t.Paths) {
            Get-ChildItem $p -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    if ($t.IsUpdate) {
        # 非阻塞启动：发起启动指令但不死等，避免"正在等待服务启动"弹窗和界面卡死
        if ($wuaRunning)  { try { (Get-Service wuauserv -ErrorAction SilentlyContinue).Start() } catch {} }
        if ($bitsRunning) { try { (Get-Service bits -ErrorAction SilentlyContinue).Start() } catch {} }
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
        $item.SubItems.Add('') | Out-Null   # 第5列：清理进度（默认空）
        $item.Tag = $t
        $item.SubItems[2].ForeColor = $levelColor[$t.Level]
        if ($t.Admin -and -not $isAdmin) { $item.ForeColor = [System.Drawing.Color]::Gray }
        $list.Items.Add($item) | Out-Null
    }
    $list.EndUpdate()
    Update-SelLabel
}

# 把单个目标插入列表的已排序位置（边扫边蹦，不整表重建）
function Add-ListItem {
    param($t)
    if ($t.Size -le 0.1) { return }
    $item = New-Object System.Windows.Forms.ListViewItem($t.Name)
    $item.SubItems.Add(("{0:N1} MB" -f $t.Size)) | Out-Null
    $item.SubItems.Add($t.Level) | Out-Null
    $sub = $t.Desc
    if ($t.Admin) { $sub += ' [需管理员]' }
    $item.SubItems.Add($sub) | Out-Null
    $item.SubItems.Add('') | Out-Null   # 第5列：清理进度
    $item.Tag = $t
    $item.SubItems[2].ForeColor = $levelColor[$t.Level]
    if ($t.Admin -and -not $isAdmin) { $item.ForeColor = [System.Drawing.Color]::Gray }
    # 按 安全等级升序、大小降序 找到插入位置，插进去而不动其他行
    $newRank = $levelRank[$t.Level]
    $insertAt = $list.Items.Count
    for ($k = 0; $k -lt $list.Items.Count; $k++) {
        $ex = $list.Items[$k].Tag
        if ($newRank -lt $levelRank[$ex.Level]) { $insertAt = $k; break }
        if ($newRank -eq $levelRank[$ex.Level] -and $t.Size -gt $ex.Size) { $insertAt = $k; break }
    }
    $list.Items.Insert($insertAt, $item) | Out-Null
}

function Do-Clean {
    if ($script:scanning) {
        [System.Windows.Forms.MessageBox]::Show('还在扫描垃圾文件，请稍候再清理。', '提示', 'OK', 'Information')
        return
    }
    if ($script:cleaning) {
        [System.Windows.Forms.MessageBox]::Show('正在清理中，请等待本次完成。', '提示', 'OK', 'Information')
        return
    }
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

    # 二次确认放在后台启动前，由 UI 线程处理（避免后台线程弹窗）
    $confirmed = @()
    foreach ($t in $selected) {
        if ($t.Admin -and -not $isAdmin) {
            $t.CleanStatus = '已跳过(需管理员)'
            $script:cleanState.Results += "$($t.Name): 需要管理员权限，已跳过"
            continue
        }
        if ($t.NeedsSecondConfirm) {
            $r2 = [System.Windows.Forms.MessageBox]::Show(
                "即将单独清理：$($t.Name)`n`n$($t.Desc)`n`n确定要清理这一项吗？",
                '二次确认', 'YesNo', 'Warning')
            if ($r2 -ne 'Yes') {
                $t.CleanStatus = '已跳过(用户取消)'
                $script:cleanState.Results += "$($t.Name): 用户取消，已跳过"
                continue
            }
        }
        $confirmed += $t
    }
    if ($confirmed.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show('没有需要清理的项目。', '提示', 'OK', 'Information')
        foreach ($t in $selected) { $t.CleanStatus = $null }
        return
    }

    Start-Clean $confirmed
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
    # 开启双缓冲，消除拖动列宽时的文字闪烁
    try { $list.GetType().GetProperty('DoubleBuffered',[System.Reflection.BindingFlags]'Instance,NonPublic').SetValue($list,$true) } catch {}
    $list.Columns.Add('项目', 165) | Out-Null
    $list.Columns.Add('大小', 90) | Out-Null
    $list.Columns.Add('安全等级', 120) | Out-Null
    $list.Columns.Add('说明', 240) | Out-Null
    $list.Columns.Add('清理进度', 110) | Out-Null

    $bottom = New-Object System.Windows.Forms.Panel
    $bottom.Dock = 'Bottom'
    $bottom.Height = 48
    $bottom.Padding = New-Object System.Windows.Forms.Padding(10, 8, 10, 8)

    $script:selLabel = New-Object System.Windows.Forms.Label
    $selLabel.Text = '已选 0 项 / 0 MB'
    $selLabel.AutoSize = $true
    $selLabel.Location = New-Object System.Drawing.Point(12, 18)

    # 底部按钮统一 96x30、间距 8px，固定坐标排在右下角
    $btnW = 96; $btnH = 30
    # 四个槽位的 x 坐标（左→右）：320, 424, 528, 632
    $btnX = @(320, 424, 528, 632)

    $btnAll = New-Object System.Windows.Forms.Button
    $btnAll.Text = '全选'
    $btnAll.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnAll.Location = New-Object System.Drawing.Point($btnX[0], 9)
    $btnAll.Add_Click({ foreach ($i in $list.Items) { $i.Checked = $true }; Update-SelLabel })

    $btnNone = New-Object System.Windows.Forms.Button
    $btnNone.Text = '全不选'
    $btnNone.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnNone.Location = New-Object System.Drawing.Point($btnX[1], 9)
    $btnNone.Add_Click({ foreach ($i in $list.Items) { $i.Checked = $false }; Update-SelLabel })

    $btnClean = New-Object System.Windows.Forms.Button
    $btnClean.Text = '清理选中项'
    $btnClean.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnClean.Location = New-Object System.Drawing.Point($btnX[2], 9)
    $btnClean.Add_Click({ Do-Clean })

    $btnRefresh = New-Object System.Windows.Forms.Button
    $btnRefresh.Text = '刷新列表'
    $btnRefresh.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnRefresh.Location = New-Object System.Drawing.Point($btnX[3], 9)
    $btnRefresh.Add_Click({
        if ($script:scanning -or $script:cleaning) { return }
        $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        Start-Scan
        $script:scanTimer.Start()
    })

    # 清理模式控件：进度条占左侧两格、暂停/取消占右侧两格（默认隐藏）
    $script:progressBar = New-Object System.Windows.Forms.ProgressBar
    $progressBar.Location = New-Object System.Drawing.Point($btnX[0], 13)
    $progressBar.Size = New-Object System.Drawing.Size(2*$btnW + 8, 22)
    $progressBar.Minimum = 0; $progressBar.Maximum = 100; $progressBar.Value = 0
    $progressBar.Visible = $false

    $script:btnPause = New-Object System.Windows.Forms.Button
    $btnPause.Text = '暂停'
    $btnPause.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnPause.Location = New-Object System.Drawing.Point($btnX[2], 9)
    $btnPause.Visible = $false
    $btnPause.Add_Click({
        if (-not $script:cleaning) { return }
        $script:cleanState.Paused = -not $script:cleanState.Paused
        $btnPause.Text = if ($script:cleanState.Paused) { '继续' } else { '暂停' }
    })

    $script:btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = '取消清理'
    $btnCancel.Size = New-Object System.Drawing.Size($btnW, $btnH)
    $btnCancel.Location = New-Object System.Drawing.Point($btnX[3], 9)
    $btnCancel.Visible = $false
    $btnCancel.Add_Click({
        if (-not $script:cleaning) { return }
        $script:cleanState.Cancel = $true
        $script:cleanState.Paused = $false
        $btnPause.Text = '暂停'
        $btnCancel.Enabled = $false
    })

    $bottom.Controls.Add($selLabel)
    $bottom.Controls.Add($btnAll)
    $bottom.Controls.Add($btnNone)
    $bottom.Controls.Add($btnClean)
    $bottom.Controls.Add($btnRefresh)
    $bottom.Controls.Add($progressBar)
    $bottom.Controls.Add($btnPause)
    $bottom.Controls.Add($btnCancel)

    $form.Controls.Add($list)
    $form.Controls.Add($bottom)
    $form.Controls.Add($topLabel)
}

# ---------------- 启动 ----------------
New-Form

# 进度轮询定时器：后台 Runspace 扫描，前台每检测到"又扫完一项"就往列表插一行（边扫边蹦）。
$script:scanTimer = New-Object System.Windows.Forms.Timer
$script:scanTimer.Interval = 50
$script:scanTimer.Add_Tick({
    # 把上一 tick 以来扫完的目标逐个插入列表（按已排序位置，不整表重建）
    while ($script:lastShown -lt $script:scanState.Index) {
        Add-ListItem $targets[$script:lastShown]
        $script:lastShown++
    }
    if ($script:scanState.Done) {
        $script:scanTimer.Stop()
        Stop-Scan
        Update-SelLabel
        Update-Top
        $form.Cursor = [System.Windows.Forms.Cursors]::Default
    } else {
        $script:topLabel.Text = "正在扫描垃圾文件，请稍候... ($($script:scanState.Index) / $($script:scanState.Count))"
    }
})

# 清理进度轮询定时器：更新第5列状态、进度条、状态标签；完成时弹结果并恢复界面。
$script:cleanTimer = New-Object System.Windows.Forms.Timer
$script:cleanTimer.Interval = 50
$script:cleanTimer.Add_Tick({
    # 第5列：把每行的 CleanStatus 显示出来
    foreach ($it in $list.Items) {
        $t = $it.Tag
        if ($null -ne $t -and $null -ne $t.CleanStatus) {
            $it.SubItems[4].Text = $t.CleanStatus
        }
    }
    # 状态标签 + 进度条
    $idx = $script:cleanState.Index
    $cnt = $script:cleanState.Count
    if ($cnt -gt 0) {
        $progressBar.Value = [math]::Min([int]($idx / $cnt * 100), 100)
        $selLabel.Text = "清理中 $idx / $cnt 项，已释放 $([math]::Round($script:cleanState.FreedTotal,1)) MB"
    }
    if ($script:cleanState.Done) {
        $script:cleanTimer.Stop()
        Stop-Clean
        # 恢复编辑模式界面
        $progressBar.Visible = $false; $btnPause.Visible = $false; $btnCancel.Visible = $false
        $btnCancel.Enabled = $true
        $btnAll.Visible = $true; $btnNone.Visible = $true; $btnClean.Visible = $true; $btnRefresh.Visible = $true
        $form.Cursor = [System.Windows.Forms.Cursors]::Default
        # 原地刷新大小与状态（不整表重建，避免"哗一下"）
        $list.BeginUpdate()
        for ($k = $list.Items.Count - 1; $k -ge 0; $k--) {
            $it = $list.Items[$k]
            $t = $it.Tag
            $it.SubItems[1].Text = ("{0:N1} MB" -f $t.Size)
            $it.SubItems[4].Text = ''
            $t.CleanStatus = $null
            if ($t.Size -le 0.1) { $list.Items.RemoveAt($k) }
        }
        $list.EndUpdate()
        Update-SelLabel
        Update-Top
        $free = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
        $cancelled = $script:cleanState.Cancel
        $title = if ($cancelled) { '清理已取消' } else { '清理完成' }
        [System.Windows.Forms.MessageBox]::Show(
            ($script:cleanState.Results -join "`n") + "`n`n本次共释放 $([math]::Round($script:cleanState.FreedTotal,1)) MB`nC 盘当前可用: $free GB",
            $title, 'OK', 'Information')
    }
})

$form.Add_Shown({
    $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    Start-Scan
    $script:scanTimer.Start()
})
$form.Add_FormClosing({
    $script:scanTimer.Stop(); Stop-Scan
    if ($script:cleaning) { $script:cleanState.Cancel = $true; $script:cleanTimer.Stop(); Stop-Clean }
})
$list.Add_ItemChecked({ Update-SelLabel })
[System.Windows.Forms.Application]::Run($form)
