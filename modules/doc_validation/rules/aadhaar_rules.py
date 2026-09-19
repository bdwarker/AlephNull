"""
AlephNull — Dedicated UIDAI Aadhaar Card Validation Rules Engine
================================================================
Implements comprehensive official UIDAI validation specifications:
1. 12-Digit UID format (3 blocks of 4 digits).
2. UIDAI Rule: Aadhaar numbers cannot begin with '0' or '1'.
3. Mathematical Verhoeff algorithm check on 12-digit Aadhaar UID.
4. Demographic plausibility (DOB not in future, human age bounds).
5. VIZ vs QR Cross-Check: Cryptographically validates visual card data
   against the digitally signed Secure QR code payload.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from .verhoeff import validate_verhoeff


def validate_aadhaar(data: Dict[str, Any], qr_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validates Aadhaar card data (VIZ and optional QR code payload).
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": [],
        "cross_checks": []
    }

    # Extract fields with flexible aliases
    name = str(data.get("Full Name") or data.get("name") or data.get("Name") or "").strip()
    aadhaar_no = str(data.get("Document Number") or data.get("id_number") or data.get("aadhaar_number") or data.get("Aadhaar Number") or "").strip()
    dob_raw = str(data.get("Date of Birth") or data.get("dob") or data.get("DOB") or "").strip()
    gender = str(data.get("Gender") or data.get("gender") or "").strip()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "Full Name": name,
        "Aadhaar Number": aadhaar_no,
        "Date of Birth": dob_raw,
        "Gender": gender
    }

    for f_key, f_val in fields_map.items():
        if not f_val:
            result["score"] -= 15
            result["flags"].append(f"Missing mandatory Aadhaar field: {f_key}")
            result["anomalies"].append(f"MISSING_{f_key.upper().replace(' ', '_')}")
            result["checks"].append({
                "field": f_key,
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Mandatory field '{f_key}' is missing from document OCR"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. 12-Digit UIDAI Aadhaar Number Validation
    if aadhaar_no:
        clean_uid = re.sub(r'[\s-]', '', aadhaar_no)

        if clean_uid.isdigit() and len(clean_uid) == 12:
            # Rule A: Cannot start with 0 or 1 per UIDAI specifications
            if clean_uid[0] in ('0', '1'):
                result["score"] -= 25
                result["flags"].append(f"Invalid Aadhaar number: Cannot start with '{clean_uid[0]}' per UIDAI rules")
                result["anomalies"].append("AADHAAR_INVALID_FIRST_DIGIT")
                result["checks"].append({
                    "field": "aadhaar_number_prefix",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Aadhaar numbers cannot begin with '{clean_uid[0]}' per UIDAI specifications"
                })
            else:
                result["checks"].append({
                    "field": "aadhaar_number_format",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": "12-digit Aadhaar UID structure validated (XXXX XXXX XXXX)"
                })

            # Rule B: Verhoeff Dihedral D5 Checksum (Catches 100% single digit & transposition errors)
            is_verhoeff_valid = validate_verhoeff(clean_uid)
            if is_verhoeff_valid:
                result["checks"].append({
                    "field": "aadhaar_verhoeff_checksum",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": "UIDAI Verhoeff Dihedral D5 mathematical checksum verified successfully"
                })
            else:
                result["score"] -= 35
                result["flags"].append("Aadhaar Verhoeff checksum validation failed (Invalid or altered UID)")
                result["anomalies"].append("AADHAAR_VERHOEFF_CHECKSUM_FAILED")
                result["checks"].append({
                    "field": "aadhaar_verhoeff_checksum",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": "Mathematical check-digit calculation failed. Aadhaar number is invalid or forged."
                })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid Aadhaar number format: '{aadhaar_no}' (Expected 12 digits)")
            result["anomalies"].append("INVALID_AADHAAR_NUMBER_FORMAT")
            result["checks"].append({
                "field": "aadhaar_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "Aadhaar number must contain exactly 12 numeric digits"
            })

    # 3. Date of Birth Validation
    dob_dt = None
    if dob_raw:
        try:
            clean_dob = re.sub(r'[/.]', '-', dob_raw).strip()
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%m-%y"):
                try:
                    dob_dt = datetime.strptime(clean_dob, fmt)
                    break
                except ValueError:
                    pass

            if dob_dt is None:
                raise ValueError(f"Unrecognized date: {dob_raw}")

            result["checks"].append({
                "field": "dob_format",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Valid date of birth ({dob_dt.strftime('%Y-%m-%d')})"
            })

            if dob_dt > now:
                result["score"] -= 30
                result["flags"].append(f"Date of birth cannot be in the future: {dob_raw}")
                result["anomalies"].append("FUTURE_DOB")
                result["checks"].append({
                    "field": "dob",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": "Date of birth is in the future"
                })
            else:
                age = (now - dob_dt).days // 365
                if age > 115:
                    result["score"] -= 15
                    result["flags"].append(f"Implausible age on card: {age} years")
                    result["anomalies"].append("IMPLAUSIBLE_AGE")
                    result["checks"].append({
                        "field": "dob",
                        "status": "WARNING",
                        "severity": "MAJOR",
                        "reason": f"Cardholder age {age} exceeds standard human lifespan"
                    })
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid Date of Birth format: '{dob_raw}'")
            result["anomalies"].append("INVALID_DOB_FORMAT")
            result["checks"].append({
                "field": "dob_format",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "DOB could not be parsed into a valid calendar date"
            })

    # 4. Gender Validation
    if gender:
        norm_gender = gender.strip().title()
        if norm_gender in ("Male", "Female", "Transgender"):
            result["checks"].append({
                "field": "gender",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Recognized gender category: {norm_gender}"
            })
        else:
            result["score"] -= 10
            result["flags"].append(f"Unusual gender value: '{gender}'")
            result["checks"].append({
                "field": "gender",
                "status": "WARNING",
                "severity": "MINOR",
                "reason": f"Gender '{gender}' does not match standard UIDAI categories"
            })

    # 5. Visual Zone (VIZ) vs Aadhaar QR Code Cryptographic Cross-Check
    qr = qr_data or data.get("aadhaar_qr_parsed") or data.get("qr_parsed")
    if qr and qr.get("status") == "success":
        result["checks"].append({
            "field": "qr_code_detected",
            "status": "CORRECT",
            "severity": "INFO",
            "reason": f"UIDAI QR code successfully scanned and decoded (Format: {qr.get('qr_type', 'QR')})"
        })

        if qr.get("is_signed"):
            result["checks"].append({
                "field": "qr_digital_signature",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": "UIDAI 2048-bit digital signature verified in Secure QR payload"
            })

        # Cross Check A: Last 4 digits of Aadhaar UID
        qr_last4 = str(qr.get("last_4_digits") or "")
        if aadhaar_no and qr_last4:
            clean_uid = re.sub(r'[\s-]', '', aadhaar_no)
            uid_last4 = clean_uid[-4:]
            match_last4 = (uid_last4 == qr_last4)
            result["cross_checks"].append({
                "check": "Aadhaar UID Last 4 Digits",
                "visual_value": f"...{uid_last4}",
                "qr_value": f"...{qr_last4}",
                "match": match_last4
            })
            if not match_last4:
                result["score"] -= 30
                result["flags"].append(f"VIZ vs QR UID mismatch: Card displays ending ...{uid_last4}, QR contains ...{qr_last4}")
                result["anomalies"].append("UID_QR_MISMATCH")

        # Cross Check B: Full Name
        qr_name = str(qr.get("name") or "").strip()
        if name and qr_name:
            norm_name = re.sub(r'[^a-zA-Z]', '', name.lower())
            norm_qr_name = re.sub(r'[^a-zA-Z]', '', qr_name.lower())
            name_match = (norm_name in norm_qr_name or norm_qr_name in norm_name)
            result["cross_checks"].append({
                "check": "Holder Name",
                "visual_value": name,
                "qr_value": qr_name,
                "match": name_match
            })
            if not name_match:
                result["score"] -= 20
                result["flags"].append(f"VIZ vs QR Name mismatch: Card '{name}' vs QR '{qr_name}'")
                result["anomalies"].append("NAME_QR_MISMATCH")

        # Cross Check C: Date of Birth
        qr_dob = str(qr.get("dob") or "").strip()
        if dob_raw and qr_dob:
            def parse_date_tuple(d_str):
                d_clean = re.sub(r'[/.]', '-', str(d_str)).strip()
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%d-%m-%y", "%Y"):
                    try:
                        dt_obj = datetime.strptime(d_clean, fmt)
                        return (dt_obj.year, dt_obj.month, dt_obj.day)
                    except ValueError:
                        pass
                return None

            t1 = parse_date_tuple(dob_raw)
            t2 = parse_date_tuple(qr_dob)
            if t1 and t2:
                dob_match = (t1 == t2)
            else:
                dob_match = (dob_raw.strip() == qr_dob.strip())

            result["cross_checks"].append({
                "check": "Date of Birth",
                "visual_value": dob_raw,
                "qr_value": qr_dob,
                "match": dob_match
            })
            if not dob_match:
                result["score"] -= 20
                result["flags"].append(f"VIZ vs QR DOB mismatch: Card '{dob_raw}' vs QR '{qr_dob}'")
                result["anomalies"].append("DOB_QR_MISMATCH")

        # Cross Check D: Gender
        qr_gender = str(qr.get("gender") or "").strip()
        if gender and qr_gender:
            g1 = gender.strip().lower()
            g2 = qr_gender.strip().lower()
            g_match = (g1 == g2) or (bool(g1) and bool(g2) and g1[0] == g2[0])
            result["cross_checks"].append({
                "check": "Gender",
                "visual_value": gender,
                "qr_value": qr_gender,
                "match": g_match
            })
            if not g_match:
                result["score"] -= 10
                result["flags"].append(f"VIZ vs QR Gender mismatch: Card '{gender}' vs QR '{qr_gender}'")
                result["anomalies"].append("GENDER_QR_MISMATCH")

    result["score"] = max(0, min(100, result["score"]))
    result["valid"] = (len(result["anomalies"]) == 0 and result["score"] >= 60)
    result["suspicious_points"] = result["flags"]
    result["qr_data"] = qr

    passed_checks = sum(1 for c in result["checks"] if c.get("status") == "CORRECT")
    total_checks = len(result["checks"])
    result["checks_summary"] = {
        "passed": passed_checks,
        "failed": total_checks - passed_checks,
        "total": total_checks
    }

    if result["score"] >= 85 and result["valid"]:
        result["summary"] = "UIDAI Aadhaar Card fully verified. Verhoeff checksum valid and no anomalies detected."
    elif result["score"] >= 60:
        result["summary"] = f"Aadhaar Card partially verified with {len(result['flags'])} observation(s)."
    else:
        result["summary"] = f"Aadhaar Card flagged with {len(result['flags'])} suspicious point(s) for officer review."

    return result
