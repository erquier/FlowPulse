<#
.SYNOPSIS
    FlowPulse — Digital signature script using a self-signed certificate.

.DESCRIPTION
    Creates a self-signed Authenticode certificate and signs FlowPulse.exe.
    Intended for testing in controlled environments where a trusted signature
    is not required.

.NOTES
    Run from the repository root:
        powershell -ExecutionPolicy Bypass -File build/sign.ps1

    The certificate is stored in the current user's Personal store.
    To trust it permanently (for testing):
        Import-PfxCertificate -FilePath .\FlowPulseCert.pfx -CertStoreLocation Cert:\LocalMachine\TrustedPublisher
#>

param(
    [string]$ExePath = (Join-Path $PSScriptRoot "..\dist\FlowPulse.exe"),
    [string]$CertSubject = "CN=FlowPulse Development, O=Testing Only, OU=Security Research"
)

$ErrorActionPreference = "Stop"

# --- Validate executable ---
if (-not (Test-Path $ExePath)) {
    Write-Error "EXE not found at: $ExePath"
    Write-Host "Build the project first with: python build/build_nuitka.py"
    exit 1
}

$ExePath = (Resolve-Path $ExePath).Path
Write-Host "[SIGN] Binary: $ExePath"

# --- Create self-signed certificate (valid 2 years) ---
$cert = New-SelfSignedCertificate `
    -Subject $CertSubject `
    -Type CodeSigning `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(2) `
    -KeyUsage DigitalSignature `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")

$thumbprint = $cert.Thumbprint
Write-Host "[SIGN] Certificate created (thumbprint: $thumbprint)"

# --- Export PFX for reuse ---
$pfxPath = Join-Path $PSScriptRoot "..\FlowPulseCert.pfx"
$pfxPassword = ConvertTo-SecureString -String "flowpulse-dev" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPassword | Out-Null
Write-Host "[SIGN] Certificate exported: $pfxPath"

# --- Sign the executable ---
try {
    $signParams = @{
        Certificate = $cert
        TimestampServer = "http://timestamp.digicert.com"
        FilePath = $ExePath
        HashAlgorithm = "sha256"
    }
    Set-AuthenticodeSignature @signParams
    Write-Host "[OK] Signed successfully: $ExePath"
}
catch {
    Write-Warning "[WARN] Timestamp server unreachable — signing without timestamp."
    Set-AuthenticodeSignature -Certificate $cert -FilePath $ExePath -HashAlgorithm sha256
    Write-Host "[OK] Signed (no timestamp): $ExePath"
}

# --- Verify signature ---
$sig = Get-AuthenticodeSignature -FilePath $ExePath
if ($sig.Status -eq "Valid") {
    Write-Host "[OK] Signature verified: $($sig.Status)"
} else {
    Write-Warning "[WARN] Signature status: $($sig.Status)"
}

Write-Host ""
Write-Host "[DONE] Signing complete."
Write-Host "  Certificate thumbprint: $thumbprint"
Write-Host "  Reusable PFX: $pfxPath"
Write-Host "  To install as trusted for testing:"
Write-Host "    Import-PfxCertificate -FilePath FlowPulseCert.pfx -CertStoreLocation Cert:\LocalMachine\TrustedPublisher"
