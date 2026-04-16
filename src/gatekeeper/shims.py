import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List

def get_npm_publish_files(project_root: Path) -> List[str]:
    """
    Simulates npm publish --dry-run to extract exactly which 
    files will be packaged into the tarball.
    """
    try:
        result = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"], 
            cwd=project_root, 
            capture_output=True, 
            text=True,
            shell=True 
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        if data and isinstance(data, list) and len(data) > 0:
            return [f["path"] for f in data[0].get("files", [])]
    except Exception:
        pass
    return []

def get_git_push_files(project_root: Path) -> List[str]:
    """
    Very crude fetch of files changed between local HEAD and remote tracking branch.
    If no remote, gets all tracked files as a fallback.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "@{u}..HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            shell=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
            
        # fallback: get all files tracked in current tree (just as a failsafe test)
        fallback = subprocess.run(["git", "ls-files"], cwd=project_root, capture_output=True, text=True, shell=True)
        if fallback.returncode == 0:
            return [line.strip() for line in fallback.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []

def execute_original_command(command_str: str, args: List[str]):
    """
    If gatekeeper clears the operation, we pass it along to the real binary.
    """
    # For a real shim, we'd need the path to the original binary to avoid infinite loops,
    # or an environment variable flag.
    # For now, we mock success.
    pass
