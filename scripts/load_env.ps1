# scripts/load_env.ps1
$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*#") { return }  # skip comments
        if ($_ -match "^\s*$") { return }  # skip empty lines
        $parts = $_ -split "=", 2
        if ($parts.Count -eq 2) {
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            Write-Host "Loaded: $name"
        }
    }
    Write-Host "`n✅ Environment variables loaded successfully."
} else {
    Write-Host "❌ .env file not found in current directory."
}
