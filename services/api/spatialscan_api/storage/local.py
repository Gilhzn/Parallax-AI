"""Dev-only storage on the local filesystem.

Objects are served (GET) and accepted (PUT) through the API's ``/media/{key}``
routes, so "presigned" URLs are just plain URLs — good enough for local
development where the API and worker share a network.
"""

from __future__ import annotations

from pathlib import Path


class LocalDiskStorage:
    def __init__(self, root: str, public_base_url: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"invalid storage key: {key}")
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise KeyError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def url_for(self, key: str) -> str:
        return f"{self.public_base_url}/media/{key}"

    def presign_get(self, key: str, expires_sec: int = 3600) -> str:
        return self.url_for(key)

    def presign_put(self, key: str, expires_sec: int = 3600) -> str:
        return self.url_for(key)
