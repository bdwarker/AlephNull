# Bounded AI Candidate Disambiguation & Active Feedback Loop

**Tags:** #ai #ocr #active-learning #disambiguation #edge #sih2026 #module1
**Status:** Architecture Specification
**Linked Concepts:** [[ocr-pipeline-prototype]], [[Edge-Inference-LlamaCPP]], [[Explainable-AI-and-Incident-Dossier]]

---

## 1. The Dilemma: Brittle Heuristics vs. Hallucinatory LLMs

In identity document processing, character recognition errors are pervasive (e.g. `SH44N` instead of `SHAAN`, or `TS3081¢` instead of `TS30810`).

Engineers typically face two problematic extremes:
1. **The Brittle Rule Trap:** Handcrafting thousands of hardcoded string replacements (`if '4' in name: replace '4' with 'a'`). This fails when non-standard spellings or legitimate numbers occur.
2. **The Hallucinatory LLM Trap:** Dumping raw OCR text into an LLM and asking it to "clean the name". A free-form LLM may change `MOHAMMAD` to `MUHAMMED`, silently altering a citizen's legal identity.

---

## 2. The Solution: Bounded Candidate Disambiguation

Instead of allowing the AI to generate arbitrary text, the pipeline splits extraction into two discrete stages:

```text
[ Raw OCR Token: "SH44N" ]
            │
            ▼
[ Deterministic Candidate Generator ]
- Generates bounded hypotheses via OCR confusion matrix:
  Candidate 0: "SH44N" (Raw as-is)
  Candidate 1: "SHAAN" (4 ↔ A leetspeak repair)
            │
            ▼
[ Constrained Local AI (llama.cpp / Qwen2.5) ]
- Multiple-choice selection under GBNF grammar constraint
- Decides between Candidate 0 and Candidate 1 based on language & layout context
            │
            ▼
[ Dual-State Record ]
- raw_token: "SH44N"
- selected_value: "SHAAN"
- confidence: 0.94
```

### Grammar-Constrained Decoding (GBNF in `llama.cpp`):
By compiling the candidate list into a dynamic context-free grammar (GBNF), the language model's logit sampler is physically restricted at decoding time:
```gbnf
root ::= "{\"selected_candidate\": \"" ( "SH44N" | "SHAAN" ) "\", \"confidence\": " [0-9] "." [0-9]+ "}"
```
This mathematically eliminates hallucination—the model cannot emit any spelling that was not in the candidate pool.

---

## 3. Dual-State Audit Schema (Legal Evidentiary Compliance)

Under Ministry of Home Affairs and police evidence acts, altering a traveler's legal identity without retaining the raw artifact renders digital evidence inadmissible in court.

Every field is stored as a **Dual-State Object**:
```json
{
  "field": "surname",
  "raw_text": "SH44N",
  "candidate_pool": ["SH44N", "SHAAN"],
  "resolved_value": "SHAAN",
  "disambiguation_source": "local_ai_gbnf",
  "confidence": 0.94,
  "source_bbox": [250, 280, 85, 24],
  "officer_override": null,
  "verified": false
}
```

Both values are displayed side-by-side in the border officer cockpit UI.

---

## 4. Active Learning Feedback Memory Cache

Border outposts encounter thousands of documents of the same national template. If a specific typewriter font or printing defect repeatedly renders `A` as `4`, invoking AI inference on every single traveler is wasteful and slow.

### Local SQLite Feedback Cache Schema:
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

### Execution Lifecycle:
1. **Cache Interception ($\mathcal{O}(1)$ Lookup):**
   When `SH44N` is encountered, check `ocr_feedback_cache`.
   If a verified match exists with high confidence, resolve instantly without waking up the local LLM.
2. **Officer Human-in-the-Loop Verification:**
   When an officer approves or corrects an extraction in the UI, an asynchronous update increments `hit_count` and updates `selected_candidate`.
3. **Few-Shot Prompt Priming:**
   When an ambiguous candidate cannot be resolved by the cache, the top-3 most recent officer-verified corrections for that document type are prepended to the prompt as few-shot demonstrations.

---

## 5. Security & Watchlist Query Strategy

When checking traveler records against national blacklists / terror watchlists:
* **Parallel Querying:** The system automatically queries the salted hash set for **both** the raw string (`SH44N`) and the AI-resolved string (`SHAAN`).
* **Anti-Evasion:** If a fugitive intentionally submits an ID with leetspeak or altered numbers to bypass exact-string database matches, parallel querying flags the identity immediately.

---

## Related Notes
* [[ocr-pipeline-prototype]]
* [[Edge-Inference-LlamaCPP]]
* [[Explainable-AI-and-Incident-Dossier]]
* [[Blockchain-Audit-Trail-and-Watchlist-Sync]]
