import json
from pathlib import Path

CONFIG_FILE = ".gatekeeper.json"

def save_config(project_root: Path, state: dict):
    """Save the dual-state database to the config file."""
    config_path = project_root / CONFIG_FILE
    serializable = {
        "public": list(state.get("public", set())),
        "private": list(state.get("private", set()))
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

def load_config(project_root: Path) -> dict:
    """Load the dual-state database from the config file."""
    config_path = project_root / CONFIG_FILE
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Migration safety from old version
                if "public_whitelist" in data:
                    return {"public": set(), "private": set()}
                    
                return {
                    "public": set(data.get("public", [])),
                    "private": set(data.get("private", []))
                }
        except Exception:
            pass
    return {"public": set(), "private": set()}
