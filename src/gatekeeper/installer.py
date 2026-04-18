import os
import stat
from pathlib import Path
from rich.console import Console
import typer

console = Console()

PRE_PUSH_HOOK = """#!/bin/sh
# >>> GateKeeper Hook >>>
gatekeeper check git-push --non-interactive
if [ $? -ne 0 ]; then
    exit 1
fi
# <<< GateKeeper Hook <<<
"""

def install_git_hook(project_root: Path) -> None:
    """
    Writes a pre-push Git hook that calls `gatekeeper check git-push` so that
    GUI clients (VS Code, GitHub Desktop, Tower, etc.) which bypass shell shims
    are also protected.
    """
    hooks_dir = project_root / ".git" / "hooks"
    if not hooks_dir.exists():
        console.print("[yellow]⚠️  No .git/hooks directory found — skipping git hook install.[/yellow]")
        return

    hook_path = hooks_dir / "pre-push"

    # Guard: don't overwrite if already installed
    if hook_path.exists() and "GateKeeper Hook" in hook_path.read_text(encoding="utf-8"):
        console.print("[bold yellow]⚠️  GateKeeper pre-push hook is already installed.[/bold yellow]")
        return

    hook_path.write_text(PRE_PUSH_HOOK, encoding="utf-8")

    # Make executable on all platforms
    current_mode = hook_path.stat().st_mode
    hook_path.chmod(current_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    console.print("[bold green]✅ GateKeeper pre-push git hook installed (.git/hooks/pre-push)[/bold green]")
    console.print("[dim]  This protects GUI clients (VS Code, GitHub Desktop, Tower, etc.) too.[/dim]")

BASH_ZSH_SHIM = """
# >>> GateKeeper Shims >>>
# NOTE: The pre-push git hook is the primary protection layer.
# These shims add interactive prompts and are optional enhanced UX.
# They gracefully fall through if gatekeeper is not found in PATH.
npm() {
    if [[ "$1" == "publish" ]]; then
        if command -v gatekeeper &>/dev/null; then
            gatekeeper check npm-publish && command npm "$@"
        else
            command npm "$@"
        fi
    else
        command npm "$@"
    fi
}
git() {
    if [[ "$1" == "push" ]]; then
        if command -v gatekeeper &>/dev/null; then
            gatekeeper check git-push && command git "$@"
        else
            command git "$@"
        fi
    else
        command git "$@"
    fi
}
# <<< GateKeeper Shims <<<
"""

POWERSHELL_SHIM = """
# >>> GateKeeper Shims >>>
# NOTE: The pre-push git hook is the primary protection layer.
# These shims add interactive prompts and are optional enhanced UX.
# They gracefully fall through if gatekeeper is not found in PATH.
function npm {
    if ($args[0] -eq "publish") {
        if (Get-Command gatekeeper -ErrorAction SilentlyContinue) {
            gatekeeper check npm-publish
            if ($LASTEXITCODE -eq 0) { & "npm.cmd" @args }
        } else {
            & "npm.cmd" @args
        }
    } else {
        & "npm.cmd" @args
    }
}
function git {
    if ($args[0] -eq "push") {
        if (Get-Command gatekeeper -ErrorAction SilentlyContinue) {
            gatekeeper check git-push
            if ($LASTEXITCODE -eq 0) { & "git.exe" @args }
        } else {
            & "git.exe" @args
        }
    } else {
        & "git.exe" @args
    }
}
# <<< GateKeeper Shims <<<
"""

def is_already_installed(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    content = file_path.read_text(encoding="utf-8")
    return "GateKeeper Shims" in content

def install_shims():
    console.print("\n[bold green]Installing GateKeeper Shell Shims...[/bold green]")
    console.print("This adds interactive prompts to `npm publish` and `git push` in your terminal.")
    console.print("[dim]Note: The pre-push git hook (installed by `gatekeeper init`) is the PRIMARY protection layer.")
    console.print("These shims are optional enhanced UX — they gracefully fall through if GateKeeper is not in PATH.[/dim]")
    console.print("Which shell environment do you want to enhance?")
    console.print("  [1] [cyan]Bash / Zsh[/cyan] (~/.bashrc or ~/.zshrc)")
    console.print("  [2] [cyan]PowerShell[/cyan] ($PROFILE)")
    
    choice = typer.prompt("Select environment (1/2)", type=int)
    
    if choice == 1:
        # Try to guess Bash vs Zsh
        rc_target = ".bashrc"
        if "zsh" in os.environ.get("SHELL", "").lower() or (Path.home() / ".zshrc").exists():
            rc_target = ".zshrc"
            
        rc_file = Path.home() / rc_target
        
        if is_already_installed(rc_file):
            console.print(f"[bold yellow]⚠️  GateKeeper shims are already installed in {rc_file}![/bold yellow]")
            return
            
        with open(rc_file, "a", encoding="utf-8") as f:
            f.write("\n" + BASH_ZSH_SHIM + "\n")
        console.print(f"[bold green]✅ Shims injected successfully![/bold green]")
        console.print(f"Please run `source ~/{rc_target}` or open a new terminal to activate.")
        
    elif choice == 2:
        # Query PowerShell for the exact $PROFILE path (handles OneDrive redirects)
        import subprocess
        profile_path = ""
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", "Write-Host -NoNewline $PROFILE"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                profile_path = result.stdout.strip()
        except Exception:
            pass
            
        if not profile_path:
            # Fallback
            docs = Path.home() / "Documents"
            profile_path = str(docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1")
            
        profile = Path(profile_path)
        profile.parent.mkdir(parents=True, exist_ok=True)
        
        if is_already_installed(profile):
            console.print(f"[bold yellow]⚠️  GateKeeper shims are already installed in {profile}![/bold yellow]")
            return
            
        with open(profile, "a", encoding="utf-8") as f:
            f.write("\n" + POWERSHELL_SHIM + "\n")
        console.print(f"[bold green]✅ Shims injected into {profile}![/bold green]")
        console.print("Please close and reopen PowerShell, or run `.` `$``PROFILE` to activate.")
        
    else:
        console.print("[bold red]Invalid option. Aborting.[/bold red]")
        raise typer.Exit(code=1)
