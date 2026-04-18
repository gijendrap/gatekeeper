import os
import platform
import urllib.request
import zipfile
import tarfile
import hashlib
from pathlib import Path
from rich.console import Console

console = Console()

GITLEAKS_VERSION = "8.18.2"
GATEKEEPER_DIR = Path.home() / ".gatekeeper"
BIN_DIR = GATEKEEPER_DIR / "bin"
GITLEAKS_BIN = BIN_DIR / ("gitleaks.exe" if platform.system().lower() == "windows" else "gitleaks")

def get_download_url() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        os_name = "darwin"
    elif system == "windows":
        os_name = "windows"
    else:
        os_name = "linux"

    if machine in ["x86_64", "amd64"]:
        arch = "x64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    elif machine in ["armv7l"]:
        arch = "armv7"
    else:
        arch = "x64" # fallback

    ext = "zip" if os_name == "windows" else "tar.gz"
    
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/gitleaks_{GITLEAKS_VERSION}_{os_name}_{arch}.{ext}"
    return url

def verify_checksum(file_path: Path, version: str, filename: str):
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{version}/checksums.txt"
    try:
        req = urllib.request.urlopen(url)
        checksums = req.read().decode("utf-8")
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise RuntimeError(f"Could not fetch checksums.txt: {e}")
        
    expected_sha = None
    for line in checksums.splitlines():
        if filename in line:
            expected_sha = line.split()[0]
            break
            
    if not expected_sha:
        file_path.unlink(missing_ok=True)
        raise RuntimeError(f"Could not find checksum for {filename} in checksums.txt")
        
    actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        file_path.unlink()
        raise RuntimeError(f"Checksum mismatch for {filename}! Expected {expected_sha}, got {actual_sha}")

def ensure_gitleaks() -> Path:
    """
    Ensures that the gitleaks binary is downloaded and available.
    Returns the Path to the executable.
    """
    if GITLEAKS_BIN.exists() and os.access(GITLEAKS_BIN, os.X_OK):
        return GITLEAKS_BIN

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    
    url = get_download_url()
    archive_path = BIN_DIR / f"gitleaks_archive.{url.split('.')[-1]}"
    
    console.print(f"[cyan]Downloading Gitleaks v{GITLEAKS_VERSION} for your system...[/cyan]")
    try:
        urllib.request.urlretrieve(url, archive_path)
        
        verify_checksum(archive_path, GITLEAKS_VERSION, archive_path.name)
        
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(BIN_DIR)
        else:
            # Handle .tar.gz
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(BIN_DIR)
                
        # Clean up archive
        archive_path.unlink()
        
        # Ensure executable permissions on Unix
        if platform.system().lower() != "windows":
            GITLEAKS_BIN.chmod(0o755)
            
        console.print("[bold green]✅ Gitleaks downloaded successfully![/bold green]")
        return GITLEAKS_BIN
        
    except Exception as e:
        console.print(f"[bold red]Failed to auto-download Gitleaks: {e}[/bold red]")
        console.print("[yellow]Please install gitleaks manually and ensure it is in your system PATH.[/yellow]")
        # Fallback to checking if it's already in the system PATH
        import shutil
        sys_gitleaks = shutil.which("gitleaks")
        if sys_gitleaks:
            return Path(sys_gitleaks)
        raise RuntimeError("Gitleaks is required but could not be downloaded or found.")

