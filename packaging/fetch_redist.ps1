# Télécharge le bootstrapper WebView2 Evergreen de Microsoft dans packaging/redist/
# (non versionné). Utilisé par le build local et par la CI avant `iscc`.
$ErrorActionPreference = 'Stop'
$dir = Join-Path $PSScriptRoot 'redist'
New-Item -ItemType Directory -Force $dir | Out-Null
$target = Join-Path $dir 'MicrosoftEdgeWebview2Setup.exe'
if (-not (Test-Path $target)) {
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $target -UseBasicParsing
}
$signature = Get-AuthenticodeSignature $target
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    Remove-Item $target
    throw "Signature du bootstrapper WebView2 invalide : $($signature.Status)"
}
Write-Output $target
