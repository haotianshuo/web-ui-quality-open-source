$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
python (Join-Path $Root 'scripts/release.py') package
