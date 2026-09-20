$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = 'C:\Users\wenbu\Desktop\Projects\[2608]OPC-APP\opc-app'
$tools = Join-Path $root '.tools'
$jdkDir = Join-Path $tools 'jdk'
$sdk = Join-Path $tools 'android-sdk'
$env:JAVA_HOME = $jdkDir
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
$sdkm = [System.IO.Path]::Combine($sdk, 'cmdline-tools', 'latest', 'bin', 'sdkmanager.bat')
if (-not [System.IO.File]::Exists($sdkm)) { throw ('sdkmanager missing: ' + $sdkm) }
Write-Host ('sdkmanager: ' + $sdkm)
Write-Host 'licenses...'
$y = ('y' + [char]10) * 80
$y | & $sdkm ('--sdk_root=' + $sdk) --licenses 2>&1 | Select-Object -Last 2
Write-Host 'packages...'
& $sdkm ('--sdk_root=' + $sdk) 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0' 2>&1 | Select-Object -Last 6
Write-Host '--- RESULT ---'
Write-Host ('adb: ' + [System.IO.File]::Exists([System.IO.Path]::Combine($sdk,'platform-tools','adb.exe')))
Write-Host ('android.jar: ' + [System.IO.File]::Exists([System.IO.Path]::Combine($sdk,'platforms','android-35','android.jar')))
Write-Host ('aapt2: ' + [System.IO.File]::Exists([System.IO.Path]::Combine($sdk,'build-tools','35.0.0','aapt2.exe')))
Write-Host 'DONE'
