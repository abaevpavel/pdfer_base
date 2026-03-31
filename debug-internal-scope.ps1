param(
    [string]$ApiBase = "http://localhost",
    [string]$ExamplePath = ".\example.json",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExamplePath)) {
    throw "Example file not found: $ExamplePath"
}

$raw = Get-Content $ExamplePath -Raw
$parsed = $raw | ConvertFrom-Json

# Supports Make-style wrapper:
# 1) [{ ..., jsonStringBodyContent: "{...}" }]
# 2) [{ ..., data: "{...}" }]
if ($parsed -is [System.Array] -and $parsed.Count -gt 0) {
    $first = $parsed[0]
    if ($first.PSObject.Properties.Name -contains "jsonStringBodyContent") {
        $payload = [string]$first.jsonStringBodyContent
    }
    elseif ($first.PSObject.Properties.Name -contains "data") {
        $payload = [string]$first.data
    }
    else {
        throw "Wrapper format not supported. Expected jsonStringBodyContent or data."
    }
} else {
    $payload = $parsed | ConvertTo-Json -Depth 100 -Compress
}
$uri = "$ApiBase/internal-scope"

Write-Host "POST $uri" -ForegroundColor Cyan
try {
    $payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $res = Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json; charset=utf-8" -Body $payloadBytes
}
catch {
    $response = $_.Exception.Response
    if ($response -and $response.GetResponseStream) {
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        $serverBody = $reader.ReadToEnd()
        if ($serverBody) {
            Write-Host "Server response body:" -ForegroundColor Yellow
            Write-Host $serverBody
        }
    }
    throw
}

$pdfUrl = $res.body.internal_scope
if (-not $pdfUrl) {
    throw "Response does not contain body.internal_scope"
}

Write-Host "PDF: $pdfUrl" -ForegroundColor Green

if (-not $NoOpen) {
    Start-Process $pdfUrl
}
