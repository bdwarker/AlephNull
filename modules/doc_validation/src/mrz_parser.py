"""
MRZ Parser and Checksum Validator
Implements ICAO Doc 9303 modulo-10 (7-3-1 weighting) validation.
"""

import sys
from datetime import datetime

# Safe UTF-8 console output for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [MRZ] {msg}", flush=True)


def char_value(c: str) -> int:
    """Returns integer value for MRZ character."""
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    return 0


def mrz_check_digit(field: str) -> int:
    """Calculates ICAO 9303 modulo-10 check digit with (7, 3, 1) weights."""
    weights = (7, 3, 1)
    total = sum(char_value(c) * weights[i % 3] for i, c in enumerate(field))
    return total % 10


def parse_mrz(mrz_lines: list) -> dict:
    """
    Parses MRZ lines and validates check digits.
    Supports TD3 (Passports) as primary example.
    """
    _log(f"Received {len(mrz_lines)} lines for MRZ parsing")
    for idx, l in enumerate(mrz_lines):
        _log(f"  Line {idx+1}: {l} (len={len(l)})")

    if len(mrz_lines) >= 2:
        line1 = mrz_lines[0].strip().upper()
        line2 = mrz_lines[1].strip().upper()

        # Normalize to 44 characters
        if len(line1) < 44:
            line1 = line1.ljust(44, '<')
        elif len(line1) > 44:
            line1 = line1[:44]

        if len(line2) < 44:
            line2 = line2.ljust(44, '<')
        elif len(line2) > 44:
            line2 = line2[:44]

        if len(line1) == 44 and len(line2) == 44:
            # TD3 Passport
            # Line 1: Type, Country, Name
            doc_type = line1[0:2].replace("<", "")
            country = line1[2:5]
            name_str = line1[5:].split("<<")
            surname = name_str[0].replace("<", " ").strip() if len(name_str) > 0 else ""
            given_names = name_str[1].replace("<", " ").strip() if len(name_str) > 1 else ""

            # Line 2: DocNumber, Nat, DOB, Gender, Expiry, PersonalNo
            doc_no = line2[0:9].replace("<", "")
            doc_no_cd = line2[9]
            nationality = line2[10:13]
            dob = line2[13:19]
            dob_cd = line2[19]
            gender = line2[20]
            expiry = line2[21:27]
            expiry_cd = line2[27]
            personal_no = line2[28:42]
            personal_no_cd = line2[42]
            composite_cd = line2[43]

            # Validate Check Digits
            calc_doc_cd = str(mrz_check_digit(line2[0:9]))
            valid_doc_no = (calc_doc_cd == doc_no_cd) if doc_no_cd != "<" else True

            calc_dob_cd = str(mrz_check_digit(dob))
            valid_dob = (calc_dob_cd == dob_cd)

            calc_exp_cd = str(mrz_check_digit(expiry))
            valid_expiry = (calc_exp_cd == expiry_cd)

            composite_str = line2[0:10] + line2[13:20] + line2[21:43]
            calc_comp_cd = str(mrz_check_digit(composite_str))
            valid_composite = (calc_comp_cd == composite_cd)

            is_valid = valid_doc_no and valid_dob and valid_expiry and valid_composite

            _log(f"Parsed TD3 Passport:")
            _log(f"  Document No: {doc_no} (CD check: {valid_doc_no})")
            _log(f"  DOB        : {dob} (CD check: {valid_dob})")
            _log(f"  Expiry     : {expiry} (CD check: {valid_expiry})")
            _log(f"  Composite  : (CD check: {valid_composite})")
            _log(f"  Overall MRZ Integrity: {'VALID' if is_valid else 'CHECKSUM_FAILED'}")

            return {
                "type": doc_type,
                "country": country,
                "surname": surname,
                "given_names": given_names,
                "document_number": doc_no,
                "nationality": nationality,
                "dob": dob,
                "gender": gender,
                "expiry": expiry,
                "personal_no": personal_no.replace("<", ""),
                "checks": {
                    "document_number_valid": valid_doc_no,
                    "dob_valid": valid_dob,
                    "expiry_valid": valid_expiry,
                    "composite_valid": valid_composite
                },
                "is_valid": is_valid
            }

    _log("Warning: MRZ format unsupported or lines insufficient")
    return {"is_valid": False, "error": "Unsupported MRZ format"}
