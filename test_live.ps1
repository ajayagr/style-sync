$url = "https://stylesync-function.azurewebsites.net/api/stylesync"
$body = @{
    source_folder = "originals/"
    output_folder = "styled/"
    container = "file-container"
    styles = @(
        @{
            name = "test-live"
            prompt_text = "test prompt"
        }
    )
} | ConvertTo-Json -Depth 3

Write-Host "Sending request to $url"
try {
    $response = Invoke-RestMethod -Method Post -Uri $url -ContentType "application/json" -Body $body -ErrorAction Stop
    Write-Host "Response Received:"
    $response | ConvertTo-Json -Depth 3
} catch {
    Write-Host "Request Failed:"
    Write-Host $_.Exception.Message
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "Details: $($reader.ReadToEnd())"
    }
}
