"""
Visa validation rules engine compliant with international border screening standards.
"""

import re
from datetime import datetime
from typing import Dict, Any

VALID_VISA_TYPES = {
    "TOURIST", "BUSINESS", "STUDENT", "EMPLOYMENT", "WORK",
    "TRANSIT", "DIPLOMATIC", "OFFICIAL", "CONFERENCE", "MEDICAL",
    "JOURNALIST", "ENTRY", "PROJECT", "RESEARCH"
}

VALID_ENTRIES = {"SINGLE", "DOUBLE", "TRIPLE", "MULTIPLE"}


def validate_visa(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates Visa document data:
    1. Mandatory fields (Visa Number, Visa Type, Expiry / Valid Until).
    2. Visa number alphanumeric structure.
    3. Classification check (Tourist, Business, Student, Work, etc.).
    4. Stay duration vs validity window coherence.
    5. Expiration check relative to current date.
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": []
    }

    visa_no = str(data.get("visa_number") or data.get("Visa Number") or data.get("visa_no") or "").strip()
    visa_type = str(data.get("visa_type") or data.get("Visa Type") or "").strip().upper()
    expiry_raw = str(data.get("expiry") or data.get("valid_until") or data.get("Date of Expiry") or data.get("Entry Validation") or "").strip()
    stay_duration = str(data.get("stay_duration") or data.get("Stay Duration") or "").strip().upper()
    issue_raw = str(data.get("issue_date") or data.get("Issue Date") or "").strip()
    entries = str(data.get("entries") or data.get("entry_validation") or data.get("Entry Type") or "").strip().upper()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "visa_number": visa_no,
        "visa_type": visa_type,
        "expiry": expiry_raw
    }

    for f_key, f_val in fields_map.items():
        if not f_val:
            result["score"] -= 20
            result["flags"].append(f"Missing mandatory visa field: {f_key}")
            result["anomalies"].append(f"MISSING_{f_key.upper()}")
            result["checks"].append({
                "field": f_key,
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": f"Mandatory visa field '{f_key}' is missing or empty"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. Visa Number Format Check
    if visa_no:
        clean_vno = re.sub(r'[\s-]', '', visa_no.upper())
        if re.match(r'^[A-Z0-9]{7,15}$', clean_vno):
            result["checks"].append({
                "field": "visa_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Visa number '{visa_no}' follows expected alphanumeric structure"
            })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid visa number format: '{visa_no}'")
            result["anomalies"].append("INVALID_VISA_NUMBER_FORMAT")
            result["checks"].append({
                "field": "visa_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "Visa number must be 7-15 alphanumeric characters"
            })

    # 3. Visa Type Validation
    if visa_type:
        matched_type = next((vt for vt in VALID_VISA_TYPES if vt in visa_type), None)
        if matched_type:
            result["checks"].append({
                "field": "visa_type",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Visa classification '{visa_type}' confirmed as legitimate category ({matched_type})"
            })
        else:
            result["score"] -= 10
            result["flags"].append(f"Unusual visa classification: '{visa_type}'")
            result["checks"].append({
                "field": "visa_type",
                "status": "WARNING",
                "severity": "MINOR",
                "reason": f"Visa type '{visa_type}' not in standard international visa list"
            })

    # 4. Entry Type Validation
    if entries:
        matched_entry = next((e for e in VALID_ENTRIES if e in entries), None)
        if matched_entry:
            result["checks"].append({
                "field": "entry_validation",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Entry type '{matched_entry}' recognized"
            })

    # 5. Temporal Validity & Stay Duration Coherence
    exp_dt = None
    iss_dt = None

    if expiry_raw:
        try:
            # Match date if embedded in string like "31/12/2025" or "2025-12-31"
            date_m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})', expiry_raw)
            if date_m:
                date_str = date_m.group(0).replace('/', '-')
                parts = date_str.split('-')
                if len(parts[0]) == 4:
                    exp_dt = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    exp_dt = datetime.strptime(date_str, "%d-%m-%Y")
                
                result["checks"].append({"field": "expiry", "status": "CORRECT", "severity": "INFO", "reason": "Valid visa expiry date format"})
                
                if exp_dt < now:
                    result["score"] -= 30
                    result["flags"].append(f"Visa expired on {exp_dt.strftime('%Y-%m-%d')}")
                    result["anomalies"].append("EXPIRED_DOCUMENT")
                    result["checks"].append({
                        "field": "expiry",
                        "status": "WRONG",
                        "severity": "CRITICAL",
                        "reason": f"Visa expired on {exp_dt.strftime('%Y-%m-%d')}. Entry strictly prohibited"
                    })
        except Exception:
            result["score"] -= 15
            result["flags"].append(f"Could not parse visa expiry date: '{expiry_raw}'")
            result["checks"].append({"field": "expiry", "status": "WRONG", "severity": "MAJOR", "reason": "Unparseable expiry date"})

    if issue_raw:
        try:
            iss_m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})', issue_raw)
            if iss_m:
                date_str = iss_m.group(0).replace('/', '-')
                parts = date_str.split('-')
                if len(parts[0]) == 4:
                    iss_dt = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    iss_dt = datetime.strptime(date_str, "%d-%m-%Y")
        except Exception:
            pass

    # Stay Duration Coherence Check
    if stay_duration:
        days_m = re.search(r'(\d+)\s*(?:DAY|DAYS|D)', stay_duration)
        if days_m and iss_dt and exp_dt:
            allowed_days = int(days_m.group(1))
            validity_window_days = (exp_dt - iss_dt).days
            if allowed_days > validity_window_days:
                result["score"] -= 25
                result["flags"].append(f"Stay duration ({allowed_days} days) exceeds visa validity window ({validity_window_days} days)")
                result["anomalies"].append("STAY_DURATION_EXCEEDS_VALIDITY")
                result["checks"].append({
                    "field": "stay_duration",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Permitted stay duration ({allowed_days} days) cannot exceed the visa validity window ({validity_window_days} days)"
                })
            else:
                result["checks"].append({
                    "field": "stay_duration",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": f"Stay duration ({allowed_days} days) fits within visa validity window"
                })

    result["score"] = max(0, min(100, result["score"]))
    has_critical = any(c.get("severity") == "CRITICAL" and c.get("status") == "WRONG" for c in result["checks"])
    result["valid"] = not has_critical and result["score"] >= 70

    return result
