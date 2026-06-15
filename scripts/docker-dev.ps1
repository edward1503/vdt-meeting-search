param(
  [string[]]$Services = @("elasticsearch", "redis", "api", "frontend"),
  [switch]$SkipEmbedding
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $SkipEmbedding) {
  $embeddingReady = $false
  try {
    Invoke-RestMethod -Uri "http://localhost:8010/health" -TimeoutSec 2 | Out-Null
    $embeddingReady = $true
  } catch {
    $embeddingReady = $false
  }

  if (-not $embeddingReady) {
    Start-Process -FilePath "python" `
      -ArgumentList @("scripts\embedding_server.py", "--host", "0.0.0.0", "--port", "8010") `
      -WorkingDirectory $root `
      -WindowStyle Hidden
    Start-Sleep -Seconds 2
  }
}

Push-Location $root
try {
  docker compose up -d --build $Services
} finally {
  Pop-Location
}
