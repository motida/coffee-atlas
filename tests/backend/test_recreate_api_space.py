"""Unit tests for the api-Space recreate helper's guard logic.

Only the pure, network-free pieces are exercised: which secrets are required and
the "refuse to recreate if any is missing locally" guard. The module imports
``huggingface_hub`` lazily (inside the destructive path), so it loads fine here
without that dependency installed.
"""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "deploy/huggingface/recreate_api_space.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("recreate_api_space", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def test_required_secrets_are_the_three_runtime_secrets():
    # The api Space's runtime secrets — drift here is exactly what breaks auth on
    # a recreate, so pin the set.
    assert set(mod.REQUIRED_SECRETS) == {"GEMINI_API_KEY", "DATABASE_URL", "JWT_SECRET"}


def test_missing_secrets_flags_absent_and_empty_values():
    secrets = {"GEMINI_API_KEY": "k", "DATABASE_URL": "", "JWT_SECRET": "j"}
    assert mod.missing_secrets(secrets) == ["DATABASE_URL"]


def test_missing_secrets_reports_in_declared_order():
    # Order follows REQUIRED_SECRETS, not dict insertion, so the error message is
    # stable regardless of how the mapping was built.
    secrets = {"JWT_SECRET": "", "DATABASE_URL": "", "GEMINI_API_KEY": ""}
    assert mod.missing_secrets(secrets) == ["GEMINI_API_KEY", "DATABASE_URL", "JWT_SECRET"]


def test_missing_secrets_empty_when_all_present():
    secrets = {"GEMINI_API_KEY": "k", "DATABASE_URL": "d", "JWT_SECRET": "j"}
    assert mod.missing_secrets(secrets) == []
