import json
from pathlib import Path
from typing import List, Set, Optional

GATEKEEPER_CONFIG_FILE = ".gatekeeper.json"

def load_whitelist(project_root: Path) -> Set[str]:
    """
    Load the explicitly whitelisted paths from .gatekeeper.json.
    """
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    if not config_path.exists():
        return set()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("public_whitelist", []))
    except (json.JSONDecodeError, IOError):
        return set()

def save_whitelist(project_root: Path, whitelist: Set[str]) -> None:
    """
    Save the explicitly whitelisted paths to .gatekeeper.json.
    """
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    data = {"public_whitelist": list(whitelist)}
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
