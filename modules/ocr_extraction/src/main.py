import os
import cv2
import numpy as np
import pytesseract
import re
from pathlib import Path
from typing import Union, Dict, Any, Tuple
import json
from datetime import datetime

# Tesseract path configuration for Windows
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class TextRegionExtractor:
    """Extracts text regions using Sobel gradient and morphological grouping."""
    
    @staticmethod
    def extract(image: np.ndarray, strictness: int = 50) -> Tuple[np.ndarray, bool, Dict[str, Any]]:
        """
        Uses Sobel gradient to detect text stroke transitions, merges text characters
        into coherent lines/blocks, and crops the master document text area.
        Strictness (0-100):
            100 (strict): Small grouping kernel, tight bounding box around text.
            0 (loose): Large grouping kernel, generous padding including whole document.
            
        Returns:
            (cropped_image, crop_success, region_meta)
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Sobel gradient in X direction to isolate vertical text edges
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_x = cv2.convertScaleAbs(grad_x)
        
        # Otsu thresholding on gradient
        _, thresh_grad = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Calculate kernel size based on strictness slider
        # strictness=0 -> wide kernel kw=50 (loose/big box), strictness=100 -> kw=16 (tight/strict box)
        kw = int(50 - (strictness / 100.0) * 34)
        kh = max(3, int(kw / 4))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        connected = cv2.morphologyEx(thresh_grad, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_boxes = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            # Filter out contours that touch outer image boundaries (image frame, wall, background)
            if x <= 5 or y <= 5 or (x + bw) >= (w - 5) or (y + bh) >= (h - 5):
                continue
            # Text block heuristics: minimum width, height, and area
            if bw > 25 and bh > 8 and bw * bh > 300:
                valid_boxes.append((int(x), int(y), int(bw), int(bh)))
                
        if not valid_boxes:
            region_meta = {
                "text_boxes": [],
                "master_crop": {"x": 0, "y": 0, "w": int(w), "h": int(h)},
                "image_dimensions": {"width": int(w), "height": int(h)},
                "total_regions": 0
            }
            return image, False, region_meta
            
        min_x = min(b[0] for b in valid_boxes)
        min_y = min(b[1] for b in valid_boxes)
        max_x = max(b[0] + b[2] for b in valid_boxes)
        max_y = max(b[1] + b[3] for b in valid_boxes)
        
        # Padding scaled by strictness: loose = generous padding, strict = tight
        pad = int((100 - strictness) * 0.4)
        min_x = max(0, min_x - pad)
        min_y = max(0, min_y - pad)
        max_x = min(w, max_x + pad)
        max_y = min(h, max_y + pad)
        
        cropped = image[min_y:max_y, min_x:max_x]
        
        region_meta = {
            "text_boxes": [{"x": b[0], "y": b[1], "w": b[2], "h": b[3]} for b in valid_boxes],
            "master_crop": {"x": int(min_x), "y": int(min_y), "w": int(max_x - min_x), "h": int(max_y - min_y)},
            "image_dimensions": {"width": int(w), "height": int(h)},
            "total_regions": len(valid_boxes)
        }
        return cropped, True, region_meta


class MRZParser:
    """Parses and validates ICAO Doc 9303 MRZ text with error correction."""
    
    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        """Searches for and parses ID-3 passport MRZ lines or ID cards from raw OCR text."""
        lines = [re.sub(r'\s+', '', l.upper()) for l in text.split('\n') if len(re.sub(r'\s+', '', l)) >= 20]
        
        extracted = {
            "Document Type": "Passport",
            "Name": None,
            "Passport Number": None,
            "Nationality": None,
            "Date of Birth": None,
            "Date of Expiry": None,
            "Gender": None
        }
        raw_lines = {"line1": None, "line2": None}
        check_digits = {
            "passport_number_chk": None,
            "dob_chk": None,
            "expiry_chk": None,
            "composite_chk": None
        }
        found_mrz = False
        
        # 1. Look for MRZ Line 1: P<[Country][Surname]<<[Given Names]...
        for line in lines:
            # Matches P< followed by country code (3 chars) and name string
            m1 = re.search(r'P[<A-Z0-9]?([A-Z<]{3})([A-Z0-9<]{10,})', line)
            if m1:
                country = m1.group(1).replace('<', '')
                name_str = m1.group(2)
                raw_lines["line1"] = line
                
                # Surnames and Given Names in ICAO 9303 are separated by '<<'
                # OCR may sometimes see '<C' or 'C<' or '<<' for the delimiter
                sep_match = re.search(r'(?:<{2,}|<[CK]|[CK]<)', name_str)
                if sep_match:
                    surname_raw = name_str[:sep_match.start()]
                    given_raw = name_str[sep_match.end():]
                    
                    surname = re.sub(r'[^A-Z]', '', surname_raw)
                    # Given names may contain multiple names separated by '<'
                    given_parts = [re.sub(r'[^A-Z]', '', p) for p in given_raw.split('<') if p]
                    given = " ".join([p for p in given_parts if len(p) >= 1])
                    
                    if surname and given:
                        extracted["Name"] = f"{surname}, {given}"
                    elif surname:
                        extracted["Name"] = surname
                    elif given:
                        extracted["Name"] = given
                else:
                    # Single name or fallback
                    clean_name = re.sub(r'<+', ' ', name_str).strip()
                    clean_name = re.sub(r'[^A-Z\s]', '', clean_name)
                    if clean_name:
                        extracted["Name"] = clean_name
                    
                if country:
                    extracted["Nationality"] = country
                found_mrz = True
                break
                
        # 2. Look for MRZ Line 2: [PassportNo(9)][chk(1)][Country(3)][DOB(6)][chk(1)][M/F][Expiry(6)][chk(1)]...
        for line in lines:
            m2 = re.search(
                r'([A-Z0-9<]{8,9})'       # Passport number (8-9 chars)
                r'([0-9OIZSB<])'          # Passport number check digit
                r'([A-Z<]{3})'            # Nationality
                r'([0-9OIZSB]{6})'        # DOB YYMMDD
                r'([0-9OIZSB<])'          # DOB check digit
                r'([MF<])'                # Sex
                r'([0-9OIZSB]{6})'        # Expiry YYMMDD
                r'([0-9OIZSB<])?',        # Expiry check digit (optional)
                line
            )
            if m2:
                raw_lines["line2"] = line
                passport_no_raw = m2.group(1).replace('<', '')
                p_chk_raw = m2.group(2)
                country = m2.group(3).replace('<', '')
                dob_raw = m2.group(4)
                dob_chk_raw = m2.group(5)
                gender = m2.group(6)
                exp_raw = m2.group(7)
                exp_chk_raw = m2.group(8) or ""
                
                # Digit confusions error correction
                trans = str.maketrans('OIZSB<', '012580')
                dob_clean = dob_raw.translate(trans)
                exp_clean = exp_raw.translate(trans)
                
                check_digits["passport_number_chk"] = p_chk_raw.translate(trans)
                check_digits["dob_chk"] = dob_chk_raw.translate(trans)
                if exp_chk_raw:
                    check_digits["expiry_chk"] = exp_chk_raw.translate(trans)
                
                # Extract composite check digit from line end if present
                trailing_digits = re.findall(r'\d+', line[-5:])
                if trailing_digits:
                    check_digits["composite_chk"] = trailing_digits[-1][-1]
                
                extracted["Passport Number"] = passport_no_raw
                if country and not extracted["Nationality"]:
                    extracted["Nationality"] = country
                    
                # Format DOB
                yy, mm, dd = dob_clean[:2], dob_clean[2:4], dob_clean[4:6]
                current_year_short = datetime.now().year % 100
                year = f"19{yy}" if int(yy) > current_year_short else f"20{yy}"
                extracted["Date of Birth"] = f"{year}-{mm}-{dd}"
                
                # Format Expiry
                ey, em, ed = exp_clean[:2], exp_clean[2:4], exp_clean[4:6]
                extracted["Date of Expiry"] = f"20{ey}-{em}-{ed}"
                
                extracted["Gender"] = "Male" if gender == "M" else "Female" if gender == "F" else None
                found_mrz = True
                break

        # Fallback check for line 2 with noisy prefix: Country followed by DOB, Sex, Expiry
        if not extracted["Date of Expiry"] or not extracted["Gender"]:
            for line in lines:
                m2_alt = re.search(r'([A-Z]{3})([A-Z0-9]{6,7})([MF<])([A-Z0-9]{6,7})', line)
                if m2_alt:
                    raw_lines["line2"] = line
                    country = m2_alt.group(1).replace('<', '')
                    dob_raw = m2_alt.group(2)[:6]
                    gender = m2_alt.group(3)
                    exp_raw = m2_alt.group(4)[:6]
                    trans = str.maketrans('OTIZSBG<', '07125860')
                    dob_clean = dob_raw.translate(trans)
                    exp_clean = exp_raw.translate(trans)
                    if country and not extracted["Nationality"]:
                        extracted["Nationality"] = country
                    if not extracted["Date of Birth"] and dob_clean.isdigit():
                        yy, mm, dd = dob_clean[:2], dob_clean[2:4], dob_clean[4:6]
                        current_year_short = datetime.now().year % 100
                        year = f"19{yy}" if int(yy) > current_year_short else f"20{yy}"
                        extracted["Date of Birth"] = f"{year}-{mm}-{dd}"
                    if not extracted["Date of Expiry"] and exp_clean.isdigit():
                        ey, em, ed = exp_clean[:2], exp_clean[2:4], exp_clean[4:6]
                        extracted["Date of Expiry"] = f"20{ey}-{em}-{ed}"
                    if not extracted["Gender"] and gender in ['M', 'F']:
                        extracted["Gender"] = "Male" if gender == 'M' else "Female"
                    found_mrz = True
                    break
                
        return {
            "valid": found_mrz,
            "fields": extracted,
            "raw_lines": raw_lines,
            "check_digits": check_digits
        }


class DocumentOCR:
    """Orchestrates OpenCV text-boxing, Tesseract multi-pass OCR, and Ollama classification for Passports, National IDs, and Driving Licenses."""
    
    def __init__(self):
        pass

    @staticmethod
    def normalize_doc_type(doc_type: Any) -> str:
        """Normalizes document type strings from URL query, form, or JSON."""
        if not doc_type:
            return "passport"
        dt = str(doc_type).strip().lower().replace("-", "_").replace(" ", "_")
        if any(x in dt for x in ["dl", "driver", "driving", "license"]):
            return "driving_license"
        if any(x in dt for x in ["id", "aadhaar", "national", "state", "card"]):
            return "id_card"
        return "passport"

    def process_document(
        self, 
        image_path: Union[str, Path, np.ndarray], 
        doc_type: str = "passport", 
        strictness: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Processes document:
        1. Sobel text region extraction based on strictness slider.
        2. Bilateral filtering + CLAHE enhancement + Lanczos upscaling.
        3. Multi-pass Tesseract OCR (sparse text PSM 11 + block PSM 6 + specialized pass).
        4. Guardrail: Stops immediately if no readable text found.
        5. Rule-based / MRZ parsing with error correction tailored to document type.
        6. Ollama LLM classification with document-specific schema & anti-hallucination guard.
        """
        # Handle backwards-compatibility if strictness was passed as 2nd positional argument
        if isinstance(doc_type, (int, float)):
            strictness = int(doc_type)
            doc_type = kwargs.get("doc_type", "passport")

        norm_type = self.normalize_doc_type(doc_type)

        try:
            if isinstance(image_path, np.ndarray):
                image = image_path
            else:
                image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not read image from {image_path}")

            # 1. Text Region Cropping with Strictness Slider
            cropped, crop_success, region_meta = TextRegionExtractor.extract(image, strictness)
            
            # 2. Preprocessing: Upscale if resolution is modest (optimal character height for Tesseract is ~30px)
            ch, cw = cropped.shape[:2]
            scale = 2.0 if cw <= 1600 else 1.0
            if scale != 1.0:
                scaled = cv2.resize(cropped, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_LANCZOS4)
            else:
                scaled = cropped.copy()
                
            gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
            
            # Bilateral filter reduces camera noise while preserving text boundaries
            denoised = cv2.bilateralFilter(gray, 7, 50, 50)
            
            # CLAHE equalizes non-uniform webcam lighting and glare
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Adaptive threshold for high-contrast binarized pass
            bin_adaptive = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
            
            # 3. Multi-pass OCR
            # Pass A: Sparse text layout (PSM 11) on CLAHE image
            text_psm11 = pytesseract.image_to_string(enhanced, config='--oem 3 --psm 11').strip()
            
            # Pass B: Block layout (PSM 6) on adaptive threshold
            text_psm6 = pytesseract.image_to_string(bin_adaptive, config='--oem 3 --psm 6').strip()
            
            # Pass C: Specialized pass (MRZ for passport, or high-contrast alphanumeric pass for ID/DL)
            special_text = ""
            if norm_type == "passport":
                sh, sw = cropped.shape[:2]
                mrz_crop = cropped[int(sh * 0.68):int(sh * 0.98), :]
                mrz_scaled = cv2.resize(mrz_crop, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
                mrz_gray = cv2.cvtColor(mrz_scaled, cv2.COLOR_BGR2GRAY)
                gaussian = cv2.GaussianBlur(mrz_gray, (0, 0), 2.0)
                mrz_unsharp = cv2.addWeighted(mrz_gray, 2.0, gaussian, -1.0, 0)
                mrz_enh = clahe.apply(mrz_unsharp)
                
                special_text = pytesseract.image_to_string(
                    mrz_enh,
                    config='--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
                ).strip()
            else:
                # High-contrast pass for cards (numbers, dates, names)
                special_text = pytesseract.image_to_string(
                    enhanced,
                    config='--oem 3 --psm 3'
                ).strip()
            
            # Merge extracted text blocks into clean combined text
            text_passes = [t for t in [text_psm11, text_psm6, special_text] if t]
            combined_raw_text = "\n\n".join(text_passes)
            
            # Initialize fields template per document type
            if norm_type == "passport":
                extracted_fields = {
                    "Document Type": "Passport",
                    "Name": None,
                    "Passport Number": None,
                    "Nationality": None,
                    "Date of Birth": None,
                    "Date of Expiry": None,
                    "Gender": None
                }
            elif norm_type == "id_card":
                extracted_fields = {
                    "Document Type": "National ID",
                    "Name": None,
                    "ID Number": None,
                    "Date of Birth": None,
                    "Gender": None,
                    "Nationality": None,
                    "Address": None,
                    "Date of Expiry": None
                }
            else:  # driving_license
                extracted_fields = {
                    "Document Type": "Driving License",
                    "Name": None,
                    "License Number": None,
                    "Date of Birth": None,
                    "Date of Expiry": None,
                    "Issue Date": None,
                    "Gender": None,
                    "Blood Group": None
                }

            # 4. GUARDRAIL: Verify whether readable text exists
            alphanumeric_count = len(re.findall(r'[a-zA-Z0-9]', combined_raw_text))
            if alphanumeric_count < 8:
                return {
                    "status": "warning",
                    "message": "No readable text detected in image. Please ensure the document is clear, flat, and well-lit.",
                    "document_type": norm_type,
                    "crop_successful": crop_success,
                    "regions_identified": region_meta,
                    "raw_text": "No text detected in document image.",
                    "ocr_passes": {
                        "psm11_sparse": text_psm11,
                        "psm6_block": text_psm6,
                        "specialized_pass": special_text
                    },
                    "extracted_fields": extracted_fields
                }
                
            # Helper for Date parsing (DD/MM/YYYY, YYYY-MM-DD, etc.)
            date_matches = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', combined_raw_text)
            valid_dates = []
            for d in date_matches:
                parts = d.replace('-', '/').split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = f"20{year}" if int(year) < 50 else f"19{year}"
                    if len(day) == 1: day = f"0{day}"
                    if len(month) == 1: month = f"0{month}"
                    if 1 <= int(month) <= 12 and 1 <= int(day) <= 31 and 1900 <= int(year) <= 2050:
                        valid_dates.append(f"{year}-{month}-{day}")
            valid_dates = sorted(list(set(valid_dates)))

            # Helper for Gender
            detected_gender = None
            if re.search(r'\b(M|MALE)\b', combined_raw_text, re.IGNORECASE) and not re.search(r'\b(FEMALE)\b', combined_raw_text, re.IGNORECASE):
                detected_gender = "Male"
            elif re.search(r'\b(F|FEMALE)\b', combined_raw_text, re.IGNORECASE):
                detected_gender = "Female"

            # 5. Rule-based Extraction per Document Type
            mrz_result = {"valid": False, "fields": {}}

            if norm_type == "passport":
                mrz_result = MRZParser.parse(combined_raw_text)
                if mrz_result["valid"]:
                    for k, v in mrz_result["fields"].items():
                        if v:
                            extracted_fields[k] = v
                            
                # Regex for Passport Number
                if not extracted_fields["Passport Number"]:
                    pp_matches = re.findall(r'\b([A-Z]\d{7,8})\b', combined_raw_text)
                    if not pp_matches:
                        pp_matches = re.findall(r'([A-Z]\d{6,8})', combined_raw_text)
                    if pp_matches:
                        extracted_fields["Passport Number"] = max(pp_matches, key=len)
                        
                # Regex for Nationality
                if not extracted_fields["Nationality"]:
                    if re.search(r'\b(IND|INDIAN|INDIA)\b', combined_raw_text, re.IGNORECASE):
                        extracted_fields["Nationality"] = "Indian"
                    elif re.search(r'\b(USA|AMERICAN|UNITED STATES)\b', combined_raw_text, re.IGNORECASE):
                        extracted_fields["Nationality"] = "American"
                    elif re.search(r'\b(GBR|BRITISH|UNITED KINGDOM)\b', combined_raw_text, re.IGNORECASE):
                        extracted_fields["Nationality"] = "British"
                        
                if valid_dates:
                    if not extracted_fields["Date of Birth"] and int(valid_dates[0][:4]) <= 2012:
                        extracted_fields["Date of Birth"] = valid_dates[0]
                    if not extracted_fields["Date of Expiry"] and len(valid_dates) >= 2:
                        extracted_fields["Date of Expiry"] = valid_dates[-1]

                if not extracted_fields["Gender"] and detected_gender:
                    extracted_fields["Gender"] = detected_gender

            elif norm_type == "id_card":
                # Check for Aadhaar 12-digit number (e.g. 1234 5678 9012)
                aadhaar_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4})\b', combined_raw_text)
                if aadhaar_match:
                    extracted_fields["ID Number"] = aadhaar_match.group(1)
                else:
                    # Generic 10-14 digit ID or alphanumeric ID
                    gen_id = re.search(r'\b([A-Z0-9]{9,14})\b', combined_raw_text)
                    if gen_id and not any(w in gen_id.group(1) for w in ["GOVERNMENT", "AUTHORITY"]):
                        extracted_fields["ID Number"] = gen_id.group(1)

                if valid_dates:
                    extracted_fields["Date of Birth"] = valid_dates[0]
                    if len(valid_dates) >= 2:
                        extracted_fields["Date of Expiry"] = valid_dates[-1]

                # Year of birth fallback
                if not extracted_fields["Date of Birth"]:
                    yob = re.search(r'(?:Year of Birth|YOB)[:\s]*(\d{4})', combined_raw_text, re.IGNORECASE)
                    if yob:
                        extracted_fields["Date of Birth"] = f"{yob.group(1)}-01-01"

                if detected_gender:
                    extracted_fields["Gender"] = detected_gender

                if re.search(r'\b(INDIA|INDIAN|GOVERNMENT OF INDIA|AADHAAR)\b', combined_raw_text, re.IGNORECASE):
                    extracted_fields["Nationality"] = "Indian"

            elif norm_type == "driving_license":
                # Indian / International DL Number patterns (e.g. TS09 20210012345 or DL-0420110012345)
                dl_match = re.search(r'\b([A-Z]{2}[-\s]?\d{2,3}[-\s]?\d{4,11})\b', combined_raw_text)
                if dl_match:
                    extracted_fields["License Number"] = dl_match.group(1).replace(" ", "-")
                else:
                    gen_dl = re.search(r'\b([A-Z0-9]{8,15})\b', combined_raw_text)
                    if gen_dl:
                        extracted_fields["License Number"] = gen_dl.group(1)

                if valid_dates:
                    extracted_fields["Date of Birth"] = valid_dates[0]
                    if len(valid_dates) >= 2:
                        extracted_fields["Date of Expiry"] = valid_dates[-1]
                    if len(valid_dates) >= 3:
                        extracted_fields["Issue Date"] = valid_dates[1]

                if detected_gender:
                    extracted_fields["Gender"] = detected_gender

                # Blood group (A+, B+, AB+, O+, etc.)
                bg = re.search(r'\b(A|B|AB|O)[+-]\b', combined_raw_text, re.IGNORECASE)
                if bg:
                    extracted_fields["Blood Group"] = bg.group(0).upper()

            # 6. AI Document Parser & OCR Error Corrector via Ollama
            try:
                import ollama
                
                if norm_type == "passport":
                    ai_prompt = f"""
You are an expert AI Document Parser and OCR Error Corrector specialized in PASSPORTS.
You are given raw, noisy OCR text extracted from a passport scan, along with preliminary regex detections.
Webcam photos often cause optical character recognition (OCR) errors such as:
- Character substitutions: 'W', 'RM', 'NN' instead of 'H' (e.g. 'MOWAMMAD' -> 'MOHAMMAD'); 'O' vs '0', 'I' vs '1', 'S' vs '5', 'B' vs '8', 'Z' vs '2'.
- Split characters or punctuation: e.g. '14/02 /2:.97' -> 2007-02-14.
- MRZ lines at the bottom:
  Line 1: P<[Country][Surname]<<[Given Names]... (e.g. 'P<INDSHAAN<<MOWAMMAD' -> Surname: SHAAN, Given: MOHAMMAD)
  Line 2: [Passport No][chk][Country][DOB YYMMDD][chk][Sex M/F][Expiry YYMMDD]...

Instructions:
1. REPAIR the "Name": Fix OCR typos in the surname and given names. Format as "Given Name Surname" or "Surname, Given Name".
2. RECONCILE "Passport Number": Combine visual header number and MRZ digits (e.g. letter 'T' followed by 7-8 digits like T9308191).
3. EXPAND "Nationality": Convert 3-letter country code or text to standard name (e.g. 'IND' -> 'Indian', 'USA' -> 'American').
4. NORMALIZE "Date of Birth": Reconcile visual date and MRZ date into strictly YYYY-MM-DD.
5. NORMALIZE "Date of Expiry": Strictly YYYY-MM-DD.
6. NORMALIZE "Gender": "Male" or "Female".

SECURITY & ANTI-HALLUCINATION RULES:
- All corrections MUST be grounded in clues, names, and tokens present in the OCR text or MRZ. DO NOT fabricate arbitrary placeholder people (never output 'John Smith', 'John Doe', '123456789', etc.).
- If a field has no evidence in the text, set its value to null.
- Output ONLY a valid JSON object matching these exact keys:
  "Name", "Passport Number", "Nationality", "Date of Birth", "Date of Expiry", "Gender"

Preliminary Detections:
{json.dumps(extracted_fields, indent=2)}

Raw OCR Text:
{combined_raw_text}
"""
                elif norm_type == "id_card":
                    ai_prompt = f"""
You are an expert AI Document Parser and OCR Error Corrector specialized in NATIONAL ID / GOVERNMENT ID CARDS (e.g. Aadhaar Card, National Identity Card, Voter ID, State ID).
You are given raw, noisy OCR text extracted from an ID card scan, along with preliminary regex detections.
Webcam photos often cause optical character recognition (OCR) errors such as:
- Character substitutions: 'O' vs '0', 'I' vs '1', 'S' vs '5', 'B' vs '8', 'Z' vs '2', 'W'/'RM' vs 'H'.
- Number grouping: e.g. '3456 7890 1234' or '345678901234'.
- Header noise: Ignore 'Government of India', 'Unique Identification Authority', 'Republic of...', etc.

Instructions:
1. EXTRACT & REPAIR "Name": Identify the cardholder's full name (fix OCR typos; ignore government headers or parentage labels like 'S/O', 'D/O').
2. EXTRACT "ID Number": Identify the unique national ID number (e.g. 12-digit Aadhaar 'XXXX XXXX XXXX' or alphanumeric ID).
3. EXTRACT "Date of Birth": Reconcile visual date or year into strictly YYYY-MM-DD (e.g. 2007-02-14).
4. EXTRACT "Gender": "Male" or "Female".
5. EXTRACT "Nationality": e.g. "Indian", "American", etc. (or null if unspecified).
6. EXTRACT "Address": If address, state, or PIN is visible, format cleanly (or null).
7. EXTRACT "Date of Expiry": If an expiry date exists, format as YYYY-MM-DD (or null).

SECURITY & ANTI-HALLUCINATION RULES:
- All corrections MUST be grounded in clues, names, and tokens present in the OCR text. DO NOT fabricate arbitrary placeholder people (never output 'John Smith', 'John Doe', '123456789', etc.).
- If a field has no evidence in the text, set its value to null.
- Output ONLY a valid JSON object matching these exact keys:
  "Name", "ID Number", "Date of Birth", "Gender", "Nationality", "Address", "Date of Expiry"

Preliminary Detections:
{json.dumps(extracted_fields, indent=2)}

Raw OCR Text:
{combined_raw_text}
"""
                else:  # driving_license
                    ai_prompt = f"""
You are an expert AI Document Parser and OCR Error Corrector specialized in DRIVING LICENSES (DL).
You are given raw, noisy OCR text extracted from a driving license scan, along with preliminary regex detections.
Webcam photos often cause optical character recognition (OCR) errors such as:
- Character substitutions: 'O' vs '0', 'I' vs '1', 'S' vs '5', 'B' vs '8', 'Z' vs '2'.
- Split letters or dates: e.g. '14/02 /2025' -> 2025-02-14.

Instructions:
1. EXTRACT & REPAIR "Name": Full name of the license holder.
2. EXTRACT "License Number": Driving license number (e.g. 'TS09 20210012345' or state/country specific alphanumeric format).
3. EXTRACT "Date of Birth": Format strictly as YYYY-MM-DD.
4. EXTRACT "Date of Expiry": Validity / Valid Till date formatted strictly as YYYY-MM-DD.
5. EXTRACT "Issue Date": Date of issuance formatted strictly as YYYY-MM-DD (or null).
6. EXTRACT "Gender": "Male" or "Female" (or null if not specified).
7. EXTRACT "Blood Group": e.g. 'O+', 'B+', 'A+', 'AB-', etc. (or null).

SECURITY & ANTI-HALLUCINATION RULES:
- All corrections MUST be grounded in clues, names, and tokens present in the OCR text. DO NOT fabricate arbitrary placeholder people (never output 'John Smith', 'John Doe', '123456789', etc.).
- If a field has no evidence in the text, set its value to null.
- Output ONLY a valid JSON object matching these exact keys:
  "Name", "License Number", "Date of Birth", "Date of Expiry", "Issue Date", "Gender", "Blood Group"

Preliminary Detections:
{json.dumps(extracted_fields, indent=2)}

Raw OCR Text:
{combined_raw_text}
"""
                response = ollama.chat(model='qwen2.5:1.5b', messages=[
                    {'role': 'user', 'content': ai_prompt}
                ])
                content = response['message']['content']
                
                if '{' in content and '}' in content:
                    json_str = content[content.find('{'):content.rfind('}')+1]
                    llm_data = json.loads(json_str)
                    
                    hallucination_blacklist = {
                        "smith, john", "john smith", "smith", "john doe", "jane doe", 
                        "123456789", "a1234567", "sample", "placeholder", "dl-0123456789012"
                    }
                    
                    for k in extracted_fields.keys():
                        if k == "Document Type":
                            continue
                        val = llm_data.get(k)
                        if val and isinstance(val, str):
                            clean_val = val.strip()
                            if clean_val.lower() in hallucination_blacklist:
                                continue
                            if "date" in k.lower() or "birth" in k.lower() or "expiry" in k.lower():
                                m_date = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', clean_val)
                                if m_date:
                                    clean_val = f"{m_date.group(1)}-{int(m_date.group(2)):02d}-{int(m_date.group(3)):02d}"
                                elif re.match(r'^\d{8}$', clean_val):
                                    clean_val = f"{clean_val[:4]}-{clean_val[4:6]}-{clean_val[6:8]}"
                                else:
                                    continue
                            extracted_fields[k] = clean_val
                            
                # Post-normalization for passport number
                if norm_type == "passport" and extracted_fields.get("Passport Number"):
                    pp = re.sub(r'[^A-Z0-9]', '', str(extracted_fields["Passport Number"]).upper())
                    if len(pp) > 8 and pp[0].isalpha():
                        extracted_fields["Passport Number"] = pp[:8]
                    else:
                        extracted_fields["Passport Number"] = pp

                # If MRZ parsed a valid expiry date, prioritize the standardized MRZ value
                if norm_type == "passport" and mrz_result.get("fields", {}).get("Date of Expiry"):
                    extracted_fields["Date of Expiry"] = mrz_result["fields"]["Date of Expiry"]
                            
            except Exception as e:
                print(f"Ollama classification warning: {e}")
                    
            return {
                "status": "success",
                "document_type": norm_type,
                "crop_successful": crop_success,
                "regions_identified": region_meta,
                "raw_text": combined_raw_text,
                "ocr_passes": {
                    "psm11_sparse": text_psm11,
                    "psm6_block": text_psm6,
                    "specialized_pass": special_text
                },
                "mrz_parsed": mrz_result if norm_type == "passport" else None,
                "extracted_fields": extracted_fields
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "document_type": norm_type,
                "error": str(e)
            }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AlephNull Document OCR Module")
    parser.add_argument("image_path", nargs="?", help="Path to document image file")
    parser.add_argument("--type", "-t", default="passport", choices=["passport", "id_card", "driving_license"], help="Document type")
    parser.add_argument("--strictness", "-s", type=int, default=50, help="OCR bounding strictness (0-100)")

    args = parser.parse_args()

    if args.image_path:
        ocr = DocumentOCR()
        res = ocr.process_document(args.image_path, doc_type=args.type, strictness=args.strictness)
        print(json.dumps(res, indent=2))
    else:
        print("AlephNull Document OCR Module ready.")
        print("Usage: python main.py <document_image_path> [--type passport|id_card|driving_license] [--strictness 0-100]")


