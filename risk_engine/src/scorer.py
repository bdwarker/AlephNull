"""
Transparent weighted scoring model for cross-module risk signals (AlephNull Risk Engine).
Fulfills Problem Statement PS26188 (SIH 2024 / Sashastra Seema Bal).
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from .audit_log import write_audit_log

# Category Weights based on importance vs AI model accuracy
# - Biometric Face Match (45%): High importance for physical presenter binding; DeepFace FaceNet512.
# - Document Security & Checksums (35%): Critical mathematical certainty (ICAO 7-3-1, Verhoeff); 100% deterministic detection of forgeries.
# - Document Standards & Temporal Coherence (20%): Expiration status, legal driving age >= 18, RTO/ISO standard codes.
CATEGORY_WEIGHTS = {
    "biometric_face": {
        "weight": 0.45,
        "name": "Biometric Face Verification",
        "rationale": "Physical person-to-document binding via 512D FaceNet embeddings. Ensures the presenter is the legitimate holder."
    },
    "document_security": {
        "weight": 0.35,
        "name": "Document Security & Checksums",
        "rationale": "ICAO 9303 / Verhoeff mathematical check-digit verification. High-confidence filter for altered numbers and tampered MRZs."
    },
    "document_standards": {
        "weight": 0.20,
        "name": "Document Standards & Coherence",
        "rationale": "Format compliance, current expiration status, legal age constraints, and cross-field temporal logic."
    }
}


def score(signals: dict[str, float], weights: dict[str, float]) -> float:
    """Return transparent weighted score for the provided signals (backward compatibility)."""
    return sum(signals.get(k, 0.0) * weights.get(k, 0.0) for k in set(signals) | set(weights))


def consolidate_pipeline_scores(
    face_data: Dict[str, Any],
    doc_data: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
    audit_log_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Consolidates scores across Module 4 (Face Verification) and Module 2 (Document Validation).
    
    Weights each category based on:
    1. Operational importance for border screening (imposter detection vs document forgery).
    2. Deterministic accuracy of the AI/algorithmic verification methods.
    
    Returns explainable breakdown, consolidated score (0-100), risk level, and officer recommendation.
    """
    # 1. Extract Biometric Face Signal
    face_verif = face_data.get("verification") if isinstance(face_data.get("verification"), dict) else face_data
    face_score = float(face_verif.get("trust_score", 0.0) if face_verif else 0.0)
    is_face_match = bool(face_verif.get("is_match", False) if face_verif else False)

    # 2. Extract Document Validation Signal
    val_data = doc_data.get("validation") if isinstance(doc_data.get("validation"), dict) else doc_data
    doc_score = float(val_data.get("score", 0.0) if val_data else 0.0)
    is_doc_valid = bool(val_data.get("valid", False) if val_data else False)
    anomalies = val_data.get("anomalies", []) if val_data else []
    checks = val_data.get("checks", []) if val_data else []

    # 3. Disaggregate Document Score into Security Checksums vs Formatting Standards
    # If checksum checks exist in validation, calculate specific security subscore
    security_checks = [c for c in checks if any(k in c.get("field", "").lower() for k in ["mrz", "checksum", "verhoeff", "cross_check"])]
    if security_checks:
        sec_passed = sum(1 for c in security_checks if c.get("status") == "CORRECT")
        sec_score = (sec_passed / len(security_checks)) * 100.0
    else:
        # Fallback to document validation score
        sec_score = doc_score

    standards_score = doc_score

    # Custom weights or defaults
    w_face = weights.get("biometric_face", 0.45) if weights else 0.45
    w_sec = weights.get("document_security", 0.35) if weights else 0.35
    w_std = weights.get("document_standards", 0.20) if weights else 0.20

    # Normalize weights to sum to 1.0
    total_w = w_face + w_sec + w_std
    w_face /= total_w
    w_sec /= total_w
    w_std /= total_w

    raw_consolidated = (face_score * w_face) + (sec_score * w_sec) + (standards_score * w_std)

    # 4. Security Guardrails & Gatekeeper Penalties
    # In border security, a critical failure in ANY pillar invalidates the clearance:
    critical_flags = []
    has_critical_failure = False

    if not is_face_match:
        critical_flags.append("BIOMETRIC_MISMATCH: Live presenter does not match document photo")
        has_critical_failure = True

    if not is_doc_valid:
        critical_flags.append(f"DOCUMENT_INVALID: {val_data.get('decision', {}).get('summary', 'Failed format or security validation')}")
        has_critical_failure = True

    if any("EXPIRED_DOCUMENT" in str(a) for a in anomalies):
        critical_flags.append("EXPIRED_TRAVEL_DOCUMENT: Document is expired and invalid for border crossing")
        has_critical_failure = True

    if any("CHECKSUM" in str(a) or "TAMPERING" in str(a) for a in anomalies):
        critical_flags.append("SECURITY_INTEGRITY_COMPROMISED: Checksum or visual/MRZ mismatch detected")
        has_critical_failure = True

    # If critical failure exists, cap consolidated score
    final_score = raw_consolidated
    if has_critical_failure:
        # Cannot exceed 48% if biometric or document security failed
        final_score = min(final_score, 48.0)

    final_score = round(max(0.0, min(100.0, final_score)), 1)

    # 5. Officer Verdict & Risk Category
    if final_score >= 82.0 and not has_critical_failure:
        verdict = "CLEARANCE"
        risk_level = "LOW"
        recommendation = "Identity and document verified with high confidence. Proceed with automated clearance."
    elif final_score >= 60.0 and not has_critical_failure:
        verdict = "SECONDARY_INSPECTION"
        risk_level = "MEDIUM"
        recommendation = "Borderline confidence or non-critical document warning. Route passenger to secondary inspection officer."
    else:
        verdict = "REJECT"
        risk_level = "HIGH"
        reasons = "; ".join(critical_flags[:2]) if critical_flags else "Consolidated risk threshold breached"
        recommendation = f"High security fraud risk detected ({reasons}). Immediate physical detention / rejection required."

    breakdown = [
        {
            "category": "Biometric Face Match",
            "score": round(face_score, 1),
            "weight": round(w_face * 100, 1),
            "contribution": round(face_score * w_face, 1),
            "passed": is_face_match,
            "status": "PASS" if is_face_match else "FAIL",
            "rationale": CATEGORY_WEIGHTS["biometric_face"]["rationale"]
        },
        {
            "category": "Document Security & Checksums",
            "score": round(sec_score, 1),
            "weight": round(w_sec * 100, 1),
            "contribution": round(sec_score * w_sec, 1),
            "passed": sec_score >= 70.0 and not any("CHECKSUM" in str(a) for a in anomalies),
            "status": "PASS" if sec_score >= 70.0 else "FAIL",
            "rationale": CATEGORY_WEIGHTS["document_security"]["rationale"]
        },
        {
            "category": "Formatting & Temporal Standards",
            "score": round(standards_score, 1),
            "weight": round(w_std * 100, 1),
            "contribution": round(standards_score * w_std, 1),
            "passed": is_doc_valid,
            "status": "PASS" if is_doc_valid else "FAIL",
            "rationale": CATEGORY_WEIGHTS["document_standards"]["rationale"]
        }
    ]

    result = {
        "consolidated_score": final_score,
        "raw_weighted_score": round(raw_consolidated, 1),
        "verdict": verdict,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "is_cleared": verdict == "CLEARANCE",
        "critical_flags": critical_flags,
        "category_breakdown": breakdown,
        "individual_scores": {
            "face_verification": {
                "score": round(face_score, 1),
                "is_match": is_face_match
            },
            "doc_validation": {
                "score": round(doc_score, 1),
                "valid": is_doc_valid
            }
        },
        "timestamp": datetime.now().isoformat()
    }

    # 6. Audit Trail Logging (SIH 2024 / SSB Requirement)
    if audit_log_path:
        try:
            log_entry = f"[{result['timestamp']}] VERDICT={verdict} SCORE={final_score} RISK={risk_level} FLAGS={len(critical_flags)}"
            write_audit_log(audit_log_path, log_entry)
        except Exception:
            pass

    return result

