# Problem Statement Analysis & Objectives
## AI-Based Fake Identity & Document Screening System

**Problem Statement ID:** 26188
**Organization:** Ministry of Home Affairs
**Department:** Sashastra Seema Bal (SSB), Police II Division
**Category:** Software
**Theme:** Blockchain & Cybersecurity

---

## 1. Problem Understanding

**Core Problem:** Border checkpoints under SSB currently rely on **manual, human-driven verification** of identity and travel documents (passports, visas, national IDs, driving licenses, permits). This process is slow, inconsistent, and structurally unable to catch sophisticated forgery techniques — leading to both security risk (fraudulent entries) and operational bottlenecks (passenger delays).

**Stakeholders:**
- **Primary organization:** SSB (Sashastra Seema Bal), Ministry of Home Affairs — the deploying security agency.
- **End users:** Border security personnel who will use the tool's output (risk scores, flags) to make faster decisions.
- **Affected parties:** Travelers/passengers (subject to screening — legitimate travelers face delay, fraudulent ones face detection), and downstream investigative/intelligence units who rely on the digital trail generated.

**Why It Matters:**
- **Security gap:** Manual inspection and "basic database lookups" cannot reliably detect **digital tampering, photo replacement, stamp forgery, or metadata manipulation** — these are precisely the failure modes sophisticated forgers exploit.
- **Operational gap:** High passenger volume against manual, minutes-long verification per document creates **queuing delays** at checkpoints, which has both economic and security implications (rushed checks = more errors).
- **Consequence of inaction:** Continued vulnerability to identity impersonation, multiple-identity fraud, and passage of blacklisted/expired travel documents — a direct national security exposure.

---

## 2. Background & Context

**Current Process:**
- Documents are inspected **visually by human personnel**, cross-referenced against databases manually or semi-manually.
- Verification depends on the inspector's experience/training to visually catch forgery cues (altered fonts, mismatched photos, irregular stamps).

**What's Broken:**
- **Human error & fatigue** at high volume — inspectors can't maintain forgery-detection accuracy across thousands of documents/day.
- **No standardization** — decision quality varies checkpoint to checkpoint, officer to officer.
- **No systematic tampering detection** — physical/digital alteration (photo swaps, modified DOB, tampered visa stamps) is hard to catch with the naked eye, especially with modern editing tools.
- **No unified digital trail** — manual checks don't naturally generate structured data for later investigation or intelligence correlation.
- **Reactive, not data-driven** — risk assessment isn't scored or quantified; it's a binary pass/fail judgment call.

---

## 3. Scope

### In Scope
- OCR-based extraction of structured fields from **passports, visas, national IDs, driving licenses, and permits**.
- Rule-based **document validation** (format/standard compliance of extracted fields).
- **Tampering detection** covering: photo replacement, text manipulation, stamp forgery, and image metadata analysis.
- **Face verification** matching the document photo against the presented individual.
- Generation of a consolidated **risk score** to assist (not replace) human decision-making.
- Creation of a **digital trail/log** of screening decisions for investigation and intelligence use.

### Out of Scope
- Physical document security features requiring specialized hardware (e.g., UV/IR forensic scanners) unless explicitly integrated as an input source.
- Real-time integration with live national/international watchlist databases (unless a dataset/API is provided — none specified in the problem statement).
- Fully autonomous pass/reject decisions — the system is a **decision-support tool**, not a replacement for human authority at the checkpoint.
- Hardware deployment logistics (kiosk design, camera procurement) — solution scope is the **software/AI platform**.

---

## 4. Objectives

1. **Automate field extraction:** Achieve OCR-based extraction of all specified fields (name, passport/visa number, nationality, DOB, expiry, gender, entry validation, stay duration) from passport, visa, national ID, driving license, and permit images with high per-field accuracy.
2. **Validate against document standards:** Build a rules engine that checks extracted data against official document formatting/standards and flags non-conforming entries automatically.
3. **Detect tampering across four vectors:** Implement detection modules for photo replacement, text manipulation, stamp forgery, and image metadata inconsistencies, each producing an interpretable flag/confidence score.
4. **Verify identity via face matching:** Match the document's photo against a live-captured image of the presenter and output a similarity/match confidence score.
5. **Reduce verification time:** Cut end-to-end document screening time from the current multi-minute manual process down to a **few seconds per document**, as targeted by the problem statement's expected impact.
6. **Generate a consolidated, auditable risk score:** Combine outputs from OCR validation, tampering detection, and face verification into a single interpretable risk score, with a logged digital trail for every screening event.

---

## 5. Key Challenges & Mitigation Strategies

**Technical:**
- *Challenge:* Building robust OCR that generalizes across **varied document layouts, fonts, languages, and image qualities**.
  **Mitigation:** Use [[Text-Line-Segmentation-and-Baseline-Clustering|Dynamic 1D-IoU Baseline Clustering]] to accurately segment text lines even on warped or noisy documents before feeding them to OCR engines.
- *Challenge:* Designing tampering detection that catches **both digital (metadata, pixel-level edits) and physical (print/stamp) forgery**.
  **Mitigation:** Use a **layered detection pipeline**: [[Document-Forensics-and-Tampering-Detection|Error-Level Analysis (ELA)]] for pixel-level tampering, EXIF analysis for metadata, and template/feature matching for stamp forgery.
- *Challenge:* Face verification accuracy under **real-world capture conditions** (lighting, angle, document photo age/quality).
  **Mitigation:** Use robust face-embedding models and set a **confidence threshold with human-review fallback** rather than a hard auto-reject.
- *Challenge:* Combining module outputs into a **single coherent, explainable risk score**.
  **Mitigation:** Generate a transparent [[Explainable-AI-and-Incident-Dossier|Explainable AI Incident Dossier]] using a structured weighted model, rather than a black-box ensemble.
- *Challenge:* Preventing AI hallucinations when parsing OCR outputs or names.
  **Mitigation:** Implement [[AI-Candidate-Disambiguation-and-Active-Learning|Bounded AI Candidate Disambiguation]] using GBNF grammar constraints (via `llama.cpp`) and an Active Feedback Cache (SQLite) to strictly limit the model to legal schemas and ensure O(1) repeats for known data.

**Data:**
- *Challenge:* **No dataset link provided** in the problem statement — sourcing/generating realistic, diverse training data.
  **Mitigation:** Use publicly available synthetic/benchmark document datasets (e.g., MIDV series for ID documents) combined with **programmatically generated forged samples**.
- *Challenge:* **Class imbalance** — forged documents are rare relative to genuine ones.
  **Mitigation:** Apply oversampling/augmentation of the forged class during training, and evaluate using precision/recall/F1 rather than raw accuracy.
- *Challenge:* Privacy/sensitivity of identity document data vs. **domain gap** when using synthetic data.
  **Mitigation:** Use synthetic data as the primary training base. Explicitly report accuracy as measured **on synthetic/benchmark data only** and flag real-world validation as a required next step before deployment.

**Deployment:**
- *Challenge:* Needs to function at **high passenger throughput** without becoming a new bottleneck.
  **Mitigation:** Optimize inference using our 4-stage hierarchy (Math $\to$ Fast OCR $\to$ Forensics/Face $\to$ Ledger), preventing expensive checks when cheaper deterministic checks (like [[Deterministic-Validation-ICAO-MRZ-and-Regional-IDs|MRZ checksums]]) fail.
- *Challenge:* Must integrate into **existing checkpoint workflows** as an assistive tool for personnel.
  **Mitigation:** Design a simple UI that highlights flagged fields, generates the Incident Dossier, and visualizes the Merkle DAG audit trail.
- *Challenge:* Deployment environment likely has **variable hardware/connectivity** at border posts.
  **Mitigation:** Ensure **100% Offline operation** using an [[Offline-First-Store-and-Forward|Offline-First Store-and-Forward Mesh]] (via Tailscale). Time-critical inference runs locally; data syncs opportunistically via a background queue.
- *Challenge:* **Edge hardware constraints** — the target lower bound hardware is a Raspberry Pi 4/5 (ARM64, 4GB/8GB RAM, 5-15W).
  **Mitigation:** Use [[Edge-Inference-LlamaCPP|Edge-Inference via Llama.cpp]] for any LLM/VLM components, and lightweight/optimized CV models (Tesseract, small custom CNNs) to ensure the full stack runs smoothly on the Pi.

---

## 6. Success Metrics

- **Speed:** Average document processing time reduced to a few seconds (from the current multi-minute manual baseline).
- **OCR accuracy:** Field-level extraction accuracy across all supported document types.
- **Tampering detection performance:** Precision/recall (or F1) on forged vs. genuine documents, separately assessed per tampering type (photo, text, stamp, metadata).
- **Face verification accuracy:** True match rate and false accept/reject rate for document-to-person verification.
- **Risk score reliability:** Correlation between system-generated risk scores and ground-truth fraud cases.
- **Standardization impact:** Consistency of screening outcomes across different simulated checkpoint scenarios.
- **Auditability:** Completeness and traceability of the digital trail generated per screening event via the blockchain ledger.

---

## 7. Deliverables — Module Breakdown (4-Stage Pipeline)

Directly derived from the problem statement's "Expected Solution" section, organized into our structured edge-inference hierarchy optimized for the Raspberry Pi.

### Stage 0: Deterministic Validation
**Objective:** Perform immediate, math-based checks without heavy ML models to filter out obvious fakes rapidly.
- [[Deterministic-Validation-ICAO-MRZ-and-Regional-IDs|MRZ & QR Code Extraction]] and standard checksum validation.
- Fast heuristic formatting checks.

### Stage 1: Extraction & Bounded AI
**Objective:** Automatically extract all relevant information from identity documents.
- **Inputs:** Passport, visa, national ID, driving license, permit images.
- **Processing:** Extract text using [[Text-Line-Segmentation-and-Baseline-Clustering|Dynamic 1D-IoU Baseline Clustering]] -> OCR engines.
- **Parsing:** Use [[AI-Candidate-Disambiguation-and-Active-Learning|Bounded AI Candidate Disambiguation]] to parse fields intelligently without hallucinations.

### Stage 2: Forensics & Face Verification
**Objective:** Detect digitally or physically altered documents and ensure identity matches.
- **Tampering Detection:** [[Document-Forensics-and-Tampering-Detection|Document Forensics]] covering photo replacement, text manipulation (ELA), stamp forgery, and EXIF metadata analysis.
- **Face Verification:** Match the document photo against a live-captured face.

### Stage 3: Risk Score & Audit Trail
**Objective:** Aggregate findings and log them securely.
- **Reporting:** Generate an [[Explainable-AI-and-Incident-Dossier|Explainable AI Incident Dossier]] & consolidated risk score.
- **Logging:** Commit the digital trail to the [[Blockchain-Audit-Trail-and-Watchlist-Sync|Merkle DAG Blockchain Audit Trail]] for tamper-proof record-keeping, syncing back to central command via the Store-and-Forward mesh.

---

## 8. Research & References

1. **Veripass — Passport Forgery Detection Using CNN, OCR, and SIFT** (IEEE Conference Publication, RAIPUR, India, July 2024). Combines Bilateral CNN for image preprocessing, OCR for text validation, and SIFT for image authentication.
   Source: https://ieeexplore.ieee.org/document/10692007

2. **D4FLY Project (EU-funded)** — developed AI tools for automated analysis of breeder and travel documents at border crossing points, including stamp authenticity checks, security-element analysis, and blockchain-backed passport-checking history.
   Source: https://cordis.europa.eu/article/id/442740-smart-tools-streamline-identity-verification-at-border-crossing-points

3. **Smart Engines — AI-based passport authenticity verification** — commercial system checking 500+ passport templates worldwide, with on-device (no network required) tampering, anti-photoshopping, and hologram-authentication capability.
   Source: https://smartengines.com/news-events/scientists-from-smart-engines-have-trained-ai-to-check-authenticity-of-passports-from-all-countries

4. **Travel Document Validation Using AI and Unsupervised Learning** (US Patent) — AI model trained to detect security-feature deviations across document classes and flag non-conforming documents for human inspection.
   Source: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12026967

5. **Authentication of Travel and Breeder Documents** (SPIE Digital Library) — surveys five categories of automated document authentication technologies to address inconsistency and fatigue in manual border-guard inspection.
   Source: https://ebooks.spiedigitallibrary.org/conference-proceedings-of-spie/11869/118690G/Authentication-of-travel-and-breeder-documents/10.1117/12.2598143.full

6. **SSB Infrastructure Context** — 308 of SSB's 734 border outposts on the Indo-Nepal/Indo-Bhutan borders lack proper road connectivity, informing this report's edge-deployment and hybrid-connectivity design assumptions.
   Source: https://www.tribuneindia.com/news/india/308-ssb-outposts-on-nepal-tibet-borders-await-road-connectivity/amp
