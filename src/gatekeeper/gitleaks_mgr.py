import os
import hashlib
import platform
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from rich.console import Console

console = Console()

GITLEAKS_VERSION = "8.18.2"
GATEKEEPER_DIR = Path.home() / ".gatekeeper"
BIN_DIR = GATEKEEPER_DIR / "bin"
GITLEAKS_BIN = BIN_DIR / ("gitleaks.exe" if platform.system().lower() == "windows" else "gitleaks")

def get_download_url() -> tuple:
    """
    Returns (url, filename) for the gitleaks archive appropriate for the
    current platform.
    """
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
    filename = f"gitleaks_{GITLEAKS_VERSION}_{os_name}_{arch}.{ext}"
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/{filename}"
    return url, filename


def verify_checksum(file_path: Path, version: str, filename: str) -> None:
    """
    Fetches the official checksums.txt from the Gitleaks GitHub release,
    locates the entry for `filename`, and compares its SHA-256 against the
    downloaded archive.  Raises RuntimeError on mismatch and deletes the
    bad file so it is never extracted.
    """
    checksums_url = (
        f"https://github.com/gitleaks/gitleaks/releases/download/"
        f"v{version}/checksums.txt"
    )
    try:
        with urllib.request.urlopen(checksums_url) as resp:
            checksums_text = resp.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch checksums.txt: {exc}") from exc

    expected_hash: str | None = None
    for line in checksums_text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].strip() == filename:
            expected_hash = parts[0].strip()
            break

    if expected_hash is None:
        file_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not find checksum entry for '{filename}' in checksums.txt."
        )

    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        file_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {filename}!\n"
            f"  expected: {expected_hash}\n"
            f"  got:      {actual_hash}\n"
            "The downloaded file has been deleted. This may indicate a MITM or tampered release."
        )

def ensure_gitleaks() -> Path:
    """
    Returns the path to a usable gitleaks binary.

    Resolution priority:
      1. System-installed gitleaks (brew / choco / apt) — preferred, no supply chain risk
      2. Cached ~/.gatekeeper/bin/gitleaks — already downloaded and verified
      3. Auto-download from GitHub Releases (SHA-256 verified) — last resort
    """
    import shutil

    # Priority 1: system-installed binary
    sys_gitleaks = shutil.which("gitleaks")
    if sys_gitleaks:
        return Path(sys_gitleaks)

    # Priority 2: previously cached download
    if GITLEAKS_BIN.exists() and os.access(GITLEAKS_BIN, os.X_OK):
        return GITLEAKS_BIN

    # Priority 3: auto-download (last resort)
    console.print(f"[cyan]Downloading Gitleaks v{GITLEAKS_VERSION} for your system...[/cyan]")
    console.print("[dim]Tip: Install gitleaks via your system package manager to avoid runtime downloads:[/dim]")
    console.print("[dim]  macOS:   brew install gitleaks[/dim]")
    console.print("[dim]  Windows: choco install gitleaks[/dim]")
    console.print("[dim]  Linux:   apt install gitleaks  (or see https://github.com/gitleaks/gitleaks)[/dim]")

    BIN_DIR.mkdir(parents=True, exist_ok=True)

    url, filename = get_download_url()
    ext = url.split(".")[-1]
    archive_path = BIN_DIR / f"gitleaks_archive.{ext}"

    try:
        urllib.request.urlretrieve(url, archive_path)

        # Verify integrity before extracting — guards against MITM / tampered releases
        console.print("[dim]Verifying checksum...[/dim]")
        verify_checksum(archive_path, GITLEAKS_VERSION, filename)
        console.print("[dim]✅ Checksum verified.[/dim]")

        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(BIN_DIR)
        else:
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
        raise RuntimeError("Gitleaks is required but could not be downloaded or found.")


