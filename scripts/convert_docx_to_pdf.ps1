$ErrorActionPreference = "Stop"

$docxPath = "D:\4th-year\Senior-Project\docs\draft_paper\CodeDEE_Senior_Project_1_Proposal_Report.docx"
$pdfPath = "D:\4th-year\Senior-Project\docs\draft_paper\CodeDEE_Senior_Project_1_Proposal_Report.pdf"

if (-not (Test-Path $docxPath)) {
    Write-Host "Error: DOCX not found at $docxPath"
    exit 1
}

try {
    Write-Host "Attempting Microsoft Word COM export to PDF..."
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = [Microsoft.Office.Interop.Word.WdAlertLevel]::wdAlertsNone

    Write-Host "Opening document: $docxPath"
    $doc = $word.Documents.Open($docxPath)

    # Update all fields including Table of Contents
    Write-Host "Updating all dynamic fields and Table of Contents..."
    $doc.Fields.Update()

    # Save as PDF (Format 17 = wdFormatPDF)
    Write-Host "Exporting to PDF: $pdfPath"
    $doc.SaveAs([ref]$pdfPath, [ref]17)

    $doc.Close([ref]$false)
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    
    if (Test-Path $pdfPath) {
        $size = (Get-Item $pdfPath).Length / 1KB
        Write-Host "SUCCESS: PDF successfully generated! ($([math]::Round($size, 1)) KB)"
    } else {
        Write-Host "WARNING: SaveAs completed but file not found."
    }
} catch {
    Write-Host "Word COM conversion not available: $_"
}
