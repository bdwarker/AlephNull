# Technologies Used

**Tags:** #tech-stack #architecture #tools #sih2024 #sih2026
**Last Updated:** 2026-09-17

---

## 1. AI, Machine Learning & Computer Vision

| Technology                           | Role / Purpose                                | Why Selected for SIH                                                                                        |
| :----------------------------------- | :-------------------------------------------- | :---------------------------------------------------------------------------------------------------------- |
| **`llama.cpp` / `llama-cpp-python`** | Local quantized LLM/VLM execution             | Direct native C++ runtime; avoids daemon overhead (ditching Ollama); fast mmap cold-starts on edge laptops. |
| **Qwen2.5-3B / SmolVLM (GGUF)**      | Bounded candidate disambiguation & VLM checks | Lightweight footprint (~2–2.6 GB RAM); grammar-constrained (GBNF) decoding prevents hallucinations.         |
| **PaddleOCR / Tesseract**            | Word & character bounding-box text extraction | Fast, high-accuracy multilingual OCR with spatial coordinates $(x, y, w, h)$.                               |
| **OpenCV (`cv2`)**                   | Image forensics & preprocessing               | Powers Error Level Analysis (ELA), SIFT/ORB stamp matching, Hough circular transforms, and deskewing.       |
| **InsightFace / ArcFace (ONNX)**     | Biometric face verification                   | Robust 512-dimensional facial embeddings with age-progression tolerance and fast CPU/GPU inference.         |
| **Pillow (PIL)**                     | Image manipulation & ELA diffing              | Re-compressing JPEG layers to compute pixel-level compression discrepancy heatmaps.                         |

---

## 2. Back-end & API Services

| Technology | Role / Purpose | Why Selected for SIH |
| :--- | :--- | :--- |
| **Python 3.10+** | Core programming language | Native ecosystem for AI/ML, computer vision, and cryptographic libraries. |
| **FastAPI** | High-performance asynchronous REST API | Async execution, automatic OpenAPI documentation, sub-millisecond route overhead. |
| **Pydantic v2** | Data modeling & schema enforcement | Strict validation for dual-state records (`raw_text` vs `resolved_value`). |
| **ReportLab / WeasyPrint** | Automated PDF generation | Instantly compiles 1-click legal Incident Dossiers (FIR attachments) with embedded ELA heatmaps. |

---

## 3. Database, Cryptography & Audit Ledger (Theme Alignment)

| Technology | Role / Purpose | Why Selected for SIH |
| :--- | :--- | :--- |
| **SQLite (WAL Mode)** | Local offline database & queues | Zero configuration, 100% offline edge operation; hosts `pending_sync_queue` and `ocr_feedback_cache`. |
| **Merkle Tree / SHA-256 DAG** | Tamper-proof append-only ledger | Cryptographic hash chaining prevents retroactive alteration of screening logs or officer override decisions. |
| **Salted Hashes / Bloom Filter**| Decentralized watchlist matching | Allows edge devices to match blacklisted documents without storing sensitive intelligence in cleartext. |

---

## 4. Front-end & Checkpoint Cockpit UI

| Technology | Role / Purpose | Why Selected for SIH |
| :--- | :--- | :--- |
| **React + Vite** | Border officer dashboard | Fast development, modular UI state, sub-second HMR. |
| **Tailwind CSS** | Styling & Theme | Rapid UI styling; dark-mode high-contrast theme optimized for 24/7 night border operations. |
| **HTML5 Canvas / SVG** | Dynamic forensic overlays | Renders interactive color-coded bounding boxes (Red/Yellow/Green) directly over scanned document images. |

---

## 5. Networking & Edge Synchronization

| Technology | Role / Purpose | Why Selected for SIH |
| :--- | :--- | :--- |
| **Tailscale / WireGuard** | Encrypted peer-to-peer mesh | Facilitates opportunistic Store-and-Forward sync when patrol vehicles or mobile units enter range. |

---

## 6. Edge Hardware & Deployment Profile

| Technology / Target                  | Role / Purpose                     | Why Selected for SIH                                                                                                                          |
| :----------------------------------- | :--------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| **Raspberry Pi 4 / Pi 5 (ARM64)**    | **Target Lower-Bound Edge Device** | Draws only 5–15W; runs on 12V solar-battery packs at off-grid outposts; ultra-low cost (₹8,000–₹12,000 / unit) vs. costly enterprise servers. |
| **Python-Capable Host Architecture** | Core Deployment Model              | The server runs flexibly on any device supporting Python 3.10+ (Raspberry Pi, Mini-PC, rugged checkpoint laptop, or x86 workstation).         |

---

## ➕ Append New Technologies Here
*Add newly introduced libraries, models, hardware, or tools during development:*

- 
