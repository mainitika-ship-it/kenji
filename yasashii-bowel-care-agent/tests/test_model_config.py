from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from model_config import (
    DEFAULT_AWS_REGION,
    DEFAULT_BEDROCK_MODEL_ID,
    resolve_bedrock_settings,
)


def test_defaults_are_explicit_and_stable(monkeypatch):
    for name in (
        "YASASHII_BEDROCK_MODEL_ID",
        "YASASHII_AWS_REGION",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = resolve_bedrock_settings()
    assert settings.model_id == DEFAULT_BEDROCK_MODEL_ID
    assert settings.region_name == DEFAULT_AWS_REGION


def test_project_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("YASASHII_BEDROCK_MODEL_ID", "example.model")
    monkeypatch.setenv("YASASHII_AWS_REGION", "ap-northeast-1")

    settings = resolve_bedrock_settings()
    assert settings.model_id == "example.model"
    assert settings.region_name == "ap-northeast-1"


def test_cli_values_have_highest_precedence(monkeypatch):
    monkeypatch.setenv("YASASHII_BEDROCK_MODEL_ID", "environment.model")
    monkeypatch.setenv("YASASHII_AWS_REGION", "ap-northeast-1")

    settings = resolve_bedrock_settings("cli.model", "us-west-2")
    assert settings.model_id == "cli.model"
    assert settings.region_name == "us-west-2"
