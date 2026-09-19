# Deterministic Validation: ICAO MRZ & Regional Border IDs

**Tags:** #ocr #mrz #icao9303 #validation #regional-ids #sih2026  #module2
**Deliverable:** Modules 1 & 2 of PS26188

---

## 1. The Power of Deterministic Validation

Before spending compute cycles running heavy neural models, rule-based mathematical checks can detect **up to 90% of amateur document forgeries instantly** (sub-millisecond latency).

Security documents are designed with embedded mathematical safeguards:
1. **ICAO Doc 9303 MRZ Checksums:** Mathematical check digits baked into travel documents.
2. **VIZ vs. MRZ Cross-Matching:** Verifying that the human-readable text matches the machine-readable code.
3. **Cryptographic QR Validation:** Verifying digital signatures on modern national ID cards.

---

## 2. ICAO Doc 9303 MRZ Checksum Algorithm

Passports (TD3), Visas (MRV-A / MRV-B), and National ID cards (TD1 / TD2) contain a Machine Readable Zone (MRZ) formatted across 2 or 3 lines.

### The Algorithm: Modulo-10 with 7-3-1 Weighting
Every character is assigned a numeric value:
* Digits `0-9` $\to$ `0-9`
* Letters `A-Z` $\to$ `10-35`
* Filler `<` $\to$ `0`

Characters are multiplied sequentially by repeating weights `[7, 3, 1, 7, 3, 1, ...]`. The sum modulo 10 must equal the printed check digit:

$$\text{Check Digit} = \left( \sum_{i=0}^{n-1} \text{value}(c_i) \times \text{weight}(i \pmod 3) \right) \pmod{10}$$

### Mandatory Fields Validated:
1. **Document Number Check Digit:** Verifies the passport or visa number.
2. **Date of Birth Check Digit:** Verifies birth year, month, and day (`YYMMDD`).
3. **Date of Expiry Check Digit:** Verifies document expiration date (`YYMMDD`).
4. **Composite / Overall Check Digit:** Combines document number, DOB, and expiry to catch multi-field tampering.

> **Operational Impact:** If a fraudster modifies their birth year or document number on a passport scan without recalculating the official check digit, the system catches the forgery with pure arithmetic in less than 2 milliseconds.

---

## 3. Cross-Field Verification (VIZ vs. MRZ)

A common forgery vector is modifying the cleartext in the Visual Inspection Zone (VIZ) while neglecting the MRZ lines at the bottom (or vice versa):
* **Name Match:** Compare VIZ surname/given name against MRZ formatted name (`LAST<NAME<<FIRST<NAME`).
* **DOB & Expiry Match:** Cross-reference calendar dates from the upper document against MRZ `YYMMDD`.
* **Discrepancy Rule:** Any divergence between VIZ and MRZ results in an immediate **High Risk Flag (Score: 100%)**.

---

## 4. Regional ID Documents (Indo-Nepal & Indo-Bhutan Borders)

In accordance with bilateral treaties monitored by SSB, cross-border travelers frequently present non-passport identification:

| Document Type | Verification Strategy | Forgery Checkpoints |
| :--- | :--- | :--- |
| **Indian Voter ID (EPIC)** | Form pattern matching + Alphanumeric EPIC ID format | State/constituency prefix rules, hologram presence |
| **Nepali Citizenship Card (*Nagrikta*)**| Bilingual OCR (Devanagari + English), Issuing District format | District seal template match, official seal position |
| **Aadhaar Card** | Offline Secure QR Code parsing | Cryptographic UIDAI public key digital signature check |
| **Border Entry Permit** | Serial number validation, SSB outpost stamp validity | Validity window, duplicate serial check in local ledger |

### Offline Aadhaar / QR Verification:
Modern Indian identity cards feature a secure signed QR code. The system verifies this signature **completely offline** using the government's pre-loaded public key certificate. If the photo or text on the card disagrees with the cryptographically signed QR data payload, fraud is 100% confirmed.

---

## Related Notes
* [[Document-Forensics-and-Tampering-Detection]]
* [[ocr-pipeline-prototype]]
* [[PS26188_Problem_Analysis]]
