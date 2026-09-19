# OCR-to-Structured-Data Pipeline: Prototype Specification

## Goal

Build a reliable prototype that turns noisy OCR from identity and government documents into a small, validated JSON record. The system should extract only supported fields, retain evidence and confidence, and avoid silently inventing personal data.

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

This is deliberately a **hybrid** system: deterministic code handles repeatable rules, while an LLM handles only the ambiguous interpretation that rules cannot safely resolve.

## The problem: raw OCR soup plus a 0.5B LLM

It is tempting to send the entire OCR result to a small instruction model and ask for JSON. This fails often, even with a prompt explaining common character confusions.

For a simple labelled input such as:

```text
N4ME Moh4mmed Sh44n DOB 14-02-2005 Addr Hyderabad
```

a model must simultaneously identify corrupt labels, separate labels from values, repair characters, infer name spelling, and emit exact JSON. A 0.5B model may include `N4ME` as part of the name, leave `Sh44n` uncorrected, or vary its answer between runs.

The supplied document OCR is much harder:

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

The text contains headers, noise, split name components, an uncertain identifier, multiple places, and dates with different meanings. Reading order alone does not reliably say which text belongs to which field. A small model is being asked to do OCR repair, document understanding, reasoning, and strict serialization in one step; that is too much responsibility for an unreliable component.

## Recommended architecture

```text
Document image/PDF
        |
        v
OCR engine (text + confidence + bounding boxes)
        |
        v
Layout and field detection
  - document type / template
  - labels, zones, lines, key-value proximity
        |
        v
Deterministic normalization
  - clean whitespace, dates, labels, safe OCR substitutions
        |
        v
LLM fuzzy interpretation (only unresolved candidates)
  - choose among evidence-backed alternatives
  - never invent values
        |
        v
Schema validation + evidence/confidence checks
        |
        v
Structured JSON / review queue
```

### Component responsibilities

| Stage                       | Responsibility                                             | Must not do                              |
| --------------------------- | ---------------------------------------------------------- | ---------------------------------------- |
| OCR                         | Produce words, line order, confidence, and coordinates     | Decide final field semantics             |
| Layout/field detection      | Associate text with a document region or label             | Guess a person’s spelling                |
| Deterministic normalization | Apply predictable, field-specific transformations          | Make broad global substitutions          |
| LLM                         | Resolve remaining ambiguity from a small set of candidates | Be the sole extractor or source of truth |
| Validation                  | Enforce schema, formats, and cross-field constraints       | “Fix” unsupported values silently        |

## Why bounding boxes and coordinates matter

OCR output should retain at least `text`, `confidence`, and `x/y/width/height` for every word or line. Coordinates turn an unstructured text stream into document layout.

```json
[
  {"text": "SURNAME", "bbox": [80, 280, 130, 24], "confidence": 0.91},
  {"text": "SHAAN", "bbox": [250, 280, 85, 24], "confidence": 0.96},
  {"text": "GIVEN", "bbox": [80, 320, 100, 24], "confidence": 0.94},
  {"text": "MOHAMMAD", "bbox": [250, 320, 140, 24], "confidence": 0.97}
]
```

With these boxes, the system can infer that `SHAAN` is the value to the right of `SURNAME`, and `MOHAMMAD` is the value to the right of `GIVEN`, even when OCR reading order is strange. It can also identify headers at the top, machine-readable zones at the bottom, table rows, and text belonging to nearby labels. Preserve the original crop or page reference too, so uncertain extractions can be reviewed.

Useful spatial rules for a prototype:

- Prefer text on the same horizontal line and immediately to the right of a label.
- For forms, define zones as percentages of page width/height rather than fixed pixels.
- Merge adjacent words only when their baseline and gap indicate one value.
- Exclude likely headers, footers, seals, and OCR fragments outside the target field zone.
- Record source word IDs for every final value.

## Field-aware OCR correction rules & Bounded Candidate Generation

Do not apply a single character map globally. `0` might mean `O` in a name, but it is normally a zero in an identifier or date. Corrections must depend on the expected field, remain strictly bounded, and preserve dual-state auditability.

| Field              | Candidate Generation Strategy                                                                              | Candidate Examples                                                       | Disambiguation Method                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ |
| Labels             | Aggressively normalize structural variants (`N4ME`, `ADDR`, `D0B`)                                         | `N4ME` → `["NAME"]`                                                      | Deterministic lookup / regex                           |
| Names              | Generate plausible candidate hypotheses for leetspeak/OCR noise (`4↔A`, `0↔O`, `5↔S`, `rn↔m`, `vv↔w`)    | `Moh4mmed Sh44n` → `["Moh4mmed Sh44n", "Mohammed Shaan"]`                | Bounded Local AI choice (constrained decoding)        |
| Dates              | Normalize separators; recognize date patterns; verify actual calendar date                                 | `14-02-2005` → `["2005-02-14"]`                                          | Deterministic calendar validation (never treat `0↔O`) |
| ID/document number | Preserve alphanumeric ambiguity as explicit alternatives; check check-digits                               | `TS3081¢` → `["TS3081", "TS3081C"]`                                      | Template pattern + MRZ/Check digit validation          |
| Nationality        | Match against controlled vocabulary (ISO 3166-1 alpha-3)                                                  | `INDIAN` → `["IND", "Indian"]`                                           | Controlled dictionary lookup                           |
| Places/address     | Normalize punctuation, whitespace; extract administrative region candidates                                | `SORAKHPUR ,UTTAR PRADESH` → `["Gorakhpur, Uttar Pradesh", "Sorakhpur"]`| Geographic Gazetteer + Bounded AI ranking              |

### Dual-State Audit Storage:
To maintain legal admissibility in border security and police proceedings, **never overwrite raw OCR evidence with AI inferences**. Every extracted field is stored in a dual-state schema:
* `raw_text`: Exact characters returned by the OCR engine (e.g. `"SH44N"`).
* `candidate_pool`: List of generated hypotheses (e.g. `["SH44N", "SHAAN"]`).
* `resolved_value`: The candidate selected by AI or confirmed by officer (e.g. `"SHAAN"`).
* `confidence`: Model or rule confidence score.
* `source_boxes`: Pixel coordinates from the original document scan.
* `officer_override`: Boolean flag indicating if human intervention confirmed or altered the decision.

## Worked examples using the supplied OCR

### 1. Name fragments

The OCR contains `SHAAN` and `MOHAMMAD`, but raw text alone does not prove their order or whether they represent surname/given names. With nearby labels and coordinates, a field detector may produce:

```json
{
  "surname": {"raw_text": "SHAAN", "value": "Shaan", "confidence": 0.96},
  "given_names": {"raw_text": "MOHAMMAD", "value": "Mohammad", "confidence": 0.97},
  "name": {"value": "Mohammad Shaan", "confidence": 0.92}
}
```

Without labels/coordinates, keep these as candidates rather than confidently emitting a full name. The LLM can be asked: “Given these evidence-backed candidates, choose an ordering only if document conventions support it.”

### 2. Dates

The values `01/11/2019` and `31/10/2024` match date formats but do not identify their roles. A validator can confirm both are real dates, but it cannot decide whether they are issue/expiry, travel dates, or unrelated dates. Use adjacent labels or template zones; otherwise return two unclassified date candidates.

```json
{
  "date_candidates": [
    {"raw": "01/11/2019", "iso": "2019-11-01", "role": null},
    {"raw": "31/10/2024", "iso": "2024-10-31", "role": null}
  ]
}
```

### 3. Place strings

`HYDERABAD` is a strong place candidate, while `SORAKHPUR ,UTTAR PRADESH` may be a mangled locality/region. The pipeline should classify them as location candidates and use their spatial context to assign a role such as `place_of_birth` or `address`; it should not treat one as the address merely because it appears later in OCR text.

### 4. Identifier

`TS3081¢` should be retained as raw evidence. A deterministic cleaner might remove an obvious terminal artifact only if the document template says the number has six characters. Otherwise, preserve uncertainty, for example `TS3081?`, and flag it for review.

## LLM / VLM role: Bounded Candidate Disambiguation & Active Feedback

The model receives structured candidates—**never a raw OCR text dump**—and acts as a constrained multi-choice resolver when deterministic rules cannot choose safely.

### Bounded Disambiguation Prompt Schema:
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

* **Constrained Decoding (Grammar-guided):** When served via `llama.cpp`, employ GBNF (Grammar-Based Context-Free Grammar) or JSON Schema mode so the model physically cannot emit tokens outside `candidate_hypotheses`.
* **Zero Temperature:** Set temperature to `0.0` for deterministic, reproducible inference.

---

## Active Learning & Feedback Memory Cache

To avoid invoking model inference for repeating OCR artifacts across batches of documents:
1. **Officer Verification Event:** When an officer approves an extraction (e.g. confirms `"SH44N"` → `"SHAAN"`), the system writes a tuple into a local SQLite table:
   ```sql
   INSERT INTO ocr_feedback_cache (raw_token, field_type, selected_candidate, verified, officer_id)
   VALUES ('SH44N', 'name', 'SHAAN', 1, 'OFF-8821');
   ```
2. **$\mathcal{O}(1)$ Cache Interception:** Before invoking `llama.cpp` for candidate disambiguation, the pipeline queries `ocr_feedback_cache`. If a high-confidence, officer-verified match exists for that raw token and field type, the resolved candidate is returned instantly with 0ms LLM overhead.
3. **Few-Shot Exemplar Injection:** If an unseen variant arises, top verified examples from the local cache are dynamically injected as few-shot prompt examples for the local model.

## Validation rules

- Require every output key; use `""` or `null` for unknown values according to one consistent schema.
- Normalize accepted dates to ISO `YYYY-MM-DD`; reject invalid calendar dates.
- Enforce document-number patterns only after document type/template detection.
- Reject a field value if it contains a known label (for example, `N4ME Moh4mmed Sh44n`).
- Reject unsupported additions: the final value must map to a raw OCR token, a deterministic transformation, or an explicitly recorded candidate decision.
- Attach confidence and route low-confidence/contradictory fields to human review.
- Keep raw OCR, coordinates, and transformations separately from the final normalized record.

## Prototype implementation phases

### Phase 1 — Minimal labelled-text baseline

1. Accept OCR plain text and extract known labels with tolerant regular expressions (`NAME`, `N4ME`, `DOB`, `ADDR`).
2. Capture values between labels.
3. Add field-specific normalizers for dates, whitespace, and label removal.
4. Produce strict JSON validated with a schema library such as Pydantic or JSON Schema.
5. Add a small test corpus containing expected JSON and failure cases.

Success criterion: labelled synthetic examples consistently produce valid JSON without the label leaking into values.

### Phase 2 — Coordinates and document layout

1. Switch OCR integration to retain word/line boxes and confidence.
2. Group words into lines; detect nearby labels and value regions.
3. Add simple page zones and template definitions for one document type.
4. Save source-box references with every field.

Success criterion: split fields such as surname/given name are extracted correctly when the same content appears in confusing reading order.

### Phase 3 — Controlled LLM fallback

1. Pass only unresolved, structured candidate sets to the LLM.
2. Use constrained JSON output where available; validate every response.
3. Measure whether the fallback improves field accuracy over deterministic-only extraction.
4. Route uncertain answers to a review queue rather than accepting them automatically.

Success criterion: the LLM resolves a documented class of ambiguous cases while never reducing validation coverage.

### Phase 4 — Evaluation and review tooling

1. Build a labelled evaluation set with representative scans, not just clean text.
2. Track field-level precision, recall, invalid-output rate, and human-review rate.
3. Add a reviewer screen showing final value, raw value, page crop, rules applied, and confidence.
4. Log recurring OCR errors to improve rules/templates.

## Suggested prototype data model

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

The public-facing simplified JSON can be derived only after this richer, auditable record is validated.

## Future improvements

- **Better OCR and preprocessing:** deskewing, denoising, perspective correction, super-resolution, language/script selection, and crop-based re-OCR for weak regions.
- **Document templates:** template matching and field-zone maps for common document types; use generic layout only when the template is unknown.
- **Controlled vocabularies:** country/nationality, administrative-area, and place-name databases to rank—not blindly replace—candidates.
- **MRZ/barcode support:** when available and authorized, use machine-readable zones or barcodes as independent evidence, then cross-check visual OCR.
- **Constrained decoding:** use a model/runtime capable of JSON-schema or grammar-constrained output rather than prompt-only JSON enforcement.
- **Active learning:** collect reviewer corrections, classify failure modes, and add targeted rules/templates/tests.
- **Privacy and security:** process identity documents locally where possible, encrypt retained samples, restrict access, minimize retention, and never log raw PII unnecessarily.

## Prototype guardrails

This pipeline should be positioned as assisted extraction, not identity verification. It must surface uncertainty, retain evidence, and require human review where a field influences access, compliance, finance, or other high-impact decisions. A plausible-looking JSON record is not proof that the OCR was correct.

## First build recommendation

Start with one document family and five to eight fields. Build deterministic labelled extraction and schema validation first, then add bounding-box-aware layout detection. Introduce the small LLM only as a constrained fallback after you can measure its contribution against a labelled test set. That ordering keeps the prototype explainable, testable, and much more reliable than asking a 0.5B model to “fix OCR soup” end-to-end.
