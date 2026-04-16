import os
import json
from pathlib import Path
from typing import List, Set, Optional

def get_ignored_paths(project_root: Path) -> Set[str]:
    """
    Reads .gitignore and returns a set of basic ignore patterns.
    (This is a simplistic parser prior to fully relying on git check-ignore).
    """
    gitignore_path = project_root / ".gitignore"
    ignored = set()
    
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Safely ignore blank lines, comments, and explicit negation logic from legacy parsers
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                ignored.add(line)
    return ignored

def check_package_json_private(project_root: Path) -> bool:
    """
    Reads package.json (if exists) and checks if "private": true.
    """
    pkg_json_path = project_root / "package.json"
    if pkg_json_path.exists():
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("private", False) is True
        except json.JSONDecodeError:
            pass
    return False

def analyze_context(project_root: Optional[Path] = None):
    """
    High-level function to evaluate the context constraints of the current repository.
    Returns Context findings.
    """
    if project_root is None:
        project_root = Path(os.getcwd())
        
    is_private_enforced = check_package_json_private(project_root)
    ignored_patterns = get_ignored_paths(project_root)
    
    return {
        "is_permanently_locked": is_private_enforced,
        "ignored_patterns": ignored_patterns
    }
