import os
import sys
from pathlib import Path
from typing import Union, Dict, Any
import numpy as np
import cv2
from deepface import DeepFace


class FaceVerification:
    def __init__(
        self,
        model_name: str = 'Facenet512',
        detector_backend: str = 'opencv',
        distance_metric: str = 'euclidean_l2',
        enforce_detection: bool = True
    ):
        """
        Initializes the FaceVerification module.
        
        Args:
            model_name (str): The face recognition model to use (default: 'Facenet512').
            detector_backend (str): The face detector to use (default: 'opencv').
            distance_metric (str): Metric for comparison (default: 'euclidean_l2').
            enforce_detection (bool): If True, raises an error if a face cannot be detected.
        """
        self.model_name = model_name
        self.detector_backend = detector_backend
        self.distance_metric = distance_metric
        self.enforce_detection = enforce_detection

    def _prepare_image_input(self, img: Union[str, Path, np.ndarray], label: str = "Image") -> np.ndarray:
        """
        Validates and converts image input to a numpy array.
        Loading it manually prevents Windows path escape issues inside DeepFace.
        """
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

    def _extract_dominant_face(self, img: np.ndarray, label: str = "Image") -> tuple[np.ndarray, Any, list, dict, int]:
        """
        Extracts the largest / dominant face from an image,
        with multi-orientation fallback (0°, 90° CW, 180°, 90° CCW).
        Crops with 15% margin to prevent background noise, watermarks, or stamps from interfering.
        
        Returns:
            (cropped_img, dominant_fa, all_detected_faces, image_dimensions, rotation_angle)
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
                faces = DeepFace.extract_faces(
                    img_path=cur_img,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                    align=False
                )
            except Exception:
                faces = []

            # Filter faces with valid dimensions and confidence
            valid = [
                f for f in faces
                if f.get('confidence', 0) > 0.5
                and f.get('facial_area', {}).get('w', 0) >= 30
                and f.get('facial_area', {}).get('h', 0) >= 30
            ]

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
            return img, None, [], dims, 0

        # Sort by bounding box area (w * h) descending -> dominant face is largest
        best_faces.sort(key=lambda f: f['facial_area']['w'] * f['facial_area']['h'], reverse=True)
        dominant = best_faces[0]
        fa = dominant['facial_area']

        all_detected = [
            {
                "facial_area": {
                    "x": int(f['facial_area']['x']),
                    "y": int(f['facial_area']['y']),
                    "w": int(f['facial_area']['w']),
                    "h": int(f['facial_area']['h'])
                },
                "confidence": round(float(f.get('confidence', 1.0)), 4)
            }
            for f in best_faces
        ]

        # Crop with 15% padding
        pad_w = int(fa['w'] * 0.15)
        pad_h = int(fa['h'] * 0.15)
        x1 = max(0, fa['x'] - pad_w)
        y1 = max(0, fa['y'] - pad_h)
        x2 = min(w, fa['x'] + fa['w'] + pad_w)
        y2 = min(h, fa['y'] + fa['h'] + pad_h)

        cropped = best_img[y1:y2, x1:x2]
        return (cropped if cropped.size > 0 else best_img), fa, all_detected, dims, best_angle

    def verify_identity(
        self, 
        person_image: Union[str, Path, np.ndarray], 
        document_image: Union[str, Path, np.ndarray],
        strictness: int = 50
    ) -> Dict[str, Any]:
        """
        Compares the face in the person_image with the face in the document_image.
        
        Args:
            person_image: File path or numpy BGR array of the live person / selfie.
            document_image: File path or numpy BGR array of the document ID photo.
            strictness: Integer from 0 to 100. 50 is default threshold. 100 is very strict. 0 is loose.
            
        Returns:
            dict: Verification results with face boxes and raw diagnostic data
        """
        try:
            img1 = self._prepare_image_input(person_image, "Person image")
            img2 = self._prepare_image_input(document_image, "Document image")

            # Extract dominant face crops to eliminate passport micro-watermarks or ghost artifacts
            face_person, fa_person, faces_person, dims_person, rot_person = self._extract_dominant_face(img1, "Person image")
            face_doc, fa_doc, faces_doc, dims_doc, rot_doc = self._extract_dominant_face(img2, "Document image")

            result = DeepFace.verify(
                img1_path=face_person,
                img2_path=face_doc,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                distance_metric=self.distance_metric,
                enforce_detection=False,
                align=True
            )

            # Convert numpy types to native Python types for JSON compatibility
            distance = float(result.get('distance', 1.0))
            
            # Default calibrated threshold
            if self.distance_metric == 'euclidean_l2' and 'threshold' not in result:
                base_threshold = 1.0400
            else:
                base_threshold = float(result.get('threshold', 1.0400 if self.distance_metric == 'euclidean_l2' else 0.40))
            
            # Apply strictness modifier:
            # strictness = 50 -> modifier = 1.00 (base threshold, e.g. 1.04)
            # strictness = 100 -> modifier = 0.85 (strict threshold, e.g. 0.884)
            # strictness = 0 -> modifier = 1.15 (loose threshold, e.g. 1.196)
            modifier = 1.0 + ((50 - strictness) / 50.0) * 0.15
            threshold = base_threshold * modifier
            
            is_match = distance <= threshold

            # Calibrated trust score (0 to 100)
            safe_thresh = max(threshold, 1e-6)
            if distance <= safe_thresh:
                # Range [0, threshold] maps to [100, 50]
                trust_score = 100.0 - ((distance / safe_thresh) * 50.0)
            else:
                # Range [threshold, threshold + 0.40] maps to [50, 0]
                excess = distance - safe_thresh
                trust_score = max(0.0, 50.0 - (excess / 0.40) * 50.0)

            trust_score = round(max(0.0, min(100.0, float(trust_score))), 2)

            return {
                'is_match': bool(is_match),
                'trust_score': trust_score,
                'distance': round(distance, 4),
                'threshold': round(threshold, 4),
                'base_threshold': round(base_threshold, 4),
                'strictness': strictness,
                'model': self.model_name,
                'detector_backend': self.detector_backend,
                'distance_metric': self.distance_metric,
                'detected_faces': {
                    'person': faces_person,
                    'document': faces_doc
                },
                'facial_areas': {
                    'person': {
                        'x': int(fa_person['x']),
                        'y': int(fa_person['y']),
                        'w': int(fa_person['w']),
                        'h': int(fa_person['h'])
                    } if fa_person else None,
                    'document': {
                        'x': int(fa_doc['x']),
                        'y': int(fa_doc['y']),
                        'w': int(fa_doc['w']),
                        'h': int(fa_doc['h'])
                    } if fa_doc else None
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
                    'distance': round(distance, 4),
                    'threshold': round(threshold, 4),
                    'base_threshold': round(base_threshold, 4),
                    'strictness_modifier': round(modifier, 4),
                    'verified': bool(is_match),
                    'model': self.model_name,
                    'detector': self.detector_backend,
                    'metric': self.distance_metric
                },
                'error': None
            }

        except ValueError as e:
            real_error = str(e)
            if hasattr(e, '__cause__') and e.__cause__:
                real_error += f" | Cause: {str(e.__cause__)}"
            
            return {
                'is_match': False,
                'trust_score': 0.0,
                'distance': None,
                'threshold': None,
                'model': self.model_name,
                'detector_backend': self.detector_backend,
                'distance_metric': self.distance_metric,
                'detected_faces': {'person': [], 'document': []},
                'facial_areas': None,
                'image_dimensions': None,
                'raw_verification': None,
                'error': f"Face detection failed: {real_error}"
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'is_match': False,
                'trust_score': 0.0,
                'distance': None,
                'threshold': None,
                'model': self.model_name,
                'detector_backend': self.detector_backend,
                'distance_metric': self.distance_metric,
                'detected_faces': {'person': [], 'document': []},
                'facial_areas': None,
                'image_dimensions': None,
                'raw_verification': None,
                'error': str(e)
            }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlephNull Face Verification Module")
    parser.add_argument("person_img", nargs="?", help="Path to person/selfie image")
    parser.add_argument("document_img", nargs="?", help="Path to document ID image")
    parser.add_argument("--model", default="Facenet512", help="Face recognition model (default: Facenet512)")
    parser.add_argument("--detector", default="opencv", help="Face detector backend (default: opencv)")
    parser.add_argument("--metric", default="euclidean_l2", help="Distance metric (default: euclidean_l2)")
    parser.add_argument("--strictness", type=int, default=50, help="Strictness 0-100 (default: 50)")
    parser.add_argument("--no-enforce", action="store_false", dest="enforce", help="Do not enforce face detection")

    args = parser.parse_args()

    if args.person_img and args.document_img:
        verifier = FaceVerification(
            model_name=args.model,
            detector_backend=args.detector,
            distance_metric=args.metric,
            enforce_detection=args.enforce
        )
        print(f"Comparing: {args.person_img} vs {args.document_img}")
        res = verifier.verify_identity(args.person_img, args.document_img, strictness=args.strictness)
        print("\n--- Verification Result ---")
        for k, v in res.items():
            print(f"  {k}: {v}")
    else:
        print("AlephNull Face Verification Module ready.")
        print("Usage: python main.py <person_image_path> <document_image_path> [--model MODEL] [--detector DETECTOR] [--metric METRIC] [--strictness 0-100]")
