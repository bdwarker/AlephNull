"""
Passport validation rules engine compliant with ICAO Doc 9303.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .icao9303 import ISO_3166_ALPHA3, COUNTRY_NAME_TO_ISO3, verify_mrz_checksums


def validate_passport(data: Dict[str, Any], mrz_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validates passport data:
    1. Required fields presence and content.
    2. Format compliance (Passport No, Nationality, Gender, Dates).
    3. Mathematical check-digit verification via ICAO 9303 (7-3-1 weights).
    4. Chronological & temporal validity (current validity, near-expiry, age).
    5. Visual OCR vs MRZ cross-verification for tampering cues.
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": [],
        "cross_checks": []
    }

    # Normalized fields extraction
    name = str(data.get("name") or data.get("Name") or "").strip()
    passport_no = str(data.get("passport_number") or data.get("Passport Number") or data.get("passport_no") or "").strip()
    nationality = str(data.get("nationality") or data.get("Nationality") or "").strip()
    dob_raw = str(data.get("dob") or data.get("Date of Birth") or data.get("date_of_birth") or "").strip()
    expiry_raw = str(data.get("expiry") or data.get("Date of Expiry") or data.get("date_of_expiry") or "").strip()
    gender = str(data.get("gender") or data.get("Gender") or "").strip()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "name": name,
        "passport_number": passport_no,
        "nationality": nationality,
        "dob": dob_raw,
        "expiry": expiry_raw,
        "gender": gender
    }

    for f_key, f_val in fields_map.items():
        if not f_val:
            result["score"] -= 15
            result["flags"].append(f"Missing mandatory field: {f_key}")
            result["anomalies"].append(f"MISSING_{f_key.upper()}")
            result["checks"].append({
                "field": f_key,
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Mandatory passport field '{f_key}' is missing or empty"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. Passport Number Format Check
    if passport_no:
        clean_pno = re.sub(r'[^A-Z0-9]', '', passport_no.upper())
        # Standard: 1-2 letters followed by 6-8 digits, or ICAO general 6-9 alphanumeric
        if re.match(r'^[A-Z][0-9]{7,8}$', clean_pno):
            result["checks"].append({
                "field": "passport_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Passport number '{clean_pno}' follows standard national format"
            })
        elif re.match(r'^[A-Z0-9]{6,9}$', clean_pno):
            result["checks"].append({
                "field": "passport_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Passport number '{clean_pno}' conforms to general ICAO TD3 format"
            })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid passport number format: '{passport_no}'")
            result["anomalies"].append("INVALID_PASSPORT_NUMBER_FORMAT")
            result["checks"].append({
                "field": "passport_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Passport number '{passport_no}' does not conform to standard format (e.g. A1234567)"
            })

    # 3. Nationality Check (ISO 3166-1 alpha-3 code or standard name)
    if nationality:
        nat_upper = nationality.upper()
        iso_code = COUNTRY_NAME_TO_ISO3.get(nat_upper, nat_upper)
        if iso_code in ISO_3166_ALPHA3 or nat_upper in COUNTRY_NAME_TO_ISO3:
            result["checks"].append({
                "field": "nationality",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Nationality '{nationality}' corresponds to valid ISO 3166-1 country code '{iso_code}'"
            })
        elif len(nationality) >= 3 and nationality.isalpha():
            result["score"] -= 5
            result["flags"].append(f"Unrecognized ISO country code for nationality: '{nationality}'")
            result["checks"].append({
                "field": "nationality",
                "status": "WARNING",
                "severity": "MINOR",
                "reason": f"Nationality '{nationality}' is alphabetic but not found in standard ISO 3166-1 index"
            })
        else:
            result["score"] -= 15
            result["flags"].append(f"Invalid nationality format: '{nationality}'")
            result["anomalies"].append("INVALID_NATIONALITY")
            result["checks"].append({
                "field": "nationality",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Nationality '{nationality}' contains non-alphabetic characters"
            })

    # 4. Gender Check
    if gender:
        gen_clean = gender.upper()
        if gen_clean in ["M", "MALE"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Male"})
        elif gen_clean in ["F", "FEMALE"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Female"})
        elif gen_clean in ["X", "OTHER", "UNSPECIFIED"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Unspecified (X)"})
        else:
            result["score"] -= 10
            result["flags"].append(f"Invalid gender value: '{gender}'")
            result["anomalies"].append("INVALID_GENDER")
            result["checks"].append({
                "field": "gender",
                "status": "WRONG",
                "severity": "MINOR",
                "reason": f"Gender '{gender}' must be Male (M), Female (F), or Unspecified (X)"
            })

    # 5. Temporal & Date Coherence
    dob_dt = None
    exp_dt = None

    if dob_raw:
        try:
            dob_clean = re.sub(r'[/.]', '-', dob_raw)
            dob_dt = datetime.strptime(dob_clean, "%Y-%m-%d")
            result["checks"].append({"field": "dob", "status": "CORRECT", "severity": "INFO", "reason": "Valid date of birth format"})
            
            # Check if DOB is in future
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
                    result["flags"].append(f"Implausible age: {age} years")
                    result["anomalies"].append("IMPLAUSIBLE_AGE")
                    result["checks"].append({
                        "field": "dob",
                        "status": "WARNING",
                        "severity": "MAJOR",
                        "reason": f"Holder age {age} exceeds normal human lifespan"
                    })
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid DOB format: '{dob_raw}'")
            result["anomalies"].append("INVALID_DOB_FORMAT")
            result["checks"].append({
                "field": "dob",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "Date of birth must be in YYYY-MM-DD format"
            })

    if expiry_raw:
        try:
            exp_clean = re.sub(r'[/.]', '-', expiry_raw)
            exp_dt = datetime.strptime(exp_clean, "%Y-%m-%d")
            result["checks"].append({"field": "expiry", "status": "CORRECT", "severity": "INFO", "reason": "Valid expiry date format"})
            
            # Check if document is currently expired
            if exp_dt < now:
                result["score"] -= 30
                result["flags"].append(f"Passport expired on {exp_clean}")
                result["anomalies"].append("EXPIRED_DOCUMENT")
                result["checks"].append({
                    "field": "expiry",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Document expired on {exp_clean}. Not valid for travel/entry"
                })
            elif exp_dt < (now + timedelta(days=180)):
                # 6-Month Rule Warning for International Travel
                result["score"] -= 10
                result["flags"].append(f"Passport expires within 6 months ({exp_clean}). Potential entry restriction")
                result["anomalies"].append("DOCUMENT_EXPIRING_SOON")
                result["checks"].append({
                    "field": "expiry",
                    "status": "WARNING",
                    "severity": "MINOR",
                    "reason": "Passport validity under 180 days; may fail international entry rules"
                })
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid Expiry format: '{expiry_raw}'")
            result["anomalies"].append("INVALID_EXPIRY_FORMAT")
            result["checks"].append({
                "field": "expiry",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "Expiry date must be in YYYY-MM-DD format"
            })

    # Cross-Date Logic (Expiry vs DOB)
    if dob_dt and exp_dt:
        if exp_dt <= dob_dt:
            result["score"] -= 30
            result["flags"].append("Expiry date is before or equal to date of birth")
            result["anomalies"].append("EXPIRY_BEFORE_DOB")
            result["checks"].append({
                "field": "date_relationship",
                "status": "WRONG",
                "severity": "CRITICAL",
                "reason": "Expiry date cannot be prior to Date of Birth"
            })
        else:
            result["checks"].append({
                "field": "date_relationship",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": "Expiry date is after date of birth"
            })

    # 6. MRZ Checksum & Cross-Validation
    if mrz_data:
        mrz_fields = mrz_data.get("fields", {})
        
        # Verify MRZ Checksums
        mrz_chk_res = verify_mrz_checksums(mrz_data)
        for chk in mrz_chk_res.get("checks", []):
            if chk["passed"]:
                result["checks"].append({
                    "field": chk["check"],
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": chk["message"]
                })
            else:
                result["score"] -= 25
                result["flags"].append(f"ICAO 9303 Checksum Failure: {chk['check']}")
                result["anomalies"].append(f"CHECKSUM_FAILED_{chk['check']}")
                result["checks"].append({
                    "field": chk["check"],
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": chk["message"]
                })

        # Cross-Check 1: Passport Number (Visual vs MRZ)
        mrz_pno = str(mrz_fields.get("Passport Number") or "").strip().upper()
        if passport_no and mrz_pno:
            clean_vis = re.sub(r'[^A-Z0-9]', '', passport_no.upper())
            clean_mrz = re.sub(r'[^A-Z0-9]', '', mrz_pno)
            is_match = clean_vis == clean_mrz or clean_vis.startswith(clean_mrz) or clean_mrz.startswith(clean_vis)
            result["cross_checks"].append({
                "check": "PASSPORT_NUMBER_MRZ_MATCH",
                "visual_value": passport_no,
                "mrz_value": mrz_pno,
                "match": is_match
            })
            if not is_match:
                result["score"] -= 25
                result["flags"].append(f"Passport Number mismatch: Visual '{passport_no}' vs MRZ '{mrz_pno}'")
                result["anomalies"].append("MRZ_PASSPORT_NUMBER_MISMATCH")
                result["checks"].append({
                    "field": "cross_check_passport_number",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Visual passport number '{passport_no}' contradicts MRZ '{mrz_pno}' (Tampering cue)"
                })

        # Cross-Check 2: DOB (Visual vs MRZ)
        mrz_dob = str(mrz_fields.get("Date of Birth") or "").strip()
        if dob_raw and mrz_dob:
            is_match = dob_raw == mrz_dob
            result["cross_checks"].append({
                "check": "DOB_MRZ_MATCH",
                "visual_value": dob_raw,
                "mrz_value": mrz_dob,
                "match": is_match
            })
            if not is_match:
                result["score"] -= 20
                result["flags"].append(f"DOB mismatch: Visual '{dob_raw}' vs MRZ '{mrz_dob}'")
                result["anomalies"].append("MRZ_DOB_MISMATCH")
                result["checks"].append({
                    "field": "cross_check_dob",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Visual DOB '{dob_raw}' does not match MRZ DOB '{mrz_dob}'"
                })

        # Cross-Check 3: Expiry (Visual vs MRZ)
        mrz_exp = str(mrz_fields.get("Date of Expiry") or "").strip()
        if expiry_raw and mrz_exp:
            is_match = expiry_raw == mrz_exp
            result["cross_checks"].append({
                "check": "EXPIRY_MRZ_MATCH",
                "visual_value": expiry_raw,
                "mrz_value": mrz_exp,
                "match": is_match
            })
            if not is_match:
                result["score"] -= 20
                result["flags"].append(f"Expiry mismatch: Visual '{expiry_raw}' vs MRZ '{mrz_exp}'")
                result["anomalies"].append("MRZ_EXPIRY_MISMATCH")
                result["checks"].append({
                    "field": "cross_check_expiry",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Visual Expiry '{expiry_raw}' does not match MRZ Expiry '{mrz_exp}'"
                })

        # Cross-Check 4: Name alignment
        mrz_name = str(mrz_fields.get("Name") or "").strip()
        if name and mrz_name:
            vis_tokens = set(re.findall(r'[A-Z]{3,}', name.upper()))
            mrz_tokens = set(re.findall(r'[A-Z]{3,}', mrz_name.upper()))
            overlap = vis_tokens & mrz_tokens
            is_match = bool(overlap) or len(vis_tokens) == 0 or len(mrz_tokens) == 0
            result["cross_checks"].append({
                "check": "NAME_MRZ_ALIGNMENT",
                "visual_value": name,
                "mrz_value": mrz_name,
                "match": is_match
            })
            if not is_match:
                result["score"] -= 20
                result["flags"].append(f"Name mismatch between visual text ('{name}') and MRZ ('{mrz_name}')")
                result["anomalies"].append("MRZ_NAME_MISMATCH")
                result["checks"].append({
                    "field": "cross_check_name",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Visual name '{name}' contradicts MRZ name '{mrz_name}'"
                })

    result["score"] = max(0, min(100, result["score"]))
    has_critical = any(c.get("severity") == "CRITICAL" and c.get("status") == "WRONG" for c in result["checks"])
    result["valid"] = not has_critical and result["score"] >= 70

    return result
