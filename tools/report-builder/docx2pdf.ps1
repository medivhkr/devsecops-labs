param([string]$In, [string]$Out)
# Экспорт DOCX в PDF через Microsoft Word (COM), с обновлением полей.
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($In, $false, $false, $false)
  $doc.Fields.Update() | Out-Null
  $doc.ExportAsFixedFormat($Out, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
  $doc.Close([ref]0)
} finally {
  $word.Quit()
  [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output "OK $Out"
