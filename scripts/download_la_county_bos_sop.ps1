param(
    [string]$FromDate = "",
    [string]$ToDate = "",
    [string]$OutputRoot = "local/downloads/la_county_bos_sop"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ToDate)) {
    $ToDate = (Get-Date).ToString("yyyy-MM-dd")
}

if ([string]::IsNullOrWhiteSpace($FromDate)) {
    $FromDate = (Get-Date).AddYears(-1).ToString("yyyy-MM-dd")
}

$fromEpoch = [DateTimeOffset]::Parse($FromDate).ToUnixTimeMilliseconds()
$toEpoch = ([DateTimeOffset]::Parse($ToDate).AddDays(1).AddMilliseconds(-1)).ToUnixTimeMilliseconds()

$headers = @{
    "x-algolia-application-id" = "USY9HV4C4P"
    "x-algolia-api-key" = "a66f1d6fe5ef613ce81b6cf0138b4c16"
    "Content-Type" = "application/json"
}

$filters = "sds_org_name:`"BOS`" AND sds_org_subfolder:`"SOP`" AND date >= $fromEpoch AND date <= $toEpoch"
$results = @()
$page = 0
$nbPages = 1

while ($page -lt $nbPages) {
    $bodyObject = @{
        query = ""
        page = $page
        hitsPerPage = 100
        filters = $filters
        attributesToRetrieve = @(
            "sds_doc_id",
            "sds_title",
            "sds_org_subfolder",
            "sds_document_dt",
            "sds_published_url",
            "sds_file_extension",
            "object_name",
            "date"
        )
    }

    $body = $bodyObject | ConvertTo-Json -Depth 6 -Compress
    $response = Invoke-RestMethod -Method Post -Uri "https://USY9HV4C4P-dsn.algolia.net/1/indexes/SopMainPrdv2/query" -Headers $headers -Body $body

    if ($null -ne $response.hits) {
        $results += $response.hits
    }

    $nbPages = [int]$response.nbPages
    $page += 1
}

$deduped = @{}
foreach ($item in $results) {
    $key = [string]$item.sds_doc_id
    if ([string]::IsNullOrWhiteSpace($key)) {
        $key = [string]$item.sds_published_url
    }
    if (-not $deduped.ContainsKey($key)) {
        $deduped[$key] = $item
    }
}

$downloadRootPath = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $downloadRootPath -Force | Out-Null

$documents = @()

foreach ($entry in ($deduped.Values | Sort-Object date)) {
    $meetingDate = ([DateTimeOffset]::FromUnixTimeMilliseconds([int64]$entry.date)).ToString("yyyy-MM-dd")
    $meetingDir = Join-Path $downloadRootPath ("bos_sop\" + $meetingDate)
    New-Item -ItemType Directory -Path $meetingDir -Force | Out-Null

    $objectName = [string]$entry.object_name
    if ([string]::IsNullOrWhiteSpace($objectName)) {
        $objectName = "$meetingDate-$($entry.sds_doc_id).pdf"
    }

    $safeName = ($objectName -replace '[^A-Za-z0-9._-]+', '_').Trim('._')
    if ([string]::IsNullOrWhiteSpace($safeName)) {
        $safeName = "$meetingDate-bos-sop.pdf"
    }

    $localPath = Join-Path $meetingDir $safeName
    Invoke-WebRequest -Uri $entry.sds_published_url -OutFile $localPath -UseBasicParsing

    $documents += [ordered]@{
        sds_doc_id = [string]$entry.sds_doc_id
        title = [string]$entry.sds_title
        meeting_date = $meetingDate
        sds_document_dt = [string]$entry.sds_document_dt
        sds_published_url = [string]$entry.sds_published_url
        local_path = $localPath
        object_name = [string]$entry.object_name
        sds_org_subfolder = [string]$entry.sds_org_subfolder
    }
}

$manifest = [ordered]@{
    source_id = "la_county_bos_sop"
    from_date = $FromDate
    to_date = $ToDate
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    query_filters = $filters
    api_result_count = $results.Count
    deduped_document_count = $documents.Count
    documents = $documents
}

$manifestPath = Join-Path $downloadRootPath "bos_sop_last_12_months_manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Output $manifestPath
