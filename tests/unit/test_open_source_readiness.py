from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEXT_SCAN_EXCLUDED_SUFFIXES = {
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".swp",
    ".swo",
    ".webp",
    ".zip",
}
# Public-file pathspecs scanned by test_public_files_do_not_contain_machine_specific_paths_or_tokens.
PUBLIC_FILE_PATHSPECS = ["README.md", "docs", "examples", "tasks", ".github"]


def _git_tracked_public_files() -> list[Path]:
    # Scan git's tracked-file list rather than the filesystem: locally generated
    # artifacts (e.g. __pycache__ left by running a docs/ smoke script) are never
    # tracked, so they can't break this test even though they can appear on disk.
    # -z gives NUL-separated, unquoted paths so non-ASCII filenames survive intact
    # (plain `git ls-files` octal-escapes them behind quotes by default).
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *PUBLIC_FILE_PATHSPECS],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        PROJECT_ROOT / relative_path
        for relative_path in result.stdout.split("\0")
        if relative_path and Path(relative_path).suffix.lower() not in TEXT_SCAN_EXCLUDED_SUFFIXES
    ]


def test_open_source_governance_files_exist() -> None:
    required_files = [
        "LICENSE",
        "NOTICE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "CITATION.cff",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ]

    for relative_path in required_files:
        assert (PROJECT_ROOT / relative_path).exists(), relative_path

    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    notice_text = (PROJECT_ROOT / "NOTICE").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Copyright" in license_text
    assert "ml-intern" in notice_text
    assert "autoresearch" in notice_text
    assert "AIDE" in notice_text
    assert "PaperBench" in notice_text
    assert "LICENSE" in readme
    assert "SECURITY.md" in readme
    assert "CONTRIBUTING.md" in readme


def test_public_files_do_not_contain_machine_specific_paths_or_tokens() -> None:
    public_files = _git_tracked_public_files()

    forbidden_snippets = [
        "/Users/",
        "file:///Users/",
        "ghp_",
        "github.com/your-username/ml-research-loop.git",
        "YOUR_GITHUB_TOKEN",
        "dm@example.com",
    ]
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in text, f"{snippet} found in {path.relative_to(PROJECT_ROOT)}"


def test_distribution_includes_product_assets() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'license = "MIT"' in pyproject
    assert 'authors = [' in pyproject
    assert "dm@example.com" not in pyproject
    assert "[tool.hatch.build.targets.wheel.force-include]" in pyproject
    assert '"skills" = "skills"' in pyproject
    assert '"examples" = "examples"' in pyproject
    assert '"LICENSE" = "LICENSE"' in pyproject
    assert '"NOTICE" = "NOTICE"' in pyproject


def test_distribution_excludes_docs_tree() -> None:
    # docs/ carries evidence archives and per-round eval scripts, not shipped
    # product code — it stays in the git repo but out of the wheel/sdist.
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    sdist_include = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]

    assert "docs" not in force_include
    assert "/docs" not in sdist_include


def test_cp_bench_extra_includes_space_submission_client() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    cp_bench_extra = pyproject["project"]["optional-dependencies"]["hf-cp-bench"]

    assert "gradio_client>=2.5.0" in cp_bench_extra


def test_ci_workflow_runs_open_source_fast_gate() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/checkout" in workflow
    assert "actions/setup-python" in workflow
    assert 'python-version: ["3.10", "3.13"]' in workflow
    assert 'pip install -e ".[dev]"' in workflow
    assert "ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/" in workflow
    assert "python -m pytest tests/ -q" in workflow
    assert "python scripts/mcp_client_acceptance.py" in workflow


def test_release_docs_track_open_source_readiness() -> None:
    todos = (PROJECT_ROOT / "docs" / "productization-todos.md").read_text(
        encoding="utf-8"
    )
    release_notes = (PROJECT_ROOT / "docs" / "release-notes.md").read_text(
        encoding="utf-8"
    )
    release_checklist = (PROJECT_ROOT / "docs" / "release-checklist.md").read_text(
        encoding="utf-8"
    )

    assert "P12: Open Source Readiness" in todos
    assert "LICENSE" in todos
    assert "SECURITY.md" in release_notes
    assert "clean checkout" in release_notes
    assert "Open Source Release Gate" in release_checklist
    assert "CITATION.cff" in release_checklist


def test_preview_feedback_paths_are_documented() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    feedback_doc = (PROJECT_ROOT / "docs" / "preview-feedback-cn.md")
    feedback_template = (
        PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "preview_feedback.yml"
    )

    assert feedback_doc.exists()
    assert feedback_template.exists()

    feedback_text = feedback_doc.read_text(encoding="utf-8")
    template_text = feedback_template.read_text(encoding="utf-8")

    assert "Try v0.1.0-preview" in readme
    assert "docs/preview-feedback-cn.md" in readme
    assert "https://github.com/MagicianDu/ml-research-loop/issues/new/choose" in readme
    assert "https://github.com/MagicianDu/ml-research-loop/issues/1" in readme
    assert "安装是否成功" in feedback_text
    assert "MCP 是否能被客户端识别" in feedback_text
    assert "哪个环节最卡" in feedback_text
    assert "https://github.com/MagicianDu/ml-research-loop/issues/1" in feedback_text
    assert "Preview feedback" in template_text
    assert "contract_version" in template_text
