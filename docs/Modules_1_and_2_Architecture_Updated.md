# Modules 1 & 2: OCR Extraction Pipeline and Deterministic Validation

**Tags:** #ocr #mrz #icao9303 #layout-analysis #active-learning #edge #validation #sih2026 #module1 #module2
**Deliverable:** Modules 1 & 2 of PS26188
**Status:** Architecture Specification (merged)
**Merged from:** `ocr-pipeline-prototype`, `Text-Line-Segmentation-and-Baseline-Clustering`, `AI-Candidate-Disambiguation-and-Active-Learning`, `Edge-Inference-LlamaCPP`, `Deterministic-Validation-ICAO-MRZ-and-Regional-IDs`, `Technologies_Used`

---

## Table of Contents

1. [Overview & Design Principles](#1-overview--design-principles)
2. [Image Preprocessing, Region Selection & OCR Boundary](#15-image-preprocessing-region-selection--ocr-boundary)
3. [End-to-End Architecture](#2-end-to-end-architecture)
4. [Module 1: OCR-to-Structured-Data Pipeline](#3-module-1-ocr-to-structured-data-pipeline)
   - 3.1 The Problem: Raw OCR Soup
   - 3.2 Why Bounding Boxes Matter
   - 3.3 Text Line Segmentation & Baseline Clustering
   - 3.4 Field-Aware Correction & Bounded Candidate Generation
   - 3.5 Bounded AI Candidate Disambiguation
   - 3.6 Dual-State Audit Schema
   - 3.7 Active Learning Feedback Cache
   - 3.8 Edge Inference via llama.cpp
   - 3.9 Worked Examples
5. [Module 2: Deterministic Validation](#4-module-2-deterministic-validation)
   - 4.1 The Power of Deterministic Validation
   - 4.2 ICAO Doc 9303 MRZ Checksums
   - 4.3 Cross-Field Verification (VIZ vs MRZ)
   - 4.4 Regional ID Documents
   - 4.5 Offline Aadhaar / QR Verification
5. [Security & Watchlist Query Strategy](#5-security--watchlist-query-strategy)
6. [Validation Rules (Combined)](#6-validation-rules-combined)
7. [Implementation Phases](#7-implementation-phases)
8. [Technology Stack](#8-technology-stack)
9. [Future Improvements](#9-future-improvements)
10. [Guardrails & First Build Recommendation](#10-guardrails--first-build-recommendation)
11. [Related Notes](#related-notes)

---

## 1. Overview & Design Principles

The goal is a reliable prototype that turns noisy OCR from identity and government documents into a small, validated JSON record. The system extracts only supported fields, retains evidence and confidence, and **never silently invents personal data**.

Example target schema:

```json
{
  "name": "",
  "document_number": "",
  "nationality": "",
  "date_of_birth": "",
  "issue_date": "",
  "expiry_date": "",
  "place_of_birth": "",
  "address": "",
  "confidence": {}
}
```

The two modules split the work by how much trust each technique deserves:

| Module | Approach | Role |
| :--- | :--- | :--- |
| **Module 1** | Hybrid: deterministic code + tightly bounded AI | Turns messy OCR into structured, auditable fields |
| **Module 2** | Purely deterministic (math and rules) | Cheaply catches forgeries *before* any neural model runs |

### Core design principles

1. **Deterministic first, AI last.** Rules handle everything repeatable. The LLM only resolves ambiguity that rules cannot safely settle.
2. **Bounded, never generative.** The model picks from a closed candidate list. It cannot emit text that wasn't already in the pool.
3. **Evidence is never overwritten.** Raw OCR output is preserved beside every resolved value (legal admissibility).
4. **Coordinates beat reading order.** Layout, not text order, decides which words belong to which field.
5. **Field-aware corrections.** No single global character map. `0` means `O` in a name but zero in an ID.
6. **Offline and edge-friendly.** Everything runs on Python 3.10+ hardware, down to a Raspberry Pi.

---

## 2. End-to-End Architecture

```text
Document image / PDF
        |
        v
Pre-processing BEFORE ANY OCR
  - grayscale conversion
  - thresholding / binarization
  - noise removal
  - deskewing
  - upscale to >= 300 DPI equivalent
        |
        v
UI region selection / automatic proposal
  - VIZ / document-text region
  - MRZ region
        |
        +-------------------------------+-------------------------------+
        |                                                               |
        v                                                               v
┌─────────────────────────────────────┐             ┌─────────────────────────────────────┐
│ MODULE 1: VIZ / DOCUMENT TEXT       │             │ MODULE 2: MRZ                       │
│                                     │             │                                     │
│ Crop excludes MRZ                   │             │ Crop contains MRZ only              │
│ EasyOCR / PaddleOCR                 │             │ EasyOCR / PaddleOCR                 │
│ text + confidence + bounding boxes  │             │ MRZ text + bounding boxes           │
│ field/layout extraction              │             │ ICAO 9303 parsing + checksums       │
│ bounded AI classification x3         │             │ deterministic validation             │
│ overlay every text + confidence      │             │ overlay MRZ + recognized text        │
└──────────────────┬──────────────────┘             └──────────────────┬──────────────────┘
                   |                                                   |
                   +--------------------+------------------------------+
                                        v
                         VIZ ↔ MRZ cross-field verification
                                        |
                           (agreement / discrepancy)
                                        |
                                        v
                            Officer review / validation
                                        |
                           +------------+------------+
                           |                         |
                        accept                    edit
                           |                         |
                           +------------+------------+
                                        v
                              Officer-validated data
                                        |
                                        v
                         Active-learning feedback cache
                         (runs ONLY after validation)
```text
Document image / PDF
        |
        v
OCR engine (text + confidence + bounding boxes)
        |
        v
Pre-processing (deskew via Hough / Min-Area Rect)
        |
        v
Layout & field detection
  - document type / template
  - line clustering (dynamic baseline)
  - labels, zones, key-value proximity
        |
        v
┌─────────────────────────────────────────────────────┐
│ MODULE 2: Deterministic Validation (sub-millisecond)│
│  - MRZ modulo-10 checksums (7-3-1)                  │
│  - VIZ vs MRZ cross-matching                        │
│  - Offline signed-QR verification (Aadhaar)         │
└─────────────────────────────────────────────────────┘
        |
        v
Deterministic normalization
  - whitespace, dates, labels, safe OCR substitutions
        |
   (Clean match?) ─── yes ──► Structured JSON
        | no: ambiguity / anomaly flagged
        v
Active-learning cache lookup (O(1) SQLite)
        | miss
        v
Load GGUF via llama.cpp ─► Bounded, grammar-constrained
        |                   candidate selection ─► Free memory
        v
Schema validation + evidence / confidence checks
        |
        v
Structured JSON  /  Officer review queue
```

### Component responsibilities

| Stage | Responsibility | Must **not** do |
| :--- | :--- | :--- |
| Pre-processing | Produce normalized OCR-ready crops | Run OCR on the raw image |
| Region selection | Define the VIZ/document-text crop and MRZ crop | Allow the two modules to read each other's regions |
| Module 1 OCR | Extract document/VIZ text, confidence, coordinates | Read or interpret MRZ data |
| Module 2 OCR | Extract MRZ text and coordinates | Read unrelated VIZ fields |
| Layout / field detection | Associate Module 1 text with a region or label | Guess a person's spelling |
| Deterministic normalization | Apply predictable, field-specific transformations | Make broad global substitutions |
| LLM | Classify/disambiguate bounded candidates in three isolated sequential runs | Be the sole extractor or source of truth |
| Validation | Enforce schema, formats, MRZ checksums, and VIZ↔MRZ constraints | "Fix" unsupported values silently |
| Active learning | Learn only from officer-validated final values | Learn from unreviewed AI/OCR output |

---

## 3. Module 1: OCR-to-Structured-Data Pipeline

### 3.0 Module 1 Boundary: Visual Document Text Only

Module 1 is responsible for **textual data printed in the Visual Inspection Zone (VIZ)**. It does not extract the MRZ. Before OCR, the system applies the mandatory preprocessing pipeline and then crops the image so the MRZ is outside the OCR input.

```text
Preprocessed document
        |
        v
Officer-selected / detected VIZ crop
        |
        |  MRZ excluded
        v
EasyOCR / PaddleOCR
        |
        v
text + confidence + bounding boxes
        |
        v
field/layout extraction -> bounded candidate generation -> AI classification x3
```

Module 1's UI overlay draws a box around **every text region detected by OCR** and displays its confidence score. The overlay must remain tied to the original source coordinates so the officer can inspect the exact evidence.

### 3.1 The Problem: Raw OCR Soup

It is tempting to dump the full OCR result into a small instruction model and ask for JSON. This fails often, even with a prompt explaining common character confusions.

For a simple labelled input:

```text
N4ME Moh4mmed Sh44n DOB 14-02-2005 Addr Hyderabad
```

the model must simultaneously identify corrupt labels, separate labels from values, repair characters, infer name spelling, and emit exact JSON. A 0.5B model may fold `N4ME` into the name, leave `Sh44n` uncorrected, or vary its answer between runs.

The real document OCR is much harder:

```text
WING THRTIGY REPUBLIC OF
INDIA
...
TS3081¢
SHAAN
...
MOHAMMAD
...
INDIAN
...
SORAKHPUR ,UTTAR PRADESH
...
HYDERABAD
...
01/11/2019
31/10/2024
```

This contains headers, noise, split name components, an uncertain identifier, multiple places, and dates with different meanings. Reading order alone does not say which text belongs to which field. Asking a small model to do OCR repair, document understanding, reasoning, and strict serialization in one step gives it too much responsibility for an unreliable component.

**Two failure extremes engineers fall into:**

1. **The Brittle Rule Trap:** thousands of hardcoded replacements (`if '4' in name: replace with 'a'`). Fails on non-standard spellings and legitimate numbers.
2. **The Hallucinatory LLM Trap:** asking a free-form LLM to "clean the name". It may change `MOHAMMAD` to `MUHAMMED`, silently altering a citizen's legal identity.

The answer to both is **bounded candidate disambiguation** (section 3.5).

### 3.2 Why Bounding Boxes Matter

OCR output must retain at least `text`, `confidence`, and `x/y/width/height` for every word or line. Coordinates turn an unstructured text stream into document layout.

```json
[
  {"text": "SURNAME",  "bbox": [80, 280, 130, 24],  "confidence": 0.91},
  {"text": "SHAAN",    "bbox": [250, 280, 85, 24],  "confidence": 0.96},
  {"text": "GIVEN",    "bbox": [80, 320, 100, 24],  "confidence": 0.94},
  {"text": "MOHAMMAD", "bbox": [250, 320, 140, 24], "confidence": 0.97}
]
```

With these boxes, the system can infer that `SHAAN` is the value to the right of `SURNAME`, and `MOHAMMAD` is the value to the right of `GIVEN`, even when reading order is strange. It can also identify headers at the top, machine-readable zones at the bottom, table rows, and text belonging to nearby labels. Preserve the original crop or page reference too, so uncertain extractions can be reviewed.

**Useful spatial rules for the prototype:**

- Prefer text on the same horizontal line and immediately to the right of a label.
- Define form zones as percentages of page width/height, not fixed pixels.
- Merge adjacent words only when baseline and gap indicate one value.
- Exclude likely headers, footers, seals, and OCR fragments outside the target zone.
- Record source word IDs for every final value.

### 3.3 Text Line Segmentation & Baseline Clustering

#### The core problem: why exact Y-coordinates fail

When associating `FIRST NAME` with `LAST NAME`, or `MOHAMMED` with `SHAAN`, naive `y1 == y2` matching fails almost every time because of:

1. **Micro-skew / document tilt:** even $0.5^\circ - 1.5^\circ$ makes words on one line drift 10-30 px across the page width.
2. **Ascenders and descenders:** `b, d, h, k, t` push box tops up; `g, j, p, q, y` push bottoms down.
3. **OCR bounding-box jitter:** Tesseract and PaddleOCR produce slight boundary noise between adjacent words.

#### First-principles intuition: dynamic vertical edge profiling

Instead of a hardcoded pixel tolerance (which breaks when resolution changes from 72 to 300 DPI), derive the threshold from the document's own typography:

1. **Vertical transition scanning:** scan pixel columns in a text band. White to ink records $y_{\text{start}}$; ink to white records $y_{\text{end}}$.
2. **Line-height extraction:** the stroke span $\Delta y = y_{\text{end}} - y_{\text{start}}$ is the character height. Averaging it over a region gives the document's intrinsic font scale $\bar{h}$.
3. **Dynamic band condition:** words $W_A$ and $W_B$ belong to the same line/field if

$$|y_{c,A} - y_{c,B}| \le \alpha \cdot \bar{h}, \qquad \alpha \approx 0.3 - 0.5$$

where $y_c$ is the box vertical center.

#### Classical CV equivalents

**A. Horizontal Projection Profile (HPP).** Sum binarized ink pixels row by row to get a 1D histogram. Valleys are inter-line gutters; peaks are text lines. Peak width gives the dynamic threshold and is immune to font-size variation.

```text
Row Pixels      Horizontal Projection
[   INK   ]  ──► ████████████████  (Peak = Line 1)
[  WHITE  ]  ──►                   (Valley = Line Gap)
[   INK   ]  ──► ██████████████    (Peak = Line 2)
```

**B. Vertical 1D-IoU.** For OCR boxes $B_1(y_{\text{top1}}, y_{\text{bot1}})$ and $B_2(y_{\text{top2}}, y_{\text{bot2}})$:

$$\text{Overlap}_y = \frac{\max(0,\ \min(y_{\text{bot1}}, y_{\text{bot2}}) - \max(y_{\text{top1}}, y_{\text{top2}}))}{\min(h_1, h_2)}$$

If $\text{Overlap}_y \ge 0.50$, both words share the same baseline band.

#### Back-end implementation

```python
from typing import List, Dict

def cluster_words_into_lines(words: List[Dict], vertical_iou_threshold: float = 0.5) -> List[List[Dict]]:
    """
    Groups OCR word bounding boxes into coherent text lines using dynamic vertical overlap.

    words: list of dicts with keys: 'text', 'box' -> [x_min, y_min, x_max, y_max]
    """
    if not words:
        return []

    # Sort words primarily top-to-bottom, secondarily left-to-right
    sorted_words = sorted(words, key=lambda w: (w['box'][1], w['box'][0]))

    lines = []

    for word in sorted_words:
        w_box = word['box']
        w_top, w_bot = w_box[1], w_box[3]
        w_height = max(1, w_bot - w_top)

        matched_line = None
        for line in lines:
            # Compare with average vertical span of the current line
            line_top = min(item['box'][1] for item in line)
            line_bot = max(item['box'][3] for item in line)
            line_height = max(1, line_bot - line_top)

            # Calculate 1D Vertical Overlap
            intersection = max(0, min(w_bot, line_bot) - max(w_top, line_top))
            min_height = min(w_height, line_height)
            overlap_ratio = intersection / min_height

            if overlap_ratio >= vertical_iou_threshold:
                matched_line = line
                break

        if matched_line is not None:
            matched_line.append(word)
        else:
            lines.append([word])

    # Sort words within each line left-to-right
    for line in lines:
        line.sort(key=lambda w: w['box'][0])

    return lines
```

#### Integration notes

1. **Deskew first:** run Hough Line Transform or Min-Area Rect to remove skew angle $\theta$ before clustering.
2. **Field reconstruction:** feed clustered lines into the deterministic normalizer to rebuild split fields (e.g. `SHAAN` + `MOHAMMAD`).
3. **Forensics link:** if two words on the same printed line have wildly different baseline offsets, flag potential **Text Manipulation** in [[Document-Forensics-and-Tampering-Detection]].

### 3.4 Field-Aware Correction & Bounded Candidate Generation

Do not apply one character map globally. `0` might mean `O` in a name, but is normally a zero in an identifier or date. Corrections must depend on the expected field, stay strictly bounded, and preserve dual-state auditability.

| Field | Candidate Generation Strategy | Candidate Example | Disambiguation Method |
| :--- | :--- | :--- | :--- |
| Labels | Aggressively normalize structural variants (`N4ME`, `ADDR`, `D0B`) | `N4ME` → `["NAME"]` | Deterministic lookup / regex |
| Names | Plausible hypotheses for leetspeak/OCR noise (`4↔A`, `0↔O`, `5↔S`, `rn↔m`, `vv↔w`) | `Moh4mmed Sh44n` → `["Moh4mmed Sh44n", "Mohammed Shaan"]` | Bounded local AI choice (constrained decoding) |
| Dates | Normalize separators; recognize patterns; verify real calendar date | `14-02-2005` → `["2005-02-14"]` | Deterministic calendar validation (never treat `0↔O`) |
| ID / document number | Preserve alphanumeric ambiguity as explicit alternatives; check digits | `TS3081¢` → `["TS3081", "TS3081C"]` | Template pattern + MRZ / check-digit validation |
| Nationality | Match against controlled vocabulary (ISO 3166-1 alpha-3) | `INDIAN` → `["IND", "Indian"]` | Controlled dictionary lookup |
| Places / address | Normalize punctuation, whitespace; extract administrative-region candidates | `SORAKHPUR ,UTTAR PRADESH` → `["Gorakhpur, Uttar Pradesh", "Sorakhpur"]` | Geographic gazetteer + bounded AI ranking |

### 3.5 Bounded AI Candidate Disambiguation

#### Three-pass stateless AI classification

When deterministic rules cannot resolve an ambiguity, Module 1 runs the AI classifier **three times sequentially**. Each run is a new, isolated model invocation. The model does not retain conversation history, hidden state, or memory from previous requests. The output from the previous run is explicitly included as structured input to the next run.

```text
Candidate pool + OCR/layout evidence
            |
            v
       AI Pass 1
            |
            v
 Pass 1 structured output
            |
            v
       AI Pass 2
  (receives Pass 1 output)
            |
            v
 Pass 2 structured output
            |
            v
       AI Pass 3
  (receives Pass 2 output)
            |
            v
 Final bounded classification
```

The application, not the model conversation, carries the state between passes. Every request therefore contains only the information explicitly supplied in that request. This prevents accidental reliance on a prior conversation while still allowing iterative classification.

Recommended pass roles are:

1. **Pass 1: independent classification** from the bounded candidate pool and document context.
2. **Pass 2: reclassification** using the original evidence plus Pass 1's structured result.
3. **Pass 3: final classification** using the original evidence plus Pass 2's structured result, followed by schema and candidate-membership validation.

No pass may introduce a candidate that was not present in the bounded candidate pool.


Instead of letting the AI generate arbitrary text, extraction splits into two discrete stages:

```text
[ Raw OCR Token: "SH44N" ]
            │
            ▼
[ Deterministic Candidate Generator ]
  Candidate 0: "SH44N" (raw as-is)
  Candidate 1: "SHAAN" (4 ↔ A repair)
            │
            ▼
[ Constrained Local AI (llama.cpp / Qwen2.5) ]
  Multiple-choice selection under GBNF grammar constraint
  Decides using language and layout context
            │
            ▼
[ Dual-State Record ]
  raw_text: "SH44N"   resolved_value: "SHAAN"   confidence: 0.94
```

The model receives **structured candidates, never a raw OCR dump**.

#### Bounded disambiguation prompt schema

```json
{
  "field": "name",
  "raw_ocr_token": "SH44N",
  "candidate_hypotheses": ["SH44N", "SHAAN"],
  "spatial_context": {
    "nearby_label": "SURNAME",
    "preceding_words": ["MOHAMMAD"],
    "document_type": "passport"
  },
  "constraint": "Return JSON containing ONLY 'selected_candidate' chosen strictly from candidate_hypotheses, and 'confidence'. Do not invent or alter characters."
}
```

#### Grammar-constrained decoding (GBNF in llama.cpp)

Compiling the candidate list into a dynamic context-free grammar physically restricts the sampler at decode time:

```gbnf
root ::= "{\"selected_candidate\": \"" ( "SH44N" | "SHAAN" ) "\", \"confidence\": " [0-9] "." [0-9]+ "}"
```

The model cannot emit any spelling that was not in the candidate pool, which removes hallucination by construction. Also set **temperature to `0.0`** for deterministic, reproducible inference. Where GBNF isn't available, use JSON Schema mode rather than prompt-only JSON enforcement.

### 3.6 Dual-State Audit Schema

Under Ministry of Home Affairs and police evidence requirements, altering a traveler's legal identity without retaining the raw artifact can make digital evidence inadmissible. **Never overwrite raw OCR evidence with AI inferences.**

Every field is stored as a Dual-State Object:

```json
{
  "field": "surname",
  "raw_text": "SH44N",
  "candidate_pool": ["SH44N", "SHAAN"],
  "resolved_value": "SHAAN",
  "disambiguation_source": "local_ai_gbnf",
  "confidence": 0.94,
  "source_bbox": [250, 280, 85, 24],
  "source_word_ids": [57],
  "transformations": ["4_to_A_repair", "title_case"],
  "officer_override": null,
  "verified": false
}
```

| Key | Meaning |
| :--- | :--- |
| `raw_text` | Exact characters returned by the OCR engine |
| `candidate_pool` | All generated hypotheses |
| `resolved_value` | Candidate chosen by rules, AI, or officer |
| `disambiguation_source` | `deterministic`, `feedback_cache`, `local_ai_gbnf`, or `officer` |
| `confidence` | Model or rule confidence |
| `source_bbox` / `source_word_ids` | Pixel coordinates and word IDs from the original scan |
| `transformations` | Ordered list of rules applied |
| `officer_override` | `null` if untouched; otherwise records the officer's confirmation or change |
| `verified` | Whether an officer has confirmed or edited and then confirmed the final value |

Both raw and resolved values are shown side by side in the border officer cockpit UI. The simplified public JSON is derived only *after* this richer record validates.

**Composite example (name with an undeterminable field):**

```json
{
  "name": {
    "value": "Mohammad Shaan",
    "confidence": 0.92,
    "raw_text": ["MOHAMMAD", "SHAAN"],
    "source_word_ids": [42, 57],
    "transformations": ["title_case", "layout_order:given_then_surname"]
  },
  "expiry_date": {
    "value": null,
    "confidence": 0.0,
    "reason": "date role cannot be determined from current OCR evidence"
  },
  "review_required": true
}
```

### 3.7 Active Learning Feedback Cache

A border outpost sees thousands of documents from the same national template. If a specific typewriter font or printing defect repeatedly renders `A` as `4`, waking the LLM for every traveler is wasteful and slow.

#### Local SQLite schema

```sql
CREATE TABLE IF NOT EXISTS ocr_feedback_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_token TEXT NOT NULL,
    field_type TEXT NOT NULL,
    document_type TEXT NOT NULL,
    selected_candidate TEXT NOT NULL,
    verified_by_officer BOOLEAN NOT NULL DEFAULT 1,
    officer_badge_id TEXT NOT NULL,
    hit_count INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(raw_token, field_type, document_type)
);
```

#### Execution lifecycle

1. **Cache interception (O(1) lookup).** On seeing `SH44N`, query `ocr_feedback_cache`. Only entries that were previously validated by an officer may be used as learning feedback.
2. **Officer human-in-the-loop.** The officer may **accept the proposed value or edit it**. The learning-feedback path remains inactive until the officer explicitly validates the final field value. Once validated, an asynchronous update increments `hit_count` and updates `selected_candidate`:
   ```sql
   INSERT INTO ocr_feedback_cache
     (raw_token, field_type, document_type, selected_candidate, verified_by_officer, officer_badge_id)
   VALUES ('SH44N', 'name', 'passport', 'SHAAN', 1, 'OFF-8821')
   ON CONFLICT(raw_token, field_type, document_type)
   DO UPDATE SET hit_count = hit_count + 1, selected_candidate = excluded.selected_candidate;
   ```
3. **Few-shot priming.** If the cache can't resolve an unseen variant, only officer-validated corrections may be used as few-shot examples. Unvalidated OCR or AI output is never promoted into the learning cache.
4. **Failure-mode logging.** Recurring officer-validated corrections are classified and fed back into rules, templates, and tests.

### 3.8 Edge Inference via llama.cpp

Standard serving frameworks like **Ollama** run background daemons with substantial memory footprints and generic abstraction layers. On border-checkpoint laptops, mini-PCs, or field kits, RAM and VRAM are strictly constrained.

**Solution: direct native inference** with `llama.cpp` (or `llama-cpp-python`) using quantized GGUF models, following a **Load-Run-Kill** lifecycle:

1. Keep the model unloaded/cold while idle.
2. Load on demand when an ambiguous field arrives.
3. Run inference for field normalization or a visual anomaly check.
4. Promptly free memory and return to low-power idle.

**Benefits:** no background-daemon memory leak; sub-second cold starts with `mmap`; lower thermal throttling and battery draw.

#### Hardware and model profile

The backend runs on any device supporting Python 3.10+, with **Raspberry Pi 4 / Pi 5 (ARM64, 4/8 GB) as the lower-bound target**. On Cortex-A72/A76, `llama.cpp` compiles with ARM NEON for accelerated integer math.

| Model | Quantization | RAM | Performance | Best use |
| :--- | :--- | :--- | :--- | :--- |
| SmolVLM-500M / 2B | Q4_K_M | ~1.2 - 2.5 GB | ~3-6 tok/s on Pi 5 | Ultra-fast layout verification, stamp check |
| Qwen2.5-VL-3B-Instruct | Q4_K_M | ~2.6 GB | Fast on x86, workable on Pi 5 | Visual inspection, multilingual OCR, stamp/photo analysis |
| Qwen2.5-3B-Instruct | Q4_K_M | ~2.0 GB | ~4-8 tok/s on Pi 5 | Text normalization, ambiguous-JSON repair |
| Llama-3.2-3B-Instruct | Q4_K_M | ~2.1 GB | ~4-7 tok/s on Pi 5 | Schema compliance, fallback verification |

#### Setup steps

1. **Environment:** install `llama-cpp-python` with hardware acceleration (CUDA for NVIDIA, OpenBLAS/Vulkan for generic hardware).
2. **Model storage:** keep `.gguf` weights on local NVMe to maximize memory-mapping speed.
3. **Cache management:** timeout eviction, e.g. purge the model from memory if no document is scanned for 60 seconds.

### 3.9 Worked Examples (Real OCR)

**1. Name fragments.** The OCR contains `SHAAN` and `MOHAMMAD`, but text alone doesn't prove order or surname/given roles. With labels and coordinates:

```json
{
  "surname":     {"raw_text": "SHAAN",    "value": "Shaan",          "confidence": 0.96},
  "given_names": {"raw_text": "MOHAMMAD", "value": "Mohammad",       "confidence": 0.97},
  "name":        {"value": "Mohammad Shaan", "confidence": 0.92}
}
```

Without labels or coordinates, keep these as candidates rather than confidently emitting a full name.

**2. Dates.** `01/11/2019` and `31/10/2024` are valid dates, but validation cannot tell issue/expiry from travel dates. Use adjacent labels or template zones; otherwise return unclassified candidates:

```json
{
  "date_candidates": [
    {"raw": "01/11/2019", "iso": "2019-11-01", "role": null},
    {"raw": "31/10/2024", "iso": "2024-10-31", "role": null}
  ]
}
```

**3. Place strings.** `HYDERABAD` is a strong place candidate; `SORAKHPUR ,UTTAR PRADESH` may be a mangled locality. Classify both as location candidates and use spatial context to assign `place_of_birth` or `address`. Don't treat one as the address merely because it appears later in OCR text.

**4. Identifier.** `TS3081¢` stays as raw evidence. A deterministic cleaner may drop an obvious terminal artifact only if the template says the number has six characters. Otherwise preserve the uncertainty (e.g. `TS3081?`) and flag for review.

---

## 4. Module 2: Deterministic Validation

### 4.0 Module 2 Boundary: MRZ Only

Module 2 receives an **MRZ-only crop**. It does not OCR the rest of the document. Its first responsibility is to read the machine-readable zone, highlight the MRZ and recognized text in the UI, parse the MRZ according to its document format, and validate its check digits.

After extraction, Module 2 compares its MRZ-derived fields against the corresponding **Module 1 VIZ/document-text fields**. The two modules therefore provide separate evidence streams:

```text
Module 1 VIZ data  ───────────────┐
                                  v
                              Cross-check
                                  ^
                                  |
Module 2 MRZ data ───────────────┘
                                  |
                                  v
                       agreement / discrepancy
```

The MRZ crop is selected by the UI or proposed automatically and can be adjusted by the officer. The selected coordinates are retained in the audit record.

### 4.1 The Power of Deterministic Validation

Before spending compute on neural models, rule-based mathematical checks can detect **a large share of amateur document forgeries instantly** (sub-millisecond latency; the source estimate is up to ~90%, to be confirmed on a real test set).

Security documents embed mathematical safeguards:

1. **ICAO Doc 9303 MRZ checksums:** check digits baked into travel documents.
2. **VIZ vs MRZ cross-matching:** the human-readable text must match the machine-readable code.
3. **Cryptographic QR validation:** digital signatures on modern national ID cards.

### 4.2 ICAO Doc 9303 MRZ Checksum Algorithm

Passports (TD3), visas (MRV-A / MRV-B), and ID cards (TD1 / TD2) carry a Machine Readable Zone across 2 or 3 lines.

#### Modulo-10 with 7-3-1 weighting

Character values:

- Digits `0-9` → `0-9`
- Letters `A-Z` → `10-35`
- Filler `<` → `0`

Multiply characters sequentially by repeating weights `[7, 3, 1, 7, 3, 1, ...]`. The sum modulo 10 must equal the printed check digit:

$$\text{Check Digit} = \left( \sum_{i=0}^{n-1} \text{value}(c_i) \times \text{weight}(i \bmod 3) \right) \bmod 10$$

#### Reference implementation

```python
def mrz_char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    raise ValueError(f"Invalid MRZ character: {c!r}")

def mrz_check_digit(field: str) -> int:
    weights = (7, 3, 1)
    total = sum(mrz_char_value(c) * weights[i % 3] for i, c in enumerate(field))
    return total % 10

# Example: verify a printed check digit
assert mrz_check_digit("520727") == 3   # ICAO 9303 specimen date field
```

#### Mandatory fields validated

1. **Document number check digit:** verifies the passport or visa number.
2. **Date-of-birth check digit:** verifies `YYMMDD`.
3. **Date-of-expiry check digit:** verifies `YYMMDD`.
4. **Composite / overall check digit:** combines document number, DOB, and expiry to catch multi-field tampering.

> **Operational impact:** if a fraudster edits a birth year or document number on a passport scan without recalculating the check digit, the system catches it with pure arithmetic in under ~2 ms.

**Link to Module 1:** the MRZ check digit is also the strongest disambiguator for ambiguous document numbers. If `TS3081¢` yields candidates `["TS3081", "TS3081C"]` and the MRZ carries a check digit, only one candidate can pass. This is how OCR ambiguity gets resolved *without* invoking the LLM at all.

### 4.3 Cross-Field Verification (VIZ vs MRZ)

A common forgery edits the cleartext in the Visual Inspection Zone (VIZ) while leaving the MRZ untouched, or vice versa.

- **Name match:** VIZ surname / given name vs MRZ formatted name (`LAST<NAME<<FIRST<NAME`).
- **DOB and expiry match:** calendar dates from the upper document vs MRZ `YYMMDD`.
- **Discrepancy rule:** any divergence between VIZ and MRZ raises an immediate **High Risk Flag (score: 100%)**.

The MRZ is an *independent evidence source* for Module 1: Module 2 extracts it from an MRZ-only crop and then cross-checks its fields against Module 1. Agreement supports consistency; disagreement routes to officer review.

### 4.4 Regional ID Documents (Indo-Nepal & Indo-Bhutan Borders)

Under bilateral treaties monitored by SSB, cross-border travelers often present non-passport identification:

| Document | Verification strategy | Forgery checkpoints |
| :--- | :--- | :--- |
| **Indian Voter ID (EPIC)** | Form pattern matching + alphanumeric EPIC ID format | State/constituency prefix rules, hologram presence |
| **Nepali Citizenship Card (*Nagrikta*)** | Bilingual OCR (Devanagari + English), issuing-district format | District seal template match, official seal position |
| **Aadhaar Card** | Offline secure QR parsing | UIDAI public-key digital-signature check |
| **Border Entry Permit** | Serial-number validation, SSB outpost stamp validity | Validity window, duplicate-serial check in local ledger |

### 4.5 Offline Aadhaar / QR Verification

Modern Indian identity cards carry a secure signed QR code. The system verifies the signature **completely offline** using the government's pre-loaded public-key certificate. If the photo or text on the card disagrees with the cryptographically signed QR payload, the card has been tampered with (or the QR was swapped), which is treated as a confirmed mismatch and escalated.

---

## 5. Security & Watchlist Query Strategy

When checking travelers against national blacklists or watchlists:

- **Parallel querying:** query the salted-hash set for **both** the raw string (`SH44N`) and the AI-resolved string (`SHAAN`).
- **Anti-evasion:** if a fugitive deliberately submits an ID with leetspeak or altered characters to dodge exact-string matches, querying both forms flags the identity immediately.
- **Privacy-preserving matching:** salted hashes / Bloom filters let edge devices match blacklisted documents without holding sensitive intelligence in cleartext.

---

## 6. Validation Rules (Combined)

**Schema and structure**

- Require every output key; use `""` or `null` consistently for unknown values.
- Normalize accepted dates to ISO `YYYY-MM-DD`; reject invalid calendar dates.
- Enforce document-number patterns only *after* document type/template detection.

**Integrity**

- Reject a field value that contains a known label (e.g. `N4ME Moh4mmed Sh44n`).
- Reject unsupported additions: every final value must map to a raw OCR token, a deterministic transformation, or an explicitly recorded candidate decision.
- Keep raw OCR, coordinates, and transformations separate from the final normalized record.

**Cryptographic and cross-source**

- MRZ check digits (document number, DOB, expiry, composite) must all pass.
- VIZ and MRZ fields must agree; any divergence is a high-risk flag.
- Signed-QR payload must agree with printed content.

**Routing**

- Attach confidence to every field; route low-confidence or contradictory fields to human review.

---

## 7. Implementation Phases

### Phase 1: Minimal labelled-text baseline

1. Add the mandatory pre-OCR pipeline: grayscale, thresholding/binarization, noise removal, deskewing, and upscaling to at least 300 DPI equivalent.
2. Add UI region selection for the VIZ/document-text crop and MRZ crop.
3. Accept OCR plain text; extract known labels with tolerant regexes (`NAME`, `N4ME`, `DOB`, `ADDR`).
4. Capture values between labels.
5. Add field-specific normalizers for dates, whitespace, and label removal.
6. Produce strict JSON validated with Pydantic or JSON Schema.
7. Build a small test corpus with expected JSON and failure cases.
8. **Add MRZ checksum validation** (cheap, high value, pure arithmetic).

*Success:* labelled synthetic examples consistently produce valid JSON with no label leakage; MRZ checks pass/fail correctly on specimen data.

### Phase 2: Coordinates and document layout

1. Retain word/line boxes and confidence from OCR.
2. Enforce separate VIZ and MRZ crops before OCR; Module 1 must exclude MRZ and Module 2 must exclude VIZ text.
3. Deskew, then group words into lines with baseline clustering; detect labels and value regions.
4. Render Module 1 text+confidence overlays and Module 2 MRZ+recognized-text overlays.
5. Add page zones and template definitions for one document type.
6. Save source-box references with every field and the selected VIZ/MRZ crop coordinates.
7. Add VIZ vs MRZ cross-matching.

*Success:* split fields such as surname/given name extract correctly even in confusing reading order.

### Phase 3: Controlled LLM fallback

1. Pass only unresolved, structured candidate sets to the LLM.
2. Use grammar/JSON-schema constrained output; validate every response.
3. Run the AI classification as three sequential, stateless passes, explicitly feeding each previous structured output into the next request.
4. Implement the SQLite feedback cache and cache-first lookup, with writes enabled only after officer validation or edit-and-validation.
5. Measure whether the fallback improves accuracy over deterministic-only extraction.
6. Route uncertain answers to review, never auto-accept.

*Success:* the LLM resolves a documented class of ambiguous cases without ever reducing validation coverage.

### Phase 4: Regional IDs, evaluation, and review tooling

1. Add Aadhaar offline QR verification and regional ID templates (EPIC, Nagrikta, Entry Permit).
2. Build a labelled evaluation set of representative *scans*, not just clean text.
3. Track field-level precision, recall, invalid-output rate, and human-review rate.
4. Build a reviewer screen: final value, raw value, page crop, rules applied, confidence.
5. Log recurring OCR errors to improve rules, templates, and tests.

---

## 8. Technology Stack

### AI, ML & computer vision

| Technology | Role | Why selected |
| :--- | :--- | :--- |
| `llama.cpp` / `llama-cpp-python` | Local quantized LLM/VLM execution | Native C++ runtime; no daemon overhead; fast mmap cold starts |
| Qwen2.5-3B / SmolVLM (GGUF) | Bounded disambiguation and VLM checks | ~2-2.6 GB RAM; GBNF decoding prevents hallucination |
| PaddleOCR / Tesseract | Word and character bounding-box extraction | Fast multilingual OCR with $(x, y, w, h)$ coordinates |
| OpenCV (`cv2`) | Preprocessing and forensics | Deskew, ELA, SIFT/ORB stamp matching, Hough transforms |
| InsightFace / ArcFace (ONNX) | Face verification | 512-d embeddings, age-progression tolerance, fast CPU/GPU inference |
| Pillow (PIL) | Image manipulation and ELA diffing | JPEG re-compression heatmaps |

### Back-end & API

| Technology | Role | Why selected |
| :--- | :--- | :--- |
| Python 3.10+ | Core language | Native AI/ML, CV, and crypto ecosystem |
| FastAPI | Async REST API | Async execution, auto OpenAPI docs, low route overhead |
| Pydantic v2 | Schema enforcement | Strict validation for dual-state records |
| ReportLab / WeasyPrint | PDF generation | One-click incident dossiers with embedded ELA heatmaps |

### Database, cryptography & audit

| Technology | Role | Why selected |
| :--- | :--- | :--- |
| SQLite (WAL mode) | Offline DB and queues | Zero-config, fully offline; hosts `pending_sync_queue` and `ocr_feedback_cache` |
| Merkle tree / SHA-256 DAG | Tamper-proof append-only ledger | Hash chaining prevents retroactive edits to logs or officer overrides |
| Salted hashes / Bloom filter | Decentralized watchlist matching | Match without storing intelligence in cleartext |

### Front-end (officer cockpit)

| Technology | Role | Why selected |
| :--- | :--- | :--- |
| React + Vite | Officer dashboard | Fast dev, modular state |
| Tailwind CSS | Styling | Dark high-contrast theme for 24/7 night operations |
| HTML5 Canvas / SVG | OCR and forensic overlays | Module 1 boxes every detected text region with confidence; Module 2 overlays MRZ and recognized text; supports editable VIZ/MRZ region selection |

### Networking & edge hardware

| Technology | Role | Why selected |
| :--- | :--- | :--- |
| Tailscale / WireGuard | Encrypted P2P mesh | Opportunistic store-and-forward sync when patrol units enter range |
| Raspberry Pi 4 / 5 (ARM64) | Lower-bound edge device | 5-15 W, runs on 12 V solar packs, ~₹8,000-₹12,000 per unit |
| Any Python 3.10+ host | Deployment model | Pi, mini-PC, rugged laptop, or x86 workstation |

---

## 9. Future Improvements

- **OCR preprocessing baseline:** every OCR pass begins with grayscale conversion, thresholding/binarization, noise removal, deskewing, and upscaling to at least 300 DPI equivalent. Future work can add perspective correction, super-resolution, script selection, and crop-based re-OCR for weak regions.
- **Document templates:** template matching and field-zone maps for common documents; generic layout only when the template is unknown.
- **Controlled vocabularies:** country, administrative-area, and place-name databases to *rank*, not blindly replace, candidates.
- **MRZ / barcode support:** use machine-readable zones and barcodes as independent evidence, then cross-check visual OCR.
- **Constrained decoding everywhere:** grammar or JSON-schema decoding instead of prompt-only JSON enforcement.
- **Active learning:** collect reviewer corrections, classify failure modes, add targeted rules, templates, and tests.
- **Privacy and security:** process identity documents locally, encrypt retained samples, restrict access, minimize retention, and never log raw PII unnecessarily.

---

## 10. Guardrails & First Build Recommendation

### Guardrails

This pipeline is **assisted extraction, not identity verification**. It must surface uncertainty, retain evidence, and require human review where a field influences access, compliance, or other high-impact decisions. A plausible-looking JSON record is not proof that the OCR was correct. **Learning feedback is never generated from an unvalidated prediction: only an officer-validated final value, including an officer-edited value, may update the feedback cache.**

### First build recommendation

Start with **one document family and five to eight fields**. Build in this order:

1. Mandatory pre-OCR preprocessing + VIZ/MRZ region selection
2. Deterministic labelled extraction + schema validation
3. MRZ checksums (cheapest, highest-signal win)
4. Bounding-box-aware layout and line clustering + OCR confidence overlays
5. VIZ vs MRZ cross-matching using independent crops
6. The small LLM, *only* as a three-pass constrained fallback, once you can measure its contribution against a labelled test set
7. Officer validation/edit workflow and validation-gated active-learning cache

That ordering keeps the prototype explainable, testable, and far more reliable than asking a 0.5B model to "fix OCR soup" end to end.

---

## Related Notes

- [[Document-Forensics-and-Tampering-Detection]]
- [[Vision-Language-Models-VLM-Architecture]]
- [[Offline-First-Store-and-Forward]]
- [[Explainable-AI-and-Incident-Dossier]]
- [[Blockchain-Audit-Trail-and-Watchlist-Sync]]
- [[PS26188_Problem_Analysis]]