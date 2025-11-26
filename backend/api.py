"""
FastAPI backend for the Photo Face Detection system.
Provides REST API endpoints for the React frontend.
"""

import os
import sys
from typing import List, Optional
from functools import lru_cache
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from loguru import logger
from pathlib import Path

# Enable HEIC/HEIF support for iPhone photos
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    logger.info("HEIC/HEIF support enabled in API server")
except ImportError:
    logger.warning("pillow-heif not installed - HEIC images won't be supported in API")

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Photo Face Detection API",
    description="API for browsing and managing face collections from photos",
    version="1.0.0",
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = DatabaseManager()

# Cache directory for thumbnails
CACHE_DIR = Path("/tmp/photo_face_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Thumbnail size for fast loading
THUMBNAIL_SIZE = (150, 150)


# Pydantic models for API responses
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


class ClusterInfo(BaseModel):
    id: int
    name: Optional[str]
    face_count: int
    representative_face_id: Optional[int]


class ClusterDetail(BaseModel):
    id: int
    name: Optional[str]
    face_count: int
    faces: List[dict]  # List of face info with photo paths


class Stats(BaseModel):
    total_photos: int
    processed_photos: int
    total_faces: int
    total_clusters: int
    named_clusters: int


# API Endpoints


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Photo Face Detection API",
        "version": "1.0.0",
        "endpoints": {
            "/stats": "Get system statistics",
            "/clusters": "List all face clusters",
            "/clusters/{cluster_id}": "Get detailed cluster information",
            "/clusters/{cluster_id}/name": "Update cluster name",
            "/photos/{photo_id}": "Get photo information",
            "/photos/{photo_id}/image": "Get actual photo file",
            "/faces/{face_id}": "Get face information",
        },
    }


@app.get("/stats", response_model=Stats)
async def get_stats():
    """Get overall system statistics."""
    stats = db.get_stats()
    return Stats(**stats)


@app.get("/clusters", response_model=List[ClusterInfo])
async def list_clusters(
    skip: int = Query(0, ge=0, description="Number of clusters to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of clusters to return"
    ),
    min_faces: int = Query(1, ge=1, description="Minimum faces per cluster"),
):
    """List all face clusters with pagination."""
    session = db.get_session()
    try:
        from backend.database import Cluster

        query = session.query(Cluster).filter(Cluster.face_count >= min_faces)
        query = query.order_by(Cluster.face_count.desc())
        query = query.offset(skip).limit(limit)

        clusters = query.all()

        return [
            ClusterInfo(
                id=cluster.id,
                name=cluster.name,
                face_count=cluster.face_count,
                representative_face_id=cluster.representative_face_id,
            )
            for cluster in clusters
        ]
    finally:
        session.close()


@app.get("/clusters/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: int):
    """Get detailed information about a specific cluster."""
    session = db.get_session()
    try:
        from backend.database import Cluster, Face, Photo

        cluster = session.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        # Get all faces in this cluster
        faces = session.query(Face).filter_by(cluster_id=cluster_id).all()

        face_list = []
        for face in faces:
            photo = session.query(Photo).filter_by(id=face.photo_id).first()
            face_list.append(
                {
                    "id": face.id,
                    "photo_id": face.photo_id,
                    "photo_path": photo.file_path if photo else None,
                    "top": face.top,
                    "right": face.right,
                    "bottom": face.bottom,
                    "left": face.left,
                    "confidence": face.confidence,
                }
            )

        return ClusterDetail(
            id=cluster.id,
            name=cluster.name,
            face_count=cluster.face_count,
            faces=face_list,
        )
    finally:
        session.close()


@app.put("/clusters/{cluster_id}/name")
async def update_cluster_name(
    cluster_id: int, name: str = Query(..., min_length=1, max_length=100)
):
    """Update the name of a cluster (assign person's name)."""
    success = db.update_cluster_name(cluster_id, name)
    if not success:
        raise HTTPException(status_code=404, detail="Cluster not found")

    return {
        "message": "Cluster name updated successfully",
        "cluster_id": cluster_id,
        "name": name,
    }


@app.get("/photos/{photo_id}", response_model=PhotoInfo)
async def get_photo_info(photo_id: int):
    """Get information about a photo."""
    session = db.get_session()
    try:
        from backend.database import Photo

        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        return PhotoInfo(
            id=photo.id,
            file_path=photo.file_path,
            width=photo.width,
            height=photo.height,
            face_count=photo.face_count,
        )
    finally:
        session.close()


@app.get("/photos/{photo_id}/image")
async def get_photo_image(photo_id: int):
    """Serve the actual photo file (converts HEIC to JPEG for browser compatibility)."""
    session = db.get_session()
    try:
        from backend.database import Photo
        from PIL import Image
        import io
        from fastapi.responses import StreamingResponse

        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        if not os.path.exists(photo.file_path):
            raise HTTPException(status_code=404, detail="Photo file not found on disk")

        # Check if it's a HEIC/HEIF file that needs conversion
        file_ext = photo.file_path.lower().split(".")[-1]
        if file_ext in ["heic", "heif"]:
            try:
                # Convert HEIC to JPEG for browser compatibility
                img = Image.open(photo.file_path)
                img_byte_arr = io.BytesIO()
                # Convert to RGB if necessary (HEIC can be RGBA)
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(img_byte_arr, format="JPEG", quality=90)
                img_byte_arr.seek(0)
                return StreamingResponse(img_byte_arr, media_type="image/jpeg")
            except Exception as e:
                logger.error(f"Error converting HEIC image {photo.file_path}: {e}")
                # Return placeholder on error
                placeholder = Image.new("RGB", (800, 600), color=(128, 128, 128))
                img_byte_arr = io.BytesIO()
                placeholder.save(img_byte_arr, format="JPEG")
                img_byte_arr.seek(0)
                return StreamingResponse(img_byte_arr, media_type="image/jpeg")
        else:
            # For JPG/PNG, serve directly
            return FileResponse(photo.file_path)
    finally:
        session.close()


@app.get("/faces/{face_id}", response_model=FaceInfo)
async def get_face_info(face_id: int):
    """Get information about a detected face."""
    session = db.get_session()
    try:
        from backend.database import Face

        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        return FaceInfo(
            id=face.id,
            photo_id=face.photo_id,
            top=face.top,
            right=face.right,
            bottom=face.bottom,
            left=face.left,
            confidence=face.confidence,
            cluster_id=face.cluster_id,
        )
    finally:
        session.close()


@app.get("/faces/{face_id}/crop")
async def get_face_crop(
    face_id: int,
    thumbnail: bool = Query(
        True, description="Generate small thumbnail for fast loading"
    ),
):
    """Get a cropped image of the detected face with caching and thumbnail support."""

    # Check cache first
    cache_suffix = "_thumb" if thumbnail else "_full"
    cache_file = CACHE_DIR / f"face_{face_id}{cache_suffix}.jpg"

    if cache_file.exists():
        # Serve from cache - FAST!
        return FileResponse(cache_file, media_type="image/jpeg")

    session = db.get_session()
    try:
        from backend.database import Face, Photo
        from PIL import Image
        import io

        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        photo = session.query(Photo).filter_by(id=face.photo_id).first()
        if not photo or not os.path.exists(photo.file_path):
            raise HTTPException(status_code=404, detail="Photo file not found")

        try:
            # Load and crop image
            img = Image.open(photo.file_path)

            # Crop face region (with some padding)
            padding = 20
            left = max(0, face.left - padding)
            top = max(0, face.top - padding)
            right = min(img.width, face.right + padding)
            bottom = min(img.height, face.bottom + padding)

            face_img = img.crop((left, top, right, bottom))

            # Generate thumbnail for faster loading
            if thumbnail:
                face_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Save to cache for next time
            face_img.save(cache_file, format="JPEG", quality=85, optimize=True)

            # Return cached file
            return FileResponse(cache_file, media_type="image/jpeg")

        except Exception as e:
            logger.error(f"Error loading image {photo.file_path}: {e}")
            # Return a placeholder gray image instead of failing
            placeholder = Image.new(
                "RGB",
                THUMBNAIL_SIZE if thumbnail else (200, 200),
                color=(128, 128, 128),
            )
            placeholder.save(cache_file, format="JPEG")
            return FileResponse(cache_file, media_type="image/jpeg")
    finally:
        session.close()


# ==================== Manual Correction Endpoints ====================


@app.post("/faces/{face_id}/exclude")
async def exclude_face(face_id: int):
    """Mark a face as 'not this person' - will be excluded in future clusterings."""
    from backend.database import Face, FaceCorrection

    session = db.get_session()
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        # Create or update correction
        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if not correction:
            correction = FaceCorrection(face_id=face_id)
            session.add(correction)

        correction.is_excluded = True
        correction.person_name = None
        correction.manual_cluster_id = None

        # Remove from current cluster
        old_cluster_id = face.cluster_id
        face.cluster_id = None

        session.commit()

        return {
            "success": True,
            "face_id": face_id,
            "excluded": True,
            "removed_from_cluster": old_cluster_id,
        }
    finally:
        session.close()


@app.post("/faces/{face_id}/assign")
async def assign_face_to_person(
    face_id: int, person_name: str = Query(...), target_cluster_id: Optional[int] = None
):
    """
    Manually assign a face to a person.
    System will learn and apply this in future clusterings.
    """
    from backend.database import Face, Cluster, FaceCorrection

    session = db.get_session()
    try:
        face = session.query(Face).filter_by(id=face_id).first()
        if not face:
            raise HTTPException(status_code=404, detail="Face not found")

        # Find or use target cluster
        if target_cluster_id:
            cluster = session.query(Cluster).filter_by(id=target_cluster_id).first()
        else:
            # Find cluster by name
            cluster = session.query(Cluster).filter_by(name=person_name).first()

        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        # Create or update correction (this is the learning data)
        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if not correction:
            correction = FaceCorrection(face_id=face_id)
            session.add(correction)

        correction.person_name = person_name
        correction.manual_cluster_id = cluster.id
        correction.is_excluded = False

        # Apply immediately
        old_cluster_id = face.cluster_id
        face.cluster_id = cluster.id
        cluster.name = person_name  # Ensure cluster has the name

        session.commit()

        return {
            "success": True,
            "face_id": face_id,
            "person_name": person_name,
            "cluster_id": cluster.id,
            "moved_from": old_cluster_id,
        }
    finally:
        session.close()


@app.delete("/faces/{face_id}/correction")
async def remove_correction(face_id: int):
    """Remove manual correction - let auto-clustering decide."""
    from backend.database import FaceCorrection

    session = db.get_session()
    try:
        correction = session.query(FaceCorrection).filter_by(face_id=face_id).first()
        if correction:
            session.delete(correction)
            session.commit()
            return {"success": True, "face_id": face_id, "correction_removed": True}
        return {"success": True, "face_id": face_id, "correction_removed": False}
    finally:
        session.close()


@app.put("/clusters/{cluster_id}/representative/{face_id}")
async def set_representative_face(cluster_id: int, face_id: int):
    """Set the representative (key) photo for a cluster."""
    from backend.database import Face, Cluster

    session = db.get_session()
    try:
        cluster = session.query(Cluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        face = session.query(Face).filter_by(id=face_id, cluster_id=cluster_id).first()
        if not face:
            raise HTTPException(
                status_code=404, detail="Face not found in this cluster"
            )

        cluster.representative_face_id = face_id
        session.commit()

        return {
            "success": True,
            "cluster_id": cluster_id,
            "representative_face_id": face_id,
        }
    finally:
        session.close()


@app.get("/clusters/by-name/{name}")
async def get_clusters_by_name(name: str):
    """Get all clusters with the same name (for auto-merge detection)."""
    from backend.database import Cluster

    session = db.get_session()
    try:
        clusters = session.query(Cluster).filter_by(name=name).all()
        return {
            "name": name,
            "count": len(clusters),
            "clusters": [
                {
                    "id": c.id,
                    "face_count": c.face_count,
                    "representative_face_id": c.representative_face_id,
                }
                for c in clusters
            ],
        }
    finally:
        session.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "database": "connected"}


@app.post("/cache/clear")
async def clear_cache():
    """Clear the thumbnail cache to free up space."""
    import shutil

    try:
        if CACHE_DIR.exists():
            # Count files before deletion
            file_count = len(list(CACHE_DIR.glob("*.jpg")))
            # Clear cache
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(exist_ok=True)
            return {
                "success": True,
                "message": f"Cleared {file_count} cached thumbnails",
                "files_deleted": file_count,
            }
        return {
            "success": True,
            "message": "Cache was already empty",
            "files_deleted": 0,
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    try:
        if CACHE_DIR.exists():
            files = list(CACHE_DIR.glob("*.jpg"))
            total_size = sum(f.stat().st_size for f in files)
            return {
                "cache_dir": str(CACHE_DIR),
                "file_count": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "thumbnail_size": f"{THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]}",
            }
        return {"cache_dir": str(CACHE_DIR), "file_count": 0, "total_size_mb": 0}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    logger.info(f"Starting API server on {host}:{port} with auto-reload")
    # Use import string for reload to work
    uvicorn.run("backend.api:app", host=host, port=port, log_level="info", reload=True)
