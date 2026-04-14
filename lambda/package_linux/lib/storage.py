"""Secrets Manager + Azure Blob Storage helpers."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient, ContentSettings
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_sm = None
_secret_cache: dict[str, Any] | None = None
_secret_fetched_at: float = 0.0


def _secrets_client():
    global _sm
    if _sm is None:
        _sm = boto3.client("secretsmanager")
    return _sm


def get_azure_config(secret_arn: str, *, ttl_sec: int | None = None) -> dict[str, str]:
    """Load Azure settings from Secrets Manager with optional in-memory TTL cache."""
    global _secret_cache, _secret_fetched_at
    ttl = ttl_sec if ttl_sec is not None else int(os.environ.get("SECRET_CACHE_TTL_SEC", "300"))
    now = time.time()
    if _secret_cache is not None and (now - _secret_fetched_at) < ttl:
        return _secret_cache

    try:
        resp = _secrets_client().get_secret_value(SecretId=secret_arn)
    except ClientError:
        logger.exception("Secrets Manager GetSecretValue failed")
        raise

    raw = resp.get("SecretString") or ""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("Secret must be a JSON object")
    _secret_cache = data
    _secret_fetched_at = now
    return data


def invalidate_secret_cache() -> None:
    global _secret_cache, _secret_fetched_at
    _secret_cache = None
    _secret_fetched_at = 0.0


def build_blob_client(azure_cfg: dict[str, str]) -> BlobServiceClient:
    cs = azure_cfg.get("connection_string")
    if cs:
        return BlobServiceClient.from_connection_string(cs)
    account_url = azure_cfg.get("account_url")
    sas = azure_cfg.get("sas_token")
    if account_url and sas:
        return BlobServiceClient(
            account_url=account_url.rstrip("/"),
            credential=sas.lstrip("?"),
        )
    raise ValueError("Azure secret must include connection_string or account_url + sas_token")


def upload_redacted_blob(
    blob_client: BlobServiceClient,
    container: str,
    blob_name: str,
    data: bytes,
    *,
    content_type: str = "text/plain; charset=utf-8",
) -> str:
    cnt = blob_client.get_container_client(container)
    blob = cnt.get_blob_client(blob_name)
    try:
        blob.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
    except AzureError:
        logger.exception("Azure upload failed for %s", blob_name)
        raise
    return blob_name
