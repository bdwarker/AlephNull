"""
Transparent weighted scoring model for cross-module risk signals (AlephNull Risk Engine).
Fulfills Problem Statement PS26188 (SIH 2024 / Sashastra Seema Bal).
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from .audit_log import write_audit_log

# Safe UTF-8 console output for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [RISK_ENGINE] {msg}", flush=True)

# Category Weights based on importance vs AI model accuracy
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
    """
    _log("=" * 60)
    _log("CONSOLIDATING MULTI-MODAL SCREENING RISK SIGNALS")
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
    # Collect all suspicious points and critical anomalies:
    suspicious_points = []
    has_critical_failure = False

    if not is_face_match:
        f_thresh = face_verif.get("threshold", 0.40) if face_verif else 0.40
        suspicious_points.append(f"Biometric Face Mismatch: Presenter does not match document photo (score: {round(face_score, 1)}/100, limit: {f_thresh})")
        has_critical_failure = True

    # Pull suspicious points directly from Module 2 Document Validation
    doc_suspicious = val_data.get("suspicious_points") or []
    for sp in doc_suspicious:
        if sp not in suspicious_points:
            suspicious_points.append(sp)

    if not is_doc_valid:
        doc_msg = val_data.get('decision', {}).get('summary') or "Document failed format or integrity checks"
        if not any("format or integrity" in s.lower() for s in suspicious_points):
            suspicious_points.append(f"Document Rule Validation Flag: {doc_msg}")
        has_critical_failure = True

    for a in anomalies:
        a_str = str(a)
        if "EXPIRED_DOCUMENT" in a_str and not any("expired" in s.lower() for s in suspicious_points):
            suspicious_points.append("Expired Document: Document is expired and invalid for border crossing")
            has_critical_failure = True
        elif ("CHECKSUM" in a_str or "TAMPERING" in a_str) and not any("checksum" in s.lower() for s in suspicious_points):
            suspicious_points.append("Security Integrity Flag: Checksum or visual/MRZ mismatch detected")
            has_critical_failure = True
        elif not any(a_str.lower() in s.lower() for s in suspicious_points):
            suspicious_points.append(a_str)

    # De-duplicate suspicious points
    unique_suspicious = []
    for p in suspicious_points:
        if p not in unique_suspicious:
            unique_suspicious.append(p)

    # If critical failure exists, cap consolidated score
    final_score = raw_consolidated
    if has_critical_failure:
        # Cannot exceed 48% if biometric or document security failed
        final_score = min(final_score, 48.0)

    final_score = round(max(0.0, min(100.0, final_score)), 1)

    # 5. Officer Decision Support (Objective score & highlighted points only - no directive guidance)
    if len(unique_suspicious) == 0 and final_score >= 80.0:
        summary_txt = "All automated biometric and document checks verified without flags. No suspicious points identified."
        status_txt = "NO_ANOMALIES"
    else:
        summary_txt = f"{len(unique_suspicious)} suspicious point(s) flagged by system for officer review."
        status_txt = "SUSPICIOUS_POINTS_FLAGGED"

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
        "score": final_score,
        "raw_weighted_score": round(raw_consolidated, 1),
        "status": status_txt,
        "suspicious_points": unique_suspicious,
        "summary": summary_txt,
        "is_cleared": len(unique_suspicious) == 0,
        "critical_flags": unique_suspicious,
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

    _log(f"Face Biometric Score: {round(face_score, 1)} (Match: {is_face_match})")
    _log(f"Doc Validation Score: {round(doc_score, 1)} (Valid: {is_doc_valid})")
    _log(f"Final Consolidated Trust Score: {final_score}/100 | Suspicious Points: {len(unique_suspicious)}")
    for sp in unique_suspicious:
        _log(f"  🚩 SUSPICIOUS POINT: {sp}")
    _log(f"Summary: {summary_txt}")
    _log("=" * 60)

    # 6. Audit Trail Logging (SIH 2024 / SSB Requirement)
    if audit_log_path:
        try:
            log_entry = f"[{result['timestamp']}] SCORE={final_score} FLAGS={len(unique_suspicious)}"
            write_audit_log(audit_log_path, log_entry)
        except Exception:
            pass

    return result

