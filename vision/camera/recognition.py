# vision/camera/recognition.py — Local Opt-In Face Recognition for SON V3
"""
Face Recognition (Local & Opt-In):
- Matches detected face embeddings against the local SQLite database of enrolled people.
- Strictly local — no public/cloud biometric databases.
- Supports face enrollment workflow ("Add Person").
"""
from dataclasses import dataclass
from typing import Any
import numpy as np

from vision.camera.face import FaceEmbedder
from memory.structured_memory import StructuredMemory


@dataclass
class RecognitionMatch:
    person_id: str
    display_name: str
    confidence: float
    is_known: bool
    box: tuple[int, int, int, int] | None = None


class FaceRecognizer:
    """
    Performs opt-in face recognition against local enrolled biometric templates.
    """

    SIMILARITY_THRESHOLD = 0.78  # Cosine similarity cutoff for known match

    def __init__(self, structured_memory: StructuredMemory | None = None):
        self.embedder = FaceEmbedder()
        self.memory = structured_memory or StructuredMemory()

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def recognize_frame(self, frame: np.ndarray) -> list[RecognitionMatch]:
        """
        Detect and identify all faces present in the given frame.
        """
        if frame is None:
            return []

        enrolled_list = self.memory.get_enrolled_people(enabled_only=True)
        face_crops = self.embedder.extract_faces(frame)
        matches = []

        for crop, box in face_crops:
            emb = self.embedder.compute_embedding(crop)
            if emb is None:
                continue

            best_match = None
            highest_score = 0.0

            for enrolled in enrolled_list:
                enrolled_emb = enrolled.get("embedding")
                if not enrolled_emb:
                    continue

                sim = self._cosine_similarity(emb, enrolled_emb)
                if sim > highest_score:
                    highest_score = sim
                    best_match = enrolled

            if best_match and highest_score >= self.SIMILARITY_THRESHOLD:
                matches.append(RecognitionMatch(
                    person_id=best_match["person_id"],
                    display_name=best_match["display_name"],
                    confidence=round(highest_score, 2),
                    is_known=True,
                    box=box,
                ))
            else:
                matches.append(RecognitionMatch(
                    person_id="unknown",
                    display_name="Unknown Person",
                    confidence=round(highest_score, 2),
                    is_known=False,
                    box=box,
                ))

        return matches

    def identify_person_in_frame(self, frame: np.ndarray | None) -> tuple[bool, str]:
        """
        Human-friendly response generator for: 'Do you recognize this person?'
        """
        if frame is None:
            return False, "Camera is not available or is paused."

        matches = self.recognize_frame(frame)
        if not matches:
            return False, "I don't detect any face clearly in front of the camera right now."

        known_matches = [m for m in matches if m.is_known]
        if known_matches:
            names = ", ".join(f"{m.display_name} ({int(m.confidence * 100)}% confidence)" for m in known_matches)
            return True, f"I recognize: {names}."
        else:
            return False, f"I see someone, but they are not enrolled in my local recognition database."

    def enroll_face_from_frame(self, name: str, frame: np.ndarray) -> tuple[bool, str]:
        """
        Enroll a new authorized person from a camera frame.
        """
        if frame is None:
            return False, "Failed to capture camera frame."

        face_crops = self.embedder.extract_faces(frame)
        if not face_crops:
            return False, "No face detected in the frame. Please face the camera and try again."

        # Pick the largest face crop
        largest_crop = max(face_crops, key=lambda item: item[1][2] * item[1][3])[0]
        emb = self.embedder.compute_embedding(largest_crop)

        if emb is None:
            return False, "Failed to generate face embedding."

        person_id = name.lower().replace(" ", "_").strip()
        self.memory.enroll_person(person_id=person_id, display_name=name.strip(), embedding=emb)
        return True, f"Successfully enrolled {name.strip()} into local recognition database."
