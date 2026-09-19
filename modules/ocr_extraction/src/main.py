"""
AlephNull — Module 1: Document OCR Extraction Engine
=====================================================
High-precision Visual Inspection Zone (VIZ) and MRZ extraction using EasyOCR,
heuristic line clustering with vertical overlap IOU, deterministic candidate formatting,
and field key-value extraction.
"""

import os
import sys
import re
import cv2
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Safe UTF-8 console output for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import easyocr

# Import MRZ Parser if available
try:
    from modules.doc_validation.src.mrz_parser import parse_mrz
except ImportError:
    try:
        from ...doc_validation.src.mrz_parser import parse_mrz
    except Exception:
        parse_mrz = None

# Global caches to avoid re-initializing models on every request
_EASYOCR_READER_CACHE: Dict[str, easyocr.Reader] = {}
_LLM_CACHE: Optional[Any] = None
_LLM_CHECKED: bool = False


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [OCR] {msg}", flush=True)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "modules" / "models"


def get_local_llm():
    """
    Auto-detects and loads any GGUF model (e.g. Qwen2.5-1.5B/3B) from modules/models/.
    Cached in memory to prevent reload overhead.
    """
    global _LLM_CACHE, _LLM_CHECKED
    if _LLM_CHECKED:
        return _LLM_CACHE

    _LLM_CHECKED = True
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    gguf_files = list(MODELS_DIR.glob("*.gguf"))

    if not gguf_files:
        _log(f"Local LLM: No .gguf model found in {MODELS_DIR}. Running in deterministic heuristic mode.")
        _LLM_CACHE = None
        return None

    model_file = gguf_files[0]
    _log(f"Local LLM: Found '{model_file.name}' in modules/models/. Initializing llama-cpp-python...")
    start_t = time.time()
    try:
        # pyrefly: ignore [missing-import]
        from llama_cpp import Llama
        _LLM_CACHE = Llama(
            model_path=str(model_file),
            n_ctx=1024,
            n_threads=max(1, (os.cpu_count() or 4) - 1),
            verbose=False
        )
        load_time = time.time() - start_t
        _log(f"Local LLM ('{model_file.name}') loaded successfully in {load_time:.2f}s!")
    except Exception as e:
        _log(f"Warning: Could not initialize llama-cpp model ({model_file.name}): {e}")
        _LLM_CACHE = None

    return _LLM_CACHE


class DocumentOCR:
    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initializes EasyOCR Reader with model caching and connects to local Qwen LLM if available.
        Default to ['en'] for standard ICAO Doc 9303 documents (passports, IDs, DLs)
        to guarantee high speed and eliminate language script incompatibility issues.
        """
        if languages is None:
            # English is default; cached locally in ~/.EasyOCR/model
            languages = ['en']

        self.languages = languages
        lang_key = "_".join(sorted(languages))

        _log(f"Initializing DocumentOCR engine (requested languages: {languages})")

        global _EASYOCR_READER_CACHE
        if lang_key in _EASYOCR_READER_CACHE:
            _log(f"Reusing cached EasyOCR Reader for: {languages}")
            self.reader = _EASYOCR_READER_CACHE[lang_key]
        else:
            _log(f"Loading EasyOCR models into memory (gpu=True if available)...")
            start_t = time.time()
            try:
                # Try GPU first; easyocr automatically falls back to CPU if CUDA unavailable
                self.reader = easyocr.Reader(self.languages, gpu=True)
            except Exception as e:
                _log(f"Warning: GPU init encountered: {e}. Retrying with gpu=False...")
                self.reader = easyocr.Reader(self.languages, gpu=False)

            load_time = time.time() - start_t
            _EASYOCR_READER_CACHE[lang_key] = self.reader
            _log(f"EasyOCR Reader initialized successfully in {load_time:.2f}s.")

        # Initialize local Qwen LLM if downloaded
        self.llm = get_local_llm()

    def cluster_words_into_lines(self, words: List[Dict], vertical_iou_threshold: float = 0.45) -> List[List[Dict]]:
        """
        Groups OCR word bounding boxes into coherent text lines using dynamic vertical overlap.
        """
        if not words:
            return []

        # Sort words top-to-bottom, then left-to-right
        sorted_words = sorted(words, key=lambda w: (min(p[1] for p in w['box']), min(p[0] for p in w['box'])))
        lines: List[List[Dict]] = []

        for word in sorted_words:
            w_box = word['box']
            w_top = min(p[1] for p in w_box)
            w_bot = max(p[1] for p in w_box)
            w_height = max(1, w_bot - w_top)

            matched_line = None
            for line in lines:
                line_top = min(min(p[1] for p in item['box']) for item in line)
                line_bot = max(max(p[1] for p in item['box']) for item in line)
                line_height = max(1, line_bot - line_top)

                intersection = max(0, min(w_bot, line_bot) - max(w_top, line_top))
                min_height = min(w_height, line_height)
                overlap_ratio = intersection / min_height if min_height > 0 else 0

                if overlap_ratio >= vertical_iou_threshold:
                    matched_line = line
                    break

            if matched_line is not None:
                matched_line.append(word)
            else:
                lines.append([word])

        # Sort words within each line left-to-right
        for line in lines:
            line.sort(key=lambda w: min(p[0] for p in w['box']))

        return lines

    def _generate_candidates(self, text: str) -> List[str]:
        """
        Deterministic candidate generator for common OCR errors (e.g., 4<->A, 0<->O, 1<->I).
        """
        candidates = [text]
        replacements = {'4': 'A', '0': 'O', '1': 'I', '8': 'B', '5': 'S'}
        for k, v in replacements.items():
            if k in text:
                candidates.append(text.replace(k, v))
            if v in text:
                candidates.append(text.replace(v, k))
        return list(set(candidates))

    def disambiguate_with_llm(self, field: str, candidates: List[str], context: str = "") -> str:
        """
        Uses local Qwen LLM via llama.cpp for bounded candidate disambiguation.
        If LLM is not loaded or candidates list has only one item, returns candidates[0].
        """
        if not candidates:
            return ""
        if len(candidates) == 1 or not getattr(self, "llm", None):
            return candidates[0]

        _log(f"Running Qwen bounded disambiguation for field '{field}' across candidates: {candidates}")
        prompt = (
            f"<|im_start|>system\n"
            f"You are a strict border document OCR verification assistant. "
            f"Choose the single most realistic and standard value for the field '{field}' "
            f"from the candidate list based on the document context. "
            f"Output ONLY the exact selected candidate text without explanation.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Candidates: {candidates}\n"
            f"Context: {context}\n"
            f"Selected Candidate:<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        try:
            output = self.llm(
                prompt,
                max_tokens=24,
                stop=["<|im_end|>", "\n"],
                temperature=0.1
            )
            raw_choice = output["choices"][0]["text"].strip()
            for c in candidates:
                if c.lower() == raw_choice.lower():
                    _log(f"Qwen disambiguated '{field}': '{c}'")
                    return c
        except Exception as e:
            _log(f"Warning during Qwen LLM disambiguation: {e}")

        return candidates[0]

    def _detect_mrz_lines(self, lines: List[List[Dict]]) -> List[str]:
        """
        Detects Machine Readable Zone lines (lines with frequent '<' symbols, P<, I<, etc.)
        """
        candidate_mrz = []
        for line in lines:
            line_str = "".join([w['text'] for w in line]).replace(" ", "").upper()
            clean_mrz = re.sub(r'[^A-Z0-9<]', '', line_str)
            # MRZ lines typically have multiple '<' chars or start with P< / I< / V<
            if clean_mrz.count('<') >= 2 or clean_mrz.startswith(('P<', 'I<', 'V<', 'A<', 'C<')):
                if len(clean_mrz) >= 28:  # Minimum valid MRZ line length
                    candidate_mrz.append(clean_mrz)

        # Return bottom-most candidate lines (MRZ is located at the bottom)
        return candidate_mrz[-2:] if len(candidate_mrz) >= 2 else candidate_mrz

    def _extract_fields(self, lines: List[List[Dict]], doc_type: str = "passport") -> Dict[str, Any]:
        """
        Heuristic extraction of key identity document fields from clustered lines.
        Supports Passports, National ID / Aadhaar cards, and Driving Licenses.
        """
        fields: Dict[str, Any] = {}
        all_lines_text = [" ".join([w['text'] for w in line]).strip() for line in lines]

        for idx, line_text in enumerate(all_lines_text):
            upper = line_text.upper()

            # 1. Aadhaar 12-digit number (e.g., "5820 1682 3077")
            aadhaar_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', line_text)
            if aadhaar_match:
                fields["Document Number"] = aadhaar_match.group(1)

            # 2. Gender / Sex detection
            if re.search(r'\b(MALE|FEMALE)\b', upper):
                g_val = "Male" if "MALE" in upper else "Female"
                fields["Gender"] = g_val

            # 3. Date of Birth (DOB)
            if "DOB" in upper or "BIRTH" in upper:
                # Check for standard date formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
                date_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b', upper)
                if date_match:
                    fields["Date of Birth"] = date_match.group(1)
                else:
                    # Fallback for OCR merged digits (e.g. 14022007)
                    digits = re.sub(r'\D', '', upper)
                    if len(digits) >= 8:
                        d_str = digits[-8:]
                        formatted_d = f"{d_str[:2]}/{d_str[2:4]}/{d_str[4:]}"
                        fields["Date of Birth"] = formatted_d

                # Look behind for Name: On Indian IDs (Aadhaar), the line directly before DOB is the holder's Name
                if idx > 0 and "Full Name" not in fields:
                    prev_line = all_lines_text[idx - 1].strip()
                    if re.match(r'^[A-Za-z\s\.\'-]{3,40}$', prev_line):
                        if not any(k in prev_line.upper() for k in ["GOV", "INDIA", "AUTHORITY", "AADHAAR", "ENROL", "HELP"]):
                            fields["Full Name"] = prev_line

            # 4. Standard Name / Surname labels (Passports, Driving Licenses)
            if any(k in upper for k in ["NAME", "SURNAME", "GIVEN NAME", "FULL NAME", "HOLDER"]):
                if idx + 1 < len(all_lines_text) and "Full Name" not in fields:
                    val = all_lines_text[idx + 1].strip()
                    if val and not any(k in val.upper() for k in ["DATE", "SEX", "PASSPORT", "NATIONAL", "GOVT"]):
                        cands = self._generate_candidates(val)
                        val = self.disambiguate_with_llm("name", cands, context=upper)
                        fields["Full Name"] = val

            # 5. Passport Number / Document Number labels
            if any(k in upper for k in ["PASSPORT NO", "PASSPORT NUMBER", "DOC NO", "DOCUMENT NO", "DL NO", "LICENSE NO"]):
                match = re.search(r'[A-Z0-9]{7,15}', upper)
                if match:
                    raw_val = match.group(0)
                    cands = self._generate_candidates(raw_val)
                    val = self.disambiguate_with_llm("document_number", cands, context=upper)
                    fields["Document Number"] = val
                elif idx + 1 < len(all_lines_text):
                    next_val = all_lines_text[idx + 1].strip()
                    match_next = re.search(r'[A-Z0-9]{7,15}', next_val.upper())
                    if match_next:
                        raw_val = match_next.group(0)
                        cands = self._generate_candidates(raw_val)
                        val = self.disambiguate_with_llm("document_number", cands, context=next_val)
                        fields["Document Number"] = val

            # 6. Expiry Date
            if any(k in upper for k in ["EXPIRY", "EXPIRATION", "VALID UNTIL", "VALID TILL"]):
                date_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b', upper)
                if date_match:
                    fields["Date of Expiry"] = date_match.group(1)
                elif idx + 1 < len(all_lines_text):
                    next_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b', all_lines_text[idx + 1].upper())
                    if next_match:
                        fields["Date of Expiry"] = next_match.group(1)

            # 7. Nationality
            if any(k in upper for k in ["NATIONALITY", "CITIZENSHIP"]):
                nat_match = re.search(r'\b([A-Z]{3})\b', upper)
                if nat_match:
                    fields["Nationality"] = nat_match.group(1)

        return fields

    def process_document(self, image_path: str, doc_type: str = "passport", strictness: int = 90) -> Dict[str, Any]:
        """
        Reads document, performs VIZ OCR, clusters lines, extracts fields, and validates MRZ.
        """
        start_time = time.time()
        _log("=" * 60)
        _log(f"STARTING OCR EXTRACTION")
        _log(f"Document Image: {image_path}")
        _log(f"Document Type : {doc_type} | Strictness: {strictness}")

        if not os.path.exists(image_path):
            _log(f"ERROR: Image file not found at {image_path}")
            return {"status": "error", "error": f"Image file not found: {image_path}"}

        # 1. Read Image or PDF
        if str(image_path).lower().endswith(".pdf"):
            _log(f"PDF document detected: {image_path}. Rendering page 1 via pypdfium2...")
            pdf = None
            try:
                import pypdfium2 as pdfium
                import numpy as np
                pdf = pdfium.PdfDocument(image_path)
                if len(pdf) == 0:
                    return {"status": "error", "error": "PDF has 0 pages"}
                pil_img = pdf[0].render(scale=3.0).to_pil()
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception as pdf_err:
                _log(f"ERROR rendering PDF in process_document: {pdf_err}")
                return {"status": "error", "error": f"Failed to render PDF: {pdf_err}"}
            finally:
                if pdf is not None:
                    try:
                        pdf.close()
                    except Exception:
                        pass
        else:
            img = cv2.imread(image_path)

        if img is None:
            _log("ERROR: Could not decode document image with OpenCV")
            return {"status": "error", "error": "Failed to read document image"}

        img_h, img_w = img.shape[:2]
        _log(f"Image loaded: {img_w}x{img_h}px, channels: {img.shape[2] if len(img.shape) > 2 else 1}")

        # 2. Run EasyOCR
        _log("Executing EasyOCR readtext()...")
        ocr_start = time.time()
        try:
            raw_results = self.reader.readtext(img)
            ocr_dur = time.time() - ocr_start
            _log(f"EasyOCR readtext() completed in {ocr_dur:.2f}s — detected {len(raw_results)} bounding boxes")
        except Exception as e:
            _log(f"ERROR running EasyOCR: {e}")
            return {"status": "error", "error": f"EasyOCR execution error: {str(e)}"}

        # 3. Format Word Detections and Bounding Boxes
        words = []
        text_boxes = []
        for bbox, text, prob in raw_results:
            clean_text = text.strip()
            if not clean_text:
                continue

            pts = [[int(p[0]), int(p[1])] for p in bbox]
            bx = min(p[0] for p in pts)
            by = min(p[1] for p in pts)
            bw = max(p[0] for p in pts) - bx
            bh = max(p[1] for p in pts) - by

            words.append({
                "box": pts,
                "text": clean_text,
                "confidence": round(float(prob), 4)
            })
            text_boxes.append({
                "x": int(bx),
                "y": int(by),
                "w": int(bw),
                "h": int(bh),
                "text": clean_text,
                "confidence": round(float(prob), 4)
            })

        _log(f"Filtered to {len(words)} valid non-empty text regions")

        # 4. Cluster Words into Lines
        lines = self.cluster_words_into_lines(words)
        _log(f"Clustered words into {len(lines)} coherent horizontal text lines")
        for i, line in enumerate(lines[:8]):  # Log first 8 lines
            line_str = " ".join([w['text'] for w in line])
            _log(f"  Line {i+1:02d}: \"{line_str}\"")
        if len(lines) > 8:
            _log(f"  ... ({len(lines) - 8} more lines)")

        # 5. Extract Fields from VIZ
        extracted_fields = self._extract_fields(lines, doc_type=doc_type)
        _log(f"Extracted fields from VIZ: {list(extracted_fields.keys())}")
        for k, v in extracted_fields.items():
            if not k.startswith("_"):
                _log(f"  > {k}: {v}")

        # 6. Check and Parse MRZ
        mrz_parsed = None
        mrz_lines = self._detect_mrz_lines(lines)
        if mrz_lines and parse_mrz:
            _log(f"Found potential MRZ lines ({len(mrz_lines)} lines):")
            for ml in mrz_lines:
                _log(f"  MRZ RAW: {ml}")
            try:
                # Format to 44 characters for TD3 if needed
                padded_lines = []
                for ml in mrz_lines:
                    if len(ml) < 44:
                        ml = ml.ljust(44, '<')
                    elif len(ml) > 44:
                        ml = ml[:44]
                    padded_lines.append(ml)

                mrz_parsed = parse_mrz(padded_lines)
                mrz_parsed["mrz_lines"] = padded_lines
                _log(f"MRZ Checksum Validation verdict: valid={mrz_parsed.get('is_valid')}")

                # Populate extracted fields with MRZ data (even if check-digits flagged a warning)
                if mrz_parsed.get("surname") or mrz_parsed.get("given_names"):
                    mrz_name = f"{mrz_parsed.get('given_names', '')} {mrz_parsed.get('surname', '')}".strip()
                    if mrz_name and not extracted_fields.get("Full Name"):
                        extracted_fields["Full Name"] = mrz_name

                if mrz_parsed.get("document_number") and not extracted_fields.get("Document Number"):
                    extracted_fields["Document Number"] = mrz_parsed["document_number"]

                if mrz_parsed.get("dob") and not extracted_fields.get("Date of Birth"):
                    raw_dob = str(mrz_parsed["dob"])
                    if len(raw_dob) == 6 and raw_dob.isdigit():
                        yy = int(raw_dob[:2])
                        century = "19" if yy > 30 else "20"
                        fmt_dob = f"{century}{raw_dob[:2]}-{raw_dob[2:4]}-{raw_dob[4:6]}"
                    else:
                        fmt_dob = raw_dob
                    extracted_fields["Date of Birth"] = fmt_dob

                if mrz_parsed.get("expiry") and not extracted_fields.get("Date of Expiry"):
                    raw_exp = str(mrz_parsed["expiry"])
                    if len(raw_exp) == 6 and raw_exp.isdigit():
                        yy = int(raw_exp[:2])
                        century = "20"
                        fmt_exp = f"{century}{raw_exp[:2]}-{raw_exp[2:4]}-{raw_exp[4:6]}"
                    else:
                        fmt_exp = raw_exp
                    extracted_fields["Date of Expiry"] = fmt_exp

                if mrz_parsed.get("nationality") and not extracted_fields.get("Nationality"):
                    extracted_fields["Nationality"] = mrz_parsed["nationality"]

            except Exception as mrz_err:
                _log(f"Warning parsing MRZ: {mrz_err}")

        # 7. Local Qwen LLM Fallback if key fields are still missing
        if getattr(self, "llm", None) and (not extracted_fields.get("Full Name") or not extracted_fields.get("Document Number")):
            _log("Key fields missing. Running local Qwen LLM for document field extraction...")
            try:
                line_texts = [" ".join([w['text'] for w in l]) for l in lines]
                llm_prompt = (
                    f"<|im_start|>system\n"
                    f"You are a document OCR field extractor. From these OCR lines, extract JSON with keys: "
                    f"'name', 'document_number', 'dob', 'expiry', 'nationality'. "
                    f"Return ONLY valid JSON with string values.<|im_end|>\n"
                    f"<|im_start|>user\n"
                    f"Document Lines:\n" + "\n".join(line_texts) + "\n<|im_end|>\n"
                    f"<|im_start|>assistant\n"
                )
                output = self.llm(llm_prompt, max_tokens=150, temperature=0.1)
                txt = output["choices"][0]["text"].strip()
                if "{" in txt and "}" in txt:
                    json_str = txt[txt.find("{"):txt.rfind("}")+1]
                    parsed_llm = json.loads(json_str)
                    key_map = {
                        "name": "Full Name",
                        "full_name": "Full Name",
                        "full name": "Full Name",
                        "document_number": "Document Number",
                        "document number": "Document Number",
                        "passport_number": "Document Number",
                        "passport number": "Document Number",
                        "dob": "Date of Birth",
                        "date_of_birth": "Date of Birth",
                        "date of birth": "Date of Birth",
                        "expiry": "Date of Expiry",
                        "date_of_expiry": "Date of Expiry",
                        "date of expiry": "Date of Expiry",
                        "nationality": "Nationality",
                        "gender": "Gender"
                    }
                    for k, v in parsed_llm.items():
                        canon_k = key_map.get(k.lower().strip(), k.title())
                        if v and isinstance(v, str) and not extracted_fields.get(canon_k):
                            clean_v = v.strip()
                            if len(clean_v) > 1 and not any(bad in clean_v.upper() for bad in ["UNKNOWN", "NULL", "NONE"]):
                                extracted_fields[canon_k] = clean_v
            except Exception as llm_err:
                _log(f"Warning in LLM fallback extraction: {llm_err}")

        # Construct raw_text and multi-pass OCR breakdown
        raw_lines = [" ".join([w['text'] for w in l]).strip() for l in lines]
        raw_text = "\n".join(raw_lines) if raw_lines else "\n".join([w['text'] for w in words])

        ocr_passes = {
            "psm11_sparse": "\n".join([w['text'] for w in words]),
            "psm6_block": raw_text
        }
        if mrz_lines:
            ocr_passes["specialized_pass"] = "\n".join(mrz_lines)

        # 8. Check for Aadhaar QR Code
        aadhaar_qr_parsed = None
        if doc_type in ["aadhaar", "id_card", "national_id"]:
            try:
                from modules.doc_validation.src.aadhaar_qr import decode_aadhaar_qr_from_file
                qr_res = decode_aadhaar_qr_from_file(image_path)
                if qr_res and qr_res.get("status") == "success":
                    _log(f"Detected and decoded Aadhaar QR code in image: {qr_res.get('qr_type')}")
                    aadhaar_qr_parsed = qr_res
                    if not extracted_fields.get("Full Name") and qr_res.get("name"):
                        extracted_fields["Full Name"] = qr_res["name"]
                    if not extracted_fields.get("Document Number") and qr_res.get("last_4_digits"):
                        extracted_fields["Document Number"] = f"XXXX XXXX {qr_res['last_4_digits']}"
                    if not extracted_fields.get("Date of Birth") and qr_res.get("dob"):
                        extracted_fields["Date of Birth"] = qr_res["dob"]
                    if not extracted_fields.get("Gender") and qr_res.get("gender"):
                        extracted_fields["Gender"] = qr_res["gender"]
            except Exception as qr_err:
                _log(f"Aadhaar QR scanner note: {qr_err}")

        # Construct full response compatible with UI overlays and downstream Module 2
        total_time = time.time() - start_time
        _log(f"OCR EXTRACTION FINISHED in {total_time:.2f}s ({len(words)} words, {len(raw_text)} chars)")
        _log("=" * 60)

        return {
            "status": "success",
            "document_type": doc_type,
            "extracted_fields": extracted_fields,
            "mrz_parsed": mrz_parsed,
            "aadhaar_qr_parsed": aadhaar_qr_parsed,
            "raw_text": raw_text,
            "ocr_passes": ocr_passes,
            "raw_ocr": words,
            "lines_clustered": len(lines),
            "regions_identified": {
                "image_dimensions": {"width": img_w, "height": img_h},
                "text_boxes": text_boxes,
                "master_crop": {"x": 0, "y": 0, "w": img_w, "h": img_h}
            },
            "processing_time_ms": round(total_time * 1000, 1)
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AlephNull Module 1: Document OCR")
    parser.add_argument("image", help="Path to document image file")
    parser.add_argument("--type", "-t", default="passport", choices=["passport", "id_card", "driving_license", "aadhaar"], help="Document type")
    parser.add_argument("--strictness", "-s", type=int, default=90, help="OCR strictness (0-100)")
    args = parser.parse_args()

    ocr = DocumentOCR()
    res = ocr.process_document(args.image, doc_type=args.type, strictness=args.strictness)
    print(json.dumps(res, indent=2))
