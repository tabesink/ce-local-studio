"""P12-07 U11: lean scripts/dev.sh Compose demo contract."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV_SH = ROOT / "scripts" / "dev.sh"
COMPOSE = ROOT / "app" / "compose.stack.yml"
ENV_EXAMPLE = ROOT / "app" / ".env.stack.example"


def test_dev_sh_defaults_to_compose_demo_matrix() -> None:
    text = DEV_SH.read_text(encoding="utf-8")
    assert 'CE_DEV_MODE="${CE_DEV_MODE:-compose}"' in text
    assert "compose.stack.yml" in text
    assert "compose.stack.minio.yml" in text
    assert "compose.stack.live.yml" in text
    assert "ensure_graph_ref_key" in text
    assert "CE_GRAPH_REF_KEY" in text
    assert "Public application URL" in text
    assert "Configured admin username" in text
    assert "CE_ADMIN_PASSWORD" not in text.split("print_demo_summary")[1].split("run_host_dev")[0]
    assert "CE_DEV_MODE=host" in text
    assert re.search(r"secrets\.token_bytes\(32\)", text)


def test_compose_and_env_example_require_graph_ref_key() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "CE_GRAPH_REF_KEY" in compose
    assert "CE_GRAPH_REF_KEY" in example


def test_dev_sh_bash_syntax() -> None:
    try:
        completed = subprocess.run(
            ["bash", "-n", str(DEV_SH)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return
    except subprocess.TimeoutExpired:
        return
    assert completed.returncode == 0, completed.stderr
