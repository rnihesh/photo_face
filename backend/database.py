"""
Database models and operations for the photo face detection system.

The schema is intentionally managed here so the existing SQLite database can be
upgraded in place without requiring Alembic for this project.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any, Iterable, Optional

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

Base = declarative_base()


class Photo(Base):
    """Stores metadata about each photo processed."""

    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    file_size = Column(Integer)
    file_hash = Column(String, index=True)
    width = Column(Integer)
    height = Column(Integer)
    modified_timestamp = Column(Float, index=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    scanned_at = Column(DateTime)
    processed = Column(Boolean, default=False, index=True)
    face_count = Column(Integer, default=0)

    faces = relationship("Face", back_populates="photo", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Photo(id={self.id}, path='{self.file_path}', faces={self.face_count})>"


class Face(Base):
    """Stores individual face detections and their embeddings."""

    __tablename__ = "faces"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False, index=True)
    top = Column(Integer)
    right = Column(Integer)
    bottom = Column(Integer)
    left = Column(Integer)
    embedding = Column(JSON, nullable=False)
    confidence = Column(Float, default=1.0)
    cluster_id = Column(Integer, ForeignKey("clusters.id"), index=True)
    needs_clustering = Column(Boolean, default=True, index=True)
    cluster_confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    photo = relationship("Photo", back_populates="faces")
    cluster = relationship("Cluster", back_populates="faces", foreign_keys=[cluster_id])

    def __repr__(self) -> str:
        return f"<Face(id={self.id}, photo_id={self.photo_id}, cluster_id={self.cluster_id})>"


class Cluster(Base):
    """Represents a cluster of similar faces."""

    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    face_count = Column(Integer, default=0)
    representative_face_id = Column(Integer)
    centroid = Column(JSON)
    is_locked = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_clustered_at = Column(DateTime)

    faces = relationship("Face", back_populates="cluster", foreign_keys=[Face.cluster_id])

    def __repr__(self) -> str:
        return f"<Cluster(id={self.id}, name='{self.name}', faces={self.face_count})>"


class ScanProgress(Base):
    """Tracks scanning progress for resumability and visibility."""

    __tablename__ = "scan_progress"

    id = Column(Integer, primary_key=True)
    directory = Column(String, nullable=False, index=True)
    last_scanned_path = Column(String)
    total_files_scanned = Column(Integer, default=0)
    total_faces_detected = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed = Column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<ScanProgress(dir='{self.directory}', files={self.total_files_scanned}, "
            f"completed={self.completed})>"
        )


class FaceCorrection(Base):
    """Tracks manual corrections and exclusions."""

    __tablename__ = "face_corrections"

    id = Column(Integer, primary_key=True)
    face_id = Column(
        Integer, ForeignKey("faces.id"), nullable=False, index=True, unique=True
    )
    manual_cluster_id = Column(Integer, ForeignKey("clusters.id"))
    person_name = Column(String, index=True)
    is_excluded = Column(Boolean, default=False)
    excluded_from_cluster_id = Column(Integer, ForeignKey("clusters.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<FaceCorrection(face_id={self.face_id}, person='{self.person_name}', "
            f"excluded={self.is_excluded})>"
        )


class SystemSetting(Base):
    """Key/value settings stored inside the project database."""

    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DatabaseManager:
    """Manages database connections, compatibility upgrades, and common queries."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.getenv("DATABASE_PATH", "./photo_face.db")

        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        self._run_migrations()

    def get_session(self):
        return self.Session()

    def _run_migrations(self) -> None:
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())

        if "photos" in existing_tables:
            self._ensure_column(
                inspector,
                "photos",
                "modified_timestamp",
                "modified_timestamp FLOAT",
            )
            self._ensure_column(
                inspector,
                "photos",
                "last_seen_at",
                "last_seen_at DATETIME",
            )

        if "faces" in existing_tables:
            self._ensure_column(
                inspector,
                "faces",
                "needs_clustering",
                "needs_clustering BOOLEAN DEFAULT 1",
            )
            self._ensure_column(
                inspector,
                "faces",
                "cluster_confidence",
                "cluster_confidence FLOAT",
            )

        if "clusters" in existing_tables:
            self._ensure_column(inspector, "clusters", "centroid", "centroid JSON")
            self._ensure_column(
                inspector,
                "clusters",
                "is_locked",
                "is_locked BOOLEAN DEFAULT 0",
            )
            self._ensure_column(
                inspector,
                "clusters",
                "last_clustered_at",
                "last_clustered_at DATETIME",
            )

        if "face_corrections" in existing_tables:
            self._ensure_column(
                inspector,
                "face_corrections",
                "excluded_from_cluster_id",
                "excluded_from_cluster_id INTEGER",
            )

        Base.metadata.create_all(self.engine)
        self._ensure_indexes()
        self._backfill_defaults()

    def _ensure_column(self, inspector, table: str, column: str, ddl: str) -> None:
        columns = {item["name"] for item in inspector.get_columns(table)}
        if column in columns:
            return
        with self.engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

    def _ensure_indexes(self) -> None:
        statements = [
            "CREATE INDEX IF NOT EXISTS ix_faces_needs_clustering ON faces (needs_clustering)",
            "CREATE INDEX IF NOT EXISTS ix_clusters_name ON clusters (name)",
            "CREATE INDEX IF NOT EXISTS ix_clusters_is_locked ON clusters (is_locked)",
            "CREATE INDEX IF NOT EXISTS ix_photos_last_seen_at ON photos (last_seen_at)",
            "CREATE INDEX IF NOT EXISTS ix_photos_modified_timestamp ON photos (modified_timestamp)",
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def _backfill_defaults(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE photos SET last_seen_at = COALESCE(last_seen_at, created_at, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "UPDATE faces SET needs_clustering = CASE "
                    "WHEN needs_clustering IS NULL AND cluster_id IS NULL THEN 1 "
                    "WHEN needs_clustering IS NULL THEN 0 "
                    "ELSE needs_clustering END"
                )
            )
            connection.execute(
                text(
                    "UPDATE clusters SET is_locked = CASE "
                    "WHEN is_locked IS NULL AND name IS NOT NULL THEN 1 "
                    "WHEN is_locked IS NULL THEN 0 "
                    "ELSE is_locked END"
                )
            )

    @staticmethod
    def _serialize_embedding(embedding: Any) -> list[float]:
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return [float(value) for value in embedding]

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        session = self.get_session()
        try:
            setting = session.get(SystemSetting, key)
            return setting.value if setting else default
        finally:
            session.close()

    def set_setting(self, key: str, value: str) -> None:
        session = self.get_session()
        try:
            setting = session.get(SystemSetting, key)
            if not setting:
                setting = SystemSetting(key=key, value=value)
                session.add(setting)
            else:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def get_photo_index(self) -> dict[str, dict[str, Any]]:
        session = self.get_session()
        try:
            photos = session.query(Photo).all()
            return {
                photo.file_path: {
                    "id": photo.id,
                    "file_size": photo.file_size,
                    "modified_timestamp": photo.modified_timestamp,
                    "processed": photo.processed,
                    "face_count": photo.face_count,
                }
                for photo in photos
            }
        finally:
            session.close()

    def upsert_photo(
        self,
        file_path: str,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        modified_timestamp: Optional[float] = None,
        force_reprocess: bool = False,
    ) -> tuple[int, str]:
        """Create or update a photo record and report its processing state."""

        session = self.get_session()
        try:
            now = datetime.utcnow()
            photo = session.query(Photo).filter_by(file_path=file_path).first()

            if not photo:
                photo = Photo(
                    file_path=file_path,
                    file_size=file_size,
                    file_hash=file_hash,
                    width=width,
                    height=height,
                    modified_timestamp=modified_timestamp,
                    last_seen_at=now,
                    processed=False,
                    face_count=0,
                )
                session.add(photo)
                session.commit()
                return photo.id, "new"

            previous_size = photo.file_size
            previous_mtime = photo.modified_timestamp

            photo.file_size = file_size
            if file_hash is not None:
                photo.file_hash = file_hash
            if width is not None:
                photo.width = width
            if height is not None:
                photo.height = height
            if modified_timestamp is not None:
                photo.modified_timestamp = modified_timestamp
            photo.last_seen_at = now

            if not photo.processed:
                changed = True
                state = "pending"
            else:
                changed = force_reprocess
                state = "changed" if force_reprocess else "unchanged"

            if not changed:
                size_changed = previous_size != file_size
                mtime_changed = not self._float_equals(previous_mtime, modified_timestamp)
                changed = size_changed or mtime_changed
                if changed:
                    state = "changed"

            if changed:
                photo.processed = False

            session.commit()
            return photo.id, state if changed else "unchanged"
        finally:
            session.close()

    @staticmethod
    def _float_equals(left: Optional[float], right: Optional[float], tolerance: float = 1e-6) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)

    def add_photo(
        self,
        file_path,
        file_size=None,
        file_hash=None,
        width=None,
        height=None,
        modified_timestamp=None,
    ):
        photo_id, _ = self.upsert_photo(
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            width=width,
            height=height,
            modified_timestamp=modified_timestamp,
        )
        return photo_id

    def reset_photo_faces(self, photo_id: int) -> int:
        """Delete all faces for a photo so it can be reprocessed safely."""

        session = self.get_session()
        try:
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if not photo:
                return 0
            deleted = len(photo.faces)
            for face in list(photo.faces):
                session.delete(face)
            photo.face_count = 0
            photo.processed = False
            session.commit()
            return deleted
        finally:
            session.close()

    def mark_photo_processed(
        self,
        photo_id: int,
        face_count: int = 0,
        file_hash: Optional[str] = None,
        modified_timestamp: Optional[float] = None,
    ) -> None:
        session = self.get_session()
        try:
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if not photo:
                return
            photo.processed = True
            photo.scanned_at = datetime.utcnow()
            photo.face_count = face_count
            if file_hash is not None:
                photo.file_hash = file_hash
            if modified_timestamp is not None:
                photo.modified_timestamp = modified_timestamp
            session.commit()
        finally:
            session.close()

    def add_face(
        self,
        photo_id,
        embedding,
        top,
        right,
        bottom,
        left,
        confidence=1.0,
        needs_clustering: bool = True,
    ):
        session = self.get_session()
        try:
            face = Face(
                photo_id=photo_id,
                embedding=self._serialize_embedding(embedding),
                top=top,
                right=right,
                bottom=bottom,
                left=left,
                confidence=confidence,
                needs_clustering=needs_clustering,
            )
            session.add(face)
            session.commit()
            return face.id
        finally:
            session.close()

    def save_photo_processing_result(
        self,
        photo_id: int,
        *,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        modified_timestamp: Optional[float] = None,
        detections: Optional[list[tuple[tuple[int, int, int, int], Any, float]]] = None,
    ) -> list[dict[str, int]]:
        """
        Persist all face detections for a photo in one transaction.

        This avoids the expensive one-face-per-commit path during large scans.
        """

        detections = detections or []
        session = self.get_session()
        try:
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if not photo:
                return []

            if file_size is not None:
                photo.file_size = file_size
            if file_hash is not None:
                photo.file_hash = file_hash
            if width is not None:
                photo.width = width
            if height is not None:
                photo.height = height
            if modified_timestamp is not None:
                photo.modified_timestamp = modified_timestamp

            faces = []
            for location, encoding, confidence in detections:
                top, right, bottom, left = location
                faces.append(
                    Face(
                        photo_id=photo_id,
                        embedding=self._serialize_embedding(encoding),
                        top=top,
                        right=right,
                        bottom=bottom,
                        left=left,
                        confidence=confidence,
                        needs_clustering=True,
                    )
                )

            if faces:
                session.add_all(faces)
                session.flush()

            photo.processed = True
            photo.scanned_at = datetime.utcnow()
            photo.face_count = len(faces)
            persisted_faces = [
                {
                    "id": face.id,
                    "top": face.top,
                    "right": face.right,
                    "bottom": face.bottom,
                    "left": face.left,
                }
                for face in faces
            ]
            session.commit()
            return persisted_faces
        finally:
            session.close()

    def get_unprocessed_photos(self, limit=None):
        session = self.get_session()
        try:
            query = session.query(Photo).filter_by(processed=False)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_all_face_embeddings(self, only_clusterable: bool = False):
        session = self.get_session()
        try:
            query = session.query(Face)
            if only_clusterable:
                query = query.filter(Face.cluster_id.is_(None))
            faces = query.all()
            return [(face.id, face.embedding) for face in faces]
        finally:
            session.close()

    def reset_clustering_state(self, clear_corrections: bool = True) -> dict[str, int]:
        """Remove clustering results while keeping scanned photos and face embeddings."""

        session = self.get_session()
        try:
            affected_faces = session.query(Face).count()
            removed_clusters = session.query(Cluster).count()
            removed_corrections = session.query(FaceCorrection).count() if clear_corrections else 0

            session.query(Face).update(
                {
                    "cluster_id": None,
                    "needs_clustering": True,
                    "cluster_confidence": None,
                },
                synchronize_session=False,
            )

            if clear_corrections:
                session.query(FaceCorrection).delete(synchronize_session=False)

            session.query(Cluster).delete(synchronize_session=False)
            session.query(SystemSetting).filter(
                SystemSetting.key == "clustering_algorithm_version"
            ).delete(synchronize_session=False)
            session.commit()

            return {
                "faces_reset": affected_faces,
                "clusters_removed": removed_clusters,
                "corrections_removed": removed_corrections,
            }
        finally:
            session.close()

    def set_faces_needs_clustering(
        self, face_ids: Iterable[int], needs_clustering: bool = True
    ) -> None:
        face_ids = list(face_ids)
        if not face_ids:
            return
        session = self.get_session()
        try:
            (
                session.query(Face)
                .filter(Face.id.in_(face_ids))
                .update({"needs_clustering": needs_clustering}, synchronize_session=False)
            )
            session.commit()
        finally:
            session.close()

    def create_cluster(
        self,
        name: Optional[str] = None,
        is_locked: bool = False,
        centroid: Optional[list[float]] = None,
    ) -> int:
        session = self.get_session()
        try:
            cluster = Cluster(
                name=name,
                is_locked=is_locked or bool(name),
                centroid=centroid,
                last_clustered_at=datetime.utcnow(),
            )
            session.add(cluster)
            session.commit()
            return cluster.id
        finally:
            session.close()

    def get_or_create_named_cluster(self, name: str) -> int:
        session = self.get_session()
        try:
            cluster = session.query(Cluster).filter_by(name=name).order_by(Cluster.face_count.desc()).first()
            if cluster:
                if not cluster.is_locked:
                    cluster.is_locked = True
                    session.commit()
                return cluster.id
            cluster = Cluster(name=name, is_locked=True, last_clustered_at=datetime.utcnow())
            session.add(cluster)
            session.commit()
            return cluster.id
        finally:
            session.close()

    def update_cluster_name(self, cluster_id, name):
        session = self.get_session()
        try:
            cluster = session.query(Cluster).filter_by(id=cluster_id).first()
            if cluster:
                cluster.name = name
                cluster.is_locked = True
                cluster.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        finally:
            session.close()

    def update_scan_progress(self, directory, last_path, files_scanned, faces_detected):
        session = self.get_session()
        try:
            progress = (
                session.query(ScanProgress)
                .filter_by(directory=directory, completed=False)
                .first()
            )
            if not progress:
                progress = ScanProgress(directory=directory)
                session.add(progress)

            progress.last_scanned_path = last_path
            progress.total_files_scanned = files_scanned
            progress.total_faces_detected = faces_detected
            progress.updated_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def mark_scan_complete(self, directory):
        session = self.get_session()
        try:
            progress = (
                session.query(ScanProgress)
                .filter_by(directory=directory, completed=False)
                .first()
            )
            if progress:
                progress.completed = True
                progress.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def update_cluster_counts(self, cluster_ids: Optional[Iterable[int]] = None):
        """Recompute face counts, centroids, and representative faces."""

        import numpy as np

        session = self.get_session()
        try:
            query = session.query(Cluster)
            if cluster_ids is not None:
                cluster_ids = list(cluster_ids)
                if not cluster_ids:
                    return
                query = query.filter(Cluster.id.in_(cluster_ids))

            clusters = query.all()

            for cluster in clusters:
                faces = session.query(Face).filter_by(cluster_id=cluster.id).all()
                cluster.face_count = len(faces)

                if not faces:
                    cluster.centroid = None
                    cluster.representative_face_id = None
                    continue

                matrix = np.array([face.embedding for face in faces], dtype=float)
                centroid = matrix.mean(axis=0)
                cluster.centroid = centroid.tolist()
                cluster.last_clustered_at = datetime.utcnow()

                distances = np.linalg.norm(matrix - centroid, axis=1)
                representative_index = int(np.argmin(distances))
                cluster.representative_face_id = faces[representative_index].id

            session.commit()
        finally:
            session.close()

    def get_clusters_with_faces(self):
        session = self.get_session()
        try:
            clusters = session.query(Cluster).filter(Cluster.face_count > 0).all()
            result = []
            for cluster in clusters:
                faces = session.query(Face).filter_by(cluster_id=cluster.id).all()
                result.append(
                    {
                        "id": cluster.id,
                        "name": cluster.name,
                        "face_count": cluster.face_count,
                        "faces": faces,
                    }
                )
            return result
        finally:
            session.close()

    def get_stats(self):
        session = self.get_session()
        try:
            total_photos = session.query(Photo).count()
            processed_photos = session.query(Photo).filter_by(processed=True).count()
            total_faces = session.query(Face).count()
            total_clusters = session.query(Cluster).filter(Cluster.face_count > 0).count()
            named_clusters = (
                session.query(Cluster)
                .filter(Cluster.name.isnot(None), Cluster.face_count > 0)
                .count()
            )
            pending_cluster_faces = (
                session.query(Face).filter(Face.needs_clustering.is_(True)).count()
            )
            unclustered_faces = (
                session.query(Face).filter(Face.cluster_id.is_(None)).count()
            )

            return {
                "total_photos": total_photos,
                "processed_photos": processed_photos,
                "total_faces": total_faces,
                "total_clusters": total_clusters,
                "named_clusters": named_clusters,
                "pending_cluster_faces": pending_cluster_faces,
                "unclustered_faces": unclustered_faces,
            }
        finally:
            session.close()


if __name__ == "__main__":
    db = DatabaseManager()
    print("Database created successfully!")
    print(f"Stats: {db.get_stats()}")
