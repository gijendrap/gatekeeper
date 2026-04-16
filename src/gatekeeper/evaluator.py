import re
from pathlib import Path
from typing import List, Set
from rich.console import Console
from gatekeeper.config import load_whitelist
import typer
import subprocess

console = Console()

# Enterprise-grade set of high-risk secret regexes (verified against Gitleaks standards)
DEFAULT_SECRETS = {
    # --- AI & Cloud ---
    "OpenAI API Key": r"(sk-[a-zA-Z0-9\-_]{48,}|sk-proj-[a-zA-Z0-9\-_]{48,})",
    "Anthropic API Key": r"sk-ant-api[a-zA-Z0-9\-_]{90,}",
    "AWS Access Key ID": r"(AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
    "Google Cloud API Key": r"AIza[0-9A-Za-z\-_]{35}",
    
    # --- Cloud Storage URLs (Anthropic Scenario) ---
    "AWS S3 Bucket": r"[a-zA-Z0-9_\-\.]+\.s3\.amazonaws\.com",
    "Cloudflare R2 Bucket": r"[a-zA-Z0-9_\-\.]+\.r2\.cloudflarestorage\.com",
    "Google Cloud Storage": r"storage\.googleapis\.com/[a-zA-Z0-9_\-\.]+",
    
    # --- Version Control ---
    "GitHub Token": r"gh[pousr]_[a-zA-Z0-9]{36}",
    "GitLab Personal Access Token": r"glpat-[a-zA-Z0-9\-]{20}",
    
    # --- Messaging & Communication ---
    "Slack Token": r"xox[bpa]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}",
    "Slack Webhook": r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8,10}/B[a-zA-Z0-9_]{8,12}/[a-zA-Z0-9_]{24}",
    "Discord Bot Token": r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27,38}",
    
    # --- Developer Tools ---
    "Ngrok Auth Token": r"(?:^|[^a-zA-Z0-9_\-])[0-9a-zA-Z]{43,55}(?:$|[^a-zA-Z0-9_\-])",
    "Heroku API Key": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    
    # --- Payment & Email ---
    "Stripe Secret Key": r"(sk_live|rk_live)_[0-9a-zA-Z]{24,99}",
    "Twilio API Key": r"SK[0-9a-fA-F]{32}",
    "SendGrid API Key": r"SG\.[0-9A-Za-z\-_]{22}\.[0-9A-Za-z\-_]{43}",
    "Mailchimp API Key": r"[0-9a-f]{32}-us[0-9]{1,2}",
    
    # --- Cryptography ---
    "Private Key Block": r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP|PRIVATE) KEY(?: BLOCK)?-----",
}

ABSOLUTE_BANNED_EXTENSIONS = {".map", ".env", ".pem", ".key", ".log", ".p8"}

def check_ip_whitelist(project_root: Path, outgoing_files: List[str]) -> List[str]:
    """
    Stage 1: Validates that all outgoing_files are explicitly whitelisted.
    Returns a list of blocked files.
    """
    whitelist = load_whitelist(project_root)
    blocked_files = []
    
    for f in outgoing_files:
        is_safe = False
        # Normalize file separators for comparison
        norm_f = Path(f).as_posix()
        
        # Immediate Hard-Ban Check: Certain extensions are universally forbidden regardless of UI selection
        if Path(f).suffix.lower() in ABSOLUTE_BANNED_EXTENSIONS:
            blocked_files.append(norm_f)
            console.print(f"[bold red]🚫 CRITICAL BAN:[/bold red] {norm_f} contains a forbidden file extension!")
            continue
            
        for allowed in whitelist:
            norm_a = Path(allowed).as_posix()
            # If the whitelist allows the root directory (.), everything inside is safe.
            if norm_a == "." or norm_a == "":
                is_safe = True
                break
            if norm_f == norm_a or norm_f.startswith(f"{norm_a}/"):
                is_safe = True
                break
        if not is_safe:
            blocked_files.append(norm_f)
            
    return blocked_files

def scan_for_secrets(project_root: Path, outgoing_files: List[str]) -> bool:
    """
    Stage 2: Scans whitelisted outgoing files for secrets.
    """
    console.print("[cyan]Running Deep Secret Scan...[/cyan]")
    found_secrets = False
    
    patterns = {name: re.compile(pat) for name, pat in DEFAULT_SECRETS.items()}
    
    for f in outgoing_files:
        filepath = project_root / f
        if filepath.exists() and filepath.is_file():
            # OOM Risk check: Skip massive files (>5MB)
            if filepath.stat().st_size > 5_000_000:
                continue
                
            # CPU Spike check: Sniff for binary null bytes before attempting to decode everything into a massive text buffer
            try:
                with open(filepath, "rb") as bf:
                    if b"\0" in bf.read(1024):
                        continue
            except Exception:
                pass
                
            try:
                content = filepath.read_text(encoding="utf-8")
                for name, compiled_regex in patterns.items():
                    if compiled_regex.search(content):
                        console.print(f"[bold red]💥 SECRET LEAK DETECTED 💥[/bold red]")
                        console.print(f"[red]Found '{name}' in {f}[/red]")
                        found_secrets = True
            except UnicodeDecodeError:
                pass # skip edge-case binary files that didn't have null bytes
                
    if found_secrets:
        return False
        
    return True
    
def evaluate_payload(project_root: Path, outgoing_files: List[str], command: str = "git-push") -> bool:
    """
    Runs the two-stage evaluation line.
    """
    if not outgoing_files:
        console.print("[yellow]No outgoing files to check.[/yellow]")
        return True
        
    blocked_files = check_ip_whitelist(project_root, outgoing_files)
    
    if blocked_files:
        console.print("[bold red]🚨 IP LEAK DETECTED 🚨[/bold red]")
        console.print("[red]The following files are NOT whitelisted but were found in the outgoing payload:[/red]")
        for b in blocked_files:
            console.print(f"  ❌ {b}")
            
        if command == "git-push":
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
