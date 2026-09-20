# AlephNull

AI-powered, offline-first identity and document screening pipeline for SIH Problem Statement **PS26188** (MHA/SSB).

AlephNull combines OCR extraction, deterministic document validation, biometric face verification, and consolidated risk scoring into a single local workflow.

---

## 1) What this project does

Given a traveler selfie and a document image (passport/ID/visa/etc.), the system:

1. **Extracts document text and structure** from OCR (`modules/ocr_extraction`)
2. **Validates extracted fields** with deterministic rules and checksums (`modules/doc_validation`)
3. **Matches face from selfie to document portrait** (`modules/face_verification`)
4. **Consolidates module outputs into a single risk score** (`risk_engine`)
5. **Exposes all functions through a local Flask API + web UI** (`api`, `ui`)

---

## 2) Repository architecture

```text
AlephNull/
├── api/
│   └── src/main.py                 # Flask app, orchestration endpoints, SSL cert generation
├── modules/
│   ├── ocr_extraction/
│   │   └── src/main.py             # EasyOCR pipeline, line clustering, MRZ detection, optional LLM fallback
│   ├── doc_validation/
│   │   ├── src/main.py             # DocumentValidator orchestrator
│   │   ├── src/mrz_parser.py       # ICAO 9303 parsing + check-digit verification
│   │   ├── src/aadhaar_qr.py       # Aadhaar QR decoding/parsing helpers
│   │   └── rules/*.py              # Passport/Aadhaar/ID/DL/Visa/Permit rule engines
│   ├── face_verification/
│   │   └── src/main.py             # InsightFace-based 1:1 biometric verification
│   └── tampering_detection/
│       └── .../.gitkeep            # Planned module scaffold
├── risk_engine/
│   └── src/scorer.py               # Weighted consolidation + suspicious-point synthesis
├── ui/
│   ├── index.html
│   ├── script.js                   # Camera capture, cropper, pipeline/admin flows
│   └── style.css
├── data/
│   ├── uploads/                    # Runtime uploads (gitignored contents)
│   ├── raw/                        # Raw datasets/artifacts (gitignored contents)
│   └── certs/                      # Auto-generated SSL certs
└── docs/                           # Architecture notes and roadmap
```

---

## 3) Runtime architecture (current implementation)

```text
User (UI camera/upload)
    -> /upload
    -> /verify_photo (Module 4)
    -> /extract_text  (Module 1)
         -> auto /validate_document (Module 2)
    -> /consolidate_score (Risk Engine)
    -> JSON response + UI rendering
```

### Key API endpoints implemented

- `GET /api` – module availability + endpoint listing
- `POST /upload` – image/PDF ingestion and storage under `data/uploads`
- `POST /verify_photo` – face matching pipeline
- `POST /extract_text` – OCR extraction pipeline
- `POST /validate_document` – deterministic rule validation
- `POST /decode_aadhaar_qr` – Aadhaar QR decode utility
- `POST /consolidate_score` – final weighted score + suspicious points

---

## 4) Module-by-module deep dive

### Module 1 — OCR extraction (`modules/ocr_extraction`)

Current behavior:

- Uses **EasyOCR** for text box extraction with confidence.
- Clusters words into lines via vertical overlap (layout-aware grouping).
- Extracts fields using deterministic heuristics (name, document number, DOB, expiry, nationality, gender).
- Detects likely MRZ lines and parses them (via Module 2 MRZ parser).
- Supports optional local `.gguf` model loading from `modules/models` through `llama-cpp-python` for bounded fallback.
- Returns rich OCR artifacts (`raw_ocr`, `regions_identified`, `ocr_passes`, timing).

### Module 2 — Document validation (`modules/doc_validation`)

Current behavior:

- Normalizes heterogeneous OCR keys into canonical field names.
- Dispatches by document type (`passport`, `aadhaar`, `national_id`, `driving_license`, `visa`, `permit`).
- Applies deterministic checks:
  - ICAO MRZ check digits
  - Verhoeff checksum for Aadhaar-like IDs
  - format/date/expiry consistency rules
  - cross-check logic (including VIZ vs MRZ and QR-derived fields when available)
- Produces transparent outputs: score, flags, anomalies, suspicious points, checks summary.

### Module 3 — Tampering detection (`modules/tampering_detection`)

Current behavior:

- **Not implemented yet in code** (scaffold folders and model placeholder only).

Planned behavior from `docs/Document-Forensics-and-Tampering-Detection.md`:

- ELA, copy-move detection, text/font inconsistency analysis, stamp authenticity checks, metadata/EXIF forensic checks.

### Module 4 — Face verification (`modules/face_verification`)

Current behavior:

- Uses **InsightFace FaceAnalysis** (ArcFace-style embeddings via model pack, default `buffalo_l`).
- Performs robust face detection with multi-rotation, multi-scale, and edge-padding fallback.
- Compares embeddings with cosine similarity.
- Applies strictness-adjusted thresholding and outputs calibrated trust score + diagnostic metadata.

### Risk Engine (`risk_engine`)

Current behavior:

- Aggregates face and validation signals into weighted consolidated score.
- Adds guardrails (caps score when critical failures exist).
- Generates suspicious points and category-wise explanation.
- Optionally appends audit entries to `data/audit.log`.

---

## 5) What is implemented vs what remains

### Implemented in repository

- End-to-end local API + UI workflow (`upload -> OCR/Face -> validate -> consolidate`).
- OCR extraction with field heuristics and MRZ parsing integration.
- Deterministic validation engines for passport, Aadhaar/national ID, driving license, visa, permit.
- Aadhaar QR decode path (where dependencies and payload conditions are met).
- InsightFace-based biometric comparison with detailed diagnostics.
- Consolidated risk scoring and audit-log writing.
- HTTPS startup mode with auto-generated self-signed certificates.

### Still pending / partially implemented (from docs roadmap)

- Full **Module 3 tampering detection engine** (currently design + scaffold only).
- Stronger OCR pre-processing pipeline described in docs (deskew/advanced preprocessing stack).
- Production-grade active-learning feedback cache (`ocr_feedback_cache`) as specified in docs.
- Offline store-and-forward queue (`pending_sync_queue`) and HQ sync workflow from architecture docs.
- Blockchain/Merkle audit ledger and decentralized watchlist sync design.
- Explainable dossier PDF generation and complete incident reporting workflow.
- Broader evaluation harness, labeled datasets, and module-level benchmark reporting.

---

## 6) Docs map (reference design source)

Use these documents in `docs/` as architecture references:

- `Problem Statement.md` – official PS26188 framing
- `PS26188_Problem_Analysis.md` – scoped objectives and stage breakdown
- `Modules_1_and_2_Architecture_Updated.md` – detailed OCR + deterministic validation architecture
- `Document-Forensics-and-Tampering-Detection.md` – Module 3 forensic design
- `Offline-First-Store-and-Forward.md` – disconnected edge deployment strategy
- `Blockchain-Audit-Trail-and-Watchlist-Sync.md` – tamper-proof ledger/watchlist concept
- `Explainable-AI-and-Incident-Dossier.md` – explainability and reporting UX direction

> Note: Some docs describe target architecture and future phases; current codebase implements only part of that full blueprint.

---

## 7) Local setup

### Prerequisites

- Python 3.11+
- Tesseract (if you use Tesseract-dependent experiments/tools)
- Optional but recommended for full flows:
  - `easyocr`, `insightface`, `onnxruntime`, `pypdfium2`, `Pillow`, `pyzbar`, `pyaadhaar`, `llama-cpp-python`

### Install

```bash
cd /home/runner/work/AlephNull/AlephNull
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
pip install -e .
```

### Run API + UI

```bash
python /home/runner/work/AlephNull/AlephNull/api/src/main.py
```

Open: `http://localhost:5000`

### Run HTTPS mode (mobile camera support)

```bash
python /home/runner/work/AlephNull/AlephNull/api/src/main.py --ssl
```

Open: `https://<your-local-ip>:5000`

---

## 8) Data and artifact handling

- Runtime uploads are stored under `data/uploads/`.
- Raw documents and tampering-model artifacts are intentionally ignored in git, with `.gitkeep` placeholders preserved.
- SSL certs are generated locally in `data/certs/` when `--ssl` is used.

---

## 9) License

MIT License. See `/home/runner/work/AlephNull/AlephNull/LICENSE`.
