param([Parameter(Mandatory=$true)][string]$Directory, [ValidateSet('Create','Trust','Remove')][string]$Action='Create')
$ErrorActionPreference = 'Stop'
function Write-Pem([string]$Path, [string]$Label, [byte[]]$Bytes) {
    $base64 = [Convert]::ToBase64String($Bytes)
    $lines = [regex]::Matches($base64, '.{1,64}') | ForEach-Object { $_.Value }
    [IO.File]::WriteAllText($Path, "-----BEGIN $Label-----`n" + ($lines -join "`n") + "`n-----END $Label-----`n")
}
if ($Action -ne 'Create') {
    if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Test root trust changes are restricted to disposable GitHub Actions runners.' }
    $root = [Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile((Join-Path $Directory 'ca.pem'))
    $store = [Security.Cryptography.X509Certificates.X509Store]::new('Root','CurrentUser')
    try {
        $store.Open('ReadWrite')
        if ($Action -eq 'Trust') { $store.Add($root) } else { $store.Remove($root) }
    } finally { $store.Close(); $root.Dispose() }
    exit
}
if (Test-Path -LiteralPath $Directory) { throw 'Certificate output directory must not exist.' }
New-Item -ItemType Directory -Path $Directory | Out-Null
$rsa = [Security.Cryptography.RSA]::Create(2048)
$hash = [Security.Cryptography.HashAlgorithmName]::SHA256
$padding = [Security.Cryptography.RSASignaturePadding]::Pkcs1
$request = [Security.Cryptography.X509Certificates.CertificateRequest]::new(('CN=Lunetile test CA ' + [guid]::NewGuid()),$rsa,$hash,$padding)
$request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true,$false,0,$true))
$request.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new('KeyCertSign, CrlSign',$true))
$now = [DateTimeOffset]::UtcNow
$root = $request.CreateSelfSigned($now.AddDays(-10),$now.AddDays(10))
try {
    Write-Pem (Join-Path $Directory 'ca.pem') 'CERTIFICATE' $root.RawData
    foreach ($name in @('valid','expired','wrong-host')) {
        $key = [Security.Cryptography.RSA]::Create(2048)
        try {
            $leaf = [Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=localhost',$key,$hash,$padding)
            $san = [Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
            if ($name -eq 'wrong-host') { $san.AddDnsName('wrong.invalid') } else { $san.AddDnsName('localhost') }
            $leaf.CertificateExtensions.Add($san.Build())
            $leaf.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false,$false,0,$true))
            $leaf.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new('DigitalSignature, KeyEncipherment',$true))
            $usage = [Security.Cryptography.OidCollection]::new()
            [void]$usage.Add([Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.1'))
            $leaf.CertificateExtensions.Add([Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($usage,$false))
            $expires = if ($name -eq 'expired') { $now.AddDays(-1) } else { $now.AddDays(2) }
            $certificate = $leaf.Create($root,$now.AddDays(-2),$expires,([guid]::NewGuid().ToByteArray()))
            try { Write-Pem (Join-Path $Directory "$name.pem") 'CERTIFICATE' $certificate.RawData }
            finally { $certificate.Dispose() }
            Write-Pem (Join-Path $Directory "$name-key.pem") 'PRIVATE KEY' $key.ExportPkcs8PrivateKey()
        } finally { $key.Dispose() }
    }
} finally { $root.Dispose(); $rsa.Dispose() }
