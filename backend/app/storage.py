"""Optional S3 storage for generated media.

When S3_BUCKET is set, finished videos, captions, scene thumbnails and illustrations are uploaded under
files/projects/<id>/… and the API returns public URLs built from MEDIA_BASE_URL (a CloudFront distribution in front of
the bucket). Without S3_BUCKET everything stays on local disk and is served from /media as before.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
from pathlib import Path

BUCKET = os.environ.get("S3_BUCKET")
PREFIX = os.environ.get("S3_PREFIX", "files")
BASE_URL = (os.environ.get("MEDIA_BASE_URL") or "").rstrip("/")
_client = None


def enabled() -> bool:
    return bool(BUCKET and BASE_URL)


def _s3():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _client


def _key(project_id: str, name: str) -> str:
    return f"{PREFIX}/projects/{project_id}/{name}"


def public_url(project_id: str, name: str) -> str:
    return f"{BASE_URL}/{_key(project_id, name)}"


def upload_sync(path: Path, project_id: str, name: str | None = None) -> str:
    name = name or path.name
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    cache = "public, max-age=31536000, immutable" if path.suffix in (".mp4", ".png", ".mp3") else "public, max-age=300"
    _s3().upload_file(str(path), BUCKET, _key(project_id, name), ExtraArgs={"ContentType": ctype, "CacheControl": cache})
    return public_url(project_id, name)


async def upload(path: Path, project_id: str, name: str | None = None) -> str:
    return await asyncio.to_thread(upload_sync, path, project_id, name)


def delete_project_sync(project_id: str) -> None:
    s3 = _s3()
    prefix = f"{PREFIX}/projects/{project_id}/"
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    keys = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
    if keys:
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys})
