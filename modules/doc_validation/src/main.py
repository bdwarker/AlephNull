"""
AlephNull — Module 2: Document Validation Engine
=================================================
Validates structured data extracted by Module 1 (Document OCR) against official
government and international standards (ICAO Doc 9303, ISO 3166-1, UIDAI Verhoeff, Indian RTO).

Inputs:
- Output of Module 1 (DocumentOCR) or raw dictionary / JSON file.

Outputs:
- Comprehensive compliance verdict, calibrated trust score (0-100), rule checks,
  anomaly flags, and border security decision recommendation.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Union, Dict, Any, Optional

# Fix Windows console encoding issues with UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure rules can be imported relative to this file or from modules
CURRENT_DIR = Path(__file__).resolve().parent
MODULE_ROOT = CURRENT_DIR.parent
PROJECT_ROOT = MODULE_ROOT.parent.parent

if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rules.passport_rules import validate_passport
from rules.id_card_rules import validate_id_card
from rules.dl_rules import validate_driving_license
from rules.visa_rules import validate_visa
from rules.permit_rules import validate_permit

SUPPORTED_DOCUMENTS = [
    "passport",
    "national_id",
    "id_card",
    "aadhaar",
    "driving_license",
    "dl",
    "visa",
    "permit"
]


class DocumentValidator:
    """
    Enterprise-grade rule engine validating identity documents against official formatting,
    cryptographic/mathematical checksums, and temporal coherence standards.
    """

    def __init__(self):
        pass

    @staticmethod
    def normalize_doc_type(doc_type: Any) -> str:
        """Normalizes document type strings from various schemas."""
        if not doc_type:
            return "passport"
        dt = str(doc_type).strip().lower().replace("-", "_").replace(" ", "_")
        if "passport" in dt or dt == "p":
            return "passport"
        if any(x in dt for x in ["dl", "driver", "driving", "license"]):
            return "driving_license"
        if any(x in dt for x in ["aadhaar", "national_id", "id_card", "state_id", "card", "national"]):
            return "national_id"
        if "visa" in dt:
            return "visa"
        if any(x in dt for x in ["permit", "entry_pass", "border_pass"]):
            return "permit"
        return "passport"

    @staticmethod
    def _normalize_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps heterogeneous field naming conventions (Title Case, camelCase, snake_case)
        to a unified accessible dictionary.
        """
        normalized = {}
        for k, v in data.items():
            normalized[k] = v
            clean_k = re.sub(r'[\s_-]', '', k.lower())
            normalized[clean_k] = v

        # Key alias mappings
        aliases = {
            "name": ["name", "fullname", "holdername"],
            "passport_number": ["passportnumber", "passportno", "documentnumber", "docnumber"],
            "id_number": ["idnumber", "idno", "aadhaarnumber", "aadhaarno", "uid"],
            "license_number": ["licensenumber", "licenseno", "dlno", "dlnumber"],
            "visa_number": ["visanumber", "visano"],
            "permit_number": ["permitnumber", "permitno"],
            "dob": ["dateofbirth", "birthdate", "dob"],
            "expiry": ["dateofexpiry", "expirydate", "validuntil", "validtill", "expiry"],
            "issue_date": ["dateofissue", "issuedate", "issuingdate"],
            "nationality": ["nationality", "country", "citizenship"],
            "gender": ["gender", "sex"],
            "address": ["address", "residentialaddress"],
            "blood_group": ["bloodgroup", "bloodtype"],
            "visa_type": ["visatype", "visacategory", "type"],
            "stay_duration": ["stayduration", "durationofstay", "duration"],
            "entries": ["entries", "entrytype", "entryvalidation"]
        }

        canonical = {}
        for target, source_keys in aliases.items():
            for sk in source_keys:
                if sk in normalized and normalized[sk] is not None:
                    canonical[target] = normalized[sk]
                    break

        # Merge raw fields alongside canonical so all lookups succeed
        canonical.update(data)
        return canonical

    def validate_document(
        self,
        ocr_input: Union[Dict[str, Any], str, Path],
        doc_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main validation pipeline.
        
        Args:
            ocr_input: Dict from Module 1 (DocumentOCR), flat dictionary, JSON string, or filepath.
            doc_type: Optional document type override ('passport', 'national_id', 'driving_license', 'visa', 'permit').
            
        Returns:
            dict: Comprehensive validation results conforming to SIH PS26188 standards.
        """
        # 1. Parse Input
        raw_data = {}
        if isinstance(ocr_input, (str, Path)):
            path_obj = Path(ocr_input)
            if path_obj.exists() and path_obj.is_file():
                try:
                    with open(path_obj, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                except Exception as e:
                    return self._error_result(f"Failed to read JSON file: {e}")
            else:
                # Attempt to parse as raw JSON string
                try:
                    raw_data = json.loads(str(ocr_input))
                except Exception:
                    return self._error_result(f"Invalid input. File not found or malformed JSON: {ocr_input}")
        elif isinstance(ocr_input, dict):
            raw_data = ocr_input
        else:
            return self._error_result(f"Unsupported input type: {type(ocr_input).__name__}")

        # 2. Extract Document Type
        detected_doc_type = (
            doc_type
            or raw_data.get("document_type")
            or raw_data.get("type")
            or raw_data.get("Document Type")
            or "passport"
        )
        norm_type = self.normalize_doc_type(detected_doc_type)

        # 3. Handle Module 1 Nested Outputs vs Direct Dicts
        extracted_fields = raw_data.get("extracted_fields") or raw_data
        mrz_data = raw_data.get("mrz_parsed")
        
        # Normalize keys
        fields = self._normalize_fields(extracted_fields)

        # 4. Dispatch to Document-Specific Rule Engine
        if norm_type == "passport":
            validation = validate_passport(fields, mrz_data=mrz_data)
        elif norm_type in ["national_id", "id_card", "aadhaar"]:
            validation = validate_id_card(fields)
        elif norm_type in ["driving_license", "dl"]:
            validation = validate_driving_license(fields)
        elif norm_type == "visa":
            validation = validate_visa(fields)
        elif norm_type == "permit":
            validation = validate_permit(fields)
        else:
            return self._error_result(f"Unsupported document type '{detected_doc_type}'")

        # 5. Compute Border Security Verdict & Recommendation
        score = validation["score"]
        is_valid = validation["valid"]
        anomalies = list(set(validation.get("anomalies", [])))

        if is_valid and score >= 80:
            status = "PASSED"
            verdict = "CLEARANCE"
            decision_summary = "Document fully compliant with official formatting and security standards. Recommended for automated clearance."
        elif score >= 60 and not any("CRITICAL" in c.get("severity", "") and c.get("status") == "WRONG" for c in validation["checks"]):
            status = "FLAGGED"
            verdict = "SECONDARY_INSPECTION"
            decision_summary = f"Document has {len(validation['flags'])} non-critical warning(s). Route to secondary inspection for physical verification."
        else:
            status = "REJECTED"
            verdict = "REJECT"
            crit_reasons = [c["reason"] for c in validation["checks"] if c.get("severity") == "CRITICAL" and c.get("status") == "WRONG"]
            reason_txt = "; ".join(crit_reasons[:2]) if crit_reasons else "Failed security and format validation"
            decision_summary = f"High fraud risk detected: {reason_txt}. Immediate officer intervention required."

        # Compute summary metrics
        total_checks = len(validation["checks"])
        passed_checks = sum(1 for c in validation["checks"] if c.get("status") == "CORRECT")
        failed_checks = sum(1 for c in validation["checks"] if c.get("status") == "WRONG")
        warning_checks = sum(1 for c in validation["checks"] if c.get("status") == "WARNING")

        return {
            "valid": is_valid,
            "score": round(score, 1),
            "status": status,
            "document_type": norm_type,
            "decision": {
                "verdict": verdict,
                "summary": decision_summary
            },
            "checks_summary": {
                "total": total_checks,
                "passed": passed_checks,
                "failed": failed_checks,
                "warnings": warning_checks
            },
            "checks": validation["checks"],
            "flags": validation["flags"],
            "anomalies": anomalies,
            "cross_checks": validation.get("cross_checks", []),
            "input_fields": {k: v for k, v in fields.items() if isinstance(v, (str, int, float, bool)) and len(str(v)) < 100}
        }

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Returns structured error dictionary."""
        return {
            "valid": False,
            "score": 0.0,
            "status": "REJECTED",
            "document_type": "unknown",
            "decision": {
                "verdict": "REJECT",
                "summary": f"Validation could not proceed: {error_message}"
            },
            "checks_summary": {"total": 0, "passed": 0, "failed": 1, "warnings": 0},
            "checks": [{
                "field": "document",
                "status": "WRONG",
                "severity": "CRITICAL",
                "reason": error_message
            }],
            "flags": [error_message],
            "anomalies": ["VALIDATION_ENGINE_ERROR"],
            "cross_checks": [],
            "input_fields": {}
        }


# Backwards compatibility function matching sample code syntax
def validate_document(ocr_output: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """Top-level functional interface matching prototype specification."""
    validator = DocumentValidator()
    return validator.validate_document(ocr_output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlephNull Module 2: Document Validation Engine")
    parser.add_argument("input", nargs="?", help="Path to JSON file or raw JSON string")
    parser.add_argument("--type", "-t", default=None, help="Document type (passport, national_id, driving_license, visa, permit)")
    parser.add_argument("--pretty", "-p", action="store_true", help="Format output with inspection box")

    args = parser.parse_args()

    validator = DocumentValidator()

    if args.input:
        res = validator.validate_document(args.input, doc_type=args.type)
    else:
        # Check if module1_output.json exists in cwd
        default_file = Path("module1_output.json")
        if default_file.exists():
            print("Found module1_output.json. Running validation...")
            res = validator.validate_document(str(default_file), doc_type=args.type)
        else:
            # Run demonstration on sample passport
            print("AlephNull Document Validation Module ready.")
            print("No input provided. Running self-diagnostic demonstration on a sample passport...")
            demo_passport = {
                "document_type": "passport",
                "name": "MOHAMMED HASSAN",
                "passport_number": "Z1234567",
                "nationality": "IND",
                "dob": "1988-01-23",
                "expiry": "2030-01-01",
                "gender": "Male"
            }
            res = validator.validate_document(demo_passport)

    print("\n========================================================")
    print("       ALEPHNULL MODULE 2 — DOCUMENT VALIDATION")
    print("========================================================")
    print(f" Document Type  : {res['document_type'].upper()}")
    print(f" Overall Status : {res['status']}")
    print(f" Validity Score : {res['score']} / 100")
    print(f" Officer Verdict: {res['decision']['verdict']}")
    print(f" Decision Note  : {res['decision']['summary']}")
    print("--------------------------------------------------------")
    print(" Checks Summary :", res["checks_summary"])
    print("--------------------------------------------------------")
    print(" Rule Checks Breakdown:")
    for c in res["checks"]:
        sym = "PASS" if c["status"] == "CORRECT" else "WARN" if c["status"] == "WARNING" else "FAIL"
        print(f"  [{sym:<4}] {c['field']:<26} -> {c['status']:<7} ({c.get('severity', 'INFO'):<8}) : {c['reason']}")

    if res["flags"]:
        print("--------------------------------------------------------")
        print(" Active Security Flags & Warnings:")
        for f in res["flags"]:
            print(f"  [FLAG] {f}")

    if res.get("cross_checks"):
        print("--------------------------------------------------------")
        print(" Cross-Verification Results:")
        for cc in res["cross_checks"]:
            match_sym = "MATCH" if cc.get("match") else "MISMATCH"
            print(f"  <-> {cc['check']:<28} : {match_sym} (Visual: {cc.get('visual_value')}, MRZ: {cc.get('mrz_value')})")
    print("========================================================\n")
