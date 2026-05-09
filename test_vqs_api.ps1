# ============================================================
# SOPHiA VQS API — PowerShell Quick Test
# ============================================================
#
# THE AUTH FLOW:
#   The IAM is browser-based (Azure B2C). You CANNOT get a token
#   via a simple POST. You must:
#
#   1. Open your browser: https://iam-vandv.sophiagenetics.com/account/token
#   2. Login with: hackathon6@hackathon.com / Gono399764
#   3. The page shows a JSON blob with "access_token":"eyJ..."
#   4. Copy the ENTIRE access_token value
#   5. Paste it in $TOKEN below
#
#   ALTERNATIVELY - grab it from the SOPHiA DDM platform:
#   1. Login to https://platform-vandv1.sophiagenetics.com
#   2. Open DevTools (F12) -> Network tab
#   3. Click on any request -> look at the Authorization header
#   4. Copy the token after "Bearer "
#
#   Token is valid for 1 HOUR (3600 seconds).
# ============================================================

# ─── PASTE YOUR TOKEN HERE ──────────────────────────────────
$TOKEN = "PASTE_YOUR_ACCESS_TOKEN_HERE"

# ─── PASTE YOUR DATASET KEY HERE ─────────────────────────────
# Get this from the browser Network tab when viewing variants:
# 1. Go to platform -> open an analysis -> Gene/Variant view
# 2. DevTools (F12) -> Network -> find POST to /api/variant/query
# 3. In the URL, copy the 'key' parameter value
$KEY = "eyJmaWNJZCI6MjA2NTA3NTM4LCJrbm93bkZpbGUiOiJMQVlFUjJfU0hPUlRfU1VCU0VUX0RBVEFTRVRfUExVU19HRU5FX0FOTk9UQVRJT05TIiwiYW5hbHlzaXNJZCI6MjAwMDQyMzYwLCJpbnRlcnByZXRhdGlvbiI6ImludGVycHJldGF0aW9uLTEwNDIiLCJ0cmFuc2NyaXB0U3RyYXRlZ3lWZXJzaW9uIjoiMTc3ODA2OTAyNjAwMCJ9"

# ============================================================
Write-Host "`n=== SOPHiA VQS API Test ===" -ForegroundColor Cyan

if ($TOKEN -eq "PASTE_YOUR_ACCESS_TOKEN_HERE") {
    Write-Host "`nNo token set! Follow these steps:" -ForegroundColor Red
    Write-Host "  1. Open browser:  https://iam-vandv.sophiagenetics.com/account/token" -ForegroundColor Yellow
    Write-Host "  2. Login with:    hackathon6@hackathon.com / Gono399764" -ForegroundColor Yellow
    Write-Host "  3. Copy the access_token value from the JSON" -ForegroundColor Yellow
    Write-Host '  4. Edit this file: replace PASTE_YOUR_ACCESS_TOKEN_HERE with your token' -ForegroundColor Yellow
    Write-Host "`nOR paste it now:" -ForegroundColor White
    $TOKEN = Read-Host "Token"
    if (-not $TOKEN) { exit 1 }
}

$headers = @{
    "Authorization" = "Bearer $TOKEN"
    "Content-Type"  = "application/json"
    "Accept"        = "*/*"
}

# ─── TEST 1: Schema endpoint (simplest) ─────────────────────
Write-Host "`n[1] GET /schema ..." -ForegroundColor Yellow

try {
    $schema = Invoke-RestMethod -Uri "https://platform-vandv1.sophiagenetics.com/api/variant/query/schema?key=$KEY" `
        -Method Get -Headers $headers -ErrorAction Stop

    Write-Host "  OK! $($schema.columns.Count) columns" -ForegroundColor Green
    Write-Host "  First 10:" -ForegroundColor Cyan
    $schema.columns[0..9] | ForEach-Object { Write-Host "    $_" }
} catch {
    Write-Host "  FAILED: $($_.Exception.Response.StatusCode) - $($_.Exception.Message)" -ForegroundColor Red
}

# ─── TEST 2: Simple query — all columns, no filter ──────────
Write-Host "`n[2] POST query (all columns, limit 5) ..." -ForegroundColor Yellow

$body = '{"columns":["*"],"filters":{"filterString":""},"pagination":{"offset":0,"limit":5}}'

try {
    $r = Invoke-RestMethod `
        -Uri "https://platform-vandv1.sophiagenetics.com/api/variant/query?key=$KEY&engine.paginate=true" `
        -Method Post -Headers $headers -Body $body -ErrorAction Stop

    $cols = $r.pageContent.columns
    $rows = $r.pageContent.data
    Write-Host "  OK! $($cols.Count) columns, $($rows.Count) rows" -ForegroundColor Green

    if ($rows.Count -gt 0) {
        Write-Host "`n  Row 1 sample:" -ForegroundColor Cyan
        for ($i = 0; $i -lt [Math]::Min(8, $cols.Count); $i++) {
            Write-Host "    $($cols[$i]) = $($rows[0][$i])"
        }
    }
} catch {
    Write-Host "  FAILED: $($_.Exception.Response.StatusCode) - $($_.Exception.Message)" -ForegroundColor Red
}

# ─── TEST 3: Pathogenic filter ──────────────────────────────
Write-Host "`n[3] POST query (Pathogenic/Likely Pathogenic filter) ..." -ForegroundColor Yellow

$bodyFql = @{
    columns = @("*")
    filters = @{
        filterString = 'fql:("userAnnotations.interpretation.acmg.result.classificationFinal" anyOf (''Pathogenic'', ''Likely Pathogenic''))'
    }
    pagination = @{ offset = 0; limit = 50 }
} | ConvertTo-Json -Depth 3

try {
    $r2 = Invoke-RestMethod `
        -Uri "https://platform-vandv1.sophiagenetics.com/api/variant/query?key=$KEY&engine.paginate=true" `
        -Method Post -Headers $headers -Body $bodyFql -ErrorAction Stop

    $rows2 = $r2.pageContent.data
    Write-Host "  OK! Found $($rows2.Count) pathogenic variants" -ForegroundColor Green
} catch {
    Write-Host "  FAILED: $($_.Exception.Response.StatusCode) - $($_.Exception.Message)" -ForegroundColor Red
}

# ─── Summary ────────────────────────────────────────────────
Write-Host @"

=== Quick Reference ===

Get a fresh token (valid 1 hour):
  Browser -> https://iam-vandv.sophiagenetics.com/account/token
  Login -> copy access_token

Get a dataset key:
  Browser -> https://platform-vandv1.sophiagenetics.com
  Navigate to an analysis -> Variant view
  F12 -> Network -> find POST to /api/variant/query
  Copy the 'key' param from the URL

One-liner test in PowerShell:
  `$h = @{Authorization="Bearer YOUR_TOKEN";"Content-Type"="application/json"}
  Invoke-RestMethod -Uri "https://platform-vandv1.sophiagenetics.com/api/variant/query/schema?key=YOUR_KEY" -Headers `$h

"@ -ForegroundColor Gray
