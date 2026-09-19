# SIH 2026 PPT Creation Guide for Unaiz

**Document Purpose:** Complete content guide and slide-by-slide blueprint for **Unaiz** to design and build the official SIH 2026 presentation.  
**Template Source:** `SIH2026-IDEA-Presentation-Format(1).pptx`  
**Problem Statement ID:** 26188 | **Category:** Software | **Theme:** Blockchain & Cybersecurity  
**Organization:** Ministry of Home Affairs (MHA) / Sashastra Seema Bal (SSB), Police II Division  
**Project Codename:** **Project SeemaDrishti (सीमा दृष्टि)** — AI-Based Document Screening System  

---

## 📌 Important Submission Constraints for Unaiz

1. **Strict 6-Slide Maximum:** 
   * The final presentation **must not exceed 6 slides** (Slide 1 Title + Slides 2 to 6 Content). 
   * Delete Slide 7 (the instruction slide from the template) before final export.
2. **Export Format:** 
   * Must be saved and exported as a **PDF** for portal submission (the SIH portal rejects `.pptx` and `.docx`).
3. **Template Headers:** 
   * Keep the official headers on Slides 2–6 intact (e.g. `Detailed explanation of the proposed solution`, `Technologies to be used`, etc.) as required by the jury rubric.
4. **Visual Layout Rule:** 
   * **Avoid large paragraphs.** Use bold lead-ins, bullet points, *flow diagrams*, and metric callouts so judges can scan the slide in 10 seconds.

---

## Slide 1: TITLE PAGE

### What goes on the slide:
* **Hackathon Banner:** SMART INDIA HACKATHON 2026
* **Project Codename:** **Project SeemaDrishti (सीमा दृष्टि)**
* **Problem Statement ID:** SIH26188
* **Problem Statement Title:** AI-Based Fake Identity & Document Screening System
* **Ministry / Department:** Ministry of Home Affairs (MHA) / Sashastra Seema Bal (SSB)
* **Theme:** Blockchain & Cybersecurity
* **Category:** Software
* **Team ID:** `[Insert Portal Team ID]`
* **Team Name:** Aleph Null

### Visual & Layout Tips for Unaiz:
* Place the title cleanly in high contrast.
* Use a subtle border security / cyber shield graphic or national security motif if space permits.
* Keep team details aligned in a structured box at the bottom right or center.

---

## Slide 2: PROPOSED SOLUTION

### Core Concept to Convey:
An edge-first platform that lets border officers screen passports, visas, and regional border IDs in **under 10 seconds** completely offline, catching digital tampering and photo edits that the human eye misses.

### Content Breakdown (Put these exact points):

#### 1. Detailed Explanation of the Proposed Solution
* **4-Engine Unified Architecture:**
  1. *Spatial OCR:* Extracts all identity fields across Passports, Visas, and regional documents (Nepali *Nagrikta*, Voter ID, Permits).
  2. *Deterministic Validation:* Instant mathematical check-digit calculations and offline cryptographic QR signature checks.
  3. *AI Tampering Forensics:* Detects digital photo splicing, altered dates/names, and cloned immigration seals.
  4. *Biometric Face Verification:* Matches document portrait photos against live webcam feed with anti-spoofing liveness.
* **Consolidated Risk Score:** Outputs an explainable Green (Pass), Yellow (Review), or Red (Detain) alert with visual bounding-box highlights so the final decision is solely the officer's.

#### 2. How It Addresses the Problem
* **Cuts Checkpoint Queues:** Reduces verification time from several minutes to **under 3 seconds**.
* **Uncovers Invisible Forgeries:** Detects microscopic pixel compression anomalies (ELA) and character baseline shifts invisible to naked-eye inspection.
* **100% Offline Edge Operation:** Functions autonomously at remote, roadless SSB border outposts with zero internet or cloud dependence.

#### 3. Innovation & Uniqueness of the Solution
* **2ms Arithmetic Check-Digit Filtering:** ICAO 9303 Modulo-10 (7-3-1) algorithms filter amateur forgeries instantly before running heavy neural models.
* **Bounded AI Candidate Disambiguation:** Local quantized models resolve ambiguous OCR text strictly within candidate options under grammar constraints (no hallucination).
* **Active Feedback Memory:** Verified officer corrections are cached in SQLite for $\mathcal{O}(1)$ zero-latency repeat resolution.
* **1-Click Legal Incident Dossier:** Automatically generates court-admissible forensic PDF reports (FIR attachments) for detentions.

### Layout Tips for Unaiz:
* Divide the slide into 3 clean visual cards or vertical columns corresponding to the 3 required pointers.
* Use small icon badges for the 4 engines (OCR, Math, Forensics, Face).

---

## Slide 3: TECHNICAL APPROACH

### Core Concept to Convey:
Our software pipeline runs a fast-to-slow hierarchy (Math $\to$ Fast OCR $\to$ Forensics/Face $\to$ Ledger). While the backend runs flexibly on any device with Python, **our target edge lower bound is a Raspberry Pi 4 / Pi 5 (4GB/8GB)**, proving ultra-low-power, low-cost edge viability without relying on expensive cloud servers.

### Content Breakdown (Put these exact points):

#### 1. Technologies to be Used
* **AI / ML & Computer Vision:**
  * `llama.cpp` + GGUF quantized models (Qwen2.5-3B / SmolVLM) for local bounded text disambiguation (zero background daemon overhead; optimized for ARM NEON & x86).
  * OpenCV (`cv2`) & Pillow for Error Level Analysis (ELA), SIFT/ORB stamp template matching, and Hough deskewing.
  * PaddleOCR / Tesseract for spatial coordinate bounding-box extraction.
  * InsightFace / ArcFace (ONNX Runtime) for 512-dimensional facial embedding cosine similarity.
* **Backend & Core Engine:**
  * Python 3.10+, FastAPI (asynchronous pipeline orchestration), Pydantic v2, ReportLab (automated PDF incident dossier generator).
* **Database & Blockchain Ledger (Theme Alignment):**
  * SQLite (WAL mode) for local offline queues (`pending_sync_queue`, `ocr_feedback_cache`).
  * Cryptographic Merkle DAG with SHA-256 block hashing for tamper-proof officer override logging.
* **Frontend & Edge Hardware Profile:**
  * React, Vite, Tailwind CSS (dark-mode cockpit UI), HTML5 Canvas/SVG dynamic color overlays.
  * **Target Edge Lower Bound:** **Raspberry Pi 4 / Pi 5 (ARM64, 4GB/8GB)** — draws only 5–15W, operable on 12V solar packs.
  * **Scalable Deployment:** Runs seamlessly on any Python-capable host (Mini-PC, rugged checkpoint laptop, or x86 workstation).

#### 2. Methodology & Implementation Process (Pipeline Flowchart)
* **Stage 0 (0–50ms):** Instant ICAO 9303 Modulo-10 (7-3-1) check digit arithmetic + offline cryptographic Aadhaar/EPIC QR verification.
* **Stage 1 (100–300ms):** Dynamic 1D-IoU & HPP text line clustering + Bounded Candidate Disambiguation via local GBNF-constrained LLMs.
* **Stage 2 (300–700ms):** Error Level Analysis (ELA) + SIFT stamp keypoint homography + ArcFace facial embedding cosine similarity & texture liveness.
* **Stage 3 (<50ms):** Consolidated Risk Score generation + Merkle audit block chaining + interactive visual overlay rendering in cockpit UI.

### Layout Tips for Unaiz:
* On the right side or bottom half, create a **horizontal 4-stage process flowchart** (`Stage 0: Math Check` $\to$ `Stage 1: Spatial OCR` $\to$ `Stage 2: Forensics & Face` $\to$ `Stage 3: Risk & Ledger`).
* Highlight the **Raspberry Pi icon / badge** to emphasize that our system runs on ultra-low-cost, low-power edge hardware!

---

## Slide 4: FEASIBILITY AND VIABILITY

### Core Concept to Convey:
The project is practically buildable, runs on modest hardware (down to a Raspberry Pi), fits real SSB border treaties, and solves tough real-world constraints (no internet, rogue officer bribes, and AI hallucination).

### Content Breakdown (Put these exact points):

#### 1. Analysis of Feasibility
* **Technical Feasibility:** Quantized edge models (InsightFace ONNX, PaddleOCR, Qwen2.5-3B 4-bit) execute efficiently on edge CPU/RAM. The server runs on any device running Python, with **Raspberry Pi 4/5 as the tested lower bound**.
* **Operational Feasibility:** Tailored for SSB's Indo-Nepal/Bhutan operational reality: natively supports non-passport regional IDs (Nepali *Nagrikta*, Voter ID, Permits) alongside international passports.
* **Cost & Power Viability:** A Raspberry Pi edge unit costs under **₹8,000–₹12,000** ($100–$150) and consumes **5–15 Watts**, allowing 24/7 solar-battery operation at outposts lacking stable electricity grid. Zero recurring cloud API fees.

#### 2. Potential Challenges & Mitigation Strategies (Table or Pair Format)
* **Challenge 1: Remote Outpost Connectivity Deficit** (Over 300 SSB outposts have zero mobile networks or broadband).
  * *Mitigation:* **Store-and-Forward Mesh Architecture** — 100% offline edge screening with opportunistic delta sync via patrol vehicle VSAT or Tailscale mesh.
* **Challenge 2: Hallucination Risk in Legal Documents** (LLMs modifying citizen names on official travel records).
  * *Mitigation:* **Dual-State Storage & GBNF Constraints** — Raw OCR evidence is permanently retained; models are physically restricted to choosing between bounded candidates.
* **Challenge 3: Officer Collusion & Bribery Risk** (Compromised personnel manually clearing high-risk travelers).
  * *Mitigation:* **Cryptographic Accountability** — Manual overrides mandate officer badge authentication permanently sealed on the immutable Merkle ledger.

### Layout Tips for Unaiz:
* Present the Challenges vs. Mitigations as a **2-column comparison table or paired cards** (Problem on left in light red, Solution on right in light green).

---

## Slide 5: IMPACT AND BENEFITS

### Core Concept to Convey:
Massive operational speedup for jawans, elimination of border queues, and tighter national security without leaking data to commercial clouds.

### Content Breakdown (Put these exact points):

#### 1. Potential Impact on Target Audience
* **For SSB Border Security Personnel:**
  * Screening time reduced from **3–5 minutes down to <3 seconds** per document.
  * Eliminates human eye fatigue and subjective judgment via glanceable Red/Yellow/Green overlays.
  * 1-Click generation of court-admissible Incident Dossiers saves hours of manual paperwork during detentions.
* **For Legitimate Travelers:**
  * Drastically reduces checkpoint delays and congestion at major border crossings (Raxaul, Jogbani, Panitanki).
* **For National Intelligence Agencies (MHA / IB):**
  * Establishes structured, standardized digital audit trails across previously disconnected frontier posts.

#### 2. Broad Social, Economic & Security Benefits
* **National Security:** Closes porous border loopholes exploited by human traffickers, contraband smugglers, and terror operatives using forged credentials.
* **Economic Trade:** Accelerates bilateral passenger transit and cross-border commercial freight between India, Nepal, and Bhutan.
* **Data Sovereignty & Privacy:** Salted cryptographic hash matching prevents sensitive watchlist leaks if edge hardware is compromised. Zero citizen biometrics sent to third-party clouds.

### Layout Tips for Unaiz:
* Use big stat callouts (e.g. `< 3 SECONDS` in 40pt bold, `100% OFFLINE` in 40pt bold, `300+ OUTPOSTS COVERED`).
* Highlight the dual impact: Tactical (for the constable) and Strategic (for national security).

---

## Slide 6: RESEARCH AND REFERENCES

### Core Concept to Convey:
Grounding our design in international civil aviation standards, published IEEE forensic literature, and EU border research.

### Content Breakdown (Put these exact references):

* **ICAO Doc 9303 Standards:** International Civil Aviation Organization specifications for Machine Readable Travel Documents (MRTD); Modulo-10 7-3-1 check digit algorithms for TD1, TD2, and TD3 passports and visas.
* **Veripass Research (IEEE 2024):** *"Passport Forgery Detection Using CNN, OCR, and SIFT"* — Validates bilateral preprocessing, text validation, and SIFT keypoint matching.
* **D4FLY Project (European Union Horizon):** AI and blockchain-backed travel document authentication at border crossing points (CORDIS EU).
* **Error Level Analysis (ELA) for Digital Forensics:** Krawetz, N. (2007) — Compression error variance detection in digital JPEG forensics.
* **ArcFace Biometric Embeddings:** Deng et al. (CVPR 2019) — Additive Angular Margin Loss for deep face recognition.
* **MHA / SSB Infrastructure Reports:** Official parliamentary data documenting road connectivity and digital infrastructure at 308 border outposts.
* **MIDV-500 & MIDV-2019 Datasets:** Public benchmark dataset series for mobile identity document analysis and forgery evaluation.

### Layout Tips for Unaiz:
* Present as a clean 2-column list with small reference icons.
* Add source links or publication badges where space permits.

---

## 🎨 Visual Styling Guide for Unaiz

* **Recommended Theme:** Defense / Modern Security (High Tech, Trustworthy, Clean).
* **Color Codes:**
  * Background: Clean Crisp Off-White (`#F8FAFC`) or Light Gray.
  * Primary / Headers: Deep Navy / Slate (`#0F172A` or `#1E293B`).
  * Accents / Highlights: Amber / Khaki (`#D97706`) and Emerald Green (`#059669`).
  * Alert / Tampering callouts: Crimson Red (`#DC2626`).
* **Fonts:**
  * Slide Titles: Arial Black or Montserrat Bold (24–28pt).
  * Section Headers: Calibri Bold or Trebuchet MS (13–15pt).
  * Bullets: Calibri or Inter (10.5–11.5pt).
* **Pre-made PowerPoint:** You can open [SIH2026_Idea_Presentation_SeemaDrishti.pptx](file:///C:/Users/Mohammed%20Shaan/Documents/Notes/SIH/SIH2026_Idea_Presentation_SeemaDrishti.pptx) in this folder as your starting base—it already has the template structure and all text populated!
