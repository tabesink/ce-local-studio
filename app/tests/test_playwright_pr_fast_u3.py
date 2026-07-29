"""P12-07 U3: named PR-fast Playwright matrix contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "app" / "client"
E2E = CLIENT / "tests" / "e2e"
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"
PACKAGE = CLIENT / "package.json"


def test_pr_fast_specs_and_scripts_exist() -> None:
    required = [
        "auth-csrf-bfcache.spec.ts",
        "isolation-bfcache.spec.ts",
        "graph-workbench.spec.ts",
        "settings-domains.spec.ts",
        "m11-open-panel.spec.ts",
    ]
    for name in required:
        path = E2E / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "@pr-fast" in text, name

    package = PACKAGE.read_text(encoding="utf-8")
    assert "test:e2e:pr-fast" in package
    assert "--grep @pr-fast" in package
    assert "test:e2e:release" in package


def test_named_playwright_ci_job_exists() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "verify-playwright-pr-fast" in workflow
    assert "test:e2e:pr-fast" in workflow
    assert "playwright" in workflow.lower()


def test_gitignore_covers_client_e2e_artifacts() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "app/client/tests/e2e/artifacts/" in gitignore
    assert "app/client/test-results/" in gitignore


def test_seed_create_sends_extraction_profile() -> None:
    seed = (E2E / "helpers" / "stack-seed.ts").read_text(encoding="utf-8")
    assert "graphExtractionProfileId" in seed
    assert "doc_pump_manual.pdf" in seed
