import json
import pytest
from pathlib import Path
from gatekeeper.evaluator import check_ip_whitelist, scan_for_secrets
from unittest.mock import patch, MagicMock

def test_check_ip_whitelist(tmp_path: Path):
    # Setup mock .gatekeeper.json
    config_path = tmp_path / ".gatekeeper.json"
    config_path.write_text(json.dumps({
        "public_whitelist": ["public/", "src/index.js"],
        "private_blacklist": ["src/private.key", "public/super_secret/"]
    }))

    outgoing_files = [
        "public/app.js", # Safe
        "src/index.js", # Safe
        "src/auth.js", # Blocked (not whitelisted)
        "public/super_secret/data.json", # Blocked (blacklisted overrides public/)
        "app.map" # Blocked (Critically banned extension)
    ]
    
    blocked = check_ip_whitelist(tmp_path, outgoing_files)
    
    assert "public/app.js" not in blocked
    assert "src/index.js" not in blocked
    assert "src/auth.js" in blocked
    assert "public/super_secret/data.json" in blocked
    assert "app.map" in blocked


@patch("gatekeeper.evaluator.ensure_gitleaks")
@patch("gatekeeper.evaluator.subprocess.run")
def test_scan_for_secrets_no_leaks(mock_run, mock_ensure, tmp_path: Path):
    mock_ensure.return_value = tmp_path / "gitleaks"
    
    # Simulate gitleaks returning 0 (no leaks)
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_run.return_value = mock_res
    
    safe_file = tmp_path / "safe.txt"
    safe_file.write_text("All good here.")
    
    assert scan_for_secrets(tmp_path, ["safe.txt"]) is True

@patch("gatekeeper.evaluator.ensure_gitleaks")
@patch("gatekeeper.evaluator.subprocess.run")
def test_scan_for_secrets_with_leaks(mock_run, mock_ensure, tmp_path: Path):
    mock_ensure.return_value = tmp_path / "gitleaks"
    
    # Simulate gitleaks returning 1 (leaks found)
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_run.return_value = mock_res
    
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("Here is my sk_live_abc123 secret.")
    
    # The evaluator function creates a temp dir and passes it via `--report-path`.
    # Let's intercept the `subprocess.run` call, read the `report_path` arg, and write a dummy JSON file to it so the test doesn't crash when it tries to open the report.
    def side_effect(args, **kwargs):
        report_idx = args.index("--report-path") + 1
        report_file = Path(args[report_idx])
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps([{"Description": "Mock Secret", "Match": "sk_live_abc123"}]))
        return mock_res
        
    mock_run.side_effect = side_effect
    
    assert scan_for_secrets(tmp_path, ["secret.txt"]) is False
