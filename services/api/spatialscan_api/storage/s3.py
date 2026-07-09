"""S3-compatible storage: AWS S3, Cloudflare R2, or MinIO via ``endpoint_url``.

Credentials come from the standard AWS env vars / credential chain
(AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


class S3Storage:
    def __init__(self, bucket: str, endpoint_url: str | None = None, region: str = "auto"):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise KeyError(key) from exc
            raise
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def url_for(self, key: str) -> str:
        # Browser-facing URL. 24h presign keeps buckets private by default;
        # front with a CDN/public bucket policy in production if preferred.
        return self.presign_get(key, expires_sec=24 * 3600)

    def presign_get(self, key: str, expires_sec: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_sec
        )

    def presign_put(self, key: str, expires_sec: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_sec
        )
