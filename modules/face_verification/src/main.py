import os
import cv2
from deepface import DeepFace

class FaceVerification:
    def __init__(self, model_name='VGG-Face', detector_backend='opencv', enforce_detection=True):
        """
        Initializes the FaceVerification module.
        
        Args:
            model_name (str): The face recognition model to use (e.g., 'VGG-Face', 'Facenet', 'ArcFace').
            detector_backend (str): The face detector to use (e.g., 'opencv', 'retinaface', 'mtcnn').
            enforce_detection (bool): If True, throws an exception if no face is detected.
        """
        self.model_name = model_name
        self.detector_backend = detector_backend
        self.enforce_detection = enforce_detection

    def verify_identity(self, person_image_path, document_image_path):
        """
        Compares the face in the person_image with the face in the document_image.
        
        Returns:
            dict: Verification results including 'is_match', 'trust_score' (0-100), and 'distance'.
        """
        if not os.path.exists(person_image_path):
            raise FileNotFoundError(f"Person image not found: {person_image_path}")
        if not os.path.exists(document_image_path):
            raise FileNotFoundError(f"Document image not found: {document_image_path}")

        try:
            # DeepFace.verify extracts faces and compares them
            result = DeepFace.verify(
                img1_path=person_image_path,
                img2_path=document_image_path,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=self.enforce_detection
            )
            
            # Extract metrics
            is_match = result.get('verified', False)
            distance = result.get('distance', 1.0)
            threshold = result.get('threshold', 1.0)
            
            # Calculate a normalized trust score (0 to 100)
            # The closer distance is to 0, the better the match.
            # If distance > threshold, they don't match, score should drop.
            if distance <= threshold:
                # Map [0, threshold] to [100, 50]
                trust_score = 100 - ( (distance / threshold) * 50 )
            else:
                # Map [threshold, max_dist] to [50, 0]
                max_dist = threshold * 2
                if distance >= max_dist:
                    trust_score = 0
                else:
                    trust_score = 50 - ( ((distance - threshold) / (max_dist - threshold)) * 50 )
                    
            trust_score = max(0.0, min(100.0, trust_score))
            
            return {
                'is_match': is_match,
                'trust_score': round(trust_score, 2),
                'distance': distance,
                'threshold': threshold
            }
            
        except ValueError as e:
            # Raised if enforce_detection is True and no face is found
            print(f"Face detection failed: {e}")
            return {
                'is_match': False,
                'trust_score': 0.0,
                'error': str(e)
            }
        except Exception as e:
            print(f"An error occurred during verification: {e}")
            return {
                'is_match': False,
                'trust_score': 0.0,
                'error': str(e)
            }
