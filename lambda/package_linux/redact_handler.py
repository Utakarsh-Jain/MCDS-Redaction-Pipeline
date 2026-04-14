"""
API Gateway (Cognito) -> Lambda -> SageMaker -> redact -> Azure Blob.

Environment variables:
  SAGEMAKER_ENDPOINT_NAME  Real-time endpoint name
  AZURE_BLOB_SECRET_ARN    Secrets Manager ARN (JSON: connection_string or account_url+sas_token)
  AZURE_OUTPUT_CONTAINER   Blob container name
  BLOB_PREFIX              Optional key prefix (no leading/trailing slash)
  MAX_INPUT_CHARS          Optional max input length (default 100000)
  SECRET_CACHE_TTL_SEC     Optional secret cache TTL (default 300)
  SAGEMAKER_CONTENT_TYPE / SAGEMAKER_ACCEPT  Optional overrides
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from botocore.exceptions import ClientError

from lib.inference import invoke_sagemaker
from lib.redaction import parse_entities, redact_index_safe
from lib.storage import build_blob_client, get_azure_config, upload_redacted_blob

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SAGEMAKER_ENDPOINT_NAME = os.environ["SAGEMAKER_ENDPOINT_NAME"]
AZURE_SECRET_ARN = os.environ["AZURE_BLOB_SECRET_ARN"]
OUTPUT_CONTAINER = os.environ["AZURE_OUTPUT_CONTAINER"]
BLOB_PREFIX = os.environ.get("BLOB_PREFIX", "").strip().strip("/")
MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "100000"))


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _blob_key(user_sub: str | None, request_id: str | None) -> str:
    safe_id = user_sub or "anonymous"
    rid = request_id or uuid.uuid4().hex
    name = f"{safe_id}/{rid}.txt"
    return f"{BLOB_PREFIX}/{name}" if BLOB_PREFIX else name


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = getattr(context, "aws_request_id", None) if context else None
    logger.info("request_id=%s", request_id)

    try:
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("claims", {})
        )
        user_sub = claims.get("sub")
    except (TypeError, AttributeError):
        user_sub = None

    try:
        raw_body = event.get("body")
        if event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw_body or b"").decode("utf-8")
            payload = json.loads(raw or "{}")
        elif isinstance(raw_body, str):
            payload = json.loads(raw_body or "{}")
        else:
            payload = raw_body if isinstance(raw_body, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _response(400, {"error": "Invalid JSON body"})

    text = payload.get("text")
    if not text or not isinstance(text, str):
        return _response(400, {"error": "Field 'text' (string) is required"})

    if len(text) > MAX_INPUT_CHARS:
        return _response(
            413,
            {"error": "Input too large", "max_chars": MAX_INPUT_CHARS},
        )

    try:
        model_out = invoke_sagemaker(text, SAGEMAKER_ENDPOINT_NAME)
        entities = parse_entities(model_out)
        redacted = redact_index_safe(text, entities)
    except (ClientError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        logger.exception("Inference or redaction failed")
        return _response(502, {"error": "Inference failed", "detail": str(e)})

    try:
        azure_cfg = get_azure_config(AZURE_SECRET_ARN)
        bsc = build_blob_client(azure_cfg)
        blob_name = _blob_key(user_sub, request_id)
        upload_redacted_blob(
            bsc,
            OUTPUT_CONTAINER,
            blob_name,
            redacted.encode("utf-8"),
        )
    except Exception as e:
        logger.exception("Storage failed")
        return _response(502, {"error": "Storage failed", "detail": str(e)})

    return _response(
        200,
        {
            "blob_path": blob_name,
            "container": OUTPUT_CONTAINER,
            "entity_count": len(entities),
            "request_id": request_id,
        },
    )
