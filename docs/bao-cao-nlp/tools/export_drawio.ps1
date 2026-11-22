# Xuất mọi sơ đồ figures/drawio/*.drawio sang figures/<tên>.png bằng draw.io desktop
param([string]$DrawIo = "$env:LOCALAPPDATA\Programs\draw.io\draw.io.exe")
$root = Split-Path $PSScriptRoot -Parent
Get-ChildItem "$root\figures\drawio\*.drawio" | ForEach-Object {
  $out = Join-Path "$root\figures" ($_.BaseName + ".png")
  & $DrawIo -x -f png -s 2 -b 12 -o $out $_.FullName | Out-Null
  Write-Output "exported $out"
}
