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
            
        # Fallback 1: Try against origin/main or origin/master if no upstream is set yet
        for base in ["origin/main", "origin/master"]:
            fallback_res = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...HEAD"],
                cwd=project_root, capture_output=True, text=True, shell=True
            )
            if fallback_res.returncode == 0 and fallback_res.stdout.strip():
                return [line.strip() for line in fallback_res.stdout.splitlines() if line.strip()]

        # Fallback 2: Check the latest commit only (prevents locking up the terminal on a massive repo)
        commit_res = subprocess.run(["git", "diff", "--name-only", "HEAD~1..HEAD"], cwd=project_root, capture_output=True, text=True, shell=True)
        if commit_res.returncode == 0 and commit_res.stdout.strip():
            return [line.strip() for line in commit_res.stdout.splitlines() if line.strip()]
            
        # Fallback 3: Get all files tracked in current tree (only if repo has 1 root commit)
        fallback = subprocess.run(["git", "ls-files"], cwd=project_root, capture_output=True, text=True, shell=True)
        if fallback.returncode == 0:
            return [line.strip() for line in fallback.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []
