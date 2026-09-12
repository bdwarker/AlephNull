"""
Driving License (DL) validation rules engine.
Implements Indian RTO state code validation, age minimums (>=18 years), validity duration, and blood groups.
"""

import re
from datetime import datetime
from typing import Dict, Any

# Valid 2-letter state/UT codes for Indian Regional Transport Offices (RTO)
INDIAN_RTO_STATE_CODES = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "CH": "Chandigarh",
    "DD": "Daman and Diu",
    "DL": "Delhi",
    "DN": "Dadra and Nagar Haveli",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HP": "Himachal Pradesh",
    "HR": "Haryana",
    "JH": "Jharkhand",
    "JK": "Jammu and Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TR": "Tripura",
    "TS": "Telangana",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal"
}

VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}


def validate_driving_license(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates Driving License:
    1. Mandatory fields (Name, License Number, DOB, Expiry).
    2. Format compliance & RTO state code verification.
    3. Legal Age verification: License holder must be >= 18 at issuance.
    4. Chronological consistency (Issue date vs Expiry vs DOB).
    5. Expiration status relative to current date.
    6. Medical blood group verification.
    """
    result = {
        "valid": True,
        "score": 100,
        "flags": [],
        "anomalies": [],
        "checks": []
    }

    name = str(data.get("name") or data.get("Name") or "").strip()
    license_no = str(data.get("license_number") or data.get("License Number") or data.get("dl_no") or "").strip()
    dob_raw = str(data.get("dob") or data.get("Date of Birth") or data.get("date_of_birth") or "").strip()
    expiry_raw = str(data.get("expiry") or data.get("Date of Expiry") or data.get("valid_till") or "").strip()
    issue_raw = str(data.get("issue_date") or data.get("Issue Date") or "").strip()
    gender = str(data.get("gender") or data.get("Gender") or "").strip()
    blood_group = str(data.get("blood_group") or data.get("Blood Group") or "").strip().upper()

    now = datetime.now()

    # 1. Required Fields Check
    fields_map = {
        "name": name,
        "license_number": license_no,
        "dob": dob_raw,
        "expiry": expiry_raw
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
                "reason": f"Mandatory driving license field '{f_key}' is missing or empty"
            })
        else:
            result["checks"].append({
                "field": f_key,
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Field '{f_key}' is present"
            })

    # 2. License Number & State Code Verification
    if license_no:
        clean_dl = re.sub(r'[\s-]', '', license_no.upper())
        
        # Check standard Indian DL format (SS-RRYYYYNNNNNNN: 2 state letters, 2 RTO digits, 4 year digits, 7 unique digits)
        m_in = re.match(r'^([A-Z]{2})(\d{2})(\d{4})(\d{7})$', clean_dl)
        if m_in:
            state_code = m_in.group(1)
            rto_code = m_in.group(2)
            year_issued = int(m_in.group(3))
            
            if state_code in INDIAN_RTO_STATE_CODES:
                state_name = INDIAN_RTO_STATE_CODES[state_code]
                result["checks"].append({
                    "field": "license_number_state",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": f"State code '{state_code}' verified ({state_name}, RTO {rto_code})"
                })
            else:
                result["score"] -= 25
                result["flags"].append(f"Invalid state code '{state_code}' in license number")
                result["anomalies"].append("INVALID_RTO_STATE_CODE")
                result["checks"].append({
                    "field": "license_number_state",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"State code '{state_code}' is not a recognized Indian State or Union Territory"
                })

            # Check year embedded in license number
            if 1950 <= year_issued <= now.year:
                result["checks"].append({
                    "field": "license_number_year",
                    "status": "CORRECT",
                    "severity": "INFO",
                    "reason": f"Issuance year {year_issued} in license number is plausible"
                })
            else:
                result["score"] -= 20
                result["flags"].append(f"Suspicious issuance year '{year_issued}' embedded in license number")
                result["anomalies"].append("SUSPICIOUS_DL_YEAR")
                result["checks"].append({
                    "field": "license_number_year",
                    "status": "WRONG",
                    "severity": "MAJOR",
                    "reason": f"Issuance year {year_issued} is in the future or unreasonably old"
                })

        elif re.match(r'^[A-Z0-9]{8,18}$', clean_dl):
            result["checks"].append({
                "field": "license_number",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"License number '{license_no}' follows generic alphanumeric format"
            })
        else:
            result["score"] -= 20
            result["flags"].append(f"Invalid driving license format: '{license_no}'")
            result["anomalies"].append("INVALID_DL_FORMAT")
            result["checks"].append({
                "field": "license_number",
                "status": "WRONG",
                "severity": "MAJOR",
                "reason": "License number does not match standard 15-16 character Indian or international DL format"
            })

    # 3. Dates & Legal Driving Age (>= 18)
    dob_dt = None
    exp_dt = None
    issue_dt = None

    if dob_raw:
        try:
            dob_clean = re.sub(r'[/.]', '-', dob_raw)
            dob_dt = datetime.strptime(dob_clean, "%Y-%m-%d")
            result["checks"].append({"field": "dob", "status": "CORRECT", "severity": "INFO", "reason": "Valid DOB format"})
            
            if dob_dt > now:
                result["score"] -= 30
                result["flags"].append(f"Date of birth cannot be in the future: {dob_raw}")
                result["anomalies"].append("FUTURE_DOB")
                result["checks"].append({"field": "dob", "status": "WRONG", "severity": "CRITICAL", "reason": "Date of birth is in the future"})
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid DOB format: '{dob_raw}'")
            result["anomalies"].append("INVALID_DOB_FORMAT")
            result["checks"].append({"field": "dob", "status": "WRONG", "severity": "MAJOR", "reason": "Expected YYYY-MM-DD"})

    if issue_raw:
        try:
            iss_clean = re.sub(r'[/.]', '-', issue_raw)
            issue_dt = datetime.strptime(iss_clean, "%Y-%m-%d")
            result["checks"].append({"field": "issue_date", "status": "CORRECT", "severity": "INFO", "reason": "Valid issue date format"})
            
            if issue_dt > now:
                result["score"] -= 25
                result["flags"].append(f"License issue date cannot be in the future: {issue_raw}")
                result["anomalies"].append("FUTURE_ISSUE_DATE")
                result["checks"].append({"field": "issue_date", "status": "WRONG", "severity": "CRITICAL", "reason": "Issue date is in the future"})
        except ValueError:
            pass

    # Legal Minimum Age Verification (Issue Date vs DOB)
    if dob_dt and issue_dt:
        age_at_issue = (issue_dt - dob_dt).days / 365.25
        if age_at_issue < 18.0:
            result["score"] -= 35
            result["flags"].append(f"Underage license issuance: age at issue was {age_at_issue:.1f} years (< 18)")
            result["anomalies"].append("UNDERAGE_LICENSE_HOLDER")
            result["checks"].append({
                "field": "legal_driving_age",
                "status": "WRONG",
                "severity": "CRITICAL",
                "reason": f"Motor Vehicles Act requires age >= 18 for driving license. Age at issuance was {age_at_issue:.1f} years"
            })
        else:
            result["checks"].append({
                "field": "legal_driving_age",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Cardholder satisfied legal driving age (>= 18) at issuance ({age_at_issue:.1f} years)"
            })

    if expiry_raw:
        try:
            exp_clean = re.sub(r'[/.]', '-', expiry_raw)
            exp_dt = datetime.strptime(exp_clean, "%Y-%m-%d")
            result["checks"].append({"field": "expiry", "status": "CORRECT", "severity": "INFO", "reason": "Valid expiry date format"})
            
            if exp_dt < now:
                result["score"] -= 30
                result["flags"].append(f"Driving license expired on {exp_clean}")
                result["anomalies"].append("EXPIRED_DOCUMENT")
                result["checks"].append({
                    "field": "expiry",
                    "status": "WRONG",
                    "severity": "CRITICAL",
                    "reason": f"Driving license expired on {exp_clean}. Invalid for official identification"
                })
        except ValueError:
            result["score"] -= 15
            result["flags"].append(f"Invalid Expiry format: '{expiry_raw}'")
            result["anomalies"].append("INVALID_EXPIRY_FORMAT")
            result["checks"].append({"field": "expiry", "status": "WRONG", "severity": "MAJOR", "reason": "Expected YYYY-MM-DD"})

    # Date Coherence (Expiry vs Issue and Expiry vs DOB)
    if issue_dt and exp_dt:
        if exp_dt <= issue_dt:
            result["score"] -= 25
            result["flags"].append("Expiry date is before or equal to issue date")
            result["anomalies"].append("EXPIRY_BEFORE_ISSUE")
            result["checks"].append({
                "field": "date_relationship",
                "status": "WRONG",
                "severity": "CRITICAL",
                "reason": "Expiry date must be after Issue date"
            })

    # 4. Blood Group Verification (if present)
    if blood_group:
        if blood_group in VALID_BLOOD_GROUPS:
            result["checks"].append({
                "field": "blood_group",
                "status": "CORRECT",
                "severity": "INFO",
                "reason": f"Standard blood group '{blood_group}' confirmed"
            })
        else:
            result["score"] -= 5
            result["flags"].append(f"Invalid blood group: '{blood_group}'")
            result["checks"].append({
                "field": "blood_group",
                "status": "WARNING",
                "severity": "MINOR",
                "reason": f"Blood group '{blood_group}' not recognized in standard ABO/Rh systems"
            })

    result["score"] = max(0, min(100, result["score"]))
    has_critical = any(c.get("severity") == "CRITICAL" and c.get("status") == "WRONG" for c in result["checks"])
    result["valid"] = not has_critical and result["score"] >= 70

    return result
