# Module 2: Document Validation Engine

Rule-based document authenticity and formatting compliance engine for border security (SSB / Problem Statement PS26188).

---

## Overview

Module 2 ingests the structured output from **Module 1 (Document OCR)** or direct document data and verifies compliance against official government standards, international formatting specifications (ICAO Doc 9303, ISO 3166-1), cryptographic/mathematical check-digit algorithms, and temporal constraints.

---

## Supported Document Standards

| Document Type | Rules & Specifications |
|---|---|
| **Passport** | ICAO Doc 9303 (TD3), 7-3-1 weight check digits (Passport No, DOB, Expiry), ISO 3166-1 alpha-3 nationality, 6-month validity warning, MRZ cross-verification. |
| **National ID / Aadhaar** | UIDAI 12-digit format rules (cannot begin with 0 or 1), Dihedral group $D_5$ **Verhoeff Checksum Algorithm** (catches 100% of single-digit and transposition errors), demographic consistency, postal PIN codes. |
| **Driving License** | Indian RTO 2-letter state code verification (all 36 states/UTs), standard 15-16 character alphanumeric structure, **Legal Driving Age $\ge 18$ years at issuance**, validity duration, ABO/Rh blood groups. |
| **Visa** | International classification (Tourist, Business, Student, Work, Diplomatic), single/multiple entry validation, **Stay duration $\le$ validity window** coherence, active expiration check. |
| **Permit** | Border / Inner Line Permit format, authorized sector/route, validity period. |

---

## Architecture

```
modules/doc_validation/
├── README.md
├── rules/
│   ├── __init__.py
│   ├── icao9303.py         # 7-3-1 check digit calculation & ISO 3166-1 index
│   ├── verhoeff.py         # Dihedral group D5 multiplication & permutation tables
│   ├── passport_rules.py   # ICAO TD3 passport rules, expiry, MRZ cross-check
│   ├── id_card_rules.py    # Aadhaar 12-digit format & Verhoeff checksum
│   ├── dl_rules.py         # Indian RTO state codes, legal driving age (>=18)
│   ├── visa_rules.py       # Visa type, stay duration <= validity window
│   └── permit_rules.py     # Border/Inner line permit verification
├── src/
│   ├── __init__.py
│   └── main.py             # DocumentValidator master class & CLI runner
└── tests/
    ├── __init__.py
    └── test_doc_validation.py # Comprehensive unit test suite (16 tests)
```

---

## Output Contract

```json
{
  "valid": true,
  "score": 100.0,
  "status": "PASSED",
  "document_type": "passport",
  "decision": {
    "verdict": "CLEARANCE",
    "summary": "Document fully compliant with official formatting and security standards. Recommended for automated clearance."
  },
  "checks_summary": {
    "total": 12,
    "passed": 12,
    "failed": 0,
    "warnings": 0
  },
  "checks": [
    {
      "field": "passport_number",
      "status": "CORRECT",
      "severity": "INFO",
      "reason": "Passport number 'Z1234567' follows standard national format"
    }
  ],
  "flags": [],
  "anomalies": [],
  "cross_checks": []
}
```

---

## CLI Usage

```bash
# Run self-diagnostic demo on sample passport
python modules/doc_validation/src/main.py

# Validate a JSON file or Module 1 output
python modules/doc_validation/src/main.py path/to/document.json --type passport
```

---

## Running Unit Tests

```bash
python -m unittest modules/doc_validation/tests/test_doc_validation.py -v
```
