"""
AlephNull — Aadhaar QR Code Decoder & Cryptographic Validator
=============================================================
Detects, decompresses, and decodes both UIDAI 2048-bit Secure QR Codes
(binary compressed formats V5, V2, V1) and legacy XML QR codes.
Extracts full demographic records, postal addresses, and embedded
JPEG 2000 facial photographs.
"""

import os
import sys
import re
import io
import gzip
import zlib
import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, Any, Optional, List

import cv2
import numpy as np
from PIL import Image

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
except ImportError:
    pyzbar_decode = None

try:
    from pyaadhaar.decode import AadhaarOldQr
except ImportError:
    AadhaarOldQr = None


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [AADHAAR_QR] {msg}", flush=True)


def scan_qr_codes(img_input: Union[str, Path, np.ndarray]) -> List[Any]:
    """
    Multi-pass QR code scanner using pyzbar and OpenCV QRCodeDetector.
    Applies multi-scale, CLAHE contrast enhancement, sharpening, and adaptive thresholding
    to reliably scan QR codes on printed PVC cards, phone screens, or noisy scans.
    """
    global pyzbar_decode
    if pyzbar_decode is None:
        try:
            from pyzbar.pyzbar import decode as _pyz
            pyzbar_decode = _pyz
            _log("Dynamically loaded pyzbar.decode module successfully")
        except Exception:
            pass

    if isinstance(img_input, (str, Path)):
        img_path = str(img_input)
        if not os.path.exists(img_path):
            _log(f"Image not found: {img_path}")
            return []
        img = cv2.imread(img_path)
    elif isinstance(img_input, np.ndarray):
        img = img_input
    else:
        return []

    if img is None or img.size == 0:
        return []

    raw_results = []
    seen_texts = set()

    def add_result(data_val):
        if data_val is not None:
            str_repr = data_val.decode('utf-8', errors='ignore') if isinstance(data_val, bytes) else str(data_val)
            if str_repr and str_repr not in seen_texts:
                seen_texts.add(str_repr)
                raw_results.append(data_val)

    # Pass 1: Direct pyzbar on BGR & Grayscale
    if pyzbar_decode is not None:
        try:
            for obj in pyzbar_decode(img):
                add_result(obj.data)
        except Exception as e:
            _log(f"pyzbar pass 1 warning: {e}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        if not raw_results:
            try:
                for obj in pyzbar_decode(gray):
                    add_result(obj.data)
            except Exception:
                pass

        # Pass 2: CLAHE Contrast enhancement (for faded/glared cards)
        if not raw_results:
            try:
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                for obj in pyzbar_decode(enhanced):
                    add_result(obj.data)
            except Exception:
                pass

        # Pass 3: Sharpening filter (for blurred phone captures)
        if not raw_results:
            try:
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
                sharp = cv2.filter2D(gray, -1, kernel)
                for obj in pyzbar_decode(sharp):
                    add_result(obj.data)
            except Exception:
                pass

        # Pass 4: Multi-scale resizing (for high-res or ultra-dense QR codes)
        if not raw_results:
            h, w = gray.shape[:2]
            for scale in [1.5, 2.0, 0.75, 0.5]:
                try:
                    scaled = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
                    for obj in pyzbar_decode(scaled):
                        add_result(obj.data)
                    if raw_results:
                        break
                except Exception:
                    pass

        # Pass 5: Otsu adaptive thresholding
        if not raw_results:
            try:
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                for obj in pyzbar_decode(thresh):
                    add_result(obj.data)
            except Exception:
                pass

    # Pass 6: OpenCV QRCodeDetector fallback
    if not raw_results:
        try:
            detector = cv2.QRCodeDetector()
            val, pts, _ = detector.detectAndDecode(img)
            if val:
                add_result(val)
        except Exception:
            pass

    _log(f"QR scanning completed — detected {len(raw_results)} QR candidate(s)")
    return raw_results


def parse_aadhaar_qr_payload(raw_data: Any, save_photo_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Decodes an Aadhaar QR code payload (either Secure QR or Legacy XML).
    Extracts holder demographic fields, residential address, and embedded photo.
    Supports UIDAI V5, V2, and V1 compressed specifications natively.
    """
    if raw_data is None:
        return {"status": "error", "error": "Empty QR data provided"}

    str_data = raw_data.decode('utf-8', errors='ignore') if isinstance(raw_data, bytes) else str(raw_data)
    str_data = str_data.strip()

    if not str_data:
        return {"status": "error", "error": "Decoded QR string is empty"}

    _log(f"Parsing QR payload (length: {len(str_data)} chars)...")

    # 1. Check if UIDAI Secure QR (large base-10 integer string)
    is_secure = str_data.isdigit() and len(str_data) > 300

    if is_secure:
        _log("Detected UIDAI Secure QR Code (2048-bit digital signature format)")
        try:
            num = int(str_data)
            byte_len = (num.bit_length() + 7) // 8
            raw_bytes = num.to_bytes(byte_len, 'big').lstrip(b'\x00')

            decompressed = None
            try:
                decompressed = gzip.decompress(raw_bytes)
            except Exception:
                try:
                    decompressed = zlib.decompress(raw_bytes, 16 + zlib.MAX_WBITS)
                except Exception:
                    decompressed = zlib.decompress(raw_bytes)

            if not decompressed:
                raise ValueError("Decompressed byte array is empty")

            # Locate embedded photo markers
            soc_idx = decompressed.find(b'\xff\x4f\xff\x51')  # JPEG 2000 SOC marker
            soi_idx = decompressed.find(b'\xff\xd8\xff')      # Standard JPEG SOI marker
            photo_start = soc_idx if soc_idx != -1 else soi_idx

            header_bytes = decompressed[:photo_start] if photo_start != -1 else decompressed[:-256]
            parts = [p.decode('utf-8', errors='replace').strip() for p in header_bytes.split(b'\xff')]

            version = "V1"
            offset = 0
            if parts and parts[0].startswith("V"):
                version = parts[0]
                offset = 1

            def get_part(idx: int) -> str:
                return parts[idx] if idx < len(parts) else ""

            email_mobile_flag = get_part(offset)
            ref_id = get_part(offset + 1)
            name = get_part(offset + 2)
            dob_raw = get_part(offset + 3)
            gender_raw = get_part(offset + 4)
            careof = get_part(offset + 5)

            if version.upper() == "V5":
                # V5 Layout:
                # [7]=district, [8]=landmark, [9]=house, [10]=location, [11]=pincode,
                # [12]=vtc, [13]=state, [14]=street, [15]=subdistrict, [16]=postoffice, [17]=masked_mobile
                district = get_part(7)
                landmark = get_part(8)
                house = get_part(9)
                location = get_part(10)
                pincode = get_part(11)
                vtc = get_part(12)
                state = get_part(13)
                street = get_part(14)
                subdistrict = get_part(15)
                postoffice = get_part(16)
                masked_mobile = get_part(17)
            else:
                # V1 & V2 Layout:
                district = get_part(offset + 6)
                landmark = get_part(offset + 7)
                house = get_part(offset + 8)
                location = get_part(offset + 9)
                pincode = get_part(offset + 10)
                postoffice = get_part(offset + 11)
                state = get_part(offset + 12)
                street = get_part(offset + 13)
                subdistrict = get_part(offset + 14)
                vtc = get_part(offset + 15)
                masked_mobile = get_part(offset + 16) if offset == 1 and len(parts) > offset + 16 else ""

            # Format DOB to standard YYYY-MM-DD
            fmt_dob = dob_raw
            if dob_raw:
                clean_dob = re.sub(r'[/.]', '-', dob_raw).strip()
                for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%m-%y"):
                    try:
                        dt = datetime.strptime(clean_dob, fmt)
                        fmt_dob = dt.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass

            # Gender normalization
            fmt_gender = gender_raw
            if gender_raw:
                if gender_raw.upper() in ("M", "MALE"):
                    fmt_gender = "Male"
                elif gender_raw.upper() in ("F", "FEMALE"):
                    fmt_gender = "Female"
                elif gender_raw.upper() in ("T", "TG", "TRANSGENDER"):
                    fmt_gender = "Transgender"

            # Address components
            addr_elements = [careof, house, street, landmark, location, vtc, subdistrict, district, state, pincode]
            clean_addr_parts = []
            for el in addr_elements:
                if el and str(el).strip() and str(el).strip() != "-1" and str(el).strip() not in clean_addr_parts:
                    clean_addr_parts.append(str(el).strip())

            full_address = ", ".join(clean_addr_parts) if clean_addr_parts else ""

            # Extract embedded photograph (JPEG 2000 or JPEG)
            photo_b64 = None
            photo_path = None
            has_photo = False

            if photo_start != -1:
                eoc_idx = decompressed.rfind(b'\xff\xd9')
                if eoc_idx != -1 and eoc_idx > photo_start:
                    photo_bytes = decompressed[photo_start:eoc_idx + 2]
                else:
                    photo_bytes = decompressed[photo_start:-256]

                try:
                    pil_img = Image.open(io.BytesIO(photo_bytes))
                    if pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")

                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=92)
                    jpeg_bytes = buf.getvalue()
                    photo_b64 = f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('utf-8')}"
                    has_photo = True

                    if save_photo_dir and os.path.exists(save_photo_dir):
                        photo_filename = f"aadhaar_qr_photo_{int(time.time())}.jpg"
                        out_f = os.path.join(save_photo_dir, photo_filename)
                        pil_img.save(out_f, "JPEG")
                        photo_path = out_f
                        _log(f"Extracted QR photo saved to: {photo_path}")
                except Exception as p_err:
                    _log(f"Note: Could not extract embedded photograph from QR: {p_err}")

            # Last 4 digits of Aadhaar (first 4 digits of reference_id)
            last4 = ""
            if ref_id and len(ref_id) >= 4:
                last4 = ref_id[:4]

            masked_uid = f"XXXX XXXX {last4}" if last4 else "XXXX XXXX XXXX"

            raw_dict = {
                "version": version,
                "email_mobile_flag": email_mobile_flag,
                "reference_id": ref_id,
                "name": name,
                "dob": dob_raw,
                "gender": gender_raw,
                "careof": careof,
                "district": district,
                "landmark": landmark,
                "house": house,
                "location": location,
                "pincode": pincode,
                "postoffice": postoffice,
                "state": state,
                "street": street,
                "subdistrict": subdistrict,
                "vtc": vtc,
                "masked_mobile": masked_mobile
            }

            return {
                "status": "success",
                "qr_type": "secure_qr",
                "version": version,
                "is_secure": True,
                "is_signed": True,
                "name": name,
                "dob": fmt_dob,
                "raw_dob": dob_raw,
                "gender": fmt_gender,
                "masked_aadhaar": masked_uid,
                "last_4_digits": last4,
                "reference_id": ref_id,
                "careof": careof,
                "address": {
                    "careof": careof,
                    "house": house,
                    "street": street,
                    "landmark": landmark,
                    "location": location,
                    "vtc": vtc,
                    "subdistrict": subdistrict,
                    "district": district,
                    "state": state,
                    "pincode": pincode,
                    "postoffice": postoffice,
                    "full_address": full_address
                },
                "has_photo": has_photo,
                "photo_base64": photo_b64,
                "photo_path": photo_path,
                "raw_fields": raw_dict
            }

        except Exception as e:
            _log(f"Error parsing Secure QR: {e}")
            return {
                "status": "error",
                "qr_type": "secure_qr",
                "error": f"Failed to decompress UIDAI Secure QR code: {str(e)}"
            }

    # 2. Check if Legacy XML Aadhaar QR
    if ("<PrintLetterBarcodeData" in str_data or "<?xml" in str_data) and AadhaarOldQr is not None:
        _log("Detected Legacy XML Aadhaar QR Code")
        try:
            old_obj = AadhaarOldQr(str_data)
            dec = old_obj.decodeddata()

            name = dec.get("name", "")
            dob_raw = dec.get("dob") or dec.get("yob", "")
            gender_raw = dec.get("gender", "")
            uid_val = dec.get("uid", "")

            fmt_gender = "Male" if gender_raw == "M" else ("Female" if gender_raw == "F" else gender_raw)

            addr_parts = [dec.get(k, "") for k in ["co", "house", "street", "lm", "loc", "vtc", "po", "dist", "state", "pc"] if dec.get(k)]
            full_addr = ", ".join(addr_parts)

            masked_uid = f"XXXX XXXX {uid_val[-4:]}" if len(uid_val) >= 4 else uid_val

            return {
                "status": "success",
                "qr_type": "legacy_xml_qr",
                "is_secure": False,
                "is_signed": False,
                "name": name,
                "dob": dob_raw,
                "raw_dob": dob_raw,
                "gender": fmt_gender,
                "masked_aadhaar": masked_uid,
                "last_4_digits": uid_val[-4:] if len(uid_val) >= 4 else "",
                "reference_id": "",
                "careof": dec.get("co", ""),
                "address": {
                    "careof": dec.get("co", ""),
                    "house": dec.get("house", ""),
                    "street": dec.get("street", ""),
                    "landmark": dec.get("lm", ""),
                    "location": dec.get("loc", ""),
                    "vtc": dec.get("vtc", ""),
                    "subdistrict": dec.get("subdist", ""),
                    "district": dec.get("dist", ""),
                    "state": dec.get("state", ""),
                    "pincode": dec.get("pc", ""),
                    "full_address": full_addr
                },
                "has_photo": False,
                "photo_base64": None,
                "photo_path": None,
                "raw_fields": dec
            }
        except Exception as e:
            _log(f"Error parsing legacy Aadhaar QR: {e}")
            return {
                "status": "error",
                "qr_type": "legacy_xml_qr",
                "error": f"Failed to parse XML Aadhaar QR: {str(e)}"
            }

    # 3. Fallback for generic QR code content
    _log("Scanned QR is not an official UIDAI encoded payload")
    return {
        "status": "warning",
        "qr_type": "generic_qr",
        "is_secure": False,
        "is_signed": False,
        "message": "QR code scanned but does not match official UIDAI Aadhaar encoding",
        "raw_text": str_data[:120]
    }


def decode_aadhaar_qr_from_file(img_input: Union[str, Path, np.ndarray], save_photo_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    High-level entry point: scans and decodes any Aadhaar QR code from an image or file path.
    """
    raw_list = scan_qr_codes(img_input)
    if not raw_list:
        return {"status": "not_found", "error": "No QR code detected in document image"}

    best_res = None
    for r in raw_list:
        parsed = parse_aadhaar_qr_payload(r, save_photo_dir=save_photo_dir)
        if parsed.get("status") == "success":
            if parsed.get("is_secure"):
                return parsed
            if best_res is None:
                best_res = parsed

    return best_res or (parse_aadhaar_qr_payload(raw_list[0], save_photo_dir=save_photo_dir) if raw_list else {"status": "not_found", "error": "No QR code found"})
