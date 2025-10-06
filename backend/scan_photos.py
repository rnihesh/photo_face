"""
Photo scanner with face detection - Optimized for Apple Silicon M4 Pro.
Recursively scans directories, detects faces, and stores embeddings.
Features:
- Resumable scanning with checkpoints
- Progress tracking with tqdm
- Read-only access to photos
- Batch processing for efficiency
"""

import os
import sys
import hashlib
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from tqdm import tqdm
from loguru import logger
from rich.console import Console
from rich.panel import Panel

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager, Photo
from backend.face_detector import FaceDetector, get_image_dimensions, is_valid_image

load_dotenv()

console = Console()


def calculate_file_hash(file_path: str, chunk_size=8192) -> str:
    """Calculate MD5 hash of a file efficiently."""
    md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}")
        return None


def find_all_images(root_dir: str, extensions: List[str]) -> List[str]:
    """
    Recursively find all image files in a directory.
    
    Args:
        root_dir: Root directory to search
        extensions: List of file extensions to look for
        
    Returns:
        List of absolute paths to image files
    """
    image_files = []
    root_path = Path(root_dir)
    
    if not root_path.exists():
        logger.error(f"Directory does not exist: {root_dir}")
        return []
    
    logger.info(f"Scanning directory structure: {root_dir}")
    
    # Use os.walk for better performance on large directories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if is_valid_image(file_path, extensions):
                image_files.append(file_path)
    
    logger.info(f"Found {len(image_files)} image files")
    return image_files


def scan_photos(root_dir: str = None, resume=True, batch_size=32):
    """
    Main scanning function.
    
    Args:
        root_dir: Root directory containing photos (defaults to PHOTOS_PATH from .env)
        resume: Whether to resume from last checkpoint
        batch_size: Number of photos to process in each batch
    """
    # Load configuration
    if root_dir is None:
        root_dir = os.getenv('PHOTOS_PATH', '/Volumes/Elements/')
    
    extensions = os.getenv('IMAGE_EXTENSIONS', '.jpg,.jpeg,.png,.bmp,.tiff,.tif,.heic,.heif').split(',')
    detection_model = os.getenv('FACE_DETECTION_MODEL', 'hog')
    
    console.print(Panel.fit(
        f"[bold cyan]Photo Face Detection Scanner[/bold cyan]\n\n"
        f"📁 Scanning: [green]{root_dir}[/green]\n"
        f"🔍 Detection Model: [yellow]{detection_model}[/yellow]\n"
        f"📦 Batch Size: [yellow]{batch_size}[/yellow]\n"
        f"🔄 Resume Mode: [yellow]{'Enabled' if resume else 'Disabled'}[/yellow]",
        title="🚀 Starting Scan"
    ))
    
    # Initialize database and face detector
    logger.info("Initializing database...")
    db = DatabaseManager()
    
    logger.info("Initializing face detector...")
    detector = FaceDetector(model=detection_model, use_gpu=True)
    
    # Find all image files
    console.print("\n[bold]📸 Finding image files...[/bold]")
    image_files = find_all_images(root_dir, extensions)
    
    if not image_files:
        console.print("[red]❌ No image files found![/red]")
        return
    
    console.print(f"[green]✓ Found {len(image_files)} images[/green]\n")
    
    # Determine which files to process
    files_to_process = []
    if resume:
        logger.info("Checking for already processed files...")
        session = db.get_session()
        try:
            processed_paths = {photo.file_path for photo in session.query(Photo).filter_by(processed=True).all()}
            files_to_process = [f for f in image_files if f not in processed_paths]
            skipped = len(image_files) - len(files_to_process)
            if skipped > 0:
                console.print(f"[yellow]⏭️  Skipping {skipped} already processed files[/yellow]")
        finally:
            session.close()
    else:
        files_to_process = image_files
    
    if not files_to_process:
        console.print("[green]✓ All files already processed![/green]")
        return
    
    console.print(f"[bold cyan]🔄 Processing {len(files_to_process)} files...[/bold cyan]\n")
    
    # Statistics
    total_files_processed = 0
    total_faces_detected = 0
    errors = 0
    
    # Process files with progress bar
    with tqdm(total=len(files_to_process), desc="Scanning photos", unit="photo",
              colour='cyan', dynamic_ncols=True) as pbar:
        
        for file_path in files_to_process:
            try:
                # Update progress bar with current file
                pbar.set_postfix_str(f"📄 {os.path.basename(file_path)[:40]}")
                
                # Get file metadata
                file_size = os.path.getsize(file_path)
                file_hash = calculate_file_hash(file_path)
                width, height = get_image_dimensions(file_path)
                
                # Add photo to database
                photo_id = db.add_photo(
                    file_path=file_path,
                    file_size=file_size,
                    file_hash=file_hash,
                    width=width,
                    height=height
                )
                
                # Detect faces
                face_locations, face_encodings, confidences = detector.detect_faces(file_path)
                
                # Store face data
                for i, (location, encoding, confidence) in enumerate(zip(face_locations, face_encodings, confidences)):
                    top, right, bottom, left = location
                    db.add_face(
                        photo_id=photo_id,
                        embedding=encoding,
                        top=top,
                        right=right,
                        bottom=bottom,
                        left=left,
                        confidence=confidence
                    )
                
                # Mark photo as processed
                db.mark_photo_processed(photo_id, len(face_locations))
                
                # Update statistics
                total_files_processed += 1
                total_faces_detected += len(face_locations)
                
                # Update progress bar stats
                pbar.set_description(f"Scanning photos (👤 {total_faces_detected} faces found)")
                
                # Update scan progress in database (checkpoint every 10 files)
                if total_files_processed % 10 == 0:
                    db.update_scan_progress(
                        directory=root_dir,
                        last_path=file_path,
                        files_scanned=total_files_processed,
                        faces_detected=total_faces_detected
                    )
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                errors += 1
            
            pbar.update(1)
    
    # Mark scan as complete
    db.mark_scan_complete(root_dir)
    
    # Print final statistics
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        f"[bold green]✅ Scan Complete![/bold green]\n\n"
        f"📊 Files Processed: [cyan]{total_files_processed}[/cyan]\n"
        f"👤 Faces Detected: [cyan]{total_faces_detected}[/cyan]\n"
        f"❌ Errors: [red]{errors}[/red]\n"
        f"📈 Average: [yellow]{total_faces_detected/max(total_files_processed, 1):.2f}[/yellow] faces per photo",
        title="📈 Results"
    ))
    
    # Print overall database stats
    stats = db.get_stats()
    console.print(Panel.fit(
        f"[bold cyan]Database Statistics[/bold cyan]\n\n"
        f"📸 Total Photos: [yellow]{stats['total_photos']}[/yellow]\n"
        f"✓ Processed: [green]{stats['processed_photos']}[/green]\n"
        f"👥 Total Faces: [yellow]{stats['total_faces']}[/yellow]\n"
        f"🏷️  Clusters: [yellow]{stats['total_clusters']}[/yellow]\n"
        f"📛 Named Clusters: [green]{stats['named_clusters']}[/green]",
        title="💾 Database"
    ))
    
    console.print("\n[bold green]✨ Next step: Run cluster_faces.py to group similar faces together![/bold green]\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scan photos and detect faces')
    parser.add_argument('--path', type=str, help='Path to photos directory', default=None)
    parser.add_argument('--no-resume', action='store_true', help='Disable resume mode (reprocess all)')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size for processing')
    
    args = parser.parse_args()
    
    try:
        scan_photos(root_dir=args.path, resume=not args.no_resume, batch_size=args.batch_size)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Scan interrupted by user. Progress has been saved![/yellow]")
        console.print("[green]💡 You can resume by running the script again.[/green]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        logger.exception("Fatal error during scan")
        sys.exit(1)
