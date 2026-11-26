# PowerShell Script: Auto-Export Project to GitHub
param (
    [string]$RepoUrl = ""
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "🚀 Automated Export to GitHub Repository" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Check if git is available
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: Git is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Initialize Git if not initialized
if (-not (Test-Path ".git")) {
    Write-Host "📦 Initializing new Git repository..." -ForegroundColor Yellow
    git init -b main
} else {
    Write-Host "✓ Git repository already initialized." -ForegroundColor Green
    git branch -M main
}

# 3. Verify .gitignore exists
if (-not (Test-Path ".gitignore")) {
    Write-Host "⚠️ Warning: .gitignore not found. Creating standard .gitignore..." -ForegroundColor Yellow
    Set-Content -Path ".gitignore" -Value ".env`n.venv`n__pycache__/`n.vercel/"
}

# 4. Handle Remote Repository URL
$currentRemote = git remote get-url origin 2>$null
if (-not $currentRemote) {
    if (-not $RepoUrl) {
        Write-Host "`n👉 Please enter your GitHub Repository URL (e.g., https://github.com/YourUsername/telegram-gemini-bot.git):" -ForegroundColor Yellow
        $RepoUrl = Read-Host "GitHub Repo URL"
    }

    if ($RepoUrl) {
        Write-Host "🔗 Adding remote origin: $RepoUrl" -ForegroundColor Yellow
        git remote add origin $RepoUrl
    } else {
        Write-Host "ℹ️ No remote URL provided. Files will be committed locally only." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "✓ Remote origin detected: $currentRemote" -ForegroundColor Green
    if ($RepoUrl -and ($RepoUrl -ne $currentRemote)) {
        Write-Host "🔄 Updating remote URL to: $RepoUrl" -ForegroundColor Yellow
        git remote set-url origin $RepoUrl
    }
}

# 5. Stage files and Commit
Write-Host "`n📝 Staging files and creating commit..." -ForegroundColor Yellow
git add .
$commitMsg = "Deploy: Telegram Gemini Flash High Reasoning Homework Solver Bot"
git commit -m $commitMsg

# 6. Push to GitHub
$hasRemote = git remote get-url origin 2>$null
if ($hasRemote) {
    Write-Host "`n🚀 Pushing code to GitHub (main branch)..." -ForegroundColor Cyan
    try {
        git push -u origin main
        Write-Host "`n=========================================" -ForegroundColor Green
        Write-Host "🎉 SUCCESS! Code has been exported to GitHub!" -ForegroundColor Green
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "Next Step: Go to https://vercel.com/new and import this GitHub repository." -ForegroundColor White
    } catch {
        Write-Host "⚠️ Git push encountered an error: $_" -ForegroundColor Red
        Write-Host "Tip: Make sure you have created the repository on GitHub and have write permissions." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n⚠️ Code committed locally. Run this script again with -RepoUrl to push to GitHub:" -ForegroundColor Yellow
    Write-Host "   .\export_to_github.ps1 -RepoUrl 'https://github.com/YourUsername/your-repo.git'" -ForegroundColor White
}
