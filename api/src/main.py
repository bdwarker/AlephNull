import os
import sys
import uuid
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding issues with UTF-8 / emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [API] {msg}", flush=True)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import FaceVerification from modules
try:
    from modules.face_verification.src.main import FaceVerification
    _log("FaceVerification module imported successfully.")
except ImportError as e:
    FaceVerification = None
    _log(f"Warning: Could not import FaceVerification: {e}")

# Import DocumentOCR from modules
try:
    from modules.ocr_extraction.src.main import DocumentOCR
    _log("DocumentOCR module imported successfully.")
except ImportError as e:
    DocumentOCR = None
    _log(f"Warning: Could not import DocumentOCR: {e}")

# Import DocumentValidator from modules
try:
    from modules.doc_validation.src.main import DocumentValidator
    _log("DocumentValidator module imported successfully.")
except ImportError as e:
    DocumentValidator = None
    _log(f"Warning: Could not import DocumentValidator: {e}")

# Import Risk Engine scorer
try:
    from risk_engine.src.scorer import consolidate_pipeline_scores
    _log("Risk Engine scorer imported successfully.")
except ImportError as e:
    consolidate_pipeline_scores = None
    _log(f"Warning: Could not import consolidate_pipeline_scores: {e}")

# Import Aadhaar QR Decoder
try:
    from modules.doc_validation.src.aadhaar_qr import decode_aadhaar_qr_from_file, parse_aadhaar_qr_payload
    _log("Aadhaar QR decoder imported successfully.")
except ImportError as e:
    decode_aadhaar_qr_from_file = None
    parse_aadhaar_qr_payload = None
    _log(f"Warning: Could not import Aadhaar QR decoder: {e}")

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "ui"), static_url_path="")
CORS(app)

# Upload directory configuration
UPLOAD_BASE_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIRS = {
    "person": UPLOAD_BASE_DIR / "person",
    "document": UPLOAD_BASE_DIR / "document",
    "aadhaar_qr": UPLOAD_BASE_DIR / "aadhaar_qr",
}

for d in UPLOAD_DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}

# Cache most recent uploads in memory
latest_uploads = {
    "person": None,
    "document": None,
    "aadhaar_qr": None
}

# Cache most recent module results
latest_face_result = None
latest_ocr_result = None

try:
    import pypdfium2 as pdfium
    _log("pypdfium2 PDF renderer imported successfully.")
except ImportError as e:
    pdfium = None
    _log(f"Warning: pypdfium2 not available: {e}")


def convert_pdf_to_image(pdf_path: str, output_path: str) -> bool:
    """Renders page 0 of a PDF file to a high-resolution JPEG image."""
    if pdfium is None:
        _log("ERROR: pypdfium2 is not available to convert PDF.")
        return False
    pdf = None
    try:
        _log(f"Rendering PDF page 1: {pdf_path} -> {output_path}")
        pdf = pdfium.PdfDocument(pdf_path)
        if len(pdf) == 0:
            _log(f"ERROR: PDF file has 0 pages: {pdf_path}")
            return False
        page = pdf[0]
        pil_img = page.render(scale=3.0).to_pil()
        pil_img.save(output_path, "JPEG", quality=95)
        _log(f"Successfully converted PDF to image ({pil_img.width}x{pil_img.height}): {output_path}")
        return True
    except Exception as e:
        _log(f"ERROR rendering PDF to image: {e}")
        return False
    finally:
        if pdf is not None:
            try:
                pdf.close()
            except Exception:
                pass


def is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image_file(file_storage, quantifier: str) -> tuple[str, str]:
    ext = file_storage.filename.rsplit(".", 1)[1].lower() if "." in file_storage.filename else "jpg"
    unique_id = uuid.uuid4().hex[:8]

    if ext == "pdf":
        temp_pdf_name = f"{quantifier}_{unique_id}.pdf"
        temp_pdf_path = UPLOAD_DIRS[quantifier] / temp_pdf_name
        file_storage.save(str(temp_pdf_path))
        _log(f"Saved uploaded PDF file -> {temp_pdf_path}")

        target_name = f"{quantifier}_{unique_id}.jpg"
        target_path = UPLOAD_DIRS[quantifier] / target_name
        success = convert_pdf_to_image(str(temp_pdf_path), str(target_path))
        if not success:
            raise ValueError(f"Failed to render PDF into document image for processing: {file_storage.filename}")

        latest_uploads[quantifier] = str(target_path)
        return target_name, str(target_path)
    else:
        unique_name = f"{quantifier}_{unique_id}.{ext}"
        target_path = UPLOAD_DIRS[quantifier] / unique_name
        file_storage.save(str(target_path))
        latest_uploads[quantifier] = str(target_path)
        _log(f"Saved uploaded {quantifier} image -> {target_path}")
        return unique_name, str(target_path)


@app.before_request
def log_incoming_request():
    # Avoid spamming logs for static file requests
    if not request.path.startswith(("/static", "/style.css", "/script.js", "/favicon")):
        _log(f"---> HTTP {request.method} {request.full_path.rstrip('?')} [Remote: {request.remote_addr}]")


@app.route("/")
def index():
    return send_from_directory(str(PROJECT_ROOT / "ui"), "index.html")


@app.route("/api")
def api_root():
    return jsonify({
        "service": "AlephNull Border Verification API",
        "version": "2.0.0",
        "status": "online",
        "modules": {
            "face_verification": bool(FaceVerification),
            "ocr_extraction": bool(DocumentOCR),
            "doc_validation": bool(DocumentValidator),
            "risk_engine": bool(consolidate_pipeline_scores)
        },
        "endpoints": [
            "POST /upload",
            "POST /verify_photo",
            "POST /extract_text",
            "POST /decode_aadhaar_qr",
            "POST /validate_document",
            "POST /consolidate_score"
        ]
    })


@app.route("/upload", methods=["POST"])
def upload_file():
    _log("Processing /upload request...")
    handled_files = {}

    for quantifier in ["person", "document", "aadhaar_qr"]:
        if quantifier in request.files:
            file_item = request.files[quantifier]
            if file_item and file_item.filename != "":
                if not is_allowed_file(file_item.filename):
                    _log(f"Upload rejected: Invalid extension for {quantifier} ({file_item.filename})")
                    return jsonify({
                        "error": f"Invalid file type for {quantifier}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
                    }), 400
                filename, filepath = save_image_file(file_item, quantifier)
                handled_files[quantifier] = {
                    "filename": filename,
                    "filepath": filepath,
                    "url": f"/uploads/{quantifier}/{filename}"
                }

    if handled_files:
        _log(f"Direct uploads successful: {list(handled_files.keys())}")
        return jsonify({
            "status": "success",
            "message": f"Uploaded {', '.join(handled_files.keys())} successfully",
            "uploads": handled_files
        }), 201

    quantifier = (
        request.form.get("type")
        or request.form.get("quantifier")
        or request.form.get("image_type")
        or request.args.get("type")
        or request.args.get("quantifier")
    )

    if not quantifier:
        return jsonify({
            "error": "Missing quantifier. Specify 'type' or 'quantifier' as 'document', 'person', or 'aadhaar_qr'."
        }), 400

    quantifier = quantifier.strip().lower()
    if quantifier not in ["document", "person", "aadhaar_qr"]:
        return jsonify({
            "error": f"Invalid quantifier '{quantifier}'. Allowed values are 'document', 'person', and 'aadhaar_qr'."
        }), 400

    file_item = request.files.get("file") or request.files.get("image")
    if not file_item or file_item.filename == "":
        return jsonify({
            "error": "No file uploaded. Use form-data field 'file' or 'image'."
        }), 400

    if not is_allowed_file(file_item.filename):
        return jsonify({
            "error": f"File type not allowed. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    filename, filepath = save_image_file(file_item, quantifier)

    return jsonify({
        "status": "success",
        "message": f"{quantifier.capitalize()} image uploaded successfully",
        "quantifier": quantifier,
        "filename": filename,
        "filepath": filepath,
        "url": f"/uploads/{quantifier}/{filename}"
    }), 201


@app.route("/verify_photo", methods=["POST", "GET"])
def verify_photo():
    _log("Processing /verify_photo request...")
    if FaceVerification is None:
        _log("ERROR: FaceVerification module not loaded.")
        return jsonify({
            "error": "FaceVerification module is not available. Please ensure dependencies are installed."
        }), 500

    person_img_path = None
    doc_img_path = None

    if "person" in request.files and "document" in request.files:
        p_file = request.files["person"]
        d_file = request.files["document"]
        if p_file.filename and d_file.filename:
            _, person_img_path = save_image_file(p_file, "person")
            _, doc_img_path = save_image_file(d_file, "document")

    if not person_img_path or not doc_img_path:
        req_json = request.get_json(silent=True) or {}
        person_img_path = req_json.get("person_path") or req_json.get("person_image")
        doc_img_path = req_json.get("document_path") or req_json.get("document_image")

    if not person_img_path:
        person_img_path = request.form.get("person_path") or request.args.get("person_path")
    if not doc_img_path:
        doc_img_path = request.form.get("document_path") or request.args.get("document_path")

    if not person_img_path:
        person_img_path = latest_uploads.get("person")
    if not doc_img_path:
        doc_img_path = latest_uploads.get("document")

    if not person_img_path or not doc_img_path:
        _log(f"Verification rejected: Missing images (person={bool(person_img_path)}, doc={bool(doc_img_path)})")
        return jsonify({
            "error": "Both person image and document image are required for verification.",
            "missing": {
                "person_image": not bool(person_img_path),
                "document_image": not bool(doc_img_path)
            },
            "hint": "Upload images first via /upload or pass person_path and document_path."
        }), 400

    if not os.path.exists(person_img_path):
        _log(f"Person image does not exist: {person_img_path}")
        return jsonify({"error": f"Person image file does not exist: {person_img_path}"}), 404
    if not os.path.exists(doc_img_path):
        _log(f"Document image does not exist: {doc_img_path}")
        return jsonify({"error": f"Document image file does not exist: {doc_img_path}"}), 404

    model_name = request.args.get("model_name") or (request.json.get("model_name") if request.is_json else None) or "buffalo_l"
    detector_backend = request.args.get("detector_backend") or (request.json.get("detector_backend") if request.is_json else None) or "retinaface"
    distance_metric = request.args.get("distance_metric") or (request.json.get("distance_metric") if request.is_json else None) or "cosine"
    enforce_detection = request.args.get("enforce_detection", "true").lower() != "false"

    face_strictness = request.args.get("face_strictness") or (request.json.get("face_strictness") if request.is_json else None)
    face_strictness = int(face_strictness) if face_strictness is not None else 20

    _log(f"Dispatching FaceVerification: model={model_name}, strictness={face_strictness}")

    try:
        verifier = FaceVerification(
            model_name=model_name,
            detector_backend=detector_backend,
            distance_metric=distance_metric,
            enforce_detection=enforce_detection
        )
        result = verifier.verify_identity(person_img_path, doc_img_path, strictness=face_strictness)

        global latest_face_result
        latest_face_result = {
            "status": "success",
            "verification": result
        }

        _log(f"Face verification complete: match={result.get('is_match')}, trust_score={result.get('trust_score')}")

        return jsonify({
            "status": "success",
            "verification": result,
            "inputs": {
                "person_image": person_img_path,
                "document_image": doc_img_path,
                "model_name": model_name,
                "detector_backend": detector_backend,
                "distance_metric": distance_metric,
                "face_strictness": face_strictness
            }
        }), 200

    except Exception as e:
        _log(f"ERROR in /verify_photo: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/extract_text", methods=["POST", "GET"])
def extract_text():
    _log("Processing /extract_text request...")
    if DocumentOCR is None:
        _log("ERROR: DocumentOCR module not loaded.")
        return jsonify({
            "error": "DocumentOCR module is not available. Please ensure dependencies are installed."
        }), 500

    doc_img_path = None

    if "document" in request.files:
        d_file = request.files["document"]
        if d_file.filename:
            _, doc_img_path = save_image_file(d_file, "document")

    if not doc_img_path:
        req_json = request.get_json(silent=True) or {}
        doc_img_path = req_json.get("document_path") or req_json.get("document_image")

    if not doc_img_path:
        doc_img_path = request.form.get("document_path") or request.args.get("document_path")

    if not doc_img_path:
        doc_img_path = latest_uploads.get("document")

    if not doc_img_path:
        _log("Extract text rejected: No document image provided.")
        return jsonify({
            "error": "Document image is required for OCR.",
            "hint": "Upload a document image first."
        }), 400

    if not os.path.exists(doc_img_path):
        _log(f"Document image file does not exist: {doc_img_path}")
        return jsonify({"error": f"Document image file does not exist: {doc_img_path}"}), 404

    doc_type = (
        request.args.get("doc_type")
        or request.args.get("type")
        or request.args.get("document_type")
        or request.args.get("q")
        or request.form.get("doc_type")
        or request.form.get("type")
        or request.form.get("q")
        or (request.json.get("doc_type") or request.json.get("type") or request.json.get("q") if request.is_json else None)
        or "passport"
    )

    ocr_strictness = request.args.get("ocr_strictness") or (request.json.get("ocr_strictness") if request.is_json else None)
    ocr_strictness = int(ocr_strictness) if ocr_strictness is not None else 90

    _log(f"Running DocumentOCR: path={doc_img_path}, type={doc_type}, strictness={ocr_strictness}")

    try:
        global latest_ocr_result
        ocr = DocumentOCR()
        result = ocr.process_document(doc_img_path, doc_type=doc_type, strictness=ocr_strictness)

        if result.get("status") == "error":
            _log(f"DocumentOCR returned error: {result.get('error')}")
            return jsonify(result), 500

        # Check for Aadhaar QR image upload or cached QR
        aadhaar_qr_path = None
        if "aadhaar_qr" in request.files:
            aq_file = request.files["aadhaar_qr"]
            if aq_file and aq_file.filename:
                _, aadhaar_qr_path = save_image_file(aq_file, "aadhaar_qr")
        if not aadhaar_qr_path:
            aadhaar_qr_path = (
                (request.json.get("aadhaar_qr_path") if request.is_json else None)
                or request.form.get("aadhaar_qr_path")
                or request.args.get("aadhaar_qr_path")
                or latest_uploads.get("aadhaar_qr")
            )

        if aadhaar_qr_path and os.path.exists(aadhaar_qr_path):
            result["aadhaar_qr_path"] = aadhaar_qr_path
            if not result.get("aadhaar_qr_parsed") and decode_aadhaar_qr_from_file:
                try:
                    qr_res = decode_aadhaar_qr_from_file(aadhaar_qr_path)
                    if qr_res.get("status") == "success":
                        result["aadhaar_qr_parsed"] = qr_res
                        _log(f"Decoded separate Aadhaar QR file: {qr_res.get('qr_type')}")
                except Exception as qr_err:
                    _log(f"Warning decoding separate Aadhaar QR: {qr_err}")

        # Auto-validate with Module 2 if available
        if DocumentValidator is not None:
            try:
                _log("Auto-validating extracted OCR data with Module 2 DocumentValidator...")
                validator = DocumentValidator()
                validation_res = validator.validate_document(result)
                result["validation"] = validation_res
                _log(f"Document validation completed: score={validation_res.get('score')}, status={validation_res.get('status')}")
            except Exception as val_err:
                _log(f"Warning during auto-validation: {val_err}")
                result["validation_warning"] = str(val_err)

        latest_ocr_result = result
        _log("/extract_text completed successfully (HTTP 200)")
        return jsonify(result), 200

    except Exception as e:
        _log(f"ERROR in /extract_text: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/decode_aadhaar_qr", methods=["POST", "GET"])
def decode_aadhaar_qr_endpoint():
    _log("Processing /decode_aadhaar_qr request...")
    if decode_aadhaar_qr_from_file is None:
        _log("ERROR: Aadhaar QR decoder not loaded.")
        return jsonify({
            "status": "error",
            "error": "Aadhaar QR decoder module is not available."
        }), 500

    qr_path = None
    payload_str = None

    if "aadhaar_qr" in request.files:
        qr_file = request.files["aadhaar_qr"]
        if qr_file and qr_file.filename:
            _, qr_path = save_image_file(qr_file, "aadhaar_qr")
    elif "file" in request.files or "image" in request.files:
        qr_file = request.files.get("file") or request.files.get("image")
        if qr_file and qr_file.filename:
            _, qr_path = save_image_file(qr_file, "aadhaar_qr")

    if not qr_path:
        req_json = request.get_json(silent=True) or {}
        qr_path = req_json.get("qr_path") or req_json.get("image_path") or req_json.get("aadhaar_qr_path")
        payload_str = req_json.get("payload") or req_json.get("qr_data")

    if not qr_path and not payload_str:
        qr_path = request.form.get("qr_path") or request.form.get("aadhaar_qr_path") or request.args.get("qr_path")
        payload_str = request.form.get("payload") or request.args.get("payload")

    if not qr_path and not payload_str:
        qr_path = latest_uploads.get("aadhaar_qr") or latest_uploads.get("document")

    if not qr_path and not payload_str:
        return jsonify({
            "status": "error",
            "error": "No Aadhaar QR code image or payload provided.",
            "hint": "Upload a QR code image using form-data field 'aadhaar_qr' or pass 'qr_path'/'payload'."
        }), 400

    try:
        if payload_str:
            _log("Parsing Aadhaar QR payload string directly...")
            res = parse_aadhaar_qr_payload(payload_str)
        else:
            if not os.path.exists(qr_path):
                return jsonify({"status": "error", "error": f"QR image not found: {qr_path}"}), 404
            _log(f"Scanning & decoding Aadhaar QR code from: {qr_path}")
            res = decode_aadhaar_qr_from_file(qr_path)

        _log(f"Aadhaar QR decode result: status={res.get('status')}, type={res.get('qr_type')}, name={res.get('name')}")
        return jsonify({
            "status": "success",
            "aadhaar_qr": res,
            "inputs": {"qr_path": qr_path}
        }), 200

    except Exception as e:
        _log(f"ERROR decoding Aadhaar QR: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/validate_document", methods=["POST", "GET"])
def validate_doc_endpoint():
    _log("Processing /validate_document request...")
    if DocumentValidator is None:
        _log("ERROR: DocumentValidator module not loaded.")
        return jsonify({
            "error": "DocumentValidator module is not available."
        }), 500

    data = None
    doc_type = request.args.get("doc_type") or request.args.get("type")

    if request.is_json:
        data = request.get_json(silent=True)

    if not data and request.form:
        data = request.form.to_dict()

    if not data:
        if latest_ocr_result is not None:
            _log("Using cached latest_ocr_result for validation")
            data = latest_ocr_result
        else:
            _log("Validation rejected: No document data available")
            return jsonify({
                "error": "No document data provided to validate.",
                "hint": "Run /extract_text first, or pass JSON data containing document fields."
            }), 400

    try:
        validator = DocumentValidator()
        result = validator.validate_document(data, doc_type=doc_type)
        _log(f"Validation successful: status={result.get('status')}, score={result.get('score')}")
        return jsonify({
            "status": "success",
            "validation": result
        }), 200

    except Exception as e:
        _log(f"ERROR in /validate_document: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/consolidate_score", methods=["POST", "GET"])
def consolidate_score_endpoint():
    _log("Processing /consolidate_score request...")
    if consolidate_pipeline_scores is None:
        _log("ERROR: Consolidated risk scoring engine not loaded.")
        return jsonify({
            "error": "Consolidated risk scoring engine is not available."
        }), 500

    payload = request.get_json(silent=True) or {}
    face_data = payload.get("face_data") or payload.get("face") or latest_face_result
    doc_data = payload.get("doc_data") or payload.get("doc") or payload.get("document") or latest_ocr_result

    if not face_data or not doc_data:
        _log(f"Consolidation rejected: Missing data (face={bool(face_data)}, doc={bool(doc_data)})")
        return jsonify({
            "error": "Both face verification data and document validation data are required.",
            "hint": "Run /verify_photo and /extract_text first, or pass face_data and doc_data in the JSON body."
        }), 400

    audit_path = str(PROJECT_ROOT / "data" / "audit.log")

    try:
        consolidated = consolidate_pipeline_scores(
            face_data=face_data,
            doc_data=doc_data,
            weights=payload.get("weights"),
            audit_log_path=audit_path
        )
        _log(f"Consolidation complete: score={consolidated.get('consolidated_score')}, suspicious_points={len(consolidated.get('suspicious_points', []))}")
        return jsonify({
            "status": "success",
            "consolidated": consolidated
        }), 200
    except Exception as e:
        _log(f"ERROR in /consolidate_score: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/uploads/<quantifier>/<filename>", methods=["GET"])
def get_uploaded_image(quantifier, filename):
    if quantifier not in UPLOAD_DIRS:
        return jsonify({"error": "Invalid quantifier directory"}), 404
    return send_from_directory(str(UPLOAD_DIRS[quantifier]), filename)


def get_or_create_ssl_cert() -> tuple[str, str]:
    cert_dir = PROJECT_ROOT / "data" / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    import ipaddress
    import socket
    from datetime import timedelta, timezone
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AlephNull Local Verification"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AlephNull"),
    ])

    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
    ]

    try:
        hostname = socket.gethostname()
        san_list.append(x509.DNSName(hostname))
        local_ip = socket.gethostbyname(hostname)
        if local_ip != "127.0.0.1":
            san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return str(cert_path), str(key_path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    use_ssl = os.environ.get("SSL", "false").lower() in ("true", "1", "yes") or "--ssl" in sys.argv

    if use_ssl:
        cert_path, key_path = get_or_create_ssl_cert()
        print(f"\n[STARTUP] Starting AlephNull Verification API with SSL (HTTPS) on port {port}...", flush=True)
        print(f"[STARTUP] Mobile In-Browser Camera URL: https://<your-machine-ip>:{port}", flush=True)
        print("[STARTUP] (Accept the self-signed certificate warning on your phone to unlock live camera viewfinders)\n", flush=True)

        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)

        app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False, ssl_context=context)
    else:
        print(f"\n[STARTUP] Starting AlephNull Verification API on http://0.0.0.0:{port}...", flush=True)
        print("[STARTUP] Note for Mobile: Android/iOS browsers disable live camera streaming on plain HTTP.", flush=True)
        print("   To open the live camera & biometric viewfinder directly in your mobile browser, run:", flush=True)
        print(f"   python api/src/main.py --ssl\n", flush=True)
        app.run(host="0.0.0.0", port=port, debug=True)
