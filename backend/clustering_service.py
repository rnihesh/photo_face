"""
Incremental face clustering with stable cluster IDs and manual-learning hooks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
from loguru import logger
from sklearn.cluster import DBSCAN
from sqlalchemy import or_

from backend.database import Cluster, DatabaseManager, Face, FaceCorrection
from backend.redis_cache import RedisCache


@dataclass
class FaceVector:
    id: int
    photo_id: int
    embedding: np.ndarray


@dataclass
class ClusterPrototype:
    id: int
    centroid: np.ndarray
    is_locked: bool
    face_count: int
    name: Optional[str] = None


class ClusteringService:
    """Coordinates incremental clustering and full rebuilds."""

    def __init__(self, db: DatabaseManager, cache: Optional[RedisCache] = None) -> None:
        self.db = db
        self.cache = cache
        self.algorithm_version = os.getenv("CLUSTERING_ALGORITHM_VERSION", "3")
        self.min_cluster_size = int(os.getenv("MIN_CLUSTER_SIZE", "2"))
        legacy_cluster_eps = float(os.getenv("CLUSTER_EPSILON", "0.25"))
        default_cluster_eps = max(0.34, legacy_cluster_eps)
        self.cluster_eps = float(
            os.getenv("CLUSTER_DBSCAN_EPSILON", str(default_cluster_eps))
        )
        self.refine_eps = float(
            os.getenv(
                "CLUSTER_REFINE_EPSILON",
                str(max(self.cluster_eps, min(self.cluster_eps + 0.02, 0.37))),
            )
        )
        self.assign_threshold = float(
            os.getenv(
                "CLUSTER_ASSIGN_EPSILON",
                str(max(0.28, min(self.cluster_eps - 0.04, 0.32))),
            )
        )
        self.locked_assign_threshold = float(
            os.getenv(
                "LOCKED_CLUSTER_ASSIGN_EPSILON",
                str(max(0.26, min(self.assign_threshold - 0.02, self.assign_threshold))),
            )
        )
        self.merge_threshold = float(
            os.getenv(
                "CLUSTER_MERGE_EPSILON",
                str(max(0.26, min(self.cluster_eps - 0.05, self.assign_threshold))),
            )
        )
        self.assignment_margin = float(os.getenv("CLUSTER_ASSIGN_MARGIN", "0.04"))

    def needs_rebuild(self) -> bool:
        version = self.db.get_setting("clustering_algorithm_version")
        return version != self.algorithm_version

    def run(self, force_rebuild: bool = False) -> dict:
        rebuild = force_rebuild or self.needs_rebuild()
        session = self.db.get_session()

        try:
            if rebuild:
                seed_cluster_ids = self._prepare_rebuild(session)
            else:
                seed_cluster_ids = set()

            corrections = session.query(FaceCorrection).all()
            correction_map = {correction.face_id: correction for correction in corrections}

            excluded_count, correction_cluster_ids = self._apply_corrections(
                session, correction_map
            )

            candidates = self._load_candidates(session, rebuild, correction_map)
            candidate_ids = {candidate.id for candidate in candidates}

            prototypes = self._build_prototypes(session, candidate_ids)
            assigned_to_existing, remaining = self._assign_candidates(
                session, candidates, prototypes
            )

            clustered_new, created_clusters, updated_cluster_ids = self._cluster_remaining(
                session, remaining, prototypes
            )

            processed_face_ids = {face.id for face in candidates}
            unresolved_ids = {face.id for face in remaining} - clustered_new
            if unresolved_ids:
                (
                    session.query(Face)
                    .filter(Face.id.in_(unresolved_ids))
                    .update(
                        {
                            "cluster_id": None,
                            "needs_clustering": False,
                            "cluster_confidence": None,
                        },
                        synchronize_session=False,
                    )
                )

            affected_cluster_ids = (
                set(seed_cluster_ids)
                | set(correction_cluster_ids)
                | set(assigned_to_existing.values())
                | set(updated_cluster_ids)
                | set(created_clusters)
            )

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        if rebuild:
            self.db.update_cluster_counts()
        elif affected_cluster_ids:
            self.db.update_cluster_counts(affected_cluster_ids)

        self.db.set_setting("clustering_algorithm_version", self.algorithm_version)
        self._invalidate_cache()

        result = {
            "mode": "rebuild" if rebuild else "incremental",
            "algorithm_version": self.algorithm_version,
            "candidate_faces": len(processed_face_ids),
            "excluded_faces": excluded_count,
            "assigned_to_existing": len(assigned_to_existing),
            "clustered_new_faces": len(clustered_new),
            "created_clusters": len(created_clusters),
            "updated_clusters": len(updated_cluster_ids),
            "left_unclustered": len(unresolved_ids),
        }
        logger.info("Clustering finished: {}", result)
        return result

    def _prepare_rebuild(self, session) -> set[int]:
        seed_clusters = (
            session.query(Cluster)
            .filter(or_(Cluster.is_locked.is_(True), Cluster.name.isnot(None)))
            .all()
        )
        seed_cluster_ids = {cluster.id for cluster in seed_clusters}

        if seed_cluster_ids:
            (
                session.query(Face)
                .filter(or_(Face.cluster_id.is_(None), ~Face.cluster_id.in_(seed_cluster_ids)))
                .update(
                    {
                        "cluster_id": None,
                        "needs_clustering": True,
                        "cluster_confidence": None,
                    },
                    synchronize_session=False,
                )
            )
            (
                session.query(Face)
                .filter(Face.cluster_id.in_(seed_cluster_ids))
                .update({"needs_clustering": False}, synchronize_session=False)
            )
            (
                session.query(Cluster)
                .filter(~Cluster.id.in_(seed_cluster_ids))
                .delete(synchronize_session=False)
            )
        else:
            session.query(Face).update(
                {
                    "cluster_id": None,
                    "needs_clustering": True,
                    "cluster_confidence": None,
                },
                synchronize_session=False,
            )
            session.query(Cluster).delete(synchronize_session=False)

        session.flush()
        return seed_cluster_ids

    def _apply_corrections(self, session, correction_map: dict[int, FaceCorrection]) -> tuple[int, set[int]]:
        excluded_count = 0
        affected_cluster_ids: set[int] = set()

        for correction in correction_map.values():
            face = session.query(Face).filter_by(id=correction.face_id).first()
            if not face:
                continue

            if correction.is_excluded:
                if correction.excluded_from_cluster_id is None and face.cluster_id is not None:
                    correction.excluded_from_cluster_id = face.cluster_id
                face.cluster_id = None
                face.needs_clustering = False
                face.cluster_confidence = 1.0
                excluded_count += 1
                continue

            if not correction.person_name and correction.manual_cluster_id is None:
                continue

            cluster = None
            if correction.manual_cluster_id is not None:
                cluster = session.query(Cluster).filter_by(id=correction.manual_cluster_id).first()
            if not cluster and correction.person_name:
                cluster = (
                    session.query(Cluster)
                    .filter_by(name=correction.person_name)
                    .order_by(Cluster.face_count.desc())
                    .first()
                )
            if not cluster:
                cluster = Cluster(
                    name=correction.person_name,
                    is_locked=True,
                    last_clustered_at=None,
                )
                session.add(cluster)
                session.flush()

            if correction.person_name:
                cluster.name = correction.person_name
            cluster.is_locked = True
            correction.manual_cluster_id = cluster.id

            face.cluster_id = cluster.id
            face.needs_clustering = False
            face.cluster_confidence = 1.0
            affected_cluster_ids.add(cluster.id)

        session.flush()
        return excluded_count, affected_cluster_ids

    def _load_candidates(
        self,
        session,
        rebuild: bool,
        correction_map: dict[int, FaceCorrection],
    ) -> list[FaceVector]:
        if rebuild:
            faces = session.query(Face).all()
        else:
            faces = (
                session.query(Face)
                .filter(or_(Face.needs_clustering.is_(True), Face.cluster_id.is_(None)))
                .all()
            )

        candidates: list[FaceVector] = []
        for face in faces:
            correction = correction_map.get(face.id)
            if correction and correction.is_excluded:
                continue
            if correction and (correction.manual_cluster_id or correction.person_name):
                continue
            candidates.append(
                FaceVector(
                    id=face.id,
                    photo_id=face.photo_id,
                    embedding=np.array(face.embedding, dtype=float),
                )
            )
        return candidates

    def _build_prototypes(
        self, session, excluded_face_ids: Iterable[int]
    ) -> list[ClusterPrototype]:
        excluded_face_ids = list(excluded_face_ids)
        clusters = session.query(Cluster).all()
        prototypes: list[ClusterPrototype] = []

        for cluster in clusters:
            query = session.query(Face).filter(Face.cluster_id == cluster.id)
            if excluded_face_ids:
                query = query.filter(~Face.id.in_(excluded_face_ids))
            faces = query.all()

            if faces:
                matrix = np.array([face.embedding for face in faces], dtype=float)
                centroid = self._centroid(matrix)
                face_count = len(faces)
            elif cluster.centroid:
                centroid = np.array(cluster.centroid, dtype=float)
                face_count = cluster.face_count or 0
            else:
                continue

            prototypes.append(
                ClusterPrototype(
                    id=cluster.id,
                    centroid=centroid,
                    is_locked=bool(cluster.is_locked or cluster.name),
                    face_count=face_count,
                    name=cluster.name,
                )
            )

        return prototypes

    def _assign_candidates(
        self,
        session,
        candidates: list[FaceVector],
        prototypes: list[ClusterPrototype],
    ) -> tuple[dict[int, int], list[FaceVector]]:
        if not candidates or not prototypes:
            return {}, candidates

        prototype_ids = [prototype.id for prototype in prototypes]
        prototype_centroids = np.stack([prototype.centroid for prototype in prototypes])
        prototype_lookup = {prototype.id: prototype for prototype in prototypes}

        assigned: dict[int, int] = {}
        remaining: list[FaceVector] = []

        for face in candidates:
            distances = np.linalg.norm(prototype_centroids - face.embedding, axis=1)
            order = np.argsort(distances)
            nearest_index = int(order[0])
            nearest_cluster_id = prototype_ids[nearest_index]
            nearest_distance = float(distances[nearest_index])
            threshold = (
                self.locked_assign_threshold
                if prototype_lookup[nearest_cluster_id].is_locked
                else self.assign_threshold
            )
            second_distance = (
                float(distances[int(order[1])]) if len(order) > 1 else None
            )

            confident = nearest_distance <= threshold
            well_separated = (
                second_distance is None
                or (second_distance - nearest_distance) >= self.assignment_margin
            )

            if confident and well_separated:
                assigned[face.id] = nearest_cluster_id
                confidence = round(
                    max(0.0, 1.0 - (nearest_distance / max(threshold, 1e-6))),
                    4,
                )
                (
                    session.query(Face)
                    .filter_by(id=face.id)
                    .update(
                        {
                            "cluster_id": nearest_cluster_id,
                            "needs_clustering": False,
                            "cluster_confidence": confidence,
                        }
                    )
                )
            else:
                remaining.append(face)

        session.flush()
        return assigned, remaining

    def _cluster_remaining(
        self,
        session,
        remaining: list[FaceVector],
        prototypes: list[ClusterPrototype],
    ) -> tuple[set[int], list[int], set[int]]:
        if not remaining:
            return set(), [], set()

        created_clusters: list[int] = []
        updated_cluster_ids: set[int] = set()
        clustered_faces: set[int] = set()

        if len(remaining) < max(self.min_cluster_size, 2):
            return clustered_faces, created_clusters, updated_cluster_ids

        matrix = np.stack([face.embedding for face in remaining])
        labels = DBSCAN(
            eps=self.cluster_eps,
            min_samples=max(self.min_cluster_size, 2),
            metric="euclidean",
            n_jobs=-1,
        ).fit_predict(matrix)

        grouped: dict[int, list[FaceVector]] = {}
        for face, label in zip(remaining, labels):
            if label == -1:
                continue
            grouped.setdefault(int(label), []).append(face)

        dynamic_prototypes = list(prototypes)

        for faces in grouped.values():
            refined_groups = self._refine_cluster_group(faces)
            for refined_faces in refined_groups:
                cluster_matrix = np.stack([face.embedding for face in refined_faces])
                centroid = self._centroid(cluster_matrix)
                target_cluster_id = self._match_existing_cluster(centroid, dynamic_prototypes)

                if target_cluster_id is None:
                    cluster = Cluster(
                        last_clustered_at=None,
                        centroid=centroid.tolist(),
                        is_locked=False,
                    )
                    session.add(cluster)
                    session.flush()
                    target_cluster_id = cluster.id
                    created_clusters.append(cluster.id)
                    dynamic_prototypes.append(
                        ClusterPrototype(
                            id=cluster.id,
                            centroid=centroid,
                            is_locked=False,
                            face_count=len(refined_faces),
                        )
                    )
                else:
                    updated_cluster_ids.add(target_cluster_id)
                    self._update_dynamic_prototype(
                        dynamic_prototypes,
                        target_cluster_id,
                        cluster_matrix,
                    )

                distances = np.linalg.norm(cluster_matrix - centroid, axis=1)
                confidence = round(
                    max(0.0, 1.0 - (float(np.mean(distances)) / max(self.refine_eps, 1e-6))),
                    4,
                )
                face_ids = [face.id for face in refined_faces]
                (
                    session.query(Face)
                    .filter(Face.id.in_(face_ids))
                    .update(
                        {
                            "cluster_id": target_cluster_id,
                            "needs_clustering": False,
                            "cluster_confidence": confidence,
                        },
                        synchronize_session=False,
                    )
                )
                clustered_faces.update(face_ids)

        session.flush()
        return clustered_faces, created_clusters, updated_cluster_ids

    def _match_existing_cluster(
        self, centroid: np.ndarray, prototypes: list[ClusterPrototype]
    ) -> Optional[int]:
        if not prototypes:
            return None
        distances = np.array(
            [self._euclidean_distance(centroid, prototype.centroid) for prototype in prototypes],
            dtype=float,
        )
        order = np.argsort(distances)
        best_index = int(order[0])
        best_distance = float(distances[best_index])
        second_distance = float(distances[int(order[1])]) if len(order) > 1 else None
        separated = second_distance is None or (
            second_distance - best_distance
        ) >= self.assignment_margin
        if best_distance <= self.merge_threshold and separated:
            return prototypes[best_index].id
        return None

    @staticmethod
    def _centroid(matrix: np.ndarray) -> np.ndarray:
        return matrix.mean(axis=0)

    @staticmethod
    def _euclidean_distance(left: np.ndarray, right: np.ndarray) -> float:
        return float(np.linalg.norm(left - right))

    def _refine_cluster_group(self, faces: list[FaceVector]) -> list[list[FaceVector]]:
        if len(faces) < max(self.min_cluster_size, 2):
            return []

        matrix = np.stack([face.embedding for face in faces])
        centroid = self._centroid(matrix)
        order = np.argsort(np.linalg.norm(matrix - centroid, axis=1))
        draft_clusters: list[dict[str, object]] = []

        for face_index in order:
            vector = matrix[face_index]
            best_index: Optional[int] = None
            best_distance: Optional[float] = None

            for cluster_index, draft in enumerate(draft_clusters):
                member_indices = draft["indices"]
                member_matrix = matrix[member_indices]
                distances = np.linalg.norm(member_matrix - vector, axis=1)
                if float(distances.max()) > self.refine_eps:
                    continue

                centroid_distance = self._euclidean_distance(draft["centroid"], vector)
                if best_index is None or centroid_distance < best_distance:
                    best_index = cluster_index
                    best_distance = centroid_distance

            if best_index is None:
                draft_clusters.append(
                    {
                        "indices": [int(face_index)],
                        "centroid": vector.copy(),
                    }
                )
                continue

            draft = draft_clusters[best_index]
            draft["indices"].append(int(face_index))
            draft["centroid"] = self._centroid(matrix[draft["indices"]])

        refined_groups: list[list[FaceVector]] = []
        for draft in draft_clusters:
            if len(draft["indices"]) < self.min_cluster_size:
                continue
            refined_groups.append([faces[index] for index in draft["indices"]])
        return refined_groups

    def _update_dynamic_prototype(
        self,
        prototypes: list[ClusterPrototype],
        cluster_id: int,
        cluster_matrix: np.ndarray,
    ) -> None:
        for prototype in prototypes:
            if prototype.id != cluster_id:
                continue
            existing_weight = max(prototype.face_count, 0)
            new_weight = len(cluster_matrix)
            combined = (
                (prototype.centroid * existing_weight) + cluster_matrix.sum(axis=0)
            ) / max(existing_weight + new_weight, 1)
            prototype.centroid = combined
            prototype.face_count = existing_weight + new_weight
            return

    def _invalidate_cache(self) -> None:
        if not self.cache:
            return
        self.cache.delete_prefix("api:")
