"""SageMaker real-time endpoint invocation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_runtime = None


def _client():
    global _runtime
    if _runtime is None:
        _runtime = boto3.client("sagemaker-runtime")
    return _runtime


def invoke_sagemaker(
    text: str,
    endpoint_name: str,
    *,
    max_length: int | None = None,
    content_type: str | None = None,
    accept: str | None = None,
) -> dict[str, Any]:
    ct = content_type or os.environ.get("SAGEMAKER_CONTENT_TYPE", "application/json")
    ac = accept or os.environ.get("SAGEMAKER_ACCEPT", "application/json")
    body = json.dumps({"text": text, "max_length": max_length})

    try:
        response = _client().invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType=ct,
            Accept=ac,
            Body=body.encode("utf-8"),
        )
    except ClientError:
        logger.exception("SageMaker invoke failed for endpoint %s", endpoint_name)
        raise

    payload = response["Body"].read().decode("utf-8")
    return json.loads(payload)
