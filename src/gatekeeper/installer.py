import os
from pathlib import Path
from rich.console import Console
import typer

console = Console()

BASH_ZSH_SHIM = """
# >>> GateKeeper Shims >>>
npm() {
    if [[ "$1" == "publish" ]]; then
        gatekeeper check npm-publish && command npm "$@"
    else
        command npm "$@"
    fi
}
git() {
    if [[ "$1" == "push" ]]; then
        gatekeeper check git-push && command git "$@"
    else
        command git "$@"
    fi
}
# <<< GateKeeper Shims <<<
"""

POWERSHELL_SHIM = """
# >>> GateKeeper Shims >>>
function npm {
    if ($args[0] -eq "publish") {
        gatekeeper check npm-publish
        if ($LASTEXITCODE -eq 0) {
            & "npm.cmd" @args
        }
    } else {
        & "npm.cmd" @args
    }
}
function git {
    if ($args[0] -eq "push") {
        gatekeeper check git-push
        if ($LASTEXITCODE -eq 0) {
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
    console.print("This will intercept `npm publish` and `git push` directly in your terminal.")
    console.print("Which shell environment do you want to secure?")
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
