"""
Reset clustering state while keeping scanned faces and photos.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager

load_dotenv()

console = Console()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Remove clusters and optional manual learning while keeping scanned faces"
    )
    parser.add_argument(
        "--keep-learning",
        action="store_true",
        help="Keep manual corrections instead of removing them",
    )
    args = parser.parse_args()

    db = DatabaseManager()
    summary = db.reset_clustering_state(clear_corrections=not args.keep_learning)

    console.print(
        Panel.fit(
            "\n".join(
                [
                    "[bold green]Clustering state reset[/bold green]",
                    f"Faces kept: [cyan]{summary['faces_reset']}[/cyan]",
                    f"Clusters removed: [yellow]{summary['clusters_removed']}[/yellow]",
                    f"Corrections removed: [yellow]{summary['corrections_removed']}[/yellow]",
                ]
            ),
            title="Reset Clustering",
        )
    )
