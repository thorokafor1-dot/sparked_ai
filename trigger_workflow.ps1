$token = [System.Environment]::GetEnvironmentVariable('GITHUB_TOKEN')
if (-not $token) {
    Write-Host "ERROR: GITHUB_TOKEN not set"
    exit 1
}

$header = @{
    'Authorization' = 'Bearer ' + $token
    'Accept' = 'application/vnd.github.v3+json'
}

$body = @{
    ref = 'main'
} | ConvertTo-Json

try {
    $resp = Invoke-WebRequest -Uri 'https://api.github.com/repos/thorokafor1-dot/sparked_ai/actions/workflows/youtube_outlier_tracker.yml/dispatches' `
        -Method POST `
        -Headers $header `
        -Body $body `
        -ContentType 'application/json' `
        -ErrorAction Stop
    
    if ($resp.StatusCode -eq 204) {
        Write-Host "✓ Workflow triggered successfully"
    } else {
        Write-Host "Response code: $($resp.StatusCode)"
    }
} catch {
    Write-Host "ERROR: $_"
    exit 1
}
