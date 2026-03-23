"""
FastAPI backend for the Photo Face Detection system.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

# Enable HEIC/HEIF support for iPhone photos
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    logger.info("HEIC/HEIF support enabled in API server")
except ImportError:
    logger.warning("pillow-heif not installed - HEIC images may not be browser-friendly")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Cluster, DatabaseManager, Face, FaceCorrection, Photo
from backend.redis_cache import RedisCache
from backend.sync_service import SyncService

load_dotenv()

app = FastAPI(
    title="Photo Face Detection API",
    description="API for browsing and managing your photo face library",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
cache = RedisCache()
sync_service = SyncService(db=db, cache=cache)

CACHE_DIR = Path("/tmp/photo_face_cache")
CACHE_DIR.mkdir(exist_ok=True)
THUMBNAIL_SIZE = (180, 180)
AUTO_SYNC_ON_STARTUP = os.getenv("AUTO_SYNC_ON_STARTUP", "true").lower() in {
    "1",
    "true",
    "yes",
}


class PhotoInfo(BaseModel):
    id: int
    file_path: str
    width: Optional[int]
    height: Optional[int]
    face_count: int


class FaceInfo(BaseModel):
    id: int
    photo_id: int
    top: int
    right: int
    bottom: int
    left: int
    confidence: float
    cluster_id: Optional[int]
    cluster_confidence: Optional[float]


class ClusterInfo(BaseModel):
    id: int
    name: Optional[str]
    face_count: int
    representative_face_id: Optional[int]
    is_locked: bool


class ClusterDetail(BaseModel):
    id: int
    name: Optional[str]
    face_count: int
    representative_face_id: Optional[int]
    is_locked: bool
    faces: List[dict]


class SyncStatus(BaseModel):
    status: str
    message: str
    path: Optional[str] = None
    reason: Optional[str] = None
    photos_seen: Optional[int] = None
    new_photos: Optional[int] = None
    changed_photos: Optional[int] = None
    processed_photos: Optional[int] = None
    pending_photos: Optional[int] = None
    faces_detected: Optional[int] = None
    pending_cluster_faces: Optional[int] = None
    cache_backend: Optional[str] = None
    updated_at: Optional[str] = None
    clustering: Optional[dict] = None


class Stats(BaseModel):
    total_photos: int
    processed_photos: int
    total_faces: int
    total_clusters: int
    named_clusters: int
    pending_cluster_faces: int
    unclustered_faces: int
    cache_backend: str
    sync_status: SyncStatus


def _invalidate_api_cache() -> None:
    cache.delete_prefix("api:")


def _get_cached_json(key: str):
    return cache.get_json(f"api:{key}")


def _set_cached_json(key: str, payload, ttl: int = 20) -> None:
    cache.set_json(f"api:{key}", payload, ttl=ttl)


@app.on_event("startup")
async def startup_event():
    if AUTO_SYNC_ON_STARTUP:
        sync_service.start_background_sync(reason="startup")


@app.get("/")
async def root():
    return {
        "message": "Photo Face Detection API",
        "version": "2.0.0",
        "cache_backend": cache.backend_name(),
        "endpoints": {
            "/stats": "Get system statistics",
            "/sync/status": "Get photo library sync status",
            "/sync/run": "Trigger a background library sync",
            "/clusters": "List face clusters",
            "/clusters/{cluster_id}": "Get detailed cluster information",
            "/clusters/{cluster_id}/name": "Rename a cluster",
            "/photos/{photo_id}/image": "Serve the original photo",
            "/faces/{face_id}/crop": "Serve a face thumbnail",
        },
    }


@app.get("/stats", response_model=Stats)
async def get_stats():
    cached = _get_cached_json("stats")
    if cached:
        return cached

    payload = {
        **db.get_stats(),
        "cache_backend": cache.backend_name(),
        "sync_status": sync_service.get_status(),
    }
    _set_cached_json("stats", payload, ttl=15)
    return payload


@app.get("/sync/status", response_model=SyncStatus)
async def get_sync_status():
    cached = _get_cached_json("sync:status")
    if cached:
        return cached

    payload = sync_service.get_status()
    _set_cached_json("sync:status", payload, ttl=5)
    return payload


@app.post("/sync/run")
async def run_sync(
    force_rescan: bool = Query(False, description="Reprocess already-known photos"),
    force_recluster: bool = Query(
        False, description="Force a clustering rebuild before returning"
    ),
):
    started = sync_service.start_background_sync(
        force_rescan=force_rescan,
        force_recluster=force_recluster,
        reason="api",
    )
    status = sync_service.get_status()
    return {
        "started": started,
        "status": status,
    }


@app.get("/clusters", response_model=List[ClusterInfo])
async def list_clusters(
    skip: int = Query(0, ge=0, description="Number of clusters to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum clusters to return"),
    min_faces: int = Query(1, ge=1, description="Minimum faces per cluster"),
    search: Optional[str] = Query(None, description="Search by cluster name or id"),
):
    cache_key = f"clusters:{skip}:{limit}:{min_faces}:{search or ''}"
    cached = _get_cached_json(cache_key)
    if cached:
        return cached

    session = db.get_session()
    try:
        query = session.query(Cluster).filter(Cluster.face_count >= min_faces)
        if search:
            search_value = search.strip()
            if search_value.isdigit():
                query = query.filter(
                    (Cluster.id == int(search_value)) | Cluster.name.like(f"%{search_value}%")
                )
            else:
                query = query.filter(Cluster.name.like(f"%{search_value}%"))
        query = query.order_by(Cluster.face_count.desc(), Cluster.updated_at.desc())
        clusters = query.offset(skip).limit(limit).all()
        payload = [
            {
                "id": cluster.id,
                "name": cluster.name,
                "face_count": cluster.face_count,
                "representative_face_id": cluster.representative_face_id,
                "is_locked": bool(cluster.is_locked or cluster.name),
            }
            for cluster in clusters
        ]
        _set_cached_json(cache_key, payload, ttl=15)
        return payload
    finally:
        session.close()


@app.get("/clusters/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: int):
    cache_key = f"cluster:{cluster_id}"
    cached = _get_cached_json(cache_key)
    if cached:
        return cached

    session = db.get_session()
    try:
        cluster = session.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        faces = (
            session.query(Face, Photo)
            .join(Photo, Photo.id == Face.photo_id)
            .filter(Face.cluster_id == cluster_id)
            .order_by(Photo.scanned_at.desc().nullslast(), Face.id.desc())
            .all()
        )

        payload = {
            "id": cluster.id,
            "name": cluster.name,
            "face_count": cluster.face_count,
            "representative_face_id": cluster.representative_face_id,
            "is_locked": bool(cluster.is_locked or cluster.name),
            "faces": [
                {
                    "id": face.id,
                    "photo_id": face.photo_id,
                    "photo_path": photo.file_path,
                    "top": face.top,
                    "right": face.right,
                    "bottom": face.bottom,
                    "left": face.left,
                    "confidence": face.confidence,
                    "cluster_confidence": face.cluster_confidence,
                }
                for face, photo in faces
            ],
        }
        _set_cached_json(cache_key, payload, ttl=15)
        return payload
    finally:
        session.close()


@app.put("/clusters/{cluster_id}/name")
async def update_cluster_name(
    cluster_id: int, name: str = Query(..., min_length=1, max_length=100)
):
    success = db.update_cluster_name(cluster_id, name.strip())
    if not success:
        raise HTTPException(status_code=404, detail="Cluster not found")
    _invalidate_api_cache()
    return {
        "message": "Cluster name updated successfully",
        "cluster_id": cluster_id,
        "name": name.strip(),
    }


@app.put("/clusters/{cluster_id}/representative/{face_id}")
async def set_representative_face(cluster_id: int, face_id: int):
    session = db.get_session()
    try:
        cluster = session.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        face = session.query(Face).filter_by(id=face_id, cluster_id=cluster_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found in this cluster")

        cluster.representative_face_id = face_id
        session.commit()
    finally:
        session.close()

    _invalidate_api_cache()
    return {
        "success": True,
        "cluster_id": cluster_id,
        "representative_face_id": face_id,
    }


@app.get("/clusters/by-name/{name}")
async def get_clusters_by_name(name: str):
    session = db.get_session()
    try:
        clusters = session.query(Cluster).filter_by(name=name).all()
        return {
            "name": name,
            "count": len(clusters),
            "clusters": [
                {
                    "id": cluster.id,
                    "face_count": cluster.face_count,
                    "representative_face_id": cluster.representative_face_id,
                    "is_locked": bool(cluster.is_locked or cluster.name),
                }
                for cluster in clusters
            ],
        }
    finally:
        session.close()


@app.get("/photos/{photo_id}", response_model=PhotoInfo)
async def get_photo_info(photo_id: int):
    session = db.get_session()
    try:
        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        return {
            "id": photo.id,
            "file_path": photo.file_path,
            "width": photo.width,
            "height": photo.height,
            "face_count": photo.face_count,
        }
    finally:
        session.close()


@app.get("/photos/{photo_id}/image")
async def get_photo_image(photo_id: int):
    session = db.get_session()
    try:
        from PIL import Image

        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        if not os.path.exists(photo.file_path):
            raise HTTPException(status_code=404, detail="Photo file not found on disk")

        extension = photo.file_path.lower().split(".")[-1]
        if extension in {"heic", "heif"}:
            try:
                image = Image.open(photo.file_path)
                output = io.BytesIO()
                if image.mode in {"RGBA", "LA", "P"}:
                    image = image.convert("RGB")
                image.save(output, format="JPEG", quality=90)
                output.seek(0)
                return StreamingResponse(output, media_type="image/jpeg")
            except Exception as exc:
                logger.error("Failed to convert HEIC image {}: {}", photo.file_path, exc)
                placeholder = Image.new("RGB", (800, 600), color=(128, 128, 128))
                output = io.BytesIO()
                placeholder.save(output, format="JPEG")
                output.seek(0)
                return StreamingResponse(output, media_type="image/jpeg")

        return FileResponse(photo.file_path)
    finally:
        session.close()


@app.post("/photos/{photo_id}/reveal")
async def reveal_photo_in_finder(photo_id: int):
    session = db.get_session()
    try:
        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        if not os.path.exists(photo.file_path):
            raise HTTPException(status_code=404, detail="Photo file not found on disk")
        file_path = photo.file_path
    finally:
        session.close()

    try:
        subprocess.run(["open", "-R", file_path], check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to reveal photo {} in Finder: {}", file_path, exc)
        raise HTTPException(status_code=500, detail="Could not reveal photo in Finder")

    return {
        "success": True,
        "photo_id": photo_id,
        "file_path": file_path,
    }


@app.get("/faces/{face_id}", response_model=FaceInfo)
async def get_face_info(face_id: int):
    session = db.get_session()
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")
        return {
            "id": face.id,
            "photo_id": face.photo_id,
            "top": face.top,
            "right": face.right,
            "bottom": face.bottom,
            "left": face.left,
            "confidence": face.confidence,
            "cluster_id": face.cluster_id,
            "cluster_confidence": face.cluster_confidence,
        }
    finally:
        session.close()


@app.get("/faces/{face_id}/crop")
async def get_face_crop(
    face_id: int,
    thumbnail: bool = Query(True, description="Generate a thumbnail for quick loading"),
):
    cache_suffix = "_thumb" if thumbnail else "_full"
    cache_file = CACHE_DIR / f"face_{face_id}{cache_suffix}.jpg"
    if cache_file.exists():
        return FileResponse(cache_file, media_type="image/jpeg")

    session = db.get_session()
    try:
        from PIL import Image

        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        photo = session.query(Photo).filter_by(id=face.photo_id).first()
        if not photo or not os.path.exists(photo.file_path):
            raise HTTPException(status_code=404, detail="Photo file not found")

        try:
            image = Image.open(photo.file_path)
            padding = 24
            left = max(0, face.left - padding)
            top = max(0, face.top - padding)
            right = min(image.width, face.right + padding)
            bottom = min(image.height, face.bottom + padding)
            face_image = image.crop((left, top, right, bottom))
            if thumbnail:
                face_image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            face_image.save(cache_file, format="JPEG", quality=86, optimize=True)
            return FileResponse(cache_file, media_type="image/jpeg")
        except Exception as exc:
            logger.error("Failed to crop face {}: {}", face_id, exc)
            placeholder = Image.new(
                "RGB",
                THUMBNAIL_SIZE if thumbnail else (200, 200),
                color=(128, 128, 128),
            )
            placeholder.save(cache_file, format="JPEG")
            return FileResponse(cache_file, media_type="image/jpeg")
    finally:
        session.close()


@app.post("/faces/{face_id}/exclude")
async def exclude_face(face_id: int):
    session = db.get_session()
    old_cluster_id = None
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if not correction:
            correction = FaceCorrection(face_id=face_id)
            session.add(correction)

        old_cluster_id = face.cluster_id
        correction.is_excluded = True
        correction.person_name = None
        correction.manual_cluster_id = None
        correction.excluded_from_cluster_id = old_cluster_id

        face.cluster_id = None
        face.needs_clustering = False
        face.cluster_confidence = 1.0
        session.commit()
    finally:
        session.close()

    if old_cluster_id:
        db.update_cluster_counts([old_cluster_id])
    _invalidate_api_cache()
    return {
        "success": True,
        "face_id": face_id,
        "excluded": True,
        "removed_from_cluster": old_cluster_id,
    }


@app.post("/faces/{face_id}/assign")
async def assign_face_to_person(
    face_id: int,
    person_name: str = Query(..., min_length=1),
    target_cluster_id: Optional[int] = None,
):
    session = db.get_session()
    old_cluster_id = None
    target_cluster = None
    person_name = person_name.strip()
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        if target_cluster_id is not None:
            target_cluster = session.query(Cluster).filter_by(id=target_cluster_id).first()
        if not target_cluster:
            target_cluster = (
                session.query(Cluster)
                .filter_by(name=person_name)
                .order_by(Cluster.face_count.desc())
                .first()
            )
        if not target_cluster:
            target_cluster = Cluster(name=person_name, is_locked=True)
            session.add(target_cluster)
            session.flush()

        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if not correction:
            correction = FaceCorrection(face_id=face_id)
            session.add(correction)

        correction.person_name = person_name
        correction.manual_cluster_id = target_cluster.id
        correction.is_excluded = False

        target_cluster.name = person_name
        target_cluster.is_locked = True

        old_cluster_id = face.cluster_id
        face.cluster_id = target_cluster.id
        face.needs_clustering = False
        face.cluster_confidence = 1.0

        session.commit()
    finally:
        session.close()

    update_ids = [cluster_id for cluster_id in {old_cluster_id, target_cluster.id} if cluster_id]
    if update_ids:
        db.update_cluster_counts(update_ids)
    _invalidate_api_cache()
    return {
        "success": True,
        "face_id": face_id,
        "person_name": person_name,
        "cluster_id": target_cluster.id,
        "moved_from": old_cluster_id,
    }


@app.delete("/faces/{face_id}/correction")
async def remove_correction(face_id: int):
    session = db.get_session()
    old_cluster_id = None
    removed = False
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if correction:
            session.delete(correction)
            removed = True

        old_cluster_id = face.cluster_id
        face.cluster_id = None
        face.needs_clustering = True
        face.cluster_confidence = None
        session.commit()
    finally:
        session.close()

    if old_cluster_id:
        db.update_cluster_counts([old_cluster_id])
    _invalidate_api_cache()
    return {
        "success": True,
        "face_id": face_id,
        "correction_removed": removed,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "cache_backend": cache.backend_name(),
        "sync_status": sync_service.get_status().get("status"),
    }


@app.post("/cache/clear")
async def clear_cache():
    import shutil

    try:
        file_count = len(list(CACHE_DIR.glob("*.jpg"))) if CACHE_DIR.exists() else 0
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(exist_ok=True)
        cache.delete_prefix("api:")
        return {
            "success": True,
            "message": f"Cleared {file_count} cached thumbnails",
            "files_deleted": file_count,
        }
    except Exception as exc:
        logger.error("Failed to clear cache: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/cache/stats")
async def get_cache_stats():
    try:
        files = list(CACHE_DIR.glob("*.jpg")) if CACHE_DIR.exists() else []
        total_size = sum(file_path.stat().st_size for file_path in files)
        return {
            "cache_dir": str(CACHE_DIR),
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "thumbnail_size": f"{THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]}",
            "backend": cache.backend_name(),
        }
    except Exception as exc:
        logger.error("Failed to read cache stats: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload_enabled = os.getenv("API_RELOAD", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    logger.info("Starting API server on {}:{} (reload={})", host, port, reload_enabled)
    uvicorn.run(
        "backend.api:app",
        host=host,
        port=port,
        log_level="info",
        reload=reload_enabled,
    )
