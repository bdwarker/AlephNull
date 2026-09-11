import os
import cv2
import numpy as np
import pytesseract
import re
from pathlib import Path
from typing import Union, Dict, Any, Tuple
import json

# Tesseract path configuration for Windows
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class TextRegionExtractor:
    """Extracts text regions using Sobel gradient and morphological grouping."""
    
    @staticmethod
    def extract(image: np.ndarray, strictness: int = 50) -> Tuple[np.ndarray, bool]:
        """
        Uses Sobel gradient to detect text stroke transitions, merges text characters
        into coherent lines/blocks, and crops the master document text area.
        Strictness (0-100):
            100 (strict): Small grouping kernel, tight bounding box around text.
            0 (loose): Large grouping kernel, generous padding including whole document.
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
                valid_boxes.append((x, y, bw, bh))
                
        if not valid_boxes:
            return image, False
            
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
        return cropped, True


class MRZParser:
    """Parses and validates ICAO Doc 9303 MRZ text with error correction."""
    
    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        """Searches for and parses ID-3 passport MRZ lines from raw OCR text."""
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
        found_mrz = False
        
        # 1. Look for MRZ Line 1: P<[Country][Surname]<<[Given Names]...
        for line in lines:
            m1 = re.search(r'P[<CKE]?([A-Z]{3})([A-Z0-9<]{8,})', line)
            if m1:
                country = m1.group(1)
                name_str = m1.group(2)
                parts = [re.sub(r'[^A-Z]', '', p) for p in re.split(r'[<CKS]{2,}', name_str)]
                parts = [p for p in parts if len(p) >= 2]
                if len(parts) >= 2:
                    extracted["Name"] = f"{parts[0]}, {parts[1]}"
                elif len(parts) == 1:
                    extracted["Name"] = parts[0]
                    
                if country in ["IND", "USA", "GBR", "CAN", "AUS", "FRA", "DEU"]:
                    extracted["Nationality"] = country
                found_mrz = True
                break
                
        # 2. Look for MRZ Line 2: [PassportNo]<[chk][Country][DOB(6)][chk][M/F][Expiry(6)]...
        for line in lines:
            m2 = re.search(r'([A-Z0-9]{8,9})[<CKE0-9]?(\d?)([A-Z]{3})(\d[0-9OIZSB]{5})[<CKE0-9]?(\d?)([MF<])(\d[0-9OIZSB]{5})', line)
            if m2:
                passport_no = m2.group(1)
                country = m2.group(3)
                dob_raw = m2.group(4)
                gender = m2.group(6)
                exp_raw = m2.group(7)
                
                # Digit confusions error correction
                trans = str.maketrans('OIZSB', '01258')
                dob_clean = dob_raw.translate(trans)
                exp_clean = exp_raw.translate(trans)
                
                extracted["Passport Number"] = passport_no
                if not extracted["Nationality"]:
                    extracted["Nationality"] = country
                    
                # Format DOB
                yy, mm, dd = dob_clean[:2], dob_clean[2:4], dob_clean[4:6]
                year = f"19{yy}" if int(yy) > 24 else f"20{yy}"
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
                    country = m2_alt.group(1)
                    dob_raw = m2_alt.group(2)[:6]
                    gender = m2_alt.group(3)
                    exp_raw = m2_alt.group(4)[:6]
                    trans = str.maketrans('OTIZSBG', '0712586')
                    dob_clean = dob_raw.translate(trans)
                    exp_clean = exp_raw.translate(trans)
                    if not extracted["Nationality"]:
                        extracted["Nationality"] = country
                    if not extracted["Date of Birth"] and dob_clean.isdigit():
                        yy, mm, dd = dob_clean[:2], dob_clean[2:4], dob_clean[4:6]
                        year = f"19{yy}" if int(yy) > 24 else f"20{yy}"
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
            "fields": extracted
        }


class DocumentOCR:
    """Orchestrates OpenCV text-boxing, Tesseract multi-pass OCR, and Ollama classification."""
    
    def __init__(self):
        pass

    def process_document(self, image_path: Union[str, Path], strictness: int = 50) -> Dict[str, Any]:
        """
        Processes document:
        1. Sobel text region extraction based on strictness slider.
        2. Bilateral filtering + CLAHE enhancement + Lanczos upscaling.
        3. Multi-pass Tesseract OCR (sparse text PSM 11 + block PSM 6 + dedicated MRZ pass).
        4. Guardrail: Stops immediately if no text found (prevents LLM hallucination).
        5. Rule-based / MRZ parsing with error correction.
        6. Ollama LLM classification for messy/missing fields with strict anti-hallucination guard.
        """
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not read image from {image_path}")

            # 1. Text Region Cropping with Strictness Slider
            cropped, crop_success = TextRegionExtractor.extract(image, strictness)
            
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
            
            # Pass C: Dedicated MRZ extraction on bottom 30% of cropped document
            sh, sw = cropped.shape[:2]
            mrz_crop = cropped[int(sh * 0.68):int(sh * 0.98), :]
            mrz_scaled = cv2.resize(mrz_crop, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
            mrz_gray = cv2.cvtColor(mrz_scaled, cv2.COLOR_BGR2GRAY)
            gaussian = cv2.GaussianBlur(mrz_gray, (0, 0), 2.0)
            mrz_unsharp = cv2.addWeighted(mrz_gray, 2.0, gaussian, -1.0, 0)
            mrz_enh = clahe.apply(mrz_unsharp)
            
            mrz_text = pytesseract.image_to_string(
                mrz_enh,
                config='--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
            ).strip()
            
            # Merge extracted text blocks into clean combined text
            text_passes = [t for t in [text_psm11, text_psm6, mrz_text] if t]
            combined_raw_text = "\n\n".join(text_passes)
            
            # 4. GUARDRAIL: Verify whether readable text exists!
            alphanumeric_count = len(re.findall(r'[a-zA-Z0-9]', combined_raw_text))
            if alphanumeric_count < 8:
                return {
                    "status": "warning",
                    "message": "No readable text detected in image. Please ensure the document is clear, flat, and well-lit.",
                    "crop_successful": crop_success,
                    "raw_text": "No text detected in document image.",
                    "extracted_fields": {
                        "Document Type": "Passport",
                        "Name": None,
                        "Passport Number": None,
                        "Nationality": None,
                        "Date of Birth": None,
                        "Date of Expiry": None,
                        "Gender": None
                    }
                }
                
            extracted_fields = {
                "Document Type": "Passport",
                "Name": None,
                "Passport Number": None,
                "Nationality": None,
                "Date of Birth": None,
                "Date of Expiry": None,
                "Gender": None
            }
            
            # 5. Rule-based & MRZ Extraction
            mrz_result = MRZParser.parse(combined_raw_text)
            if mrz_result["valid"]:
                for k, v in mrz_result["fields"].items():
                    if v:
                        extracted_fields[k] = v
                        
            # Regex for Passport Number (e.g. T9308191)
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
                    
            # Regex for Dates (DD/MM/YYYY)
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
            if valid_dates:
                if not extracted_fields["Date of Birth"]:
                    # Earliest date is likely DOB
                    if int(valid_dates[0][:4]) <= 2012:
                        extracted_fields["Date of Birth"] = valid_dates[0]
                if not extracted_fields["Date of Expiry"] and len(valid_dates) >= 2:
                    # Latest date is likely Expiry
                    extracted_fields["Date of Expiry"] = valid_dates[-1]
                    
            # Regex for Gender
            if not extracted_fields["Gender"]:
                if re.search(r'\b(M|MALE)\b', combined_raw_text, re.IGNORECASE) and not re.search(r'\b(FEMALE)\b', combined_raw_text, re.IGNORECASE):
                    extracted_fields["Gender"] = "Male"
                elif re.search(r'\b(F|FEMALE)\b', combined_raw_text, re.IGNORECASE):
                    extracted_fields["Gender"] = "Female"

            # 6. AI Document Parser & OCR Error Corrector
            try:
                import ollama
                ai_prompt = f"""
You are an expert AI Document Parser and OCR Error Corrector.
You are given raw, noisy OCR text extracted from a passport scan, along with preliminary regex detections.
Webcam photos often cause optical character recognition (OCR) errors such as:
- Character substitutions: 'W', 'RM', 'NN' instead of 'H' (e.g. 'MOWAMMAD' or 'ROHAMRMAD' -> 'MOHAMMAD'); 'O' vs '0', 'I' vs '1', 'S' vs '5', 'B' vs '8', 'Z' vs '2'.
- Split characters or punctuation: e.g. '14/02 /2:.97' -> 2007-02-14.
- MRZ lines at the bottom:
  Line 1: P<[Country][Surname]<<[Given Names]... (e.g. 'P<INDSHAAN<<MOWAMMAD' -> Surname: SHAAN, Given: MOHAMMAD)
  Line 2: [Passport No][chk][Country][DOB YYMMDD][chk][Sex M/F][Expiry YYMMDD]... (e.g. '070214' -> 2007-02-14)

Instructions:
1. REPAIR the "Name": Fix OCR typos in the surname and given names (e.g. 'MOWAMMAD' -> 'MOHAMMAD', 'SHAAN' -> 'SHAAN'). Format as "Given Name Surname" or "Surname, Given Name" (e.g. "Mohammad Shaan" or "Shaan, Mohammad").
2. RECONCILE "Passport Number": Combine visual header number and MRZ digits (e.g. letter 'T' followed by 7-8 digits like T9308191).
3. EXPAND "Nationality": Convert 3-letter country code or text to standard name (e.g. 'IND' -> 'Indian', 'USA' -> 'American').
4. NORMALIZE "Date of Birth": Reconcile visual date (e.g. 14/02/...) and MRZ date (e.g. 070214) into strictly YYYY-MM-DD (e.g. 2007-02-14).
5. NORMALIZE "Date of Expiry": Strictly YYYY-MM-DD (e.g. 2024-10-31).
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
                response = ollama.chat(model='qwen2.5:1.5b', messages=[
                    {'role': 'user', 'content': ai_prompt}
                ])
                content = response['message']['content']
                
                if '{' in content and '}' in content:
                    json_str = content[content.find('{'):content.rfind('}')+1]
                    llm_data = json.loads(json_str)
                    
                    hallucination_blacklist = {
                        "smith, john", "john smith", "smith", "john doe", "jane doe", 
                        "123456789", "a1234567", "sample", "placeholder"
                    }
                    
                    for k in ["Name", "Passport Number", "Nationality", "Date of Birth", "Date of Expiry", "Gender"]:
                        val = llm_data.get(k)
                        if val and isinstance(val, str):
                            clean_val = val.strip()
                            if clean_val.lower() in hallucination_blacklist:
                                continue
                            if "date" in k.lower():
                                m_date = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', clean_val)
                                if m_date:
                                    clean_val = f"{m_date.group(1)}-{int(m_date.group(2)):02d}-{int(m_date.group(3)):02d}"
                                elif re.match(r'^\d{8}$', clean_val):
                                    clean_val = f"{clean_val[:4]}-{clean_val[4:6]}-{clean_val[6:8]}"
                                else:
                                    continue
                            extracted_fields[k] = clean_val
                            
                # Post-normalization for passport number
                if extracted_fields.get("Passport Number"):
                    pp = re.sub(r'[^A-Z0-9]', '', str(extracted_fields["Passport Number"]).upper())
                    if len(pp) > 8 and pp[0].isalpha():
                        extracted_fields["Passport Number"] = pp[:8]
                    else:
                        extracted_fields["Passport Number"] = pp

                # If MRZ parsed a valid expiry date, prioritize the standardized MRZ value
                if mrz_result.get("fields", {}).get("Date of Expiry"):
                    extracted_fields["Date of Expiry"] = mrz_result["fields"]["Date of Expiry"]
                            
            except Exception as e:
                print(f"Ollama classification warning: {e}")
                    
            return {
                "status": "success",
                "crop_successful": crop_success,
                "raw_text": combined_raw_text,
                "mrz_parsed": mrz_result,
                "extracted_fields": extracted_fields
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e)
            }
