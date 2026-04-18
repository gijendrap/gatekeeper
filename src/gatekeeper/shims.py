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
            shell=False 
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
    touched_files = set()
    try:
        # Collect all unpushed commit SHAs
        result = subprocess.run(
            ["git", "log", "--format=%H", "@{u}..HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            shell=False
        )
        out = result.stdout.strip()
        if result.returncode == 0:
            if not out:
                return [] # No unpushed commits
            shas = [line.strip() for line in out.splitlines() if line.strip()]
            for sha in shas:
                diff_res = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", sha],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    shell=False
                )
                diff_out = diff_res.stdout.strip()
                if diff_res.returncode == 0 and diff_out:
                    for line in diff_out.splitlines():
                        if line.strip():
                            touched_files.add(line.strip())
            return list(touched_files)
    except Exception:
        pass
        
    # Fallback to ls-files
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            capture_output=True,
            text=True,
            shell=False
        )
        out = result.stdout.strip()
        if result.returncode == 0 and out:
            return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        pass
        
    return []

