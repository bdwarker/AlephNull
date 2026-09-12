"""
National ID and Aadhaar Card validation rules engine.
Implements 12-digit Aadhaar Verhoeff checksum, format verification, and demographic consistency.
"""

import re
from datetime import datetime
from typing import Dict, Any
from .verhoeff import validate_verhoeff


def validate_id_card(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates National ID / Aadhaar card data:
    1. Mandatory fields (Name, ID Number, DOB, Gender).
    2. Format validation (Aadhaar 12-digit, generic alphanumeric).
    3. Mathematical Verhoeff algorithm check on 12-digit Aadhaar.
    4. Demographic plausibility (DOB not in future, realistic age).
    5. Address & PIN code structure validation.
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": []
    }

    name = str(data.get("name") or data.get("Name") or "").strip()
    id_number = str(data.get("id_number") or data.get("ID Number") or data.get("id_no") or "").strip()
    dob_raw = str(data.get("dob") or data.get("Date of Birth") or data.get("date_of_birth") or "").strip()
    gender = str(data.get("gender") or data.get("Gender") or "").strip()
    address = str(data.get("address") or data.get("Address") or "").strip()
    nationality = str(data.get("nationality") or data.get("Nationality") or "").strip()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "name": name,
        "id_number": id_number,
        "dob": dob_raw,
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
                "reason": f"Mandatory ID field '{f_key}' is missing or empty"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. ID Number Validation (Aadhaar vs Generic National ID)
    if id_number:
        clean_id = re.sub(r'[\s-]', '', id_number)
        
        # Check if 12-digit Indian Aadhaar
        if clean_id.isdigit() and len(clean_id) == 12:
            # Rule A: UIDAI rule - Aadhaar number cannot start with 0 or 1
            if clean_id[0] in ('0', '1'):
                result["score"] -= 25
                result["flags"].append(f"Invalid Aadhaar number: cannot start with '{clean_id[0]}'")
                result["anomalies"].append("AADHAAR_INVALID_FIRST_DIGIT")
                result["checks"].append({
                    "field": "id_number",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Aadhaar numbers cannot begin with '{clean_id[0]}' per UIDAI specifications"
                })
            else:
                result["checks"].append({
                    "field": "id_number_format",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": "12-digit Aadhaar number format validated"
                })

            # Rule B: Verhoeff Checksum Algorithm (Catches 100% single-digit & transposition errors)
            is_verhoeff_valid = validate_verhoeff(clean_id)
            if is_verhoeff_valid:
                result["checks"].append({
                    "field": "id_number_verhoeff",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": "Aadhaar Verhoeff dihedral D5 checksum verified successfully"
                })
            else:
                result["score"] -= 35
                result["flags"].append("Aadhaar Verhoeff checksum calculation failed (Invalid or forged ID)")
                result["anomalies"].append("AADHAAR_VERHOEFF_CHECKSUM_FAILED")
                result["checks"].append({
                    "field": "id_number_verhoeff",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": "Verhoeff check digit validation failed. Number is mathematically invalid or manipulated"
                })

        elif re.match(r'^[A-Z0-9]{8,16}$', clean_id.upper()):
            # Generic National ID (alphanumeric 8-16 characters)
            result["checks"].append({
                "field": "id_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"National ID '{id_number}' conforms to standard alphanumeric identification format"
            })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid National ID number format: '{id_number}'")
            result["anomalies"].append("INVALID_ID_NUMBER_FORMAT")
            result["checks"].append({
                "field": "id_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "ID number must be a 12-digit Aadhaar or 8-16 character alphanumeric code"
            })

    # 3. Date of Birth & Age Check
    if dob_raw:
        try:
            dob_clean = re.sub(r'[/.]', '-', dob_raw)
            dob_dt = datetime.strptime(dob_clean, "%Y-%m-%d")
            result["checks"].append({"field": "dob", "status": "CORRECT", "severity": "INFO", "reason": "Valid date of birth format"})
            
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
                        "reason": f"Cardholder age {age} exceeds standard human lifespan"
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

    # 4. Gender Validation
    if gender:
        gen_clean = gender.upper()
        if gen_clean in ["M", "MALE"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Male"})
        elif gen_clean in ["F", "FEMALE"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Female"})
        elif gen_clean in ["T", "TRANSGENDER", "OTHER", "X"]:
            result["checks"].append({"field": "gender", "status": "CORRECT", "severity": "INFO", "reason": "Gender validated as Transgender / Other"})
        else:
            result["score"] -= 10
            result["flags"].append(f"Invalid gender value: '{gender}'")
            result["anomalies"].append("INVALID_GENDER")
            result["checks"].append({
                "field": "gender",
                "status": "WRONG",
                "severity": "MINOR",
                "reason": f"Gender '{gender}' expected Male, Female, or Transgender"
            })

    # 5. Address Validation (if provided)
    if address:
        if len(address) < 8:
            result["score"] -= 5
            result["flags"].append("Address appears abnormally short")
            result["checks"].append({
                "field": "address",
                "status": "WARNING",
                "severity": "MINOR",
                "reason": f"Address '{address}' is under 8 characters"
            })
        else:
            # Check for standard Indian 6-digit postal PIN code
            pin_match = re.search(r'\b([1-9][0-9]{5})\b', address)
            if pin_match:
                result["checks"].append({
                    "field": "address_pincode",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": f"Valid 6-digit postal PIN code '{pin_match.group(1)}' identified in address"
                })
            else:
                result["checks"].append({
                    "field": "address",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": "Address text present"
                })

    result["score"] = max(0, min(100, result["score"]))
    has_critical = any(c.get("severity") == "CRITICAL" and c.get("status") == "WRONG" for c in result["checks"])
    result["valid"] = not has_critical and result["score"] >= 70

    return result
