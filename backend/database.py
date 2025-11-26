"""
Database models and operations for the photo face detection system.
Stores face embeddings, photo metadata, and clustering results.
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    LargeBinary,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class Photo(Base):
    """Stores metadata about each photo processed."""

    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    file_size = Column(Integer)
    file_hash = Column(String, index=True)  # MD5 hash for duplicate detection
    width = Column(Integer)
    height = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    scanned_at = Column(DateTime)
    processed = Column(Boolean, default=False, index=True)
    face_count = Column(Integer, default=0)

    # Relationship to faces detected in this photo
    faces = relationship("Face", back_populates="photo", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Photo(id={self.id}, path='{self.file_path}', faces={self.face_count})>"
        )


class Face(Base):
    """Stores individual face detections and their embeddings."""

    __tablename__ = "faces"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False, index=True)

    # Bounding box coordinates
    top = Column(Integer)
    right = Column(Integer)
    bottom = Column(Integer)
    left = Column(Integer)

    # Face embedding (128-dimensional vector stored as JSON)
    embedding = Column(JSON, nullable=False)

    # Confidence score from detection
    confidence = Column(Float, default=1.0)

    # Clustering information
    cluster_id = Column(Integer, ForeignKey("clusters.id"), index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    photo = relationship("Photo", back_populates="faces")
    cluster = relationship("Cluster", back_populates="faces")

    def __repr__(self):
        return f"<Face(id={self.id}, photo_id={self.photo_id}, cluster_id={self.cluster_id})>"


class Cluster(Base):
    """Represents a cluster of similar faces (likely the same person)."""

    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True)
    name = Column(String)  # User-assigned name for this person
    face_count = Column(Integer, default=0)

    # Representative face for this cluster (for thumbnails)
    representative_face_id = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    faces = relationship(
        "Face", back_populates="cluster", foreign_keys="Face.cluster_id"
    )

    def __repr__(self):
        return f"<Cluster(id={self.id}, name='{self.name}', faces={self.face_count})>"


class ScanProgress(Base):
    """Tracks scanning progress for resumability."""

    __tablename__ = "scan_progress"

    id = Column(Integer, primary_key=True)
    directory = Column(String, nullable=False, index=True)
    last_scanned_path = Column(String)
    total_files_scanned = Column(Integer, default=0)
    total_faces_detected = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed = Column(Boolean, default=False)

    def __repr__(self):
        return f"<ScanProgress(dir='{self.directory}', files={self.total_files_scanned}, completed={self.completed})>"


class FaceCorrection(Base):
    """Tracks manual corrections - ground truth for learning."""

    __tablename__ = "face_corrections"

    id = Column(Integer, primary_key=True)
    face_id = Column(
        Integer, ForeignKey("faces.id"), nullable=False, index=True, unique=True
    )
    # Manual cluster assignment - overrides automatic clustering
    manual_cluster_id = Column(Integer, ForeignKey("clusters.id"))
    # If None, face is marked as "noise" / "not this person"
    person_name = Column(String, index=True)  # The person's name (for grouping)
    is_excluded = Column(Boolean, default=False)  # True if marked as "not this person"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FaceCorrection(face_id={self.face_id}, person='{self.person_name}', excluded={self.is_excluded})>"


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.getenv("DATABASE_PATH", "./photo_face.db")

        # Ensure the directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        """Get a new database session."""
        return self.Session()

    def add_photo(
        self, file_path, file_size=None, file_hash=None, width=None, height=None
    ):
        """Add or update a photo record."""
        session = self.get_session()
        try:
            photo = session.query(Photo).filter_by(file_path=file_path).first()
            if not photo:
                photo = Photo(
                    file_path=file_path,
                    file_size=file_size,
                    file_hash=file_hash,
                    width=width,
                    height=height,
                )
                session.add(photo)
            session.commit()
            return photo.id
        finally:
            session.close()

    def mark_photo_processed(self, photo_id, face_count=0):
        """Mark a photo as processed."""
        session = self.get_session()
        try:
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if photo:
                photo.processed = True
                photo.scanned_at = datetime.utcnow()
                photo.face_count = face_count
                session.commit()
        finally:
            session.close()

    def add_face(self, photo_id, embedding, top, right, bottom, left, confidence=1.0):
        """Add a detected face."""
        session = self.get_session()
        try:
            face = Face(
                photo_id=photo_id,
                embedding=(
                    embedding.tolist() if hasattr(embedding, "tolist") else embedding
                ),
                top=top,
                right=right,
                bottom=bottom,
                left=left,
                confidence=confidence,
            )
            session.add(face)
            session.commit()
            return face.id
        finally:
            session.close()

    def get_unprocessed_photos(self, limit=None):
        """Get photos that haven't been processed yet."""
        session = self.get_session()
        try:
            query = session.query(Photo).filter_by(processed=False)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_all_face_embeddings(self):
        """Get all face embeddings for clustering."""
        session = self.get_session()
        try:
            faces = session.query(Face).all()
            return [(face.id, face.embedding) for face in faces]
        finally:
            session.close()

    def update_cluster_assignments(self, face_cluster_map):
        """Update cluster assignments for faces.

        Args:
            face_cluster_map: Dict mapping face_id to cluster_id
        """
        session = self.get_session()
        try:
            for face_id, cluster_label in face_cluster_map.items():
                # Skip noise points (labeled as -1)
                if cluster_label == -1:
                    continue

                # Get or create cluster
                cluster = session.query(Cluster).filter_by(id=cluster_label).first()
                if not cluster:
                    cluster = Cluster(id=cluster_label)
                    session.add(cluster)

                # Update face's cluster
                face = session.query(Face).filter_by(id=face_id).first()
                if face:
                    face.cluster_id = cluster_label

            session.commit()

            # Update cluster face counts
            self.update_cluster_counts()
        finally:
            session.close()

    def update_cluster_counts(self):
        """Update face counts for all clusters."""
        session = self.get_session()
        try:
            clusters = session.query(Cluster).all()
            for cluster in clusters:
                cluster.face_count = (
                    session.query(Face).filter_by(cluster_id=cluster.id).count()
                )

                # Check if current representative face is still in this cluster
                if cluster.representative_face_id:
                    rep_face = (
                        session.query(Face)
                        .filter_by(
                            id=cluster.representative_face_id, cluster_id=cluster.id
                        )
                        .first()
                    )
                    if not rep_face:
                        # Representative face is no longer in this cluster, choose a new one
                        first_face = (
                            session.query(Face).filter_by(cluster_id=cluster.id).first()
                        )
                        cluster.representative_face_id = (
                            first_face.id if first_face else None
                        )
                else:
                    # Set representative face if not set
                    first_face = (
                        session.query(Face).filter_by(cluster_id=cluster.id).first()
                    )
                    if first_face:
                        cluster.representative_face_id = first_face.id

            session.commit()
        finally:
            session.close()

    def get_clusters_with_faces(self):
        """Get all clusters with their faces."""
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

    def update_cluster_name(self, cluster_id, name):
        """Update the name of a cluster."""
        session = self.get_session()
        try:
            cluster = session.query(Cluster).filter_by(id=cluster_id).first()
            if cluster:
                cluster.name = name
                session.commit()
                return True
            return False
        finally:
            session.close()

    def update_scan_progress(self, directory, last_path, files_scanned, faces_detected):
        """Update scanning progress."""
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
        """Mark a scan as completed."""
        session = self.get_session()
        try:
            progress = (
                session.query(ScanProgress)
                .filter_by(directory=directory, completed=False)
                .first()
            )
            if progress:
                progress.completed = True
                session.commit()
        finally:
            session.close()

    def get_stats(self):
        """Get overall statistics."""
        session = self.get_session()
        try:
            total_photos = session.query(Photo).count()
            processed_photos = session.query(Photo).filter_by(processed=True).count()
            total_faces = session.query(Face).count()
            total_clusters = (
                session.query(Cluster).filter(Cluster.face_count > 0).count()
            )
            named_clusters = (
                session.query(Cluster)
                .filter(Cluster.name.isnot(None), Cluster.face_count > 0)
                .count()
            )

            return {
                "total_photos": total_photos,
                "processed_photos": processed_photos,
                "total_faces": total_faces,
                "total_clusters": total_clusters,
                "named_clusters": named_clusters,
            }
        finally:
            session.close()


if __name__ == "__main__":
    # Test database creation
    db = DatabaseManager()
    print("Database created successfully!")
    print(f"Stats: {db.get_stats()}")
