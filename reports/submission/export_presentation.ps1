# Export the accepted editorial deck with desktop PowerPoint on Windows.
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$sourceDeck = Join-Path $projectRoot 'outputs/submission/DOEF_Competition_Presentation.pptx'
$outputPdf = Join-Path $projectRoot 'outputs/submission/DOEF_Competition_Presentation.pdf'
$renderDir = Join-Path $projectRoot 'tmp/competition_style/final_slides'
New-Item -ItemType Directory -Force -Path $renderDir | Out-Null
$deckApp = New-Object -ComObject PowerPoint.Application
$existingCount = $deckApp.Presentations.Count
$deck = $null
try {
    $deck = $deckApp.Presentations.Open($sourceDeck, -1, 0, 0)
    $deck.SaveAs($outputPdf, 32)
    $deck.Export($renderDir, 'PNG', 1600, 900)
    Write-Output ('Exported ' + $deck.Slides.Count + ' slides and presentation PDF.')
} finally {
    if ($deck) { $deck.Close() }
    if ($existingCount -eq 0) { $deckApp.Quit() }
}
