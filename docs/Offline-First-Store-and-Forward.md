# Offline-First & Store-and-Forward Architecture

**Tags:** #architecture #offline #edge #ssb #sih2024 #resilience
**Target Problem:** Remote Border Outpost Connectivity Gap (PS26188)

---

## 1. Ground Reality & Motivation

According to Ministry of Home Affairs (MHA) records:
* Over **300 out of 734 SSB border outposts** along the Indo-Nepal and Indo-Bhutan borders have **no cellular reception, fiber broadband, or all-weather road connectivity**.
* Any document screening system requiring real-time cloud APIs, remote databases, or persistent internet connections is **inoperable** at these outposts.
* **The Mission Requirement:** The checkpoint must operate **100% autonomously offline**, while still ensuring that central command (MHA / Intelligence Bureau) receives logs and distributes updated watchlists.

---

## 2. Architecture Overview

The system uses a **Store-and-Forward** architecture with local ledger queues and opportunistic synchronization:

```text
┌────────────────────────────────────────────────────────┐
│               REMOTE BORDER OUTPOST (OFFLINE)          │
│                                                        │
│  [ Traveler Document ] ──► [ Local AI Pipeline ]       │
│                                   │                    │
│                                   ▼                    │
│                        [ Local SQLite Ledger ]         │
│                        - Screening Events              │
│                        - Forensic Hash Trail           │
│                        - Pending Sync Queue            │
└────────────────────────────────────────────────────────┘
                            ▲
                            │ Opportunistic Connection
                            ▼
┌────────────────────────────────────────────────────────┐
│             INTERMITTENT DATA CARRIER (MULE)           │
│  - SSB Patrol Vehicle with Satellite Terminal (VSAT)   │
│  - Officer Mobile Unit with Encrypted Mesh (Tailscale) │
│  - Scheduled Field Patrol Link                         │
└────────────────────────────────────────────────────────┘
                            ▲
                            │ Uplink
                            ▼
┌────────────────────────────────────────────────────────┐
│           CENTRAL HEADQUARTERS (MHA / SSB HQ)          │
│  - Central Audit Repository (Consolidated Blockchain)  │
│  - National Terror & Fake Passport Watchlist           │
│  - Intelligence Analytics Dashboard                    │
└────────────────────────────────────────────────────────┘
```

---

## 3. How Store-and-Forward Works in Operation

### Step 1: 100% Offline Edge Processing
* The outpost laptop/mini-PC runs all OCR, face matching, tampering checks, and cryptographic hashing locally.
* Every traveler screening creates an immutable local record:
  * Timestamp, Document metadata, Extracted fields
  * Tampering risk scores, Face match confidence
  * SHA-256 hash of original document image
  * Officer decision (Pass / Flag / Detain / Manual Override)
* Records are committed to an encrypted local queue (`pending_sync_queue`).

### Step 2: Opportunistic Sync Trigger
* When a patrol vehicle or officer unit enters local Wi-Fi / physical range:
  1. A background daemon detects the secure peer/gateway (via Tailscale mesh or local network ping).
  2. Handshake authenticates the outpost device using public/private key pairs.

### Step 3: Bidirectional Delta Synchronization
* **Push (Outpost $\to$ HQ):** Batched transmission of queued screening records and forensic hashes. Once acknowledged by HQ, records transition from `pending` to `synced`.
* **Pull (HQ $\to$ Outpost):** Incremental delta update of the national blacklist / fraudulent document watchlist (transferred as compact salted cryptographic hashes).
* **Graceful Disconnect:** If the vehicle leaves midway through sync, the transaction rollbacks cleanly and resumes on the next connection without duplicate records.

---

## 4. Key Advantages for the SIH Jury Presentation

* **Operational Credibility:** Addresses the exact topographical challenges documented in SSB outposts.
* **Zero Cloud Dependency:** Outposts maintain high passenger throughput even during weeks-long connectivity outages.
* **Data Integrity:** Local cryptographic hashing guarantees that offline records cannot be retroactively tampered with before transmission.

---

## Related Notes
* [[Blockchain-Audit-Trail-and-Watchlist-Sync]]
* [[Edge-Inference-LlamaCPP]]
* [[PS26188_Problem_Analysis]]
