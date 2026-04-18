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
    Collect every file touched by any unpushed commit by enumerating
    all unpushed SHAs via git log and diffing each one individually.
    Falls back to git ls-files when no remote tracking branch exists.
    Uses shell=False throughout to avoid shell-injection risk.
    """
    files: set = set()

    # Step 1: Try to collect all unpushed commit SHAs
    try:
        sha_result = subprocess.run(
            ["git", "log", "--format=%H", "@{u}..HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if sha_result.returncode == 0 and sha_result.stdout.strip():
            shas = [s.strip() for s in sha_result.stdout.splitlines() if s.strip()]
            for sha in shas:
                try:
                    diff_result = subprocess.run(
                        ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", sha],
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                    )
                    if diff_result.returncode == 0 and diff_result.stdout.strip():
                        for line in diff_result.stdout.splitlines():
                            line = line.strip()
                            if line:
                                files.add(line)
                except Exception:
                    continue
            if files:
                return list(files)
    except Exception:
        pass

    # Step 2: Fallback — no remote exists, list all tracked files
    try:
        ls_result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if ls_result.returncode == 0 and ls_result.stdout.strip():
            return [line.strip() for line in ls_result.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    return []
