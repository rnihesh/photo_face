"""
Photo library sync service.

Discovers new or changed photos, processes them, and triggers incremental
clustering only when the library actually changed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.clustering_service import ClusteringService
from backend.database import DatabaseManager
from backend.image_cache import warm_face_crop_cache
from backend.redis_cache import RedisCache

_worker_state = threading.local()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
    md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as handle:
            while chunk := handle.read(chunk_size):
                md5.update(chunk)
    except Exception as exc:
        logger.error("Failed to hash {}: {}", file_path, exc)
        return None
    return md5.hexdigest()


def _should_calculate_hash() -> bool:
    return os.getenv("ENABLE_FILE_HASH", "false").lower() in {"1", "true", "yes"}


def find_all_images(root_dir: str, extensions: list[str]) -> list[str]:
    image_files: list[str] = []
    root_path = Path(root_dir)
    if not root_path.exists():
        return image_files

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if _is_valid_image(file_path, extensions):
                image_files.append(file_path)
    return image_files


def _is_valid_image(file_path: str, extensions: list[str]) -> bool:
    basename = os.path.basename(file_path)
    if basename.startswith("._") or basename.startswith("."):
        return False
    return os.path.splitext(file_path)[1].lower() in extensions


def _resolve_scan_workers(total_files: int) -> int:
    configured = os.getenv("SCAN_WORKERS")
    if configured:
        try:
            value = int(configured)
            if value > 0:
                return min(value, max(total_files, 1))
        except ValueError:
            logger.warning("Invalid SCAN_WORKERS value '{}', using auto mode.", configured)

    cpu_count = os.cpu_count() or 4
    auto_workers = max(1, min(6, cpu_count))
    return min(auto_workers, max(total_files, 1))


def _should_prebuild_face_crops() -> bool:
    return os.getenv("PREBUILD_FACE_CROPS", "false").lower() in {"1", "true", "yes"}


def _get_thread_detector(model: str):
    detector = getattr(_worker_state, "detector", None)
    detector_model = getattr(_worker_state, "detector_model", None)
    if detector is not None and detector_model == model:
        return detector

    from backend.face_detector import FaceDetector

    detector = FaceDetector(model=model, use_gpu=True)
    _worker_state.detector = detector
    _worker_state.detector_model = model
    return detector


def _process_photo_file(item: dict, detection_model: str) -> dict:
    from backend.face_detector import get_image_dimensions

    file_path = item["file_path"]
    result = {
        **item,
        "width": None,
        "height": None,
        "file_hash": None,
        "detections": [],
        "error": None,
    }

    try:
        detector = _get_thread_detector(detection_model)
        width, height = get_image_dimensions(file_path)
        file_hash = calculate_file_hash(file_path) if _should_calculate_hash() else None
        locations, encodings, confidences = detector.detect_faces(file_path)

        result["width"] = width
        result["height"] = height
        result["file_hash"] = file_hash
        result["detections"] = list(zip(locations, encodings, confidences))
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


class SyncService:
    """Handles backend library sync and exposes status for the UI."""

    def __init__(self, db: DatabaseManager, cache: Optional[RedisCache] = None) -> None:
        self.db = db
        self.cache = cache or RedisCache()
        self.clustering_service = ClusteringService(db=self.db, cache=self.cache)
        self._status_key = "sync:status"
        self._lock_key = "sync:lock"
        self._thread_lock = threading.Lock()
        self._active_thread: Optional[threading.Thread] = None

    def get_status(self) -> dict:
        default = {
            "status": "idle",
            "message": "Waiting for the next sync.",
            "updated_at": _utc_now_iso(),
            "cache_backend": self.cache.backend_name(),
        }
        return self.cache.get_json(self._status_key, default=default)

    def start_background_sync(
        self,
        root_dir: Optional[str] = None,
        force_rescan: bool = False,
        force_recluster: bool = False,
        reason: str = "manual",
    ) -> bool:
        with self._thread_lock:
            if self._active_thread and self._active_thread.is_alive():
                return False

            thread = threading.Thread(
                target=self._background_worker,
                kwargs={
                    "root_dir": root_dir,
                    "force_rescan": force_rescan,
                    "force_recluster": force_recluster,
                    "reason": reason,
                },
                daemon=True,
            )
            self._active_thread = thread
            thread.start()
            return True

    def _background_worker(self, **kwargs) -> None:
        try:
            self.sync_library(**kwargs)
        except Exception:
            logger.exception("Background sync failed")
        finally:
            with self._thread_lock:
                self._active_thread = None

    def sync_library(
        self,
        root_dir: Optional[str] = None,
        force_rescan: bool = False,
        force_recluster: bool = False,
        reason: str = "manual",
    ) -> dict:
        root_dir = root_dir or os.getenv("PHOTOS_PATH")
        if not root_dir:
            status = {
                "status": "waiting",
                "message": "PHOTOS_PATH is not configured.",
                "path": None,
                "updated_at": _utc_now_iso(),
                "cache_backend": self.cache.backend_name(),
            }
            self._set_status(status)
            return status

        root_path = Path(root_dir)
        if not root_path.exists():
            status = {
                "status": "waiting",
                "message": "Photo drive is not available. Connect it and retry.",
                "path": str(root_path),
                "updated_at": _utc_now_iso(),
                "cache_backend": self.cache.backend_name(),
            }
            self._set_status(status)
            return status

        token = self.cache.acquire_lock(self._lock_key, ttl=60 * 60)
        if not token:
            status = self.get_status()
            status["message"] = "Sync is already running."
            return status

        try:
            return self._sync_locked(
                root_dir=str(root_path),
                force_rescan=force_rescan,
                force_recluster=force_recluster,
                reason=reason,
            )
        except Exception as exc:
            status = {
                "status": "error",
                "message": str(exc),
                "path": str(root_path),
                "updated_at": _utc_now_iso(),
                "cache_backend": self.cache.backend_name(),
            }
            self._set_status(status)
            raise
        finally:
            self.cache.release_lock(self._lock_key, token)

    def _sync_locked(
        self,
        root_dir: str,
        force_rescan: bool,
        force_recluster: bool,
        reason: str,
    ) -> dict:
        extensions = [
            value.strip().lower()
            for value in os.getenv(
                "IMAGE_EXTENSIONS",
                ".jpg,.jpeg,.png,.bmp,.tiff,.tif,.heic,.heif",
            ).split(",")
            if value.strip()
        ]
        detection_model = os.getenv("FACE_DETECTION_MODEL", "hog")
        image_files = find_all_images(root_dir, extensions)

        files_to_process: list[dict] = []
        new_photos = 0
        changed_photos = 0

        self._set_status(
            {
                "status": "discovering",
                "message": "Scanning photo library for new files.",
                "path": root_dir,
                "reason": reason,
                "photos_seen": len(image_files),
                "updated_at": _utc_now_iso(),
                "cache_backend": self.cache.backend_name(),
            }
        )

        for file_path in image_files:
            try:
                stat = os.stat(file_path)
            except OSError as exc:
                logger.warning("Skipping unreadable file {}: {}", file_path, exc)
                continue

            photo_id, status = self.db.upsert_photo(
                file_path=file_path,
                file_size=stat.st_size,
                modified_timestamp=stat.st_mtime,
                force_reprocess=force_rescan,
            )

            if status == "new":
                new_photos += 1
                files_to_process.append(
                    {
                        "photo_id": photo_id,
                        "file_path": file_path,
                        "file_size": stat.st_size,
                        "modified_timestamp": stat.st_mtime,
                    }
                )
                continue

            if status == "pending":
                files_to_process.append(
                    {
                        "photo_id": photo_id,
                        "file_path": file_path,
                        "file_size": stat.st_size,
                        "modified_timestamp": stat.st_mtime,
                    }
                )
                continue

            if status == "changed":
                changed_photos += 1
                self.db.reset_photo_faces(photo_id)
                files_to_process.append(
                    {
                        "photo_id": photo_id,
                        "file_path": file_path,
                        "file_size": stat.st_size,
                        "modified_timestamp": stat.st_mtime,
                    }
                )

        processed_photos = 0
        detected_faces = 0
        processing_errors = 0

        if files_to_process:
            worker_count = _resolve_scan_workers(len(files_to_process))
            logger.info(
                "Processing {} photo(s) with {} worker(s)",
                len(files_to_process),
                worker_count,
            )

            def persist_result(result: dict, completed_count: int) -> None:
                nonlocal processed_photos, detected_faces, processing_errors

                file_path = result["file_path"]
                if result.get("error"):
                    processing_errors += 1
                    logger.error("Failed to process {}: {}", file_path, result["error"])
                    return

                created_faces = self.db.save_photo_processing_result(
                    result["photo_id"],
                    file_size=result.get("file_size"),
                    file_hash=result.get("file_hash"),
                    width=result.get("width"),
                    height=result.get("height"),
                    modified_timestamp=result.get("modified_timestamp"),
                    detections=result.get("detections"),
                )
                face_count = len(created_faces)
                processed_photos += 1
                detected_faces += face_count

                if created_faces and _should_prebuild_face_crops():
                    try:
                        warm_face_crop_cache(file_path, created_faces, thumbnail=True)
                    except Exception as exc:
                        logger.warning(
                            "Failed to warm thumbnail cache for {}: {}",
                            file_path,
                            exc,
                        )

                self.db.update_scan_progress(
                    directory=root_dir,
                    last_path=file_path,
                    files_scanned=processed_photos,
                    faces_detected=detected_faces,
                )
                self._set_status(
                    {
                        "status": "processing",
                        "message": "Detecting faces in new photos.",
                        "path": root_dir,
                        "reason": reason,
                        "photos_seen": len(image_files),
                        "new_photos": new_photos,
                        "changed_photos": changed_photos,
                        "processed_photos": processed_photos,
                        "pending_photos": max(len(files_to_process) - completed_count, 0),
                        "faces_detected": detected_faces,
                        "updated_at": _utc_now_iso(),
                        "cache_backend": self.cache.backend_name(),
                    }
                )

            if worker_count == 1:
                for index, item in enumerate(files_to_process, start=1):
                    result = _process_photo_file(item, detection_model)
                    persist_result(result, index)
            else:
                with ThreadPoolExecutor(
                    max_workers=worker_count,
                    thread_name_prefix="photo-scan",
                ) as executor:
                    futures = [
                        executor.submit(_process_photo_file, item, detection_model)
                        for item in files_to_process
                    ]
                    for completed_count, future in enumerate(as_completed(futures), start=1):
                        persist_result(future.result(), completed_count)

        self.db.mark_scan_complete(root_dir)
        pending_faces = self.db.get_stats()["pending_cluster_faces"]
        should_cluster = (
            force_recluster
            or self.clustering_service.needs_rebuild()
            or processed_photos > 0
            or pending_faces > 0
        )

        clustering_summary = None
        if should_cluster:
            self._set_status(
                {
                    "status": "clustering",
                    "message": "Updating face clusters.",
                    "path": root_dir,
                    "reason": reason,
                    "photos_seen": len(image_files),
                    "new_photos": new_photos,
                    "changed_photos": changed_photos,
                    "processed_photos": processed_photos,
                    "faces_detected": detected_faces,
                    "pending_cluster_faces": pending_faces,
                    "updated_at": _utc_now_iso(),
                    "cache_backend": self.cache.backend_name(),
                }
            )
            clustering_summary = self.clustering_service.run(
                force_rebuild=force_recluster
            )

        summary = {
            "status": "completed",
            "message": (
                "Library synced successfully."
                if (processed_photos or clustering_summary)
                else "No new or changed photos were found."
            ),
            "path": root_dir,
            "reason": reason,
            "photos_seen": len(image_files),
            "new_photos": new_photos,
            "changed_photos": changed_photos,
            "processed_photos": processed_photos,
            "faces_detected": detected_faces,
            "processing_errors": processing_errors,
            "clustering": clustering_summary,
            "updated_at": _utc_now_iso(),
            "cache_backend": self.cache.backend_name(),
        }
        self._set_status(summary)
        return summary

    def _set_status(self, payload: dict) -> None:
        self.cache.set_json(self._status_key, payload, ttl=60 * 60 * 24)
        self.cache.delete_prefix("api:stats")
        self.cache.delete_prefix("api:sync")
