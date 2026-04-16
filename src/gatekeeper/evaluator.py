import re
from pathlib import Path
from typing import List, Set
from rich.console import Console
from gatekeeper.config import load_whitelist

console = Console()

# Basic set of regex rules for secrets
DEFAULT_SECRETS = {
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{48}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Anthropic API Key": r"sk-ant-api03-[a-zA-Z0-9\-_]{93}",
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
    console.print("[cyan]Running Deep Secret Scan...[/cyan]")
    found_secrets = False
    
    patterns = {name: re.compile(pat) for name, pat in DEFAULT_SECRETS.items()}
    
    for f in outgoing_files:
        filepath = project_root / f
        if filepath.exists() and filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8")
                for name, compiled_regex in patterns.items():
                    if compiled_regex.search(content):
                        console.print(f"[bold red]💥 SECRET LEAK DETECTED 💥[/bold red]")
                        console.print(f"[red]Found '{name}' in {f}[/red]")
                        found_secrets = True
            except UnicodeDecodeError:
                pass # skip binary files
                
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
