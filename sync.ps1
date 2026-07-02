<#
.SYNOPSIS
  Safely syncs this repo with GitHub: pulls the daily briefing commits made by
  GitHub Actions, replays your local edits on top, then commits and pushes.

.DESCRIPTION
  Because a GitHub Action commits new briefing files to this repo every day,
  your local main branch falls behind quickly. Pushing without pulling first
  causes rejected pushes or merge conflicts. This script always pulls
  (rebasing, so history stays linear) before it ever pushes.

  Safe to run any time - if you have no local changes, it just updates you
  to the latest. If you do have local changes, it stashes them, pulls, then
  reapplies them before committing and pushing.

.PARAMETER Message
  Commit message to use if you have local changes to commit. Defaults to
  "Update" with the current date/time.

.EXAMPLE
  .\sync.ps1
  .\sync.ps1 -Message "Add new blog post"
#>

param(
    [string]$Message = "Update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

function Write-Step($text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed (exit code $LASTEXITCODE)"
    }
}

$stashed = $false

try {
    & git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "This folder isn't a git repository." -ForegroundColor Red
        exit 1
    }

    $branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    Write-Step "On branch '$branch'"

    $status = & git status --porcelain
    if ($status) {
        Write-Step "Stashing your local changes so the pull can't conflict"
        Invoke-Git stash push -u -m "sync.ps1 auto-stash"
        $stashed = $true
    }
    else {
        Write-Step "No local changes yet"
    }

    Write-Step "Fetching and rebasing onto origin/$branch (picks up today's GitHub Actions briefing commits)"
    Invoke-Git fetch origin
    Invoke-Git pull --rebase origin $branch

    if ($stashed) {
        Write-Step "Reapplying your local changes"
        & git stash pop
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "Your local changes conflict with what just came from GitHub." -ForegroundColor Yellow
            Write-Host "Resolve the conflicts shown above, then run:" -ForegroundColor Yellow
            Write-Host "    git add ."
            Write-Host "    git stash drop"
            Write-Host "...and re-run this script to commit and push."
            exit 1
        }
    }

    $status = & git status --porcelain
    if (-not $status) {
        Write-Step "Nothing to commit - you're already up to date with origin/$branch."
        exit 0
    }

    Write-Step "Staging and committing your changes"
    Invoke-Git add -A
    Invoke-Git commit -m $Message

    Write-Step "Pulling once more in case anything landed while you were working"
    Invoke-Git pull --rebase origin $branch

    Write-Step "Pushing to origin/$branch"
    Invoke-Git push origin $branch

    Write-Step "Done - local and remote are in sync."
}
catch {
    Write-Host ""
    Write-Host "sync.ps1 stopped: $_" -ForegroundColor Red
    Write-Host "Nothing further was pushed. Run 'git status' to see where things stand." -ForegroundColor Red
    exit 1
}
