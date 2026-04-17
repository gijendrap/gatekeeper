import json
from pathlib import Path
from gatekeeper.context import get_ignored_paths, check_package_json_private, analyze_context

def test_get_ignored_paths(tmp_path: Path):
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(
        "node_modules/\n"
        "\n"
        "# Comment\n"
        "*.log\n"
        "!important.log\n"
    )
    
    ignored = get_ignored_paths(tmp_path)
    assert ignored == {"node_modules/", "*.log"}

def test_check_package_json_private_true(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "app", "private": True}))
    
    assert check_package_json_private(tmp_path) is True

def test_check_package_json_private_false(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "app", "private": False}))
    
    assert check_package_json_private(tmp_path) is False

def test_analyze_context_defaults(tmp_path: Path):
    # Empty dir, should return safe defaults
    context = analyze_context(tmp_path)
    assert context["is_permanently_locked"] is False
    assert len(context["ignored_patterns"]) == 0
