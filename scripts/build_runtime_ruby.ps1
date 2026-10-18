param([Parameter(Mandatory=$true)][string]$BaseRuby)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5 turns native stderr into ErrorRecords even on exit 0.
function Invoke-Logged([string]$Program, [object[]]$Parameters, [string]$Log) {
    $ErrorActionPreference = 'Continue'
    & $Program @Parameters *> $Log
    if ($LASTEXITCODE -ne 0) { throw "$Program exited $LASTEXITCODE; see $Log" }
}
$repo = Split-Path $PSScriptRoot -Parent
$lock = Get-Content (Join-Path $repo 'src/runtime/ruby.lock.json') -Raw | ConvertFrom-Json
$deps = Join-Path $repo 'build/runtime-deps'
$archive = Join-Path $deps "ruby-$($lock.version).tar.gz"
$source = Join-Path $deps "ruby-$($lock.version)-rgssxp-msvc32"
$out = Join-Path $repo "build/runtime-ruby-x86/patched-$($lock.version)"
New-Item -ItemType Directory -Force $deps | Out-Null
New-Item -ItemType Directory -Force -Path $out | Out-Null
$report = [ordered]@{version=$lock.version; target=$lock.target; source_sha256=$null; stage='prerequisites'; passed=$false}
try {
    if (!(Test-Path -LiteralPath $BaseRuby -PathType Leaf)) { throw 'BaseRuby must identify an existing Ruby 3.1+ executable used only as a build tool.' }
    $baseVersion = & $BaseRuby --version
    if ($LASTEXITCODE -ne 0) { throw 'Bootstrap Ruby could not run.' }
    $report.bootstrap = "$baseVersion"
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $vs = & $vswhere -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (!$vs) { throw 'MSVC 2022 x86/x64 C++ component is required.' }
    $devcmd = Join-Path (@($vs)[0]) 'Common7/Tools/VsDevCmd.bat'
    $environment = & $env:COMSPEC /d /c "call `"$devcmd`" -arch=x86 -host_arch=x64 >nul && set"
    if ($LASTEXITCODE -ne 0) { throw 'MSVC x86 environment initialization failed.' }
    foreach ($line in $environment) {
        if ($line -match '^(PATH|INCLUDE|LIB|LIBPATH|VCINSTALLDIR|VCToolsInstallDir|WindowsSdkDir|WindowsSDKVersion|VSINSTALLDIR)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')
        }
    }
    $report.compiler = (Get-Command cl.exe).Source
    if (!(Test-Path -LiteralPath $archive)) { Invoke-WebRequest -Uri $lock.source_url -OutFile $archive }
    $digest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($digest -ne $lock.sha256) { throw 'Ruby source SHA-256 mismatch; refusing to build.' }
    $report.source_sha256 = $digest
    if (!(Test-Path -LiteralPath $source)) {
        New-Item -ItemType Directory -Path $source | Out-Null
        & tar.exe -xzf $archive -C $source --strip-components=1
        if ($LASTEXITCODE -ne 0) { throw 'Source extraction failed.' }
    }
    & python (Join-Path $PSScriptRoot 'patch_runtime_ruby.py') $source
    if ($LASTEXITCODE -ne 0) { throw 'Reviewed MSVC x86 source patch failed.' }
    $report.patches = $lock.patches
    Push-Location $out
    try {
        $report.stage = 'configure'
        $configure = Join-Path $source 'win32/configure.bat'
        $base = $BaseRuby.Replace('\','/')
        Invoke-Logged $env:COMSPEC @('/d','/c',"call `"$configure`" --target=$($lock.target) --with-baseruby=$base --without-gmp --disable-install-doc --disable-rubygems --disable-yjit --disable-zjit") 'configure.log'
        $report.stage = 'build-local-shell'
        Invoke-Logged 'cl.exe' @('/nologo','/O2','/W3','/MT',"$repo/src/runtime/build_shell.c",'/Fe:build-shell.exe') 'shell-build.log'
        $priorComspec = $env:COMSPEC
        $env:COMSPEC = Join-Path $out 'build-shell.exe'
        $report.stage = 'generate-config'
        Invoke-Logged 'nmake.exe' @('/nologo','.config.h.time','YJIT_SUPPORT=no','ZJIT_SUPPORT=no','DEBUGFLAGS=-Z7') 'config-header.log'
        $report.stage = 'verify-x86-atomics'
        $configInclude = Join-Path $out '.ext/include/i386-mswin32_140'
        Invoke-Logged 'cl.exe' @('/nologo','/O2','/W3',"/I$configInclude","/I$source/include","$repo/tests/runtime_atomic_probe.c",'/Fe:atomic_probe.exe','/link','/MACHINE:X86') 'atomic-build.log'
        Invoke-Logged './atomic_probe.exe' @() 'atomic-smoke.log'
        $report.atomic_exit_code = 0
        $report.atomic_output = (Get-Content atomic-smoke.log -Raw).Trim()
        if ($report.atomic_exit_code -ne 0) { throw "Ruby x86 atomic memory integrity failed; see $out/atomic-smoke.log" }
        $report.stage = 'build-miniruby'
        $includes = "-I$out -I$configInclude -I$out/.ext/include -I$source/include -I$source -I$source/prism -I$source/enc/unicode/17.0.0"
        foreach ($subdir in @('prism','prism/util','enc','enc/trans','missing','win32','coroutine/win32')) { New-Item -ItemType Directory -Force (Join-Path $out $subdir) | Out-Null }
        # Reassemble cached coroutine objects with x86 SafeSEH metadata for the DLL linker.
        Invoke-Logged 'ml.exe' @('/nologo','/safeseh','/coff',"/Fo$out/coroutine/win32/Context.obj",'/c',"$source/coroutine/win32/Context.asm") 'coroutine-build.log'
        $vpath = "$out;$configInclude/ruby;$source/include/ruby;$source;$source/missing;$source/win32"
        $compilerWrapper = (Join-Path $out 'compile.cmd').Replace('/','\')
        @('@echo off', 'cd /d "%~dp0"', ('"' + $report.compiler + '" -nologo -source-charset:utf-8 %*'), 'exit /b %ERRORLEVEL%') | Set-Content $compilerWrapper -Encoding ascii
        $env:PATH = $out + ';' + $env:PATH
        $resourceWrapper = (Join-Path $out 'resource.cmd').Replace('/','\')
        $resourceCompiler = (Get-Command rc.exe).Source
        @('@echo off', 'cd /d "%~dp0"', ('"' + $resourceCompiler + '" %*'), 'exit /b %ERRORLEVEL%') | Set-Content $resourceWrapper -Encoding ascii
        $makeOptions = @('YJIT_SUPPORT=no','ZJIT_SUPPORT=no','DEBUGFLAGS=-Z7','ASFLAGS=-safeseh',"CC=$compilerWrapper","RC=$resourceWrapper","INCFLAGS=$includes","COUTFLAG=-Fo$out/","EXTOUT=$out/.ext","VPATH=$vpath")
        Invoke-Logged 'nmake.exe' (@('/nologo','miniruby.exe') + $makeOptions) 'build.log'
        $report.stage = 'verify-miniruby'
        Invoke-Logged './miniruby.exe' @("$repo/tests/runtime_ruby.rb") 'smoke.log'
        $report.stage = 'build-static-library'
        $archiveWrapper = (Join-Path $out 'archive.cmd').Replace('/','\')
        $librarian = (Get-Command lib.exe).Source
        @('@echo off', 'cd /d "%~dp0"', ('"' + $librarian + '" %*'), 'exit /b %ERRORLEVEL%') | Set-Content $archiveWrapper -Encoding ascii
        Invoke-Logged 'nmake.exe' (@('/nologo','vcruntime140-ruby400-static.lib') + $makeOptions + @("AR=$archiveWrapper")) 'static-build.log'
        $report.stage = 'generate-encoding-tables'
        Invoke-Logged $BaseRuby @("$source/tool/generic_erb.rb",'-c','-o',"$out/encdb.h","$source/template/encdb.h.tmpl","$source/enc") 'encoding-tables.log'
        Invoke-Logged $BaseRuby @("$source/tool/generic_erb.rb",'-c','-o',"$out/transdb.h","$source/template/transdb.h.tmpl","$source/enc/trans") 'transcoder-tables.log'
        $report.source_directory = $source
        $report.config_include = $configInclude
        $report.static_library = Join-Path $out 'vcruntime140-ruby400-static.lib'
        $report.stage = 'x86-interpreter-and-library-passed'
        $report.passed = $true
        Write-Output "x86 interpreter verified: $out (DLL embedding remains a separate gate)"
    } finally {
        if ($priorComspec) { $env:COMSPEC = $priorComspec }
        Pop-Location
    }
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $out 'gate.json')
}
