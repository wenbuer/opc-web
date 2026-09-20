# 构建 Windows 可执行产物（PyInstaller onedir）。
#
#   .\build.ps1                    → dist/opc-web/（不含 dsh，开箱即用走直连 API 引擎）
#   .\build.ps1 -WithDsh            → 额外捆绑 node + @deepseek-ai/dsh（+190MB，要用 DSH 引擎才需要）
#   .\build.ps1 -Zip                → 构建后打成 dist/opc-web-<版本>-win64.zip（GitHub Release 资产）
#
# 依赖：Python 3.9+ 与 pip install pyinstaller zstandard
param(
    [switch]$WithDsh,
    [switch]$Zip
)
$ErrorActionPreference = 'Stop'
# 注意：项目路径里带 `[2608]`，PowerShell 会把方括号当通配符 —— 凡是接路径的地方一律用 -LiteralPath。
$Root = Split-Path $PSScriptRoot -Parent      # 本脚本在 scripts/ 下，仓库根是上一层
Set-Location -LiteralPath $Root
$env:PYTHONIOENCODING = 'utf-8'

$m = Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"(.+)"' | Select-Object -First 1
$ver = if ($m) { $m.Matches[0].Groups[1].Value } else { '0.0.0' }
Write-Host "== 构建 opc-web $ver ==" -ForegroundColor Cyan

# 员工手册不用在这里生成：它就是 agents-seed/员工手册.md 本身（随仓库走），
# spec 已经把整个 agents-seed 目录打进产物，bootstrap 直接从那儿读。

python -m PyInstaller --noconfirm --clean "$PSScriptRoot\opc-web.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败" }

$dist = "$Root\dist\opc-web"
$exe = "$dist\opc-web.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "未生成 $exe" }

if ($WithDsh) {
    # node 位置：先看 PATH，再看环境变量 NODE_EXE（本机装在非默认目录时用它指定）
    $nodeSrc = (Get-Command node -ErrorAction SilentlyContinue).Source
    if (-not $nodeSrc) { $nodeSrc = $env:NODE_EXE }
    $dshSrc = Join-Path $env:APPDATA 'npm/node_modules/@deepseek-ai/dsh'
    if (-not (Test-Path -LiteralPath $nodeSrc)) { throw "找不到 node.exe：$nodeSrc" }
    if (-not (Test-Path -LiteralPath $dshSrc)) { throw "找不到 dsh 包：$dshSrc（npm i -g @deepseek-ai/dsh）" }
    $dshDst = "$dist\_dsh"
    New-Item -ItemType Directory -Force -Path $dshDst | Out-Null
    Copy-Item -LiteralPath $nodeSrc -Destination (Join-Path $dshDst 'node.exe') -Force
    $inner = Join-Path $dshDst 'node_modules/@deepseek-ai/dsh'
    New-Item -ItemType Directory -Force -Path (Split-Path $inner) | Out-Null
    if (Test-Path -LiteralPath $inner) { Remove-Item -LiteralPath $inner -Recurse -Force }
    Copy-Item -LiteralPath $dshSrc -Destination $inner -Recurse -Force
    # dsh.cmd 垫片：让捆绑的 node 跑捆绑的 bin.js（不依赖系统 PATH）
    $shim = '@echo off' + "`r`n" + '"%~dp0node.exe" "%~dp0node_modules\@deepseek-ai\dsh\lib\bin.js" %*' + "`r`n"
    Set-Content -LiteralPath (Join-Path $dshDst 'dsh.cmd') -Value $shim -Encoding ASCII
    Write-Host "  已捆绑 dsh 运行时（node + @deepseek-ai/dsh）"
}

if ($Zip) {
    # 变量名不能叫 $zip —— PowerShell 变量名大小写不敏感，$zip 和 -Zip 开关**是同一个变量**，
    # 而它被 param 声明成 [switch]，于是这行赋值必然抛
    # 「Cannot convert <路径> to type SwitchParameter」，-Zip 这条路从来没走通过。
    $zipFile = "$Root\dist\opc-web-$ver-win64.zip"    # 字符串插值：本机 Join-Path 对第二个位置参数解析异常
    if (Test-Path -LiteralPath $zipFile) { Remove-Item -LiteralPath $zipFile -Force }
    # 用 .NET API 打包：本机 Compress-Archive 在这条路径上会把参数解析拧掉
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $dist, $zipFile, [System.IO.Compression.CompressionLevel]::Optimal, $true)
    # 发布包自检：只允许 opc-web.exe 与 _internal/，混进本机技能 / 项目数据 / 配置就直接失败。
    # 这类东西一旦发出去就收不回来，宁可打包失败也别默认通过。
    $z = [System.IO.Compression.ZipFile]::OpenRead($zipFile)
    $bad = $z.Entries | Where-Object {
        $_.FullName -match '(?i)(^|/)(skills|工作区|批阅台|知识库|项目|opc-data|agents)(/|$)' -or
        $_.FullName -match '(?i)(^|/)(\.env|opc-config\.json)$'
    }
    $top = $z.Entries | ForEach-Object { ($_.FullName -split '/')[0] } | Sort-Object -Unique
    $z.Dispose()
    if ($bad) { throw "发布包混入了不该有的内容：" + (($bad | ForEach-Object { $_.FullName }) -join ', ') }
    Write-Host ("  自检通过：顶层只含 " + ($top -join '、'))
    $mb = [Math]::Round((Get-Item -LiteralPath $zipFile).Length / 1MB, 1)
    Write-Host "== 打包完成：$zipFile（$mb MB）==" -ForegroundColor Green
} else {
    Write-Host "== 构建完成：$exe ==" -ForegroundColor Green
}
