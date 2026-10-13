$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$videoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$videoOut = Join-Path $videoRoot 'outputs/demo_video'
$videoAudio = Join-Path $videoOut 'sources/audio'
New-Item -ItemType Directory -Force -Path $videoAudio | Out-Null
$videoSentences = Get-Content -LiteralPath (Join-Path $videoOut 'speech_input.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$videoSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $videoSynth.SelectVoice('Microsoft Huihui')
    $videoSynth.Rate = 0
    $videoSynth.Volume = 100
    foreach ($sentence in $videoSentences) {
        $videoWav = Join-Path $videoAudio ($sentence.id + '.wav')
        $videoSynth.SetOutputToWaveFile($videoWav)
        $videoSynth.Speak([string]$sentence.text)
        $videoSynth.SetOutputToNull()
        Write-Output ('Speech ready: ' + $sentence.id)
    }
} finally { $videoSynth.Dispose() }
