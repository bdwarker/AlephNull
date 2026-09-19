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
import time
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, Any, Optional

# Safe UTF-8 console output for Windows
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

try:
    from .mrz_parser import parse_mrz
except (ImportError, ValueError):
    try:
        # pyrefly: ignore [missing-import]
        from mrz_parser import parse_mrz
    except ImportError:
        from modules.doc_validation.src.mrz_parser import parse_mrz

# pyrefly: ignore [missing-import]
from rules.passport_rules import validate_passport
# pyrefly: ignore [missing-import]
from rules.id_card_rules import validate_id_card
# pyrefly: ignore [missing-import]
from rules.dl_rules import validate_driving_license
# pyrefly: ignore [missing-import]
from rules.visa_rules import validate_visa
# pyrefly: ignore [missing-import]
from rules.permit_rules import validate_permit

try:
    # pyrefly: ignore [missing-import]
    from rules.aadhaar_rules import validate_aadhaar
except ImportError:
    try:
        from ..rules.aadhaar_rules import validate_aadhaar
    except Exception:
        from modules.doc_validation.rules.aadhaar_rules import validate_aadhaar

try:
    from .aadhaar_qr import decode_aadhaar_qr_from_file
except (ImportError, ValueError):
    try:
        # pyrefly: ignore [missing-import]
        from aadhaar_qr import decode_aadhaar_qr_from_file
    except ImportError:
        from modules.doc_validation.src.aadhaar_qr import decode_aadhaar_qr_from_file


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [DOC_VAL] {msg}", flush=True)


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
        if "aadhaar" in dt or "aadhar" in dt or "uidai" in dt:
            return "aadhaar"
        if any(x in dt for x in ["dl", "driver", "driving", "license"]):
            return "driving_license"
        if any(x in dt for x in ["national_id", "id_card", "state_id", "card", "national"]):
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

        alias_map = {
            "name": ["name", "fullname", "holdername", "givenname", "full_name"],
            "passport_number": ["passportnumber", "passportno", "documentnumber", "docnumber", "docno"],
            "id_number": ["idnumber", "idno", "documentnumber", "docnumber", "docno", "aadhaarnumber", "aadhaar", "nationalid"],
            "dob": ["dob", "dateofbirth", "birthdate", "birth"],
            "expiry": ["expiry", "dateofexpiry", "expirationdate", "validuntil", "validtill"],
            "nationality": ["nationality", "countrycode", "country", "citizenship"],
            "gender": ["gender", "sex"],
            "license_number": ["licensenumber", "licenseno", "dlno", "drivinglicensenumber"],
            "issue_date": ["issuedate", "dateofissue"],
            "blood_group": ["bloodgroup", "blood"]
        }

        canonical = {}
        for target, aliases in alias_map.items():
            for alias in aliases:
                if alias in normalized and normalized[alias]:
                    canonical[target] = normalized[alias]
                    break

        canonical.update(data)
        return canonical

    def validate_document(
        self,
        ocr_input: Union[Dict[str, Any], str, Path],
        doc_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main validation pipeline.
        """
        start_time = time.time()
        _log("=" * 60)
        _log("STARTING DOCUMENT VALIDATION ENGINE")

        # 1. Parse Input
        raw_data = {}
        if isinstance(ocr_input, (str, Path)):
            path_obj = Path(ocr_input)
            if path_obj.exists() and path_obj.is_file():
                try:
                    with open(path_obj, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    _log(f"Loaded JSON input from file: {path_obj}")
                except Exception as e:
                    _log(f"ERROR reading JSON file: {e}")
                    return self._error_result(f"Failed to read JSON file: {e}")
            else:
                try:
                    raw_data = json.loads(str(ocr_input))
                    _log("Parsed raw JSON string input")
                except Exception:
                    _log(f"ERROR: Invalid input string/file: {ocr_input}")
                    return self._error_result(f"Invalid input. File not found or malformed JSON: {ocr_input}")
        elif isinstance(ocr_input, dict):
            raw_data = ocr_input
            _log(f"Received dictionary input with {len(raw_data)} keys")
        else:
            _log(f"ERROR: Unsupported input type: {type(ocr_input).__name__}")
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
        _log(f"Detected Document Type: '{detected_doc_type}' -> Normalized: '{norm_type}'")

        # 3. Handle Module 1 Nested Outputs vs Direct Dicts
        extracted_fields = raw_data.get("extracted_fields") or raw_data
        mrz_data = raw_data.get("mrz_parsed")

        # Normalize keys
        fields = self._normalize_fields(extracted_fields)
        _log(f"Normalized fields for rule checking ({len(fields)} fields): {list(fields.keys())}")

        # 4. Dispatch to Document-Specific Rule Engine
        validation = {}
        _log(f"Dispatching to validation rule engine for: {norm_type}")
        if norm_type == "passport":
            validation = validate_passport(fields, mrz_data=mrz_data)
        elif norm_type == "aadhaar":
            qr_data = raw_data.get("aadhaar_qr_parsed") or raw_data.get("qr_parsed") or raw_data.get("qr_data")
            if not qr_data and (raw_data.get("aadhaar_qr_path") or raw_data.get("qr_path")):
                qr_file = raw_data.get("aadhaar_qr_path") or raw_data.get("qr_path")
                try:
                    qr_data = decode_aadhaar_qr_from_file(qr_file)
                    _log(f"Decoded Aadhaar QR from {qr_file}: status={qr_data.get('status')}")
                except Exception as qr_err:
                    _log(f"Warning decoding Aadhaar QR: {qr_err}")
            validation = validate_aadhaar(fields, qr_data=qr_data)
        elif norm_type in ["national_id", "id_card"]:
            validation = validate_id_card(fields)
        elif norm_type in ["driving_license", "dl"]:
            validation = validate_driving_license(fields)
        elif norm_type == "visa":
            validation = validate_visa(fields)
        elif norm_type == "permit":
            validation = validate_permit(fields)
        else:
            _log(f"ERROR: Unsupported document type '{detected_doc_type}'")
            return self._error_result(f"Unsupported document type '{detected_doc_type}'")

        # Cross Validation VIZ vs MRZ
        cross_checks = validation.get("cross_checks", [])
        anomalies = list(set(validation.get("anomalies", [])))

        if mrz_data and "mrz_lines" in mrz_data:
            _log("Cross-verifying Visual Inspection Zone (VIZ) against MRZ data...")
            parsed_mrz = parse_mrz(mrz_data["mrz_lines"])
            if parsed_mrz.get("is_valid"):
                if "dob" in fields:
                    viz_dob = str(fields["dob"]).replace("-", "")[2:]
                    mrz_dob = parsed_mrz.get("dob")
                    match = (viz_dob == mrz_dob)
                    cross_checks.append({"check": "DOB VIZ vs MRZ", "match": match, "visual_value": viz_dob, "mrz_value": mrz_dob})
                    _log(f"  Cross-Check DOB : VIZ={viz_dob} vs MRZ={mrz_dob} -> {'MATCH' if match else 'MISMATCH'}")

                if "document_number" in fields or "passport_number" in fields:
                    viz_doc = str(fields.get("document_number", fields.get("passport_number", "")))
                    mrz_doc = parsed_mrz.get("document_number")
                    match = (viz_doc == mrz_doc)
                    cross_checks.append({"check": "Doc Number VIZ vs MRZ", "match": match, "visual_value": viz_doc, "mrz_value": mrz_doc})
                    _log(f"  Cross-Check Doc#: VIZ={viz_doc} vs MRZ={mrz_doc} -> {'MATCH' if match else 'MISMATCH'}")
            else:
                anomalies.append("MRZ Checksum Validation Failed")
                _log("  WARNING: MRZ Checksum Validation Failed!")

        # 5. Compile Suspicious Points & Document Compliance Score
        score = validation["score"]
        is_valid = validation["valid"]

        suspicious_points = []
        for c in validation.get("checks", []):
            if c.get("status") in ["WRONG", "WARNING"]:
                fld = c.get("field", "Field")
                rsn = c.get("reason", "Validation issue")
                suspicious_points.append(f"{fld}: {rsn}")

        for cc in cross_checks:
            if not cc.get("match"):
                sec_val = cc.get("qr_value") if cc.get("qr_value") is not None else cc.get("mrz_value")
                sec_type = "QR" if cc.get("qr_value") is not None else "MRZ"
                suspicious_points.append(f"Visual vs {sec_type} Mismatch: {cc.get('check', 'Cross-check')} (Visual: '{cc.get('visual_value')}' vs {sec_type}: '{sec_val}')")

        for anom in anomalies:
            anom_str = str(anom)
            if not any(anom_str.lower() in sp.lower() for sp in suspicious_points):
                suspicious_points.append(anom_str)

        # De-duplicate suspicious points while preserving order
        unique_suspicious = []
        for pt in suspicious_points:
            if pt not in unique_suspicious:
                unique_suspicious.append(pt)

        if len(unique_suspicious) == 0:
            status = "VERIFIED"
            summary_txt = "All document checks, format rules, and mathematical checksums verified successfully. No suspicious points identified."
        else:
            status = "SUSPICIOUS_POINTS_IDENTIFIED"
            summary_txt = f"{len(unique_suspicious)} suspicious point(s) flagged by document validation engine for officer review."

        # Compute summary metrics
        total_checks = len(validation["checks"])
        passed_checks = sum(1 for c in validation["checks"] if c.get("status") == "CORRECT")
        failed_checks = sum(1 for c in validation["checks"] if c.get("status") == "WRONG")
        warning_checks = sum(1 for c in validation["checks"] if c.get("status") == "WARNING")

        dur = time.time() - start_time
        _log(f"Validation Checks Summary: {passed_checks}/{total_checks} passed, {failed_checks} failed, {warning_checks} warnings")
        _log(f"COMPLIANCE SCORE: {round(score, 1)}/100 | STATUS: {status} | SUSPICIOUS POINTS: {len(unique_suspicious)}")
        for pt in unique_suspicious:
            _log(f"  🚩 SUSPICIOUS: {pt}")
        _log(f"DOCUMENT VALIDATION FINISHED in {dur:.2f}s")
        _log("=" * 60)

        return {
            "valid": is_valid,
            "score": round(score, 1),
            "status": status,
            "document_type": norm_type,
            "suspicious_points": unique_suspicious,
            "decision": {
                "score": round(score, 1),
                "suspicious_points": unique_suspicious,
                "summary": summary_txt
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
            "cross_checks": cross_checks,
            "aadhaar_qr": validation.get("qr_data") or raw_data.get("aadhaar_qr_parsed") or raw_data.get("qr_parsed"),
            "input_fields": {k: v for k, v in fields.items() if isinstance(v, (str, int, float, bool)) and len(str(v)) < 100}
        }

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Returns structured error dictionary."""
        _log(f"Document validation error: {error_message}")
        return {
            "valid": False,
            "score": 0.0,
            "status": "ERROR",
            "document_type": "unknown",
            "suspicious_points": [f"Document validation error: {error_message}"],
            "decision": {
                "score": 0.0,
                "suspicious_points": [f"Document validation error: {error_message}"],
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


# Functional interface
def validate_document(ocr_output: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """Top-level functional interface matching prototype specification."""
    validator = DocumentValidator()
    return validator.validate_document(ocr_output)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlephNull Module 2: Document Validation Engine")
    parser.add_argument("input", nargs="?", help="Path to JSON file or raw JSON string")
    parser.add_argument("--type", "-t", default=None, help="Document type")

    args = parser.parse_args()
    validator = DocumentValidator()

    if args.input:
        res = validator.validate_document(args.input, doc_type=args.type)
    else:
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

    print(json.dumps(res, indent=2))
