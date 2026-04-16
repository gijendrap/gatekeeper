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
    Fetch files changed between local HEAD and remote tracking branch.
    Includes multiple fallbacks if the tracking branch hasn't been established yet.
    """
    strategies = [
        ["git", "diff", "--name-only", "@{u}..HEAD"],
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        ["git", "diff", "--name-only", "origin/master...HEAD"],
        ["git", "ls-files"]
    ]
    
    for cmd in strategies:
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                shell=True
            )
            out = result.stdout.strip()
            if result.returncode == 0 and out:
                return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            continue
            
    return []

