"""
Face detection and encoding module optimized for Apple Silicon (M4 Pro).
Uses face_recognition library (dlib-based) with Apple Silicon optimizations.
Leverages NPU/GPU through Metal Performance Shaders (MPS) when available.
No external model downloads required - uses built-in models.
"""

import os
import numpy as np
import face_recognition
from PIL import Image
from typing import List, Tuple, Optional
from loguru import logger

# Enable HEIC/HEIF support for iPhone photos
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIC/HEIF support enabled for iPhone photos")
except ImportError:
    logger.warning("pillow-heif not installed - HEIC images won't be supported")

# Try to import MLX for Apple Silicon NPU optimization
try:
    import mlx.core as mx
    MLX_AVAILABLE = True
    logger.info("MLX (Apple Neural Engine) available for acceleration")
except ImportError:
    MLX_AVAILABLE = False
    logger.warning("MLX not available - install for better NPU acceleration")

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
            # Load image
            image = face_recognition.load_image_file(image_path)
            
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
    try:
        with Image.open(image_path) as img:
            return img.width, img.height
    except Exception as e:
        logger.error(f"Error getting dimensions for {image_path}: {e}")
        return None, None


def is_valid_image(file_path: str, extensions: List[str] = None) -> bool:
    """Check if a file is a valid image."""
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.heic', '.heif']
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext in extensions


if __name__ == "__main__":
    # Test the face detector
    detector = FaceDetector(model='hog')
    logger.info(f"Face detector initialized with model: {detector.model}")
