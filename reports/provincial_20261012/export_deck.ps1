$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$sourceDeck = Join-Path $taskRoot 'outputs/provincial_20261012/DOEF_Provincial_Submission.pptx'
$outputPdf = Join-Path $taskRoot 'outputs/provincial_20261012/DOEF_Provincial_Submission.pdf'
$renderDir = Join-Path $taskRoot 'tmp/provincial_review/submission_slides'
New-Item -ItemType Directory -Force -Path $renderDir | Out-Null
$deckApp = New-Object -ComObject PowerPoint.Application
$existingCount = $deckApp.Presentations.Count
$deck = $null
try {
    $deck = $deckApp.Presentations.Open($sourceDeck, -1, 0, 0)
    $deck.SaveAs($outputPdf, 32)
    $deck.Export($renderDir, 'PNG', 1600, 900)
    Write-Output ('Exported ' + $deck.Slides.Count + ' slides and PDF with PowerPoint.')
} finally {
    if ($deck) { $deck.Close() }
    if ($existingCount -eq 0) { $deckApp.Quit() }
}
