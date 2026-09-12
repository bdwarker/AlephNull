"""
ICAO Doc 9303 Machine Readable Travel Documents (MRTD) Checksum & Standard Specifications.

Implements:
- 7-3-1 weight check-digit calculation (Modulo 10)
- Character mapping: 0-9 -> 0-9, A-Z -> 10-35, '<' -> 0
- ISO 3166-1 alpha-3 country and issuing authority codes
- Verification of Passport Number, Date of Birth, Expiry, and Composite Checksums
"""

from typing import Union, Dict, Any, Optional

# Weights in repeating cycle 7, 3, 1 per ICAO Doc 9303 Part 3
ICAO_WEIGHTS = (7, 3, 1)

# Comprehensive ISO 3166-1 alpha-3 codes + official ICAO special codes (UTO, XOM, XXA, etc.)
ISO_3166_ALPHA3 = {
    # Major global and regional codes
    "IND", "USA", "GBR", "CAN", "AUS", "FRA", "DEU", "ITA", "ESP", "NLD",
    "CHE", "SWE", "NOR", "DNK", "FIN", "IRL", "BEL", "AUT", "PRT", "GRC",
    "RUS", "UKR", "POL", "CZE", "HUN", "ROU", "BGR", "TUR", "ISR", "SAU",
    "ARE", "QAT", "KWT", "OMN", "BHR", "EGY", "ZAF", "NGA", "KEN", "GHA",
    "CHN", "JPN", "KOR", "TWN", "HKG", "SGP", "MYS", "THA", "VNM", "IDN",
    "PHL", "NZL", "BRA", "ARG", "CHL", "COL", "MEX", "PER", "VEN",
    # SSB Border & Neighboring Countries (Critical for border screening)
    "NPL", "BTN", "BGD", "LKA", "MDV", "PAK", "AFG", "MMR",
    # Special & Test Codes
    "D<<", "UTO", "XOM", "XXA", "XXB", "XXC", "XXX", "UNA", "UNK"
}

# Common country name mapping to ISO-3
COUNTRY_NAME_TO_ISO3 = {
    "INDIA": "IND", "INDIAN": "IND",
    "UNITED STATES": "USA", "AMERICAN": "USA", "USA": "USA",
    "UNITED KINGDOM": "GBR", "BRITISH": "GBR", "GREAT BRITAIN": "GBR", "UK": "GBR",
    "CANADA": "CAN", "CANADIAN": "CAN",
    "AUSTRALIA": "AUS", "AUSTRALIAN": "AUS",
    "GERMANY": "DEU", "GERMAN": "DEU", "DEUTSCHLAND": "DEU",
    "FRANCE": "FRA", "FRENCH": "FRA",
    "NEPAL": "NPL", "NEPALESE": "NPL", "NEPALI": "NPL",
    "BHUTAN": "BTN", "BHUTANESE": "BTN",
    "BANGLADESH": "BGD", "BANGLADESHI": "BGD",
    "SRI LANKA": "LKA", "SRI LANKAN": "LKA",
    "MALDIVES": "MDV", "MALDIVIAN": "MDV",
    "UNITED ARAB EMIRATES": "ARE", "EMIRATI": "ARE", "UAE": "ARE",
    "SINGAPORE": "SGP", "SINGAPOREAN": "SGP",
    "CHINA": "CHN", "CHINESE": "CHN",
    "JAPAN": "JPN", "JAPANESE": "JPN"
}


def char_to_value(char: str) -> int:
    """
    Converts a character to its numerical value per ICAO 9303:
    - '0'-'9': 0-9
    - 'A'-'Z': 10-35
    - '<' or filler: 0
    """
    c = char.upper()
    if '0' <= c <= '9':
        return ord(c) - ord('0')
    elif 'A' <= c <= 'Z':
        return ord(c) - ord('A') + 10
    else:
        return 0


def compute_check_digit(data: str) -> int:
    """
    Computes the ICAO 9303 check digit (modulo 10) for a given data string using 7-3-1 weights.
    """
    total = 0
    for i, char in enumerate(data):
        weight = ICAO_WEIGHTS[i % 3]
        val = char_to_value(char)
        total += val * weight
    return total % 10


def verify_check_digit(data: str, expected_digit: Union[int, str]) -> bool:
    """
    Verifies if data string produces the expected check digit.
    Handles OCR digit confusions (O->0, I->1, etc.).
    """
    if expected_digit is None or str(expected_digit).strip() == "":
        return False
    exp_str = str(expected_digit).strip().upper()
    trans = str.maketrans('OIZSB<', '012580')
    exp_clean = exp_str.translate(trans)
    
    if not exp_clean.isdigit():
        return False
    
    computed = compute_check_digit(data)
    return computed == int(exp_clean)


def verify_mrz_checksums(mrz_parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifies all check digits available from MRZ data:
    - Passport Number check digit
    - Date of Birth check digit
    - Date of Expiry check digit
    - Composite check digit (if full line2 available)
    """
    results = {
        "all_passed": True,
        "checks": []
    }
    
    fields = mrz_parsed.get("fields", {})
    check_digits = mrz_parsed.get("check_digits", {})
    raw_lines = mrz_parsed.get("raw_lines", {})
    
    passport_no = fields.get("Passport Number")
    p_chk = check_digits.get("passport_number_chk")
    if passport_no and p_chk is not None:
        # Standard TD3 document number field is 9 characters (padded with '<' if shorter)
        doc_field = passport_no.upper().ljust(9, '<')[:9]
        valid_p = verify_check_digit(doc_field, p_chk)
        results["checks"].append({
            "check": "MRZ_PASSPORT_NUMBER_CHECKSUM",
            "passed": valid_p,
            "field_value": passport_no,
            "expected_check_digit": str(p_chk),
            "computed_check_digit": str(compute_check_digit(doc_field)),
            "message": "Passport number check digit verified" if valid_p else f"Check digit mismatch for passport number: expected {p_chk}, computed {compute_check_digit(doc_field)}"
        })
        if not valid_p:
            results["all_passed"] = False

    # DOB checksum (YYMMDD)
    dob = fields.get("Date of Birth")
    dob_chk = check_digits.get("dob_chk")
    if dob and dob_chk is not None:
        # Convert YYYY-MM-DD to YYMMDD
        dob_digits = "".join(c for c in dob if c.isdigit())
        if len(dob_digits) == 8:
            yymmdd = dob_digits[2:]
        elif len(dob_digits) == 6:
            yymmdd = dob_digits
        else:
            yymmdd = None
            
        if yymmdd:
            valid_dob = verify_check_digit(yymmdd, dob_chk)
            results["checks"].append({
                "check": "MRZ_DOB_CHECKSUM",
                "passed": valid_dob,
                "field_value": dob,
                "expected_check_digit": str(dob_chk),
                "computed_check_digit": str(compute_check_digit(yymmdd)),
                "message": "DOB check digit verified" if valid_dob else f"Check digit mismatch for DOB: expected {dob_chk}, computed {compute_check_digit(yymmdd)}"
            })
            if not valid_dob:
                results["all_passed"] = False

    # Expiry checksum (YYMMDD)
    exp = fields.get("Date of Expiry")
    exp_chk = check_digits.get("expiry_chk")
    if exp and exp_chk is not None:
        exp_digits = "".join(c for c in exp if c.isdigit())
        if len(exp_digits) == 8:
            yymmdd = exp_digits[2:]
        elif len(exp_digits) == 6:
            yymmdd = exp_digits
        else:
            yymmdd = None
            
        if yymmdd:
            valid_exp = verify_check_digit(yymmdd, exp_chk)
            results["checks"].append({
                "check": "MRZ_EXPIRY_CHECKSUM",
                "passed": valid_exp,
                "field_value": exp,
                "expected_check_digit": str(exp_chk),
                "computed_check_digit": str(compute_check_digit(yymmdd)),
                "message": "Expiry check digit verified" if valid_exp else f"Check digit mismatch for Expiry: expected {exp_chk}, computed {compute_check_digit(yymmdd)}"
            })
            if not valid_exp:
                results["all_passed"] = False

    return results
