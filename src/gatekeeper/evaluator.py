import re
from pathlib import Path
from typing import List, Set
from rich.console import Console
from gatekeeper.config import load_whitelist
import typer
import subprocess

console = Console()

import json
import subprocess
import tempfile

from gatekeeper.gitleaks_mgr import ensure_gitleaks

ABSOLUTE_BANNED_EXTENSIONS = {".map", ".env", ".pem", ".key", ".log", ".p8"}
BLOAT_DIRECTORIES = {"venv", ".venv", "node_modules", "__pycache__", "dist", ".env"}

ABSOLUTE_BANNED_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "credentials.json",
    "credentials.yaml",
    "serviceaccountkey.json",
    "firebase-adminsdk.json",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    ".htpasswd",
    "wp-config.php",
}

def check_bloat(project_root: Path, outgoing_files: List[str], command: str, non_interactive: bool = False) -> int:
    """
    Checks if massive bloat directories are accidentally included.
    Returns:
      0: Clean (no bloat)
      1: Bloat detected and forcefully removed
     -1: Aborted by user or error
    """
    bloat_detected = set()
    for f in outgoing_files:
        parts = Path(f).parts
        for part in parts:
            if part in BLOAT_DIRECTORIES:
                bloat_detected.add(part)
                
    if not bloat_detected:
        return 0
        
    console.print("\n[bold red]🚨 MASSIVE BLOAT CHECK-IN DETECTED 🚨[/bold red]")
    console.print(f"[red]You are about to upload massive dependency folders:[/red] [bold yellow]{', '.join(bloat_detected)}[/bold yellow]")
    
    if command == "git-push":
        if non_interactive:
            console.print("[bold red]Non-interactive mode: aborting push due to bloat. Please un-commit these directories and add them to .gitignore.[/bold red]")
            return -1
        if typer.confirm("Would you like GateKeeper to forcefully un-commit these and add them to .gitignore?"):
            console.print("[cyan]Applying Git Amendments...[/cyan]")
            for bloat in bloat_detected:
                subprocess.run(["git", "rm", "--cached", "-r", "--ignore-unmatch", bloat], cwd=project_root, capture_output=True)
                
            res = subprocess.run(["git", "commit", "--amend", "--no-edit"], cwd=project_root, capture_output=True)
            if res.returncode != 0:
                console.print("[bold red]Fatal Error: Could not amend commit to remove bloat. Un-commit them manually.[/bold red]")
                return -1
                
            existing_lines = []
            gitignore_path = project_root / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path, "r", encoding="utf-8") as r:
                    existing_lines = [line.strip() for line in r.readlines()]
            
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n")
                for bloat in bloat_detected:
                    if f"{bloat}/" not in existing_lines and bloat not in existing_lines:
                        f.write(f"{bloat}/\n")
            console.print("[bold green]✅ Bloat successfully ripped out and .gitignore updated![/bold green]")
            return 1
        else:
            return -1
            
    return -1

def check_ip_whitelist(project_root: Path, outgoing_files: List[str]) -> List[str]:
    """
    Stage 1: Validates that all outgoing_files are explicitly whitelisted.
    Returns a list of blocked files.
    """
    whitelist, blacklist = load_whitelist(project_root)
    blocked_files = []
    
    for f in outgoing_files:
        is_safe = False
        # Normalize file separators for comparison
        norm_f = Path(f).as_posix()
        
        # Immediate Hard-Ban Check: Certain filenames are universally forbidden regardless of UI selection
        if Path(f).name.lower() in ABSOLUTE_BANNED_FILENAMES:
            blocked_files.append(norm_f)
            console.print(f"[bold red]🚫 CRITICAL BAN:[/bold red] {norm_f} is a permanently banned secret filename!")
            continue

        # Immediate Hard-Ban Check: Certain extensions are universally forbidden regardless of UI selection
        if Path(f).suffix.lower() in ABSOLUTE_BANNED_EXTENSIONS:
            blocked_files.append(norm_f)
            console.print(f"[bold red]🚫 CRITICAL BAN:[/bold red] {norm_f} contains a forbidden file extension!")
            continue
            
        allow_len = -1
        for allowed in whitelist:
            norm_a = Path(allowed).as_posix()
            if norm_a == "." or norm_a == "":
                allow_len = max(allow_len, 0)
            elif norm_f == norm_a or norm_f.startswith(f"{norm_a}/"):
                allow_len = max(allow_len, len(norm_a))
                
        deny_len = -1
        for denied in blacklist:
            norm_b = Path(denied).as_posix()
            if norm_f == norm_b or norm_f.startswith(f"{norm_b}/"):
                deny_len = max(deny_len, len(norm_b))
                
        if allow_len > deny_len:
            is_safe = True
        else:
            is_safe = False
                
        if not is_safe:
            blocked_files.append(norm_f)
            
    return blocked_files

def scan_for_secrets(project_root: Path, outgoing_files: List[str]) -> bool:
    """
    Stage 2: Scans whitelisted outgoing files for secrets using Gitleaks.
    """
    console.print("[cyan]Running Deep Secret Scan with Gitleaks...[/cyan]")
    
    try:
        gitleaks_bin = ensure_gitleaks()
    except RuntimeError:
        console.print("[bold red]Cannot proceed without Gitleaks.[/bold red]")
        return False

    found_secrets = False
    
    # Create a temporary directory to stream files into so Gitleaks can scan them rapidly without touching history
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = Path(temp_dir) / "gitleaks_report.json"
        
        # We will write the list of files to scan into a file if there are many, but gitleaks detect --no-git wants a directory pointing to the repo or specific files.
        # However, gitleaks detect --no-git -s <file/dir> is standard. 
        # For simplicity and precise control, we will just pipe the files or use a loop if files are few, or let gitleaks scan the repo but with a massive ignore?
        # Actually, running gitleaks on individual files is fast enough for typical push payloads.
        
        for f in outgoing_files:
            filepath = project_root / f
            if not filepath.exists() or not filepath.is_file():
                continue
                
            if filepath.stat().st_size > 5_000_000:
                continue # OOM avoidance for huge binaries

            res = subprocess.run(
                [str(gitleaks_bin), "detect", "--no-git", "--source", str(filepath), "--report-path", str(report_path), "--exit-code", "1"],
                capture_output=True,
                text=True
            )
            
            if res.returncode == 1 and report_path.exists():
                found_secrets = True
                try:
                    with open(report_path, "r", encoding="utf-8") as rf:
                        leaks = json.load(rf)
                        for leak in leaks:
                            console.print(f"[bold red]💥 SECRET LEAK DETECTED 💥[/bold red]")
                            console.print(f"[red]Found '{leak.get('Description', 'Secret')}' in {f}[/red]")
                            # console.print(f"[dim]Match: {leak.get('Match')}[/dim]") # Optional: hide the actual secret to avoid console logging
                except Exception:
                    console.print(f"[bold red]💥 SECRET LEAK DETECTED in {f}![/bold red]")
                    
    return not found_secrets
    
def evaluate_payload(project_root: Path, outgoing_files: List[str], command: str = "git-push", non_interactive: bool = False) -> bool:
    """
    Runs the two-stage evaluation line.
    """
    if not outgoing_files:
        console.print("[yellow]No outgoing files to check.[/yellow]")
        return True

    # --- Security Policy Tamper Guard ---
    # If .gatekeeper.json itself is being modified in this push, it means the
    # whitelist (security policy) is changing. This must never happen silently.
    POLICY_FILE = ".gatekeeper.json"
    policy_being_modified = any(
        Path(f).as_posix() == POLICY_FILE or Path(f).name == POLICY_FILE
        for f in outgoing_files
    )
    if policy_being_modified:
        if non_interactive:
            console.print("\n[bold red]❌ PUSH BLOCKED: .gatekeeper.json is being modified.[/bold red]")
            console.print("[red]Security policy changes must be reviewed interactively — they cannot pass through CI or git hooks silently.[/red]")
            return False
        else:
            console.print("\n[bold yellow]⚠️  WARNING: This push modifies the GateKeeper security policy (.gatekeeper.json)[/bold yellow]")
            console.print("[dim]Showing what changed:[/dim]")
            try:
                diff_result = subprocess.run(
                    ["git", "diff", "HEAD", POLICY_FILE],
                    cwd=project_root, capture_output=True, text=True
                )
                if diff_result.returncode == 0 and diff_result.stdout.strip():
                    console.print(diff_result.stdout)
                else:
                    # New file being added for the first time
                    console.print("[dim](New policy file being committed for the first time.)[/dim]")
            except Exception:
                pass
            if not typer.confirm("\nThe security policy is changing. Do you want to proceed?"):
                console.print("[bold red]❌ Push aborted. Review your .gatekeeper.json changes before pushing.[/bold red]")
                return False

    blocked_files = check_ip_whitelist(project_root, outgoing_files)
    
    if blocked_files:
        console.print("[bold red]🚨 IP LEAK DETECTED 🚨[/bold red]")
        console.print("[red]The following files are NOT whitelisted but were found in the outgoing payload:[/red]")
        for b in blocked_files:
            console.print(f"  ❌ {b}")
            
        if command == "git-push":
            if non_interactive:
                console.print("[bold red]Non-interactive mode: push blocked. Remove or whitelist the files above.[/bold red]")
                return False
            console.print("\n[bold yellow]Do you want to strip these private files from the payload and push ONLY the public files?[/bold yellow]")
            if typer.confirm("Automatically remove private files from this commit?"):
                console.print("[cyan]Applying Git Amendments...[/cyan]")
                for b in blocked_files:
                    subprocess.run(["git", "rm", "--cached", "-r", "--ignore-unmatch", b], cwd=project_root, capture_output=True)
                    
                res = subprocess.run(["git", "commit", "--amend", "--no-edit"], cwd=project_root, capture_output=True)
                if res.returncode != 0:
                    console.print("[bold red]Fatal Error: Could not amend commit. These files might be scattered across multiple unpushed commits. Please manually rebase or un-commit them.[/bold red]")
                    return False
                
                console.print("[bold green]✅ Private files safely stripped from your commit![/bold green]")
                outgoing_files = [f for f in outgoing_files if Path(f).as_posix() not in blocked_files]
            else:
                return False
                
        elif command == "npm-publish":
            console.print("\n[bold yellow]Do you want to dynamically ignore these private files for this npm publish?[/bold yellow]")
            if typer.confirm("Automatically append them to .npmignore?"):
                with open(project_root / ".npmignore", "a", encoding="utf-8") as f:
                    for b in blocked_files:
                        f.write(f"\n{b}\n")
                console.print("[bold green]✅ Private files safely appended to .npmignore![/bold green]")
                outgoing_files = [f for f in outgoing_files if Path(f).as_posix() not in blocked_files]
            else:
                return False
        else:
            return False

    if not outgoing_files:
        console.print("[yellow]No public files remain to check.[/yellow]")
        return True
        
    if not scan_for_secrets(project_root, outgoing_files):
        return False
        
    console.print("[bold green]✅ All GateKeeper Checks Passed![/bold green]")
    return True
