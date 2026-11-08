# Explicitly authorized reset: derived artifacts only, source data is protected.
$ErrorActionPreference = 'Stop'
$dataRoot = (Resolve-Path -LiteralPath 'D:\Index-Beast\backend\data').Path.TrimEnd('\')
$targetNames = @('clean_runs','chunk_runs','research_runs','delivery')
$targets = @()
$links = @()
foreach ($name in $targetNames) {
    $candidate = Join-Path $dataRoot $name
    if (-not (Test-Path -LiteralPath $candidate)) {continue}
    $absolute = (Resolve-Path -LiteralPath $candidate).Path
    if ($absolute -ne (Join-Path $dataRoot $name) -or -not $absolute.StartsWith($dataRoot+'\')) {throw 'Unsafe reset target'}
    if ((Get-Item -LiteralPath $absolute).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {throw 'Root must be physical'}
    foreach ($entry in Get-ChildItem -LiteralPath $absolute -Recurse -Force) {
        if ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            if (-not $entry.FullName.StartsWith((Join-Path $dataRoot 'delivery')+'\')) {throw 'Unexpected linked tree'}
            foreach ($dest in @($entry.Target)) {
                if (-not ([System.IO.Path]::GetFullPath($dest)).StartsWith($dataRoot+'\')) {throw 'Link leaves data root'}
            }
            $links += $entry.FullName
        }
    }
    $targets += $absolute
}
# Remove junction entries without recursion, then delete only checked physical roots.
foreach ($link in $links | Select-Object -Unique) {Remove-Item -LiteralPath $link -Force}
foreach ($target in $targets) {Remove-Item -LiteralPath $target -Recurse -Force}
Write-Output ('Removed derived roots: '+($targets -join ', '))
