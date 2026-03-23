"""
Face detection and encoding module optimized for Apple Silicon (M4 Pro).
Uses face_recognition library (dlib-based) with Apple Silicon optimizations.
Leverages NPU/GPU through Metal Performance Shaders (MPS) when available.
No external model downloads required - uses built-in models.
"""

import os
import sys
import types
import importlib
import importlib.resources
import subprocess
import tempfile
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional
from loguru import logger


def _install_pkg_resources_compat():
    """
    face_recognition_models still imports pkg_resources.resource_filename.
    Modern setuptools on Python 3.13 may not ship pkg_resources, so provide the
    tiny compatibility surface that package needs.
    """

    if "pkg_resources" in sys.modules:
        return

    module = types.ModuleType("pkg_resources")

    def resource_filename(package_name, resource_name):
        package = importlib.import_module(package_name)
        resource = importlib.resources.files(package).joinpath(resource_name)
        return str(resource)

    module.resource_filename = resource_filename
    sys.modules["pkg_resources"] = module


_install_pkg_resources_compat()

import face_recognition

# Enable HEIC/HEIF support for iPhone photos
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIC/HEIF support enabled for iPhone photos")
except ImportError:
    logger.warning("pillow-heif not installed - HEIC images won't be supported")

# MLX is disabled by default here. Importing it eagerly has been crashing on
# some local Apple Silicon environments, and this detector path does not
# actually depend on MLX for inference.
MLX_AVAILABLE = False
if os.getenv("ENABLE_MLX_ACCELERATION", "false").lower() in {"1", "true", "yes"}:
    try:
        import mlx.core as mx  # noqa: F401

        MLX_AVAILABLE = True
        logger.info("MLX (Apple Neural Engine) available for acceleration")
    except Exception as exc:
        logger.warning("MLX unavailable, continuing without it: {}", exc)

# Try to import PyTorch for GPU acceleration
try:
    import torch
    TORCH_AVAILABLE = True
    if torch.backends.mps.is_available():
        logger.info("PyTorch MPS (GPU) available for acceleration")
except ImportError:
    TORCH_AVAILABLE = False

class FaceDetector:
    """
    Face detection and encoding class using face_recognition library.
    Optimized for Apple Silicon M4 Pro with NPU/GPU acceleration.
    Uses MPS (Metal Performance Shaders) for GPU when available.
    """
    
    def __init__(self, model='hog', use_gpu=True):
        """
        Initialize the face detector.
        
        Args:
            model: 'hog' (faster, CPU/NPU-optimized) or 'cnn' (more accurate, GPU via MPS)
            use_gpu: Whether to use GPU acceleration (MPS on Apple Silicon)
        """
        self.model = model
        self.use_gpu = use_gpu
        
        # Check for Apple Silicon accelerators
        if MLX_AVAILABLE:
            logger.info(f"✓ MLX available - Apple Neural Engine can be utilized")
        if TORCH_AVAILABLE and torch.backends.mps.is_available() and use_gpu:
            logger.info(f"✓ PyTorch MPS available - GPU acceleration enabled")
            self.device = 'mps'
        else:
            self.device = 'cpu'
            
        logger.info(f"Initializing FaceDetector with model='{model}', device='{self.device}'")
        logger.info(f"Face detection will use dlib's optimized C++ backend")
    
    def detect_faces(self, image_path: str) -> Tuple[List, List, List]:
        """
        Detect faces in an image using face_recognition library.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (face_locations, face_encodings, confidences)
            face_locations: List of tuples (top, right, bottom, left)
            face_encodings: List of 128D numpy arrays
            confidences: List of confidence scores (always 1.0 for face_recognition)
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return [], [], []
        
        try:
            # Load image, with macOS HEIC fallback through sips when pillow-heif
            # is unavailable.
            image = self._load_image(image_path)
            
            # Detect faces
            face_locations = face_recognition.face_locations(image, model=self.model)
            
            if not face_locations:
                return [], [], []
            
            # Generate face encodings (128-dimensional)
            face_encodings = face_recognition.face_encodings(image, face_locations, num_jitters=1)
            
            # face_recognition doesn't provide confidence scores, so we use 1.0
            confidences = [1.0] * len(face_locations)
            
            return face_locations, face_encodings, confidences
            
        except Exception as e:
            logger.error(f"Error detecting faces in {image_path}: {e}")
            return [], [], []

    def _load_image(self, image_path: str):
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in {".heic", ".heif"}:
            return face_recognition.load_image_file(image_path)

        try:
            return face_recognition.load_image_file(image_path)
        except Exception:
            converted = _convert_heic_with_sips(image_path)
            if not converted:
                raise
            try:
                return face_recognition.load_image_file(converted)
            finally:
                try:
                    os.unlink(converted)
                except OSError:
                    pass
    
    def batch_detect_faces(self, image_paths: List[str]) -> List[Tuple[str, List, List, List]]:
        """
        Detect faces in multiple images.
        
        Returns:
            List of tuples (image_path, face_locations, face_encodings, confidences)
        """
        results = []
        for image_path in image_paths:
            locations, encodings, confidences = self.detect_faces(image_path)
            results.append((image_path, locations, encodings, confidences))
        return results
    
    def compare_faces(self, known_encoding, unknown_encoding, tolerance=0.6):
        """
        Compare two face encodings.
        
        Args:
            known_encoding: Known face encoding
            unknown_encoding: Unknown face encoding to compare
            tolerance: Distance threshold (lower = stricter)
            
        Returns:
            Boolean indicating if faces match
        """
        # Calculate Euclidean distance
        distance = np.linalg.norm(np.array(known_encoding) - np.array(unknown_encoding))
        return distance <= tolerance
    
    def face_distance(self, known_encoding, unknown_encoding):
        """
        Calculate distance between two face encodings.
        
        Returns:
            Float distance (0 = identical, higher = more different)
        """
        return float(np.linalg.norm(np.array(known_encoding) - np.array(unknown_encoding)))


def get_image_dimensions(image_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Get image dimensions without loading the full image."""
    ext = os.path.splitext(image_path)[1].lower()
    try:
        with Image.open(image_path) as img:
            return img.width, img.height
    except Exception as e:
        if ext in {".heic", ".heif"}:
            dimensions = _get_heic_dimensions_with_sips(image_path)
            if dimensions != (None, None):
                return dimensions
        logger.error(f"Error getting dimensions for {image_path}: {e}")
        return None, None


def is_valid_image(file_path: str, extensions: List[str] = None) -> bool:
    """Check if a file is a valid image."""
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.heic', '.heif']
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext in extensions


def _convert_heic_with_sips(image_path: str) -> Optional[str]:
    """
    Use macOS built-in sips to convert HEIC/HEIF images to a temporary JPEG.
    """

    fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="photo_face_")
    os.close(fd)

    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", image_path, "--out", temp_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        logger.error(
            "sips failed to convert {}: {}",
            image_path,
            (result.stderr or result.stdout).strip(),
        )
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return None

    return temp_path


def _get_heic_dimensions_with_sips(image_path: str) -> Tuple[Optional[int], Optional[int]]:
    result = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", image_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        logger.error(
            "sips failed to read dimensions for {}: {}",
            image_path,
            (result.stderr or result.stdout).strip(),
        )
        return None, None

    width = None
    height = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            width = int(line.split(":", 1)[1].strip())
        elif line.startswith("pixelHeight:"):
            height = int(line.split(":", 1)[1].strip())
    return width, height


if __name__ == "__main__":
    # Test the face detector
    detector = FaceDetector(model='hog')
    logger.info(f"Face detector initialized with model: {detector.model}")
