from typing import Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Object storage abstraction: local disk in dev, S3/R2/MinIO elsewhere."""

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Store an object."""
        ...

    def get_bytes(self, key: str) -> bytes:
        """Fetch an object. Raises KeyError if missing."""
        ...

    def exists(self, key: str) -> bool: ...

    def url_for(self, key: str) -> str:
        """Public (or long-lived presigned) GET URL for browsers."""
        ...

    def presign_get(self, key: str, expires_sec: int = 3600) -> str:
        """Short-lived GET URL for workers."""
        ...

    def presign_put(self, key: str, expires_sec: int = 3600) -> str:
        """Short-lived PUT URL for workers to upload results."""
        ...
