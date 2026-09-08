param(
    [switch]$DryRun
)

# ============================================================
# Documo Fax -> Network Share Sync (PowerShell -- no installs needed)
# ============================================================
# EDIT THE VALUES BELOW, save this file, then run it.
# Confirmed working endpoints/settings as of live testing:
#   base:    https://api.documo.com
#   auth:    "Authorization: Basic <api_key>"
#   list:    GET /v1/fax/history  -> { rows: [...] }
#   fields:  messageId / faxNumber / createdAt / classificationLabel
#   download: GET /v1/fax/{id}/download?format=pdf

$ApiKey     = "your_documo_api_key"
$ApiBase    = "https://api.documo.com"
$ShareDir   = "\\KLG-AzureFS\Faxes"
$MarkAsRead = $false

# ============================================================
# You shouldn't need to edit anything below this line.
# ============================================================

$StateFile = Join-Path $PSScriptRoot "processed_faxes.json"
$LogFile   = Join-Path $PSScriptRoot "sync.log"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Get-ProcessedIds {
    if (Test-Path $StateFile) {
        return @(Get-Content $StateFile -Raw | ConvertFrom-Json)
    }
    return @()
}

function Save-ProcessedIds {
    param($Ids)
    ($Ids | Sort-Object -Unique) | ConvertTo-Json | Set-Content -Path $StateFile
}

function Get-SafeFilename {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return "unknown" }
    return ($Value -replace '[\\/:*?"<>|]', '_')
}

if (-not $ApiKey -or $ApiKey -eq "your_documo_api_key") {
    Write-Log "ERROR: Set your real DOCUMO API key at the top of this script (sync.ps1)."
    exit 1
}

if (-not (Test-Path $ShareDir)) {
    New-Item -ItemType Directory -Path $ShareDir -Force | Out-Null
}

$Headers = @{ Authorization = "Basic $ApiKey" }

Write-Log "Checking Documo for faxes..."
try {
    $Result = Invoke-RestMethod -Uri "$ApiBase/v1/fax/history" -Headers $Headers -Method Get
} catch {
    Write-Log "ERROR contacting Documo: $($_.Exception.Message)"
    exit 1
}

$AllFaxes = @($Result.rows)
$InboundFaxes = $AllFaxes | Where-Object { $_.classificationLabel -ne "outbound" }
Write-Log "Found $($InboundFaxes.Count) inbound fax(es) ($($AllFaxes.Count) total returned)"

$ProcessedIds = @(Get-ProcessedIds)

foreach ($Fax in $InboundFaxes) {
    $FaxId = $Fax.messageId
    if (-not $FaxId) { continue }
    if ($ProcessedIds -contains $FaxId) { continue }

    $SafeId     = Get-SafeFilename $FaxId
    $SafeNumber = Get-SafeFilename $Fax.faxNumber
    $SafeDate   = Get-SafeFilename $Fax.createdAt
    $FileName   = "${SafeDate}_${SafeNumber}_${SafeId}.pdf"

    if ($DryRun) {
        Write-Log "[DRY RUN] Would save fax $FaxId as $FileName (nothing written, nothing marked read)"
        continue
    }

    try {
        $DownloadUrl = "$ApiBase/v1/fax/$FaxId/download?format=pdf"
        $DestPath = Join-Path $ShareDir $FileName
        Invoke-WebRequest -Uri $DownloadUrl -Headers $Headers -OutFile $DestPath
        Write-Log "Saved fax $FaxId to $DestPath"
    } catch {
        Write-Log "Failed to process fax $FaxId : $($_.Exception.Message)"
        continue
    }

    # Record as processed now, before attempting mark-as-read, so a
    # mark-read failure can never cause this fax to be re-saved later.
    $ProcessedIds += $FaxId
    Save-ProcessedIds $ProcessedIds

    if ($MarkAsRead) {
        try {
            $Body = @{ status = "read" } | ConvertTo-Json
            Invoke-RestMethod -Uri "$ApiBase/v1/fax/$FaxId" -Headers $Headers -Method Patch -Body $Body -ContentType "application/json" | Out-Null
        } catch {
            Write-Log "Saved fax $FaxId but could not mark it read in Documo: $($_.Exception.Message)"
        }
    }
}

Write-Log "Done."
