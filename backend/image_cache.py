"""
Helpers for face crop caching on local disk.
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger
from PIL import Image

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass


CACHE_DIR = Path(os.getenv("FACE_CACHE_DIR", "/tmp/photo_face_cache"))
CACHE_DIR.mkdir(exist_ok=True)
THUMBNAIL_SIZE = (180, 180)
FACE_PADDING = int(os.getenv("FACE_CROP_PADDING", "24"))


def get_face_cache_path(face_id: int, thumbnail: bool = True) -> Path:
    cache_suffix = "_thumb" if thumbnail else "_full"
    return CACHE_DIR / f"face_{face_id}{cache_suffix}.jpg"


def _prepare_face_crop(image: Image.Image, bounds, thumbnail: bool) -> Image.Image:
    top, right, bottom, left = bounds
    left = max(0, left - FACE_PADDING)
    top = max(0, top - FACE_PADDING)
    right = min(image.width, right + FACE_PADDING)
    bottom = min(image.height, bottom + FACE_PADDING)

    face_image = image.crop((left, top, right, bottom))
    if face_image.mode in {"RGBA", "LA", "P"}:
        face_image = face_image.convert("RGB")
    if thumbnail:
        face_image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    return face_image


def build_face_crop_cache(
    face_id: int,
    photo_path: str,
    bounds,
    thumbnail: bool = True,
) -> Path:
    cache_file = get_face_cache_path(face_id, thumbnail=thumbnail)
    if cache_file.exists():
        return cache_file

    with Image.open(photo_path) as image:
        face_image = _prepare_face_crop(image, bounds, thumbnail=thumbnail)
        face_image.save(cache_file, format="JPEG", quality=86, optimize=True)
    return cache_file


def warm_face_crop_cache(photo_path: str, faces: list[dict], thumbnail: bool = True) -> int:
    if not faces:
        return 0

    cached_count = 0
    with Image.open(photo_path) as image:
        for face in faces:
            cache_file = get_face_cache_path(face["id"], thumbnail=thumbnail)
            if cache_file.exists():
                continue
            try:
                face_image = _prepare_face_crop(
                    image,
                    (face["top"], face["right"], face["bottom"], face["left"]),
                    thumbnail=thumbnail,
                )
                face_image.save(cache_file, format="JPEG", quality=86, optimize=True)
                cached_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to warm crop cache for face {} from {}: {}",
                    face["id"],
                    photo_path,
                    exc,
                )
    return cached_count
