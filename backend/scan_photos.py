"""
CLI entrypoint for library sync and face detection.
"""

from __future__ import annotations

import sys
import os

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager
from backend.redis_cache import RedisCache
from backend.sync_service import SyncService

load_dotenv()

console = Console()


def scan_photos(root_dir: str | None = None, resume: bool = True) -> dict:
    db = DatabaseManager()
    cache = RedisCache()
    service = SyncService(db=db, cache=cache)
    return service.sync_library(
        root_dir=root_dir,
        force_rescan=not resume,
        force_recluster=False,
        reason="cli-scan",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan photos and detect faces")
    parser.add_argument("--path", type=str, default=None, help="Path to the photo library")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Reprocess already-known files",
    )
    args = parser.parse_args()

    try:
        summary = scan_photos(root_dir=args.path, resume=not args.no_resume)
        clustering = summary.get("clustering") or {}
        console.print(
            Panel.fit(
                "\n".join(
                    [
                        "[bold green]Library Sync Complete[/bold green]",
                        f"Photos seen: [cyan]{summary.get('photos_seen', 0)}[/cyan]",
                        f"New photos: [yellow]{summary.get('new_photos', 0)}[/yellow]",
                        f"Changed photos: [yellow]{summary.get('changed_photos', 0)}[/yellow]",
                        f"Processed photos: [yellow]{summary.get('processed_photos', 0)}[/yellow]",
                        f"Faces detected: [yellow]{summary.get('faces_detected', 0)}[/yellow]",
                        f"Clustering mode: [cyan]{clustering.get('mode', 'skipped')}[/cyan]",
                    ]
                ),
                title="Photo Sync",
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Scan interrupted by user.[/yellow]")
    except Exception as exc:
        console.print(f"\n[red]Fatal scan error: {exc}[/red]")
        sys.exit(1)
