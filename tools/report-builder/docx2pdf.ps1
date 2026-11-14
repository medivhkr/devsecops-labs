param([string]$In, [string]$Out)
# DOCX открывается в Microsoft Word (COM): обновляются поля, документ сохраняется
# средствами Word и экспортируется в PDF.
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($In, $false, $false, $false)
  $doc.Fields.Update() | Out-Null
  $doc.Saved = $false
  $doc.Save()
  $doc.ExportAsFixedFormat($Out, 17, $false, 0, 0, 1, 1, 0, $true, $true, 1)
  $doc.Close([ref]0)
} finally {
  $word.Quit()
  [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output "OK $Out"
