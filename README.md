# AlephNull — AI-Powered Identity Verification

> Offline-first, local identity verification pipeline for **face matching** and **document OCR**, built for the Smart India Hackathon (SIH 2024, PS26188).

---

## What It Does

AlephNull verifies a person's identity against a government-issued ID in a fully offline, privacy-preserving pipeline:

1. **📄 Document OCR (Module 1)** — Extracts structured fields (Name, Passport Number, Date of Birth, Nationality, Expiry, MRZ) from a photographed passport or national ID using Tesseract + Ollama LLM correction.
2. **👤 Face Verification (Module 4)** — Compares a live selfie against the photo on the ID document using DeepFace + FaceNet512 with a calibrated Euclidean-L2 threshold.
3. **🌐 Full Pipeline** — Both modules run in parallel via a Flask REST API and results are rendered in a premium dark-themed single-page web UI.

---

## Screenshots

| Live Biometric Viewfinder | Interactive Crop Tool |
|---|---|
| Neon SVG oval + document frame overlaid on live camera stream | Touch & mouse drag, rotation, aspect ratio presets |

---

## Features

- **In-browser camera viewfinder** with animated biometric SVG overlays (face oval, document corner brackets) on both desktop and mobile.
- **Interactive image cropper** — drag handles, 90° rotation, Passport/ID Card/1:1 aspect presets, rule-of-thirds grid. Only the cropped sub-image is sent to the backend.
- **Adjustable strictness sliders** for both face match threshold and OCR bounding box confidence.
- **Admin diagnostic tabs** — test OCR or Face matching independently without running the full pipeline.
- **HTTPS / mobile support** — run with `--ssl` to enable in-browser live camera on Android & iOS (self-signed cert auto-generated).
- **AI-assisted OCR correction** — Ollama (LLaMA3 / Gemma2) intelligently corrects Tesseract raw output field-by-field.
- **Dominant face extraction** — strips holographic watermarks and micro-prints from passport photos before embedding comparison.
- **Multi-orientation fallback** — tries 0°, 90°, 180°, 270° if face is not detected at default orientation.

---

## Project Structure

```
AlephNull/
├── api/
│   └── src/
│       └── main.py           # Flask REST API (serves UI + /upload /verify_photo /extract_text)
├── modules/
│   ├── face_verification/
│   │   ├── src/main.py       # FaceVerification class — DeepFace + FaceNet512
│   │   └── tests/
│   ├── ocr_extraction/
│   │   ├── src/main.py       # DocumentOCR class — Tesseract + Ollama correction
│   │   └── tests/
│   ├── doc_validation/       # (Planned) Document authenticity validation
│   └── tampering_detection/  # (Planned) Image tampering detection
├── ui/
│   └── index.html            # Single-page frontend (vanilla JS + CSS, no framework)
├── data/
│   ├── uploads/              # Runtime: captured images saved here by Flask
│   │   ├── person/
│   │   └── document/
│   ├── certs/                # Auto-generated self-signed SSL certs (gitignored)
│   └── raw/                  # Training/test data (gitignored)
├── docs/
│   ├── PS26188_Problem_Analysis.md   # SIH problem statement analysis
│   └── architecture.md
├── pyproject.toml
└── README.md
```

---

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | ≥ 5.x, add to PATH |
| [Ollama](https://ollama.com) + `llama3` or `gemma2` model | Optional — used for OCR correction |
| pip / venv | Standard |

### Install

```bash
git clone https://github.com/bdwarker/AlephNull.git
cd AlephNull

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -e .
pip install cryptography deepface tf-keras pillow ollama
```

### Run

```bash
# Standard (localhost only — camera works in browser on your PC)
python api/src/main.py

# HTTPS mode (enables live in-browser camera on Android/iOS over LAN)
python api/src/main.py --ssl
```

Then open `http://localhost:5000` (or `https://<your-ip>:5000` for mobile).

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Serves the web UI (`ui/index.html`) |
| `GET` | `/health` | Health check + module status |
| `POST` | `/upload` | Upload `person` and/or `document` image files |
| `POST` | `/verify_photo` | Run face match on last uploaded images |
| `POST` | `/extract_text` | Run OCR on last uploaded document image |

### Query Parameters

**`POST /verify_photo`**
- `face_strictness` (0–100, default 50) — Maps to DeepFace distance threshold
- `model_name` — `Facenet512` (default), `VGG-Face`, `ArcFace`, `GhostFaceNet`
- `detector_backend` — `opencv` (default), `ssd`, `mtcnn`

**`POST /extract_text`**
- `type` — `passport` (default) or `id_card`
- `ocr_strictness` (0–100) — Tesseract bounding box confidence floor

---

## Mobile Camera Setup

Mobile browsers (Android Chrome, iOS Safari) block `getUserMedia()` on plain HTTP origins.

**Option A — `--ssl` flag (recommended):**
```bash
python api/src/main.py --ssl
```
A self-signed cert is auto-generated at `data/certs/`. Open `https://<your-local-ip>:5000` on your phone and accept the certificate warning once.

**Option B — Chrome flag (Android only):**
1. Open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Enter your machine URL, enable, relaunch.

---

## Module Details

### Face Verification
- **Model:** FaceNet512 (512-dimensional embeddings)
- **Metric:** Euclidean-L2, calibrated threshold `1.0400`
- **Key feature:** Dominant face extraction isolates the largest face, eliminating passport hologram and watermark false matches
- **Multi-orientation:** Automatically retries at 90°, 180°, 270° if no face is detected

### Document OCR
- **Stage 1:** Tesseract with `--psm 6` (uniform block) + bounding box confidence filtering
- **Stage 2:** Ollama LLM (LLaMA3/Gemma2) corrects raw Tesseract output field-by-field using structured prompts
- **Extracts:** Name, Passport Number / ID Number, Date of Birth, Date of Expiry, Nationality, MRZ line

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML + CSS + JS (no framework), Google Fonts Inter |
| Backend | Flask, Flask-CORS |
| Face AI | DeepFace, FaceNet512, RetinaFace |
| OCR | Tesseract OCR, Pillow, OpenCV |
| OCR Correction | Ollama (LLaMA3 / Gemma2) |
| SSL | `cryptography` — self-signed cert generation |

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built for SIH 2024 — Problem Statement PS26188.*