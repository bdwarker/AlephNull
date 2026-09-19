import os
import sys
from pathlib import Path
from typing import Union, Dict, Any
import numpy as np
import cv2
import insightface
from insightface.app import FaceAnalysis
from numpy.linalg import norm

class FaceVerification:
    def __init__(
        self,
        model_name: str = 'buffalo_l',
        detector_backend: str = 'retinaface',
        distance_metric: str = 'cosine',
        enforce_detection: bool = True,
        *args, **kwargs
    ):
        """
        Initializes the FaceVerification module using native InsightFace (ONNX).
        
        Args:
            model_name (str): The InsightFace model pack to use (default: 'buffalo_l').
            detector_backend (str): Kept for API compatibility, uses retinaface internally.
            distance_metric (str): Kept for API compatibility, uses cosine distance internally.
            enforce_detection (bool): If True, raises an error if a face cannot be detected.
        """
        # Override the old DeepFace default if passed by the API
        if model_name == 'Facenet512':
            model_name = 'buffalo_l'
            
        self.model_name = model_name
        self.enforce_detection = enforce_detection
        
        # Initialize InsightFace FaceAnalysis pipeline
        # providers=['CPUExecutionProvider'] ensures it works natively on edge devices without CUDA
        self.app = FaceAnalysis(name=self.model_name, providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    def _prepare_image_input(self, img: Union[str, Path, np.ndarray], label: str = "Image") -> np.ndarray:
        if isinstance(img, (str, Path)):
            path_str = str(Path(img).resolve())
            if not os.path.exists(path_str):
                raise FileNotFoundError(f"{label} not found: {path_str}")
            image = cv2.imread(path_str)
            if image is None:
                raise ValueError(f"Could not read {label} from path: {path_str}")
            return image
        elif isinstance(img, np.ndarray):
            if img.size == 0:
                raise ValueError(f"{label} numpy array is empty.")
            return img
        else:
            raise TypeError(f"{label} must be a file path (str, Path) or a numpy.ndarray, got {type(img).__name__}")

    def _extract_dominant_face(self, img: np.ndarray, label: str = "Image") -> tuple[Any, list, dict, int]:
        """
        Extracts the dominant face from an image using InsightFace.
        Returns:
            (dominant_face_obj, all_detected_faces_info, image_dimensions, rotation_angle)
        """
        rotations = [
            (0, None),
            (90, cv2.ROTATE_90_CLOCKWISE),
            (180, cv2.ROTATE_180),
            (270, cv2.ROTATE_90_COUNTERCLOCKWISE)
        ]

        best_faces = []
        best_img = img
        best_angle = 0

        for angle, rot_code in rotations:
            cur_img = img if rot_code is None else cv2.rotate(img, rot_code)
            try:
                faces = self.app.get(cur_img)
            except Exception:
                faces = []

            # Filter faces with valid confidence
            valid = [f for f in faces if getattr(f, 'det_score', 0) > 0.5]

            if valid:
                best_faces = valid
                best_img = cur_img
                best_angle = angle
                break

        h, w = best_img.shape[:2]
        dims = {"width": int(w), "height": int(h)}

        if not best_faces:
            if self.enforce_detection:
                raise ValueError(f"No face detected in {label}. Please ensure the face is visible, uncovered, and well-lit.")
            return None, [], dims, 0

        # Sort by bounding box area (w * h) descending -> dominant face is largest
        def get_area(f):
            bbox = f.bbox
            return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            
        best_faces.sort(key=get_area, reverse=True)
        dominant = best_faces[0]

        all_detected = []
        for f in best_faces:
            bbox = f.bbox
            all_detected.append({
                "facial_area": {
                    "x": int(bbox[0]),
                    "y": int(bbox[1]),
                    "w": int(bbox[2] - bbox[0]),
                    "h": int(bbox[3] - bbox[1])
                },
                "confidence": round(float(f.det_score), 4)
            })

        return dominant, all_detected, dims, best_angle

    def verify_identity(
        self, 
        person_image: Union[str, Path, np.ndarray], 
        document_image: Union[str, Path, np.ndarray],
        strictness: int = 50
    ) -> Dict[str, Any]:
        """
        Compares the face in the person_image with the face in the document_image using InsightFace ONNX.
        """
        try:
            img1 = self._prepare_image_input(person_image, "Person image")
            img2 = self._prepare_image_input(document_image, "Document image")

            face_person, faces_person, dims_person, rot_person = self._extract_dominant_face(img1, "Person image")
            face_doc, faces_doc, dims_doc, rot_doc = self._extract_dominant_face(img2, "Document image")

            if not face_person or not face_doc:
                raise ValueError("Could not find a dominant face in one or both images.")

            # Compute Cosine Similarity between 512-d ArcFace embeddings
            emb1 = face_person.embedding
            emb2 = face_doc.embedding
            
            # cosine similarity
            sim = np.dot(emb1, emb2) / (norm(emb1) * norm(emb2))
            sim = float(sim)
            
            # Distance mapping (1 - sim) for output format compatibility
            distance = 1.0 - sim
            
            # InsightFace ArcFace typical match threshold is around ~0.45 similarity
            base_sim_threshold = 0.45
            
            # Apply strictness modifier to similarity:
            # strictness = 50 -> modifier = 0.0
            # strictness = 100 -> modifier = +0.15 (threshold 0.60, stricter)
            # strictness = 0 -> modifier = -0.15 (threshold 0.30, looser)
            modifier = ((strictness - 50) / 50.0) * 0.15
            sim_threshold = base_sim_threshold + modifier
            
            is_match = sim >= sim_threshold

            # Calibrated trust score (0 to 100) based on similarity
            if sim >= sim_threshold:
                # Map [sim_threshold, 1.0] to [50, 100]
                range_size = 1.0 - sim_threshold
                if range_size <= 0:
                    trust_score = 100.0
                else:
                    trust_score = 50.0 + ((sim - sim_threshold) / range_size) * 50.0
            else:
                # Map [0.0, sim_threshold] to [0, 50]
                if sim_threshold <= 0:
                    trust_score = 0.0
                else:
                    trust_score = (max(0.0, sim) / sim_threshold) * 50.0

            trust_score = round(max(0.0, min(100.0, float(trust_score))), 2)

            def extract_fa(face_obj):
                if not face_obj: return None
                bbox = face_obj.bbox
                return {
                    'x': int(bbox[0]), 'y': int(bbox[1]),
                    'w': int(bbox[2] - bbox[0]), 'h': int(bbox[3] - bbox[1])
                }

            fa_person = extract_fa(face_person)
            fa_doc = extract_fa(face_doc)

            return {
                'is_match': bool(is_match),
                'trust_score': trust_score,
                'distance': round(distance, 4), # using cosine distance for backwards compatibility
                'similarity': round(sim, 4), # native similarity
                'threshold': round(1.0 - sim_threshold, 4), # return as distance threshold
                'sim_threshold': round(sim_threshold, 4),
                'base_threshold': round(1.0 - base_sim_threshold, 4),
                'strictness': strictness,
                'model': self.model_name,
                'detector_backend': 'retinaface', # inherent to buffalo_l
                'distance_metric': 'cosine',
                'detected_faces': {
                    'person': faces_person,
                    'document': faces_doc
                },
                'facial_areas': {
                    'person': fa_person,
                    'document': fa_doc
                },
                'image_dimensions': {
                    'person': dims_person,
                    'document': dims_doc
                },
                'rotations': {
                    'person': rot_person,
                    'document': rot_doc
                },
                'raw_verification': {
                    'similarity': round(sim, 4),
                    'sim_threshold': round(sim_threshold, 4),
                    'strictness_modifier': round(modifier, 4),
                    'verified': bool(is_match),
                    'model': self.model_name,
                    'detector': 'retinaface',
                    'metric': 'cosine'
                },
                'error': None
            }

        except ValueError as e:
            real_error = str(e)
            if hasattr(e, '__cause__') and e.__cause__:
                real_error += f" | Cause: {str(e.__cause__)}"
            
            return self._error_response(f"Face detection failed: {real_error}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._error_response(str(e))
            
    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        return {
            'is_match': False,
            'trust_score': 0.0,
            'distance': None,
            'similarity': None,
            'threshold': None,
            'sim_threshold': None,
            'model': self.model_name,
            'detector_backend': 'retinaface',
            'distance_metric': 'cosine',
            'detected_faces': {'person': [], 'document': []},
            'facial_areas': None,
            'image_dimensions': None,
            'raw_verification': None,
            'error': error_msg
        }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlephNull Face Verification Module (InsightFace ONNX)")
    parser.add_argument("person_img", nargs="?", help="Path to person/selfie image")
    parser.add_argument("document_img", nargs="?", help="Path to document ID image")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack (default: buffalo_l)")
    parser.add_argument("--strictness", type=int, default=50, help="Strictness 0-100 (default: 50)")
    parser.add_argument("--no-enforce", action="store_false", dest="enforce", help="Do not enforce face detection")

    args = parser.parse_args()

    if args.person_img and args.document_img:
        verifier = FaceVerification(
            model_name=args.model,
            enforce_detection=args.enforce
        )
        print(f"Comparing: {args.person_img} vs {args.document_img}")
        res = verifier.verify_identity(args.person_img, args.document_img, strictness=args.strictness)
        print("\n--- Verification Result ---")
        for k, v in res.items():
            print(f"  {k}: {v}")
    else:
        print("AlephNull Face Verification Module ready.")
        print("Usage: python main.py <person_image_path> <document_image_path> [--model buffalo_l] [--strictness 0-100]")
