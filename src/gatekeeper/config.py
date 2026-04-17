import json
from pathlib import Path
from typing import List, Set, Tuple, Optional

GATEKEEPER_CONFIG_FILE = ".gatekeeper.json"

def load_whitelist(project_root: Path) -> Tuple[Set[str], Set[str]]:
    """
    Load the explicitly whitelisted and blacklisted paths from .gatekeeper.json.
    """
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    if not config_path.exists():
        return set(), set()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Support legacy config structures
            if isinstance(data, list):
                return set(data), set()
            return set(data.get("public_whitelist", [])), set(data.get("private_blacklist", []))
    except (json.JSONDecodeError, IOError):
        return set(), set()

def save_whitelist(project_root: Path, whitelist: Set[str], blacklist: Optional[Set[str]] = None) -> None:
    """
    Save the dual lists to .gatekeeper.json.
    """
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    data = {
        "public_whitelist": list(whitelist),
        "private_blacklist": list(blacklist) if blacklist else []
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
