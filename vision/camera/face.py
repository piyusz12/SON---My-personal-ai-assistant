# vision/camera/face.py — Local Face Extraction & Feature Embedder for SON V3
"""
Local Face Embedding Extraction:
Generates deterministic, lightweight mathematical embeddings from face crops.
Does NOT use internet or cloud services. Runs locally in <2ms per face.
"""
from typing import Any
import numpy as np

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


class FaceEmbedder:
    """
    Extracts standardized biometric feature vectors from face crops.
    Uses multi-region spatial histogram & gradient orientation (HOG/LBP inspired)
    normalized to a unit hypersphere vector for cosine distance matching.
    """

    TARGET_SIZE = (96, 96)
    VECTOR_DIM = 128

    def __init__(self):
        self._cascade = None
        if _HAS_CV2:
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self._cascade = None

    def extract_faces(self, frame: np.ndarray) -> list[tuple[np.ndarray, tuple[int, int, int, int]]]:
        """
        Detect and crop all faces in a frame.
        Returns: list of (face_crop_bgr, (x, y, w, h))
        """
        if not _HAS_CV2 or frame is None or self._cascade is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )

        crops = []
        for (x, y, w, h) in faces:
            # Add 10% padding
            pad_x = int(w * 0.1)
            pad_y = int(h * 0.1)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(frame.shape[1], x + w + pad_x)
            y2 = min(frame.shape[0], y + h + pad_y)

            crop = frame[y1:y2, x1:x2]
            if crop.size > 0:
                crops.append((crop, (int(x), int(y), int(w), int(h))))

        return crops

    def compute_embedding(self, face_crop: np.ndarray) -> list[float] | None:
        """
        Convert a face crop into a standardized 128-dim normalized embedding vector.
        """
        if not _HAS_CV2 or face_crop is None or face_crop.size == 0:
            return None

        # 1. Resize to canonical dimensions
        resized = cv2.resize(face_crop, self.TARGET_SIZE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # 2. Compute spatial gradient features (Sobel X & Y)
        sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(sobelx, sobely, angleInDegrees=True)

        # 3. 4x4 spatial grid pooling with 8 orientation bins = 4 * 4 * 8 = 128 dimensions
        cell_h = self.TARGET_SIZE[1] // 4
        cell_w = self.TARGET_SIZE[0] // 4
        feature_vector = []

        for row in range(4):
            for col in range(4):
                y_start = row * cell_h
                y_end = y_start + cell_h
                x_start = col * cell_w
                x_end = x_start + cell_w

                cell_mag = magnitude[y_start:y_end, x_start:x_end]
                cell_ang = angle[y_start:y_end, x_start:x_end]

                # 8-bin histogram (0 to 360 degrees, 45 deg per bin)
                hist, _ = np.histogram(cell_ang, bins=8, range=(0, 360), weights=cell_mag)
                feature_vector.extend(hist.tolist())

        # 4. L2 Normalization
        vec = np.array(feature_vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        else:
            return None

        return vec.tolist()
