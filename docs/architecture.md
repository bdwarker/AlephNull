# AlephNull — System Architecture

## Overview

AlephNull is a modular, offline-first identity verification pipeline. It exposes a Flask REST API backed by independent AI modules, with a premium single-page web UI.

```
┌────────────────────────────────────────────────────────────┐
│                    Browser (ui/index.html)                  │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────────┐ │
│  │ Face Slot  │  │  Doc Slot  │  │   Results / Admin UI   │ │
│  │ (Biometric │  │ (Document  │  │  OCR fields + Face     │ │
│  │  Viewfinder│  │  Viewfinder│  │  match verdict + trust │ │
│  │  + Cropper)│  │  + Cropper)│  │  score                 │ │
│  └─────┬──────┘  └─────┬──────┘  └───────────────────────┘ │
└────────┼───────────────┼─────────────────────────────────────┘
         │ POST /upload  │
         ▼               ▼
┌──────────────────────────────────┐
│        Flask REST API            │
│        api/src/main.py           │
│                                  │
│  POST /upload                    │
│    └─ saves to data/uploads/     │
│       person/ and document/      │
│                                  │
│  POST /verify_photo  ────────────┼──► Module 4: FaceVerification
│    └─ face_strictness (0-100)    │    modules/face_verification/src/main.py
│                                  │    DeepFace + FaceNet512 + RetinaFace
│  POST /extract_text  ────────────┼──► Module 1: DocumentOCR
│    └─ type, ocr_strictness       │    modules/ocr_extraction/src/main.py
│                                  │    Tesseract → Ollama LLM correction
└──────────────────────────────────┘
```

---

## Data Flow: Image Capture → AI

```
User camera / upload
        │
        ▼
  Browser canvas (viewfinder overlay)
        │  User frames face/document inside guide
        ▼
  User taps "Snap" → full-resolution JPEG captured
        │
        ▼
  Interactive Cropper Modal opens
        │  User adjusts/confirms crop region
        ▼
  cropCanvas.toBlob() → croppedBlob (JPEG, 0.95 quality)
        │  Only cropped pixels leave the browser
        ▼
  FormData.append('person'/'document', croppedBlob)
  POST /upload
        │
        ▼
  Flask saves to data/uploads/{person,document}/
        │
        ├─────────────────────────┐
        ▼                         ▼
  POST /verify_photo        POST /extract_text
  FaceVerification          DocumentOCR
  (DeepFace + FaceNet512)   (Tesseract + Ollama)
        │                         │
        ▼                         ▼
  { is_match, distance,     { extracted_fields,
    trust_score, ... }         raw_text, ... }
        │                         │
        └────────┬─────────────────┘
                 ▼
          UI renders results
```

---

## Module Descriptions

### Module 1 — Document OCR (`modules/ocr_extraction/`)

| Stage | Tool | Purpose |
|---|---|---|
| Pre-processing | OpenCV + Pillow | Grayscale, CLAHE, adaptive threshold |
| Text detection | Tesseract `--psm 6` | Raw character extraction with bounding box confidence filtering |
| Field extraction | Regex + heuristics | Extracts Name, DOB, Expiry, Passport No., Nationality, MRZ |
| Correction | Ollama (LLaMA3 / Gemma2) | Structured prompt corrects Tesseract OCR errors field-by-field |

**Strictness slider** (0–100): controls Tesseract bounding box `conf` floor.  
- Low (0) → bigger boxes, more text captured  
- High (100) → only very high-confidence characters

### Module 4 — Face Verification (`modules/face_verification/`)

| Component | Detail |
|---|---|
| Embedding model | FaceNet512 (512-dimensional vectors) |
| Distance metric | Euclidean-L2, calibrated threshold 1.0400 |
| Detector | RetinaFace (primary), OpenCV Haar (fallback) |
| Dominant face | Largest detected face by area — eliminates passport micro-print false matches |
| Multi-orientation | Retries at 0°, 90°, 180°, 270° |
| Trust score | `max(0, (1 - d/threshold) * 100)` mapped 0–100 |

**Strictness slider** (0–100): 0 = most lenient (threshold 1.30), 100 = strictest (threshold 0.60).

---

## Planned Modules

| Module | Status | Description |
|---|---|---|
| Module 2 — Doc Validation | Planned | Check document format, font, layout against known templates |
| Module 3 — Tampering Detection | Planned | CNN-based image manipulation / splicing detection |
| Risk Engine | Scaffold | Aggregates module scores into a final fraud risk score |

---

## SSL / HTTPS Architecture

For mobile in-browser camera (Android Chrome, iOS Safari), HTTPS is required.

`api/src/main.py --ssl` auto-generates a self-signed certificate using Python's `cryptography` library:
- **Key:** RSA 2048, stored at `data/certs/key.pem`
- **Cert:** SHA-256, SAN includes `localhost`, `127.0.0.1`, and the machine's LAN IP
- **Validity:** 365 days
- Certs are gitignored and regenerated on first run.
