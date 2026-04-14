#Requires -Version 5.1
<#
.SYNOPSIS
  Install lambda/requirements.txt into lambda/package and produce lambda/deployment.zip
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LambdaDir = Join-Path $Root "lambda"
$Pkg = Join-Path $LambdaDir "package"
$Zip = Join-Path $LambdaDir "deployment.zip"

if (Test-Path $Pkg) { Remove-Item -Recurse -Force $Pkg }
if (Test-Path $Zip) { Remove-Item -Force $Zip }
New-Item -ItemType Directory -Path $Pkg | Out-Null

# Build for AWS Lambda Linux runtime even when packaging on Windows.
python -m pip install -r (Join-Path $LambdaDir "requirements.txt") -t $Pkg `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 3.12 `
  --only-binary=:all:
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Copy-Item (Join-Path $LambdaDir "redact_handler.py") $Pkg -Force
Copy-Item (Join-Path $LambdaDir "lib") $Pkg -Recurse -Force

Push-Location $Pkg
try {
    if (Test-Path $Zip) { Remove-Item -Force $Zip }
    Compress-Archive -Path * -DestinationPath $Zip -CompressionLevel Optimal -Force
} finally {
    Pop-Location
}

Write-Host "Wrote $Zip"
