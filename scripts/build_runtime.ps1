param([Parameter(Mandatory=$true)][string]$BaseRuby)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'build_runtime_ruby.ps1') -BaseRuby $BaseRuby
$lock = Get-Content (Join-Path $repo 'src/runtime/dependencies.lock.json') -Raw | ConvertFrom-Json
$deps = Join-Path $repo 'build/runtime-deps'
$zlib = $lock.zlib
$archive = Join-Path $deps "zlib-$($zlib.version).tar.gz"
if (!(Test-Path $archive)) { Invoke-WebRequest -Uri $zlib.url -OutFile $archive }
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $zlib.sha256) { throw 'zlib source hash mismatch' }
if (!(Test-Path (Join-Path $deps "zlib-$($zlib.version)"))) {
    & tar.exe -xzf $archive -C $deps
    if ($LASTEXITCODE -ne 0) { throw 'zlib extraction failed' }
}
$native = Join-Path $repo 'build/runtime-native'
$webview = $lock.webview2
$webviewArchive = Join-Path $deps "microsoft.web.webview2.$($webview.version).nupkg"
$webviewSource = Join-Path $deps "webview2-$($webview.version)"
if (!(Test-Path $webviewArchive)) { Invoke-WebRequest -Uri $webview.url -OutFile $webviewArchive }
if ((Get-FileHash $webviewArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $webview.sha256) { throw 'WebView2 SDK hash mismatch' }
if (!(Test-Path (Join-Path $webviewSource 'build/native/include/WebView2.h'))) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($webviewArchive, $webviewSource)
}
foreach ($name in @('ogg', 'vorbis', 'theora')) {
    $dependency = $lock.$name
    $source = Join-Path $deps "lib$name-$($dependency.version)"
    $archive = "$source.tar.gz"
    if (!(Test-Path $archive)) { Invoke-WebRequest -Uri $dependency.url -OutFile $archive }
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $dependency.sha256) { throw "$name source hash mismatch" }
    if (!(Test-Path $source)) {
        & tar.exe -xzf $archive -C $deps
        if ($LASTEXITCODE -ne 0) { throw "$name extraction failed" }
    }
}
& cmake.exe -S $repo -B $native -G 'Visual Studio 17 2022' -A Win32
if ($LASTEXITCODE -ne 0) { throw 'Runtime CMake configure failed' }
& cmake.exe --build $native --config Release
if ($LASTEXITCODE -ne 0) { throw 'Runtime DLL build failed' }
& python -X utf8 -B (Join-Path $repo 'scripts/runtime_validation.py') stamp (Join-Path $native 'bin/Release')
if ($LASTEXITCODE -ne 0) { throw 'Runtime build identity failed' }
Write-Output "Runtime DLL: $native/bin/Release/Lunetile.dll"
Write-Output "Ruby migration helper: $native/bin/Release/rgssxp-ruby.exe"
