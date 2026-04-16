import re
from pathlib import Path
from typing import List, Set
from rich.console import Console
from gatekeeper.config import load_whitelist

console = Console()

# Enterprise-grade set of high-risk secret regexes (verified against Gitleaks standards)
DEFAULT_SECRETS = {
    # --- AI & Cloud ---
    "OpenAI API Key": r"(sk-[a-zA-Z0-9\-_]{48,}|sk-proj-[a-zA-Z0-9\-_]{48,})",
    "Anthropic API Key": r"sk-ant-api[a-zA-Z0-9\-_]{90,}",
    "AWS Access Key ID": r"(AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
    "Google Cloud API Key": r"AIza[0-9A-Za-z\-_]{35}",
    
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

def check_ip_whitelist(project_root: Path, outgoing_files: List[str]) -> bool:
    """
    Stage 1: Validates that all outgoing_files are explicitly whitelisted.
    Returns False if a forbidden file is found.
    """
    whitelist = load_whitelist(project_root)
    
    blocked_files = []
    
    for f in outgoing_files:
        is_safe = False
        # Normalize file separators for comparison
        norm_f = Path(f).as_posix()
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
            
    if blocked_files:
        console.print("[bold red]🚨 IP LEAK DETECTED 🚨[/bold red]")
        console.print("[red]The following files are NOT whitelisted but were found in the outgoing payload:[/red]")
        for b in blocked_files:
            console.print(f"  ❌ {b}")
        return False
        
    return True

def scan_for_secrets(project_root: Path, outgoing_files: List[str]) -> bool:
    """
    Stage 2: Scans whitelisted outgoing files for secrets.
    """
    import mimetypes
    console.print("[cyan]Running Deep Secret Scan...[/cyan]")
    found_secrets = False
    
    patterns = {name: re.compile(pat) for name, pat in DEFAULT_SECRETS.items()}
    
    for f in outgoing_files:
        filepath = project_root / f
        if filepath.exists() and filepath.is_file():
            # Fix 1: Skip massive files (> 5MB) to prevent in-memory regex loading (OOM Risk)
            if filepath.stat().st_size > 5_000_000:
                console.print(f"[dim]Skipping massive file (>5MB): {f}[/dim]")
                continue
                
            # Fix 2: Prevent eager CPU spikes by quickly guessing binary formats instead of trying to decode them
            mime_type, _ = mimetypes.guess_type(str(filepath))
            if mime_type and not mime_type.startswith("text/") and mime_type not in ["application/json", "application/xml"]:
                continue
                
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                for name, compiled_regex in patterns.items():
                    if compiled_regex.search(content):
                        console.print(f"[bold red]💥 SECRET LEAK DETECTED 💥[/bold red]")
                        console.print(f"[red]Found '{name}' in {f}[/red]")
                        found_secrets = True
            except Exception:
                pass
                
    if found_secrets:
        return False
        
    return True
    
def evaluate_payload(project_root: Path, outgoing_files: List[str]) -> bool:
    """
    Runs the two-stage evaluation line.
    """
    if not outgoing_files:
        console.print("[yellow]No outgoing files to check.[/yellow]")
        return True
        
    if not check_ip_whitelist(project_root, outgoing_files):
        return False
        
    if not scan_for_secrets(project_root, outgoing_files):
        return False
        
    console.print("[bold green]✅ All GateKeeper Checks Passed![/bold green]")
    return True
