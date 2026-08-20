from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-lite-v1:0"
DEFAULT_AWS_REGION = "us-east-1"


@dataclass(frozen=True)
class BedrockSettings:
    model_id: str
    region_name: str


def resolve_bedrock_settings(
    model_id: str | None = None,
    region_name: str | None = None,
) -> BedrockSettings:
    """Resolve the Bedrock model and region without reading any secrets.

    Precedence is CLI argument -> environment variable -> safe project default.
    Credentials are intentionally left to the normal AWS SDK credential chain.
    """

    resolved_model = (
        model_id
        or os.environ.get("YASASHII_BEDROCK_MODEL_ID")
        or DEFAULT_BEDROCK_MODEL_ID
    ).strip()
    resolved_region = (
        region_name
        or os.environ.get("YASASHII_AWS_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_AWS_REGION
    ).strip()

    if not resolved_model:
        raise ValueError("Bedrock model ID must not be blank")
    if not resolved_region:
        raise ValueError("AWS region must not be blank")

    return BedrockSettings(model_id=resolved_model, region_name=resolved_region)
