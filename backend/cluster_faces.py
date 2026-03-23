"""
CLI entrypoint for face clustering.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.clustering_service import ClusteringService
from backend.database import DatabaseManager
from backend.redis_cache import RedisCache

load_dotenv()

console = Console()


def cluster_faces(force_rebuild: bool = False) -> dict:
    db = DatabaseManager()
    cache = RedisCache()
    service = ClusteringService(db=db, cache=cache)
    return service.run(force_rebuild=force_rebuild)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cluster detected faces")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild clusters using the latest algorithm version",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=None,
        help="Minimum faces to form a new cluster",
    )
    parser.add_argument(
        "--eps",
        type=float,
        default=None,
        help="Raw Euclidean distance threshold for the coarse DBSCAN pass",
    )
    args = parser.parse_args()

    if args.min_size is not None:
        os.environ["MIN_CLUSTER_SIZE"] = str(args.min_size)
    if args.eps is not None:
        os.environ["CLUSTER_DBSCAN_EPSILON"] = str(args.eps)

    try:
        summary = cluster_faces(force_rebuild=args.rebuild)
        console.print(
            Panel.fit(
                "\n".join(
                    [
                        "[bold green]Clustering Complete[/bold green]",
                        f"Mode: [cyan]{summary['mode']}[/cyan]",
                        f"Candidate faces: [yellow]{summary['candidate_faces']}[/yellow]",
                        f"Assigned to existing clusters: [yellow]{summary['assigned_to_existing']}[/yellow]",
                        f"Clustered into new groups: [yellow]{summary['clustered_new_faces']}[/yellow]",
                        f"Created clusters: [yellow]{summary['created_clusters']}[/yellow]",
                        f"Left unclustered: [yellow]{summary['left_unclustered']}[/yellow]",
                    ]
                ),
                title="Face Clustering",
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Clustering interrupted by user.[/yellow]")
    except Exception as exc:
        console.print(f"\n[red]Fatal clustering error: {exc}[/red]")
        sys.exit(1)
