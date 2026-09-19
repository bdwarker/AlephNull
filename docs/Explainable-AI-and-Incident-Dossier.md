# Explainable AI (XAI) & Border Incident Dossier

**Tags:** #xai #ui-ux #ssb #incident-response #sih2026  #module4
**Focus:** Operational Usability & Legal Traceability for Border Personnel

---

## 1. The Explainability Gap

In military, paramilitary (SSB), and police deployments, AI systems that only produce opaque probabilities (e.g., *"Fraud Probability: 87.4%"*) fail in practice:
* **Constable Dilemma:** A border guard cannot legally detain a citizen based solely on a black-box AI number.
* **Legal Accountability:** Courts require concrete, documented evidentiary trails (e.g. proof of digital tampering, mismatched check digits, or physical forgery cues) to substantiate formal charges or First Information Reports (FIR).

---

## 2. Visual Explainable Overlays (The Officer Cockpit)

The dashboard presents immediate visual proof superimposed directly onto the scanned document:

```text
┌────────────────────────────────────────────────────────┐
│  [PHOTO REGION]        PASSPORT OF INDIA               │
│  ┌──────────────┐                                      │
│  │ 🟥 [RED BOX] │  Name: MOHAMMED SHAAN                │
│  │ Splice Blur  │  Nationality: INDIAN                 │
│  │ Artifact     │                                      │
│  └──────────────┘  DOB: 14/02/2005 🟨 [YELLOW BOX]     │
│                                    (MRZ Check Mismatch)│
│                                                        │
│  P<INDSHAAN<<MOHAMMED<<<<<<<<<<<<<<<<<<<<<             │
│  Z1234567<8IND0502148M3002142<<<<<<<<<<<<<<04          │
└────────────────────────────────────────────────────────┘
```

### Visual Alert Hierarchy:
* 🟥 **Critical Anomaly (Red Box):**
  - High-confidence pixel splicing / boundary halo detected around photo.
  - SIFT stamp mismatch (fake or unrecognized seal).
  - Explicit MRZ mathematical check digit failure.
* 🟨 **Suspicious Variance (Yellow Box):**
  - Character baseline or font thickness irregularity.
  - Slight discrepancy between OCR text and visual layout.
  - Borderline face recognition confidence (recommended for human secondary interview).
* 🟩 **Validated Field (Green Box):**
  - Exact match between OCR, MRZ, and database standards.

---

## 3. One-Click Incident Dossier Generation (PDF / Legal Report)

When a traveler is flagged and detained for investigation, the officer clicks **"Generate Incident Dossier"**. The system instantly compiles a court-admissible forensic summary document containing:

1. **Header:** Incident ID, Outpost Location, Date & Timestamp, Inspecting Officer Name & Badge ID.
2. **Subject Information:** Declared identity, document number, issuing country, nationality.
3. **Forensic Evidence Summary:**
   - Raw document image alongside side-by-side **ELA Heatmap**.
   - Bounding-box crop of the tampered region (e.g., altered digit with baseline deviation graph).
   - Live face capture vs. document photo with cosine similarity score and facial landmark alignment.
4. **Cryptographic Proof:**
   - SHA-256 hash of original document scan.
   - Block hash / Merkle proof from the local audit ledger.
5. **Officer Attestation Section:** Formal sign-off box for officer signature, biometric thumbprint, and physical observation notes.

---

## 4. Frontend & Backend Collaboration

* **Front-end (Kushal, Praneel):**
  - Implement canvas/SVG overlays to render bounding boxes dynamically over scanned documents.
  - Design a high-contrast dark-mode cockpit UI optimized for nighttime checkpoint visibility.
  - Build responsive modal for the 1-click PDF preview.
* **Back-end (Maheshwar, Shaan, Praneel):**
  - Provide bounding-box coordinate arrays and risk breakdown via REST API (`/api/v1/screen-document`).
  - Generate PDF dossiers server-side using ReportLab or WeasyPrint.

---

## Related Notes
* [[Document-Forensics-and-Tampering-Detection]]
* [[Blockchain-Audit-Trail-and-Watchlist-Sync]]
* [[Team]]
