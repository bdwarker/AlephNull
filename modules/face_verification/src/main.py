"""
AlephNull — Face Verification Module
====================================
Uses native InsightFace (ONNX) with ArcFace 512D embeddings and RetinaFace detection
to perform 1:1 facial biometric matching between person and ID document photos.
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, Any, Optional
import numpy as np
import cv2
from numpy.linalg import norm
import insightface
from insightface.app import FaceAnalysis

# Safe UTF-8 console output for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Global cache for InsightFace FaceAnalysis models to prevent redundant reloading
_INSIGHTFACE_CACHE: Dict[str, FaceAnalysis] = {}


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [FACE] {msg}", flush=True)


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
        Initializes FaceVerification using native InsightFace ONNX models.
        """
        if model_name in ('Facenet512', 'VGG-Face', 'ArcFace', 'GhostFaceNet', 'facenet'):
            model_name = 'buffalo_l'

        self.model_name = model_name
        self.enforce_detection = enforce_detection

        global _INSIGHTFACE_CACHE
        if self.model_name in _INSIGHTFACE_CACHE:
            _log(f"Reusing cached InsightFace model: {self.model_name}")
            self.app = _INSIGHTFACE_CACHE[self.model_name]
        else:
            _log(f"Loading InsightFace FaceAnalysis ('{self.model_name}')...")
            start_t = time.time()
            self.app = FaceAnalysis(name=self.model_name, providers=['CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.35)
            _INSIGHTFACE_CACHE[self.model_name] = self.app
            _log(f"InsightFace models ready in {time.time() - start_t:.2f}s.")

    def _prepare_image_input(self, img: Union[str, Path, np.ndarray], label: str = "Image") -> np.ndarray:
        if isinstance(img, (str, Path)):
            path_str = str(Path(img).resolve())
            if not os.path.exists(path_str):
                raise FileNotFoundError(f"{label} file not found: {path_str}")
            image = cv2.imread(path_str)
            if image is None:
                raise ValueError(f"Could not decode {label} from path: {path_str}")
            return image
        elif isinstance(img, np.ndarray):
            if img.size == 0:
                raise ValueError(f"{label} numpy array is empty.")
            return img
        else:
            raise TypeError(f"{label} must be a file path or numpy.ndarray, got {type(img).__name__}")

    def _extract_dominant_face(self, img: np.ndarray, label: str = "Image") -> tuple[Any, list, dict, int]:
        rotations = [
            (0, None),
            (90, cv2.ROTATE_90_CLOCKWISE),
            (180, cv2.ROTATE_180),
            (270, cv2.ROTATE_90_COUNTERCLOCKWISE)
        ]

        best_faces = []
        best_img = img
        best_angle = 0

        # Pass 1: Standard 640x640 detection across rotations (threshold 0.35)
        self.app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.35)
        for angle, rot_code in rotations:
            cur_img = img if rot_code is None else cv2.rotate(img, rot_code)
            try:
                faces = self.app.get(cur_img)
            except Exception:
                faces = []

            valid = [f for f in faces if getattr(f, 'det_score', 0) >= 0.35]
            if valid:
                best_faces = valid
                best_img = cur_img
                best_angle = angle
                break

        # Pass 2: Multi-scale fallback for tight crops and small faces
        if not best_faces:
            for fallback_size in [(480, 480), (320, 320)]:
                self.app.prepare(ctx_id=0, det_size=fallback_size, det_thresh=0.30)
                for angle, rot_code in rotations:
                    cur_img = img if rot_code is None else cv2.rotate(img, rot_code)
                    try:
                        faces = self.app.get(cur_img)
                    except Exception:
                        faces = []
                    valid = [f for f in faces if getattr(f, 'det_score', 0) >= 0.30]
                    if valid:
                        best_faces = valid
                        best_img = cur_img
                        best_angle = angle
                        break
                if best_faces:
                    break

        # Pass 3: Edge-padding fallback if face touches image borders
        if not best_faces:
            h, w = img.shape[:2]
            pad_h, pad_w = int(h * 0.15), int(w * 0.15)
            padded = cv2.copyMakeBorder(img, pad_h, pad_h, pad_w, pad_w, cv2.BORDER_REFLECT)
            self.app.prepare(ctx_id=0, det_size=(480, 480), det_thresh=0.25)
            try:
                faces = self.app.get(padded)
            except Exception:
                faces = []
            valid = [f for f in faces if getattr(f, 'det_score', 0) >= 0.25]
            if valid:
                for f in valid:
                    f.bbox[0] = max(0, f.bbox[0] - pad_w)
                    f.bbox[1] = max(0, f.bbox[1] - pad_h)
                    f.bbox[2] = min(w, f.bbox[2] - pad_w)
                    f.bbox[3] = min(h, f.bbox[3] - pad_h)
                best_faces = valid
                best_img = img
                best_angle = 0

        h, w = best_img.shape[:2]
        dims = {"width": int(w), "height": int(h)}

        if not best_faces:
            if self.enforce_detection:
                raise ValueError(f"No face detected in {label}. Please ensure the face is visible, uncovered, and well-lit.")
            return None, [], dims, 0

        # Sort by bounding box area descending
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
        strictness: int = 20
    ) -> Dict[str, Any]:
        start_time = time.time()
        _log("=" * 60)
        _log("STARTING 1:1 BIOMETRIC FACE VERIFICATION")
        _log(f"Person image  : {person_image}")
        _log(f"Document image: {document_image}")
        _log(f"Strictness    : {strictness}/100 | Model: {self.model_name}")

        try:
            img1 = self._prepare_image_input(person_image, "Person image")
            img2 = self._prepare_image_input(document_image, "Document image")

            _log("Detecting dominant face in Person selfie...")
            face_person, faces_person, dims_person, rot_person = self._extract_dominant_face(img1, "Person image")
            _log(f"Person face found: area {face_person.bbox.astype(int).tolist()} (confidence: {float(face_person.det_score):.3f}, rotation: {rot_person} deg)")

            _log("Detecting dominant face in Document ID crop...")
            face_doc, faces_doc, dims_doc, rot_doc = self._extract_dominant_face(img2, "Document image")
            _log(f"Document face found: area {face_doc.bbox.astype(int).tolist()} (confidence: {float(face_doc.det_score):.3f}, rotation: {rot_doc} deg)")

            # Compute Cosine Similarity between 512-d ArcFace embeddings
            emb1 = face_person.embedding
            emb2 = face_doc.embedding

            sim = float(np.dot(emb1, emb2) / (norm(emb1) * norm(emb2)))
            distance = 1.0 - sim

            base_sim_threshold = 0.45
            modifier = ((strictness - 50) / 50.0) * 0.15
            sim_threshold = base_sim_threshold + modifier

            is_match = sim >= sim_threshold

            # Calibrated trust score (0 to 100)
            if sim >= sim_threshold:
                range_size = 1.0 - sim_threshold
                trust_score = 50.0 + ((sim - sim_threshold) / range_size) * 50.0 if range_size > 0 else 100.0
            else:
                trust_score = (max(0.0, sim) / sim_threshold) * 50.0 if sim_threshold > 0 else 0.0

            trust_score = round(max(0.0, min(100.0, float(trust_score))), 2)

            def extract_fa(face_obj):
                if not face_obj:
                    return None
                bbox = face_obj.bbox
                return {
                    'x': int(bbox[0]), 'y': int(bbox[1]),
                    'w': int(bbox[2] - bbox[0]), 'h': int(bbox[3] - bbox[1])
                }

            fa_person = extract_fa(face_person)
            fa_doc = extract_fa(face_doc)

            verdict_str = "MATCH (IDENTICAL)" if is_match else "NO MATCH (DISCREPANCY)"
            dur = time.time() - start_time
            _log(f"Similarity: {sim:.4f} (Required Threshold: {sim_threshold:.4f}, Cosine Dist: {distance:.4f})")
            _log(f"VERDICT   : {verdict_str} | Calibrated Trust Score: {trust_score}/100")
            _log(f"FACE VERIFICATION FINISHED in {dur:.2f}s")
            _log("=" * 60)

            return {
                'is_match': bool(is_match),
                'trust_score': trust_score,
                'distance': round(distance, 4),
                'similarity': round(sim, 4),
                'threshold': round(1.0 - sim_threshold, 4),
                'sim_threshold': round(sim_threshold, 4),
                'base_threshold': round(1.0 - base_sim_threshold, 4),
                'strictness': strictness,
                'model': self.model_name,
                'detector_backend': 'retinaface',
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
                'processing_time_ms': round((time.time() - start_time) * 1000, 1),
                'error': None
            }

        except ValueError as e:
            real_error = str(e)
            if hasattr(e, '__cause__') and e.__cause__:
                real_error += f" | Cause: {str(e.__cause__)}"
            _log(f"Face verification validation error: {real_error}")
            return self._error_response(f"Face detection failed: {real_error}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            _log(f"Unexpected error in face verification: {e}")
            return self._error_response(str(e))

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        _log(f"Returning face verification error: {error_msg}")
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

    parser = argparse.ArgumentParser(description="AlephNull Face Verification Module")
    parser.add_argument("person_img", nargs="?", help="Path to person/selfie image")
    parser.add_argument("document_img", nargs="?", help="Path to document ID image")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model pack (default: buffalo_l)")
    parser.add_argument("--strictness", type=int, default=20, help="Strictness 0-100 (default: 20)")

    args = parser.parse_args()

    if args.person_img and args.document_img:
        verifier = FaceVerification(model_name=args.model)
        res = verifier.verify_identity(args.person_img, args.document_img, strictness=args.strictness)
        print(json.dumps(res, indent=2))
    else:
        print("AlephNull Face Verification Module ready.")
