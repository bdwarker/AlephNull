# SIH Team Roles & Task Assignments

**Problem Statement:** PS26188 — AI-Based Fake Identity & Document Screening System  
**Organization:** Sashastra Seema Bal (SSB), Ministry of Home Affairs  
**Theme:** Blockchain & Cybersecurity  

---

## 👥 Team Roster & Module Ownership

| Track | Primary Owners | Key Deliverable |
| :--- | :--- | :--- |
| **Front-end** | Kushal, Praneel | Officer Cockpit UI, Bounding Box Overlays, Dossier Preview |
| **Back-end** | Maheshwar, Shaan, Praneel | Core Pipeline API, MRZ Math Engine, Offline Sync & Ledger |
| **AI / ML & Forensics** | Srivani, Shaan | ELA Heatmaps, CMFD, Face Match, Quantized Edge Inference |
| **Research & Data** | Unaiz, Kushal | Synthetic Forgery Datasets, Indo-Nepal ID Specs & Metrics |
| **PPT Creation & Design**| Unaiz | 6-Slide Master Presentation Deck, Visual Layout, PDF Export |
| **Pitch & Presentation** | Maheshwar, Srivani | Live Pitch Delivery, Demo Choreography, Video Script & Jury Q&A |

---

## 🛠️ Detailed Task Breakdown

### 1. Front-end (Kushal, Praneel)
- [ ] **Officer Cockpit Dashboard:**
  - Build a dark-mode, high-contrast dashboard optimized for 24/7 border checkpoint operations.
  - Implement dual-feed intake: Document scanner upload + live webcam passenger feed.
- [ ] **Visual Explainable Overlays (XAI):**
  - Render dynamic SVG/Canvas bounding boxes directly over the scanned document (🟥 Red for critical forgery, 🟨 Yellow for variance, 🟩 Green for verified).
  - Side-by-side modal displaying the original document vs. Error Level Analysis (ELA) heatmap.
- [ ] **Officer Actions & Incident Dossier:**
  - One-click **"Export Incident Dossier (PDF)"** preview modal for legal detention records.
  - Officer override modal with compulsory badge ID input and justification logging.
- [ ] **Dual-State Field Inspection UI:**
  - Render side-by-side comparison of raw OCR tokens vs. AI-resolved values with 1-click officer verification buttons.

### 2. Back-end (Maheshwar, Shaan, Praneel)
- [ ] **Core API Orchestration:**
  - Build a high-throughput FastAPI/Python backend pipeline linking Modules 1, 2, 3, and 4.
  - Target sub-second total execution time for deterministic passes.
- [ ] **Deterministic Rules Engine (Module 1 & 2):**
  - Implement ICAO Doc 9303 modulo-10 (7-3-1 weight) checksum validation algorithm for MRZ.
  - Implement VIZ (Visual Inspection Zone) vs. MRZ cross-checking rules.
  - Implement dynamic vertical overlap (1D-IoU / HPP) to cluster OCR word tokens into cohesive text lines/fields.
- [ ] **Bounded Candidate Generator & Feedback Cache:**
  - Build rule-based candidate hypothesis generator (OCR confusion matrix) and local SQLite active learning cache (`ocr_feedback_cache`).
- [ ] **Offline-First Store-and-Forward Engine:**
  - Implement local SQLite storage (`pending_sync_queue`) for 100% offline edge operation.
  - Build auto-sync background daemon triggered when local network/patrol mesh connects.
- [ ] **Cryptographic Audit Trail (Blockchain Theme):**
  - Implement append-only Merkle tree / cryptographic hash chaining of all screening events.
  - Build automated PDF dossier generator (ReportLab / WeasyPrint).

### 3. AI / ML & Forensics (Srivani, Shaan)
- [ ] **Document Forensics Suite (Module 3):**
  - Implement Error Level Analysis (ELA) for image compression inconsistencies.
  - Implement Copy-Move Forgery Detection (CMFD) using SIFT/ORB keypoint clustering.
  - Build character baseline alignment and font kerning variance detector.
  - Build stamp authenticity template matching with homography validation.
- [ ] **Edge Inference & Quantization:**
  - Set up direct `llama.cpp` / `llama-cpp-python` runtime using quantized GGUF models.
  - Implement on-demand model load/unload lifecycle management to prevent memory leaks.
  - Implement GBNF grammar-constrained decoding to restrict AI decisions strictly to candidate options.
- [ ] **Face Verification & Liveness (Module 4):**
  - Implement face detection, alignment, and ArcFace/InsightFace embedding cosine similarity.
  - Add lightweight passive liveness/anti-spoofing check (blink/texture verification).

### 4. Research & Compliance (Unaiz, Kushal)
- [ ] **Dataset Sourcing & Synthetic Forgery Generation:**
  - Acquire public benchmark datasets (e.g. MIDV-500 / MIDV-2019).
  - Create a Python script generating controlled synthetic forgeries (swapped photos, edited birth years, cloned stamps) for evaluation.
- [ ] **Regional ID Specifications:**
  - Document field specifications for Indo-Nepal/Bhutan documents: Nepali *Nagrikta*, Indian Voter ID (EPIC), and Border Entry Permits.
  - Research offline Aadhaar QR verification public-key specifications.
- [ ] **Metrics & Benchmark Reporting:**
  - Calculate field-level OCR accuracy, precision, recall, and F1 scores across genuine vs. forged sets.

### 5. PPT Creation & Visual Design (Unaiz)
- [ ] **Official SIH Template Construction:**
  - Build the 6-slide presentation following `SIH2026-IDEA-Presentation-Format(1).pptx` without altering official section pointers.
  - Implement 4-stage pipeline flowchart on Slide 3 (Math $\to$ OCR $\to$ Forensics $\to$ Ledger).
  - Structure Slide 4 Challenges vs. Mitigations into clean comparative cards.
  - Ensure strict compliance with 6-slide limit (delete Slide 7) and export to final PDF.

### 6. Pitch & Presentation Delivery (Maheshwar, Srivani)
- [ ] **Pitch Narrative & Timing:**
  - Rehearse the 5-minute pitch narrative: Real SSB problem (300+ remote outposts, human fatigue) $\to$ Technical innovation (Instant MRZ math + ELA Forensics) $\to$ Blockchain auditability $\to$ Live prototype.
- [ ] **Live Demo Choreography (The "Showstopper"):**
  1. *Test Case 1:* Genuine passport $\to$ Sub-second Green Pass.
  2. *Test Case 2:* Forged passport (spliced photo/edited DOB) $\to$ Red box flags + ELA heatmap display.
  3. *Test Case 3:* **Unplug Ethernet/Wi-Fi live on stage** $\to$ Show system running 100% offline with Store-and-Forward queue.
  4. *Test Case 4:* 1-Click Incident Dossier PDF generation for legal handover.
- [ ] **Jury Q&A Preparation:**
  - Prepare bulletproof responses for edge hardware specs, legal admissibility, false acceptance rates, and offline synchronization.

---

## 🔗 Related Architecture Notes
- [[SIH2026_PPT_Submission_Guide]]
- [[Technologies Used]]
- [[Problem Statement]]
- [[PS26188_Problem_Analysis]]
- [[Offline-First-Store-and-Forward]]
- [[Text-Line-Segmentation-and-Baseline-Clustering]]
- [[Deterministic-Validation-ICAO-MRZ-and-Regional-IDs]]
- [[AI-Candidate-Disambiguation-and-Active-Learning]]
- [[Document-Forensics-and-Tampering-Detection]]
- [[Blockchain-Audit-Trail-and-Watchlist-Sync]]
- [[Explainable-AI-and-Incident-Dossier]]
- [[Edge-Inference-LlamaCPP]]
- [[Vision-Language-Models-VLM-Architecture]]
- [[Current Ideas]]