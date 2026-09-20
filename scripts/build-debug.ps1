# OPC 移动端 debug 构建：自动带上工程内自带工具链（.tools），不依赖系统 PATH。
#   pwsh -File scripts/build-debug.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$jdk = Join-Path $root '.tools\jdk'
$sdk = Join-Path $root '.tools\android-sdk'

if (-not (Test-Path (Join-Path $jdk 'bin\java.exe'))) { throw "缺少 JDK：先跑 scripts/setup-android-sdk.ps1（或自行安装 JDK 17 并设 JAVA_HOME）" }
if (-not (Test-Path (Join-Path $sdk 'platforms\android-35\android.jar'))) { throw "缺少 Android SDK 35：先跑 scripts/setup-android-sdk.ps1" }

$env:JAVA_HOME = $jdk
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk

Push-Location $root
try {
    & (Join-Path $root 'gradlew.bat') :app:assembleDebug --no-daemon @args
    if ($LASTEXITCODE -ne 0) { throw "构建失败（exit $LASTEXITCODE）" }
    $apk = Join-Path $root 'app\build\outputs\apk\debug\app-debug.apk'
    if (Test-Path $apk) {
        Write-Host ("APK: " + $apk + "  " + [math]::Round((Get-Item $apk).Length/1MB,1) + " MB")
    }
} finally {
    Pop-Location
}
