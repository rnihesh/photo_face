"""
Face clustering module using DBSCAN algorithm.
Groups similar face embeddings to identify the same person across multiple photos.
Optimized for large datasets with progress tracking.
"""

import os
import sys
import numpy as np
from typing import List, Tuple
from dotenv import load_dotenv
from tqdm import tqdm
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager

load_dotenv()

console = Console()


def apply_manual_corrections(db):
    """
    Apply manual corrections after auto-clustering.
    This allows the system to "learn" from user feedback.
    
    Returns:
        Number of corrections applied
    """
    from backend.database import Face, FaceCorrection, Cluster
    
    session = db.get_session()
    try:
        corrections = session.query(FaceCorrection).all()
        
        if not corrections:
            return 0
        
        # Group corrections by person name
        person_clusters = {}  # name -> cluster_id
        corrections_applied = 0
        
        for correction in corrections:
            face = session.query(Face).filter_by(id=correction.face_id).first()
            if not face:
                continue
            
            if correction.is_excluded:
                # Face marked as "not this person" - remove from cluster
                if face.cluster_id is not None:
                    face.cluster_id = None
                    corrections_applied += 1
            elif correction.person_name:
                # Get or create cluster for this person
                if correction.person_name not in person_clusters:
                    # Find existing cluster with this name or use manual_cluster_id
                    cluster = session.query(Cluster).filter_by(name=correction.person_name).first()
                    if cluster:
                        person_clusters[correction.person_name] = cluster.id
                    elif correction.manual_cluster_id is not None:
                        # Use the manually assigned cluster
                        cluster = session.query(Cluster).filter_by(id=correction.manual_cluster_id).first()
                        if cluster:
                            cluster.name = correction.person_name
                            person_clusters[correction.person_name] = cluster.id
                
                # Assign face to the person's cluster
                if correction.person_name in person_clusters:
                    face.cluster_id = person_clusters[correction.person_name]
                    corrections_applied += 1
        
        # Update cluster face counts
        clusters = session.query(Cluster).all()
        for cluster in clusters:
            cluster.face_count = session.query(Face).filter_by(cluster_id=cluster.id).count()
        
        session.commit()
        return corrections_applied
    finally:
        session.close()


def cluster_faces(min_cluster_size=3, eps=0.5):
    """
    Cluster detected faces using DBSCAN algorithm.
    
    Args:
        min_cluster_size: Minimum number of faces to form a cluster
        eps: Maximum distance between faces in the same cluster (lower = stricter)
    """
    console.print(Panel.fit(
        f"[bold cyan]Face Clustering System[/bold cyan]\n\n"
        f"🎯 Algorithm: [yellow]DBSCAN[/yellow]\n"
        f"📊 Min Cluster Size: [yellow]{min_cluster_size}[/yellow]\n"
        f"📏 Distance Threshold (eps): [yellow]{eps}[/yellow]",
        title="🧩 Starting Clustering"
    ))
    
    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager()
    
    # Get all face embeddings
    console.print("\n[bold]📥 Loading face embeddings from database...[/bold]")
    face_data = db.get_all_face_embeddings()
    
    if not face_data:
        console.print("[red]❌ No face embeddings found! Run scan_photos.py first.[/red]")
        return
    
    console.print(f"[green]✓ Loaded {len(face_data)} face embeddings[/green]\n")
    
    # Extract face IDs and embeddings
    face_ids = []
    embeddings = []
    
    console.print("[bold]🔄 Preparing embeddings for clustering...[/bold]")
    for face_id, embedding in tqdm(face_data, desc="Processing embeddings", colour='cyan'):
        face_ids.append(face_id)
        # Convert embedding from list to numpy array if needed
        if isinstance(embedding, list):
            embeddings.append(np.array(embedding))
        else:
            embeddings.append(embedding)
    
    # Convert to numpy array
    X = np.array(embeddings)
    
    # Normalize embeddings for better clustering
    console.print("\n[bold]📐 Normalizing embeddings...[/bold]")
    X_normalized = normalize(X)
    
    # Perform clustering
    console.print(f"\n[bold cyan]🧩 Clustering {len(face_ids)} faces...[/bold cyan]")
    console.print("[yellow]This may take a few minutes for large datasets...[/yellow]\n")
    
    # DBSCAN clustering
    clusterer = DBSCAN(
        eps=eps,
        min_samples=min_cluster_size,
        metric='euclidean',
        n_jobs=-1  # Use all CPU cores
    )
    
    with console.status("[bold green]Computing clusters...") as status:
        labels = clusterer.fit_predict(X_normalized)
    
    # Analyze results
    unique_labels = set(labels)
    n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
    n_noise = list(labels).count(-1)
    
    console.print(f"\n[green]✓ Clustering complete![/green]")
    console.print(f"[cyan]  • Found {n_clusters} unique faces[/cyan]")
    console.print(f"[yellow]  • {n_noise} faces marked as noise (outliers)[/yellow]\n")
    
    # Update database with cluster assignments
    console.print("[bold]💾 Saving cluster assignments to database...[/bold]")
    
    face_cluster_map = {}
    for face_id, cluster_label in zip(face_ids, labels):
        if cluster_label != -1:  # Skip noise points
            face_cluster_map[face_id] = int(cluster_label)
    
    db.update_cluster_assignments(face_cluster_map)
    
    # Apply manual corrections (learning from user feedback)
    console.print("\n[bold]🎓 Applying manual corrections (learning from your feedback)...[/bold]")
    corrections_applied = apply_manual_corrections(db)
    if corrections_applied > 0:
        console.print(f"[green]✓ Applied {corrections_applied} manual corrections[/green]")
    
    # Calculate cluster statistics
    console.print("\n[bold]📊 Calculating cluster statistics...[/bold]")
    
    cluster_sizes = {}
    for label in labels:
        if label != -1:
            cluster_sizes[label] = cluster_sizes.get(label, 0) + 1
    
    # Sort clusters by size
    sorted_clusters = sorted(cluster_sizes.items(), key=lambda x: x[1], reverse=True)
    
    # Display top 10 largest clusters
    console.print("\n[bold cyan]🏆 Top 10 Largest Face Collections:[/bold cyan]\n")
    
    for i, (cluster_id, size) in enumerate(sorted_clusters[:10], 1):
        bar = "█" * min(50, size)
        console.print(f"  {i:2d}. Cluster {cluster_id:3d}: [{size:4d} faces] {bar}")
    
    # Print final statistics
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        f"[bold green]✅ Clustering Complete![/bold green]\n\n"
        f"🎯 Total Clusters: [cyan]{n_clusters}[/cyan]\n"
        f"👤 Clustered Faces: [cyan]{len(face_cluster_map)}[/cyan]\n"
        f"⚠️  Noise Points: [yellow]{n_noise}[/yellow]\n"
        f"📊 Average Cluster Size: [yellow]{len(face_cluster_map)/max(n_clusters, 1):.2f}[/yellow]",
        title="📈 Results"
    ))
    
    # Print overall database stats
    stats = db.get_stats()
    console.print(Panel.fit(
        f"[bold cyan]Updated Database Statistics[/bold cyan]\n\n"
        f"📸 Total Photos: [yellow]{stats['total_photos']}[/yellow]\n"
        f"✓ Processed: [green]{stats['processed_photos']}[/green]\n"
        f"👥 Total Faces: [yellow]{stats['total_faces']}[/yellow]\n"
        f"🏷️  Face Collections: [yellow]{stats['total_clusters']}[/yellow]\n"
        f"📛 Named Collections: [green]{stats['named_clusters']}[/green]",
        title="💾 Database"
    ))
    
    console.print("\n[bold green]✨ Next step: Start the API server and React UI to browse and name face collections![/bold green]\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cluster detected faces')
    parser.add_argument('--min-size', type=int, default=None, 
                        help='Minimum cluster size (default from .env)')
    parser.add_argument('--eps', type=float, default=None,
                        help='DBSCAN epsilon parameter (default from .env)')
    
    args = parser.parse_args()
    
    # Get values from .env or use args
    min_cluster_size = args.min_size if args.min_size is not None else int(os.getenv('MIN_CLUSTER_SIZE', '3'))
    eps = args.eps if args.eps is not None else float(os.getenv('CLUSTER_EPSILON', '0.5'))
    
    try:
        cluster_faces(min_cluster_size=min_cluster_size, eps=eps)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Clustering interrupted by user.[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        logger.exception("Fatal error during clustering")
        sys.exit(1)
