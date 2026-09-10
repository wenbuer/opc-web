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
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

$m = Select-String -Path pyproject.toml -Pattern '^version\s*=\s*"(.+)"' | Select-Object -First 1
$ver = if ($m) { $m.Matches[0].Groups[1].Value } else { '0.0.0' }
Write-Host "== 构建 opc-web $ver ==" -ForegroundColor Cyan

# 员工手册种子：由代码生成，打进 _seed/ —— 打包后 bootstrap 优先读它
python -c "import sys; sys.path.insert(0, 'src'); from opc_web import templates; import pathlib; p = pathlib.Path('_seed'); p.mkdir(exist_ok=True); (p / '员工手册.md').write_text(templates.handbook_text(), encoding='utf-8'); print('  已生成 _seed/员工手册.md')"
if ($LASTEXITCODE -ne 0) { throw "生成员工手册种子失败" }

python -m PyInstaller --noconfirm --clean opc-web.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败" }

$dist = "$PSScriptRoot\dist\opc-web"
$exe = "$dist\opc-web.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "未生成 $exe" }

# 员工手册种子随产物走（datas 之外单独放，_seed 是运行时可替换的覆盖层）
# 资源目录：PyInstaller 6.x 把 datas 放 _internal/，_seed 也跟着放那儿（config.ASSET）
$seedDst = "$dist\_internal\_seed"
New-Item -ItemType Directory -Force -Path $seedDst | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '_seed/员工手册.md') -Destination $seedDst -Force
Write-Host "  已放入 _seed/员工手册.md"

if ($WithDsh) {
    $nodeSrc = (Get-Command node -ErrorAction SilentlyContinue).Source
    if (-not $nodeSrc) { $nodeSrc = 'D:/nodejs/node.exe' }
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
    $zip = "$PSScriptRoot\dist\opc-web-$ver-win64.zip"    # 字符串插值：本机 Join-Path 对第二个位置参数解析异常
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -LiteralPath $dist -DestinationPath $zip -CompressionLevel Optimal
    $mb = [Math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)
    Write-Host "== 打包完成：$zip（$mb MB）==" -ForegroundColor Green
} else {
    Write-Host "== 构建完成：$exe ==" -ForegroundColor Green
}
