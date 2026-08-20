from __future__ import annotations

import argparse
import json

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from model_config import resolve_bedrock_settings


def _extract_text(response: dict) -> str:
    output = response.get("output", {})
    message = output.get("message", {})
    for block in message.get("content", []):
        if isinstance(block, dict) and "text" in block:
            return str(block["text"]).strip()
    return ""


def run_preflight(model_id: str | None = None, region_name: str | None = None) -> dict:
    """Verify AWS credentials and make one tiny Bedrock Nova request.

    The function intentionally does not return the AWS account ID or ARN so the
    preflight output can be safely shown in screenshots and demo recordings.
    """
    settings = resolve_bedrock_settings(model_id, region_name)
    result = {
        "credentials_ok": False,
        "bedrock_ok": False,
        "model_id": settings.model_id,
        "region": settings.region_name,
        "response": "",
    }

    try:
        boto3.client("sts", region_name=settings.region_name).get_caller_identity()
        result["credentials_ok"] = True

        client = boto3.client("bedrock-runtime", region_name=settings.region_name)
        response = client.converse(
            modelId=settings.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Reply with exactly READY"}],
                }
            ],
            inferenceConfig={"maxTokens": 16, "temperature": 0.0},
        )
        result["response"] = _extract_text(response)
        result["bedrock_ok"] = bool(result["response"])
        return result
    except (NoCredentialsError, BotoCoreError, ClientError) as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check AWS credentials and Amazon Bedrock Nova access."
    )
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    result = run_preflight(args.model_id, args.region)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["credentials_ok"] and result["bedrock_ok"] else 1)


if __name__ == "__main__":
    main()
