# Problem Statement Briefing: PS26188

**Tags:** #sih2026 #mha #ssb #problem-statement #official
**Last Updated:** 2026-09-17

---

## 1. Official Metadata

| Attribute                   | Details                                                 |
| :-------------------------- | :------------------------------------------------------ |
| **Problem Statement ID**    | **26188**                                               |
| **Problem Statement Title** | **AI-Based Fake Identity & Document Screening System**  |
| **Organization**            | Ministry of Home Affairs (MHA)                          |
| **Department**              | Sashastra Seema Bal (SSB), Police II Division           |
| **Category**                | Software                                                |
| **Theme**                   | Blockchain & Cybersecurity                              |
| **Possible Project Name**   | AI-Based Fake Identity & Document Screening System      |
| **Dataset Link**            | *None provided (Synthetic / Public Benchmark required)* |
| **YouTube Link**            | *None provided*                                         |

---

## 2. Background

Border checkpoints face severe operational and security challenges under current screening methods:
* **Prevalent Forgery Types:**
  - Fake passports and visas
  - Altered photographs (photo replacement/splicing)
  - Modified dates of birth
  - Tampered visa stamps
  - Identity impersonation
  - Multiple identities used by the same person
  - Expired or blacklisted travel documents
* **Operational Bottlenecks:**
  - High passenger volume causing severe checkpoint queues and delays.
  - Verification currently relies heavily on **manual human inspection** and basic database lookups.
  - Human inspection is prone to fatigue and cannot systematically detect sophisticated digital or physical alterations.

---

## 3. Detailed Problem Description

> *"Border checkpoints process thousands of identity documents every day, including passports, visas, national identity cards, permits, and travel authorizations. Manual verification is time-consuming, prone to human error, and often unable to detect sophisticated forgeries, tampering, or identity fraud.*
> 
> *Develop an AI-powered document screening platform that automatically analyzes identity and travel documents, detects signs of tampering or forgery, validates information against rules and databases, and generates a risk score to assist border security personnel in making faster and more accurate decisions."*

---

## 4. Expected Solution & Module Breakdown

The problem statement mandates four core functional modules:

### Module 1: OCR Extraction
* **Objective:** Automatically extract all relevant information from identity and travel documents.
* **Supported Input Document Types:**
  - Passport image
  - Visa image
  - National ID image
  - Driving license
  - Permit documents
* **Mandatory Extracted Fields:**
  * **Passport:**
    - Name
    - Passport Number
    - Nationality
    - Date of Birth
    - Date of Expiry
    - Gender
  * **Visa:**
    - Visa Number
    - Visa Type
    - Entry Validation
    - Stay Duration

### Module 2: Document Validation
* **Objective:** Verify whether the extracted information follows official document standards (format rules, validity checks, and structural compliance).

### Module 3: Tampering Detection (Core AI Innovation)
* **Objective:** Detect digitally or physically altered documents.
* **Core Use Cases:**
  - **Photo Replacement:** Detecting face swaps, spliced boundaries, or altered portraits.
  - **Text Manipulation:** Spotting altered characters, modified dates, font discrepancies, or erased text.
  - **Stamp Forgery Detection:** Identifying counterfeit, re-printed, or cloned immigration stamps and official seals.
  - **Image Metadata Analysis:** Analyzing digital image traces, software signatures, and file metadata inconsistencies.

### Module 4: Face Verification
* **Objective:** Ensure that the document owner matches the presented individual (matching the document photograph against a live-captured face).

---

## 5. Decision Support & Output Requirements

* **Risk Score Generation:** Consolidated score assessing the document's overall fraud/authenticity risk to assist—not replace—human border personnel.
* **Digital Audit Trail:** Generate a structured, verifiable digital log for every screening event for downstream intelligence and counter-terror investigation.

---

## 6. Expected Impact

1. **Verification Speed:** Reduce document verification time from several minutes down to a **few seconds**.
2. **Detection Rate:** Significantly improve detection of forged, tampered, and fraudulent identity documents.
3. **Decision Standardization:** Standardize screening quality and decisions consistently across all checkpoints.
4. **Data-Driven Assessment:** Transition border security from subjective human visual inspection to objective, quantified risk evaluation.
5. **Traceability:** Create an auditable digital trail for intelligence correlation, analytics, and legal investigations.
