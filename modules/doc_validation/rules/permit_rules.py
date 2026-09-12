"""
Border and travel permit validation rules engine.
"""

import re
from datetime import datetime
from typing import Dict, Any


def validate_permit(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates Border / Inner Line Permit:
    1. Mandatory fields (Permit Number, Name, Expiry / Valid Till).
    2. Format structure.
    3. Expiration status relative to current date.
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": []
    }

    permit_no = str(data.get("permit_number") or data.get("Permit Number") or data.get("permit_no") or "").strip()
    name = str(data.get("name") or data.get("Name") or "").strip()
    expiry_raw = str(data.get("expiry") or data.get("valid_until") or data.get("Date of Expiry") or "").strip()
    route = str(data.get("route") or data.get("destination") or data.get("sector") or "").strip()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "permit_number": permit_no,
        "name": name,
        "expiry": expiry_raw
    }

    for f_key, f_val in fields_map.items():
        if not f_val:
            result["score"] -= 20
            result["flags"].append(f"Missing mandatory permit field: {f_key}")
            result["anomalies"].append(f"MISSING_{f_key.upper()}")
            result["checks"].append({
                "field": f_key,
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Mandatory permit field '{f_key}' is missing or empty"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. Permit Number Format Check
    if permit_no:
        clean_p = re.sub(r'[\s-]', '', permit_no.upper())
        if len(clean_p) >= 6 and re.match(r'^[A-Z0-9]+$', clean_p):
            result["checks"].append({
                "field": "permit_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Permit number '{permit_no}' follows valid alphanumeric pattern"
            })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid permit number format: '{permit_no}'")
            result["anomalies"].append("INVALID_PERMIT_NUMBER_FORMAT")
            result["checks"].append({
                "field": "permit_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "Permit number must contain at least 6 alphanumeric characters"
            })

    # 3. Expiration Check
    if expiry_raw:
        try:
            exp_clean = re.sub(r'[/.]', '-', expiry_raw)
            exp_dt = datetime.strptime(exp_clean, "%Y-%m-%d")
            result["checks"].append({"field": "expiry", "status": "CORRECT", "severity": "INFO", "reason": "Valid expiry date format"})
            
            if exp_dt < now:
                result["score"] -= 30
                result["flags"].append(f"Permit expired on {exp_clean}")
                result["anomalies"].append("EXPIRED_DOCUMENT")
                result["checks"].append({
                    "field": "expiry",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Permit expired on {exp_clean}. Entry restricted"
                })
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid Expiry format: '{expiry_raw}'")
            result["checks"].append({"field": "expiry", "status": "WRONG", "severity": "MAJOR", "reason": "Expected YYYY-MM-DD"})

    result["score"] = max(0, min(100, result["score"]))
    has_critical = any(c.get("severity") == "CRITICAL" and c.get("status") == "WRONG" for c in result["checks"])
    result["valid"] = not has_critical and result["score"] >= 70

    return result
