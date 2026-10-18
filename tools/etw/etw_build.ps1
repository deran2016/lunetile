param([string]$OutputRoot)
$ErrorActionPreference='Stop'
$repoRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$outDir=if($OutputRoot){[IO.Path]::GetFullPath($OutputRoot)}else{Join-Path $repoRoot 'build/etw'}
$vswhere=Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if(!$vs){throw 'MSVC 2022 C++ build tools are required'}
$devcmd=Join-Path (@($vs)[0]) 'Common7/Tools/VsDevCmd.bat'
$environment=& $env:COMSPEC /d /c ('call "{0}" -arch=x64 -host_arch=x64 >nul && set' -f $devcmd)
if($LASTEXITCODE -ne 0){throw 'MSVC x64 environment initialization failed'}
foreach($line in $environment){
 if($line -match '^(PATH|INCLUDE|LIB|LIBPATH)=(.*)$'){[Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')}
}
[IO.Directory]::CreateDirectory($outDir) | Out-Null
& cl.exe /nologo /O2 /EHsc /W4 /MT "$PSScriptRoot/etw_extract.cpp" "/Fo$outDir/etw_extract.obj" /link "/OUT:$outDir/etw_extract.exe" tdh.lib advapi32.lib
if($LASTEXITCODE -ne 0){throw 'ETW extractor build failed'}
