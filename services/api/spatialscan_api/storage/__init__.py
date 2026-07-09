from ..config import Settings
from .base import Storage
from .local import LocalDiskStorage
from .s3 import S3Storage


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalDiskStorage(settings.local_storage_dir, settings.public_base_url)
    if settings.storage_backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
        )
    raise ValueError(f"unknown STORAGE_BACKEND '{settings.storage_backend}' (local|s3)")


__all__ = ["Storage", "LocalDiskStorage", "S3Storage", "build_storage"]
