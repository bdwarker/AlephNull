import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import FaceVerification from modules
try:
    from modules.face_verification.src.main import FaceVerification
except ImportError as e:
    FaceVerification = None
    print(f"Warning: Could not import FaceVerification: {e}")

# Import DocumentOCR from modules
try:
    from modules.ocr_extraction.src.main import DocumentOCR
except ImportError as e:
    DocumentOCR = None
    print(f"Warning: Could not import DocumentOCR: {e}")

app = Flask(__name__, static_folder=str(PROJECT_ROOT / "ui"), static_url_path="")
CORS(app)

# Upload directory configuration
UPLOAD_BASE_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIRS = {
    "person": UPLOAD_BASE_DIR / "person",
    "document": UPLOAD_BASE_DIR / "document",
}

for d in UPLOAD_DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}

# Cache for the most recently uploaded images
latest_uploads = {
    "person": None,
    "document": None
}


def is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image_file(file_storage, quantifier: str) -> tuple[str, str]:
    """
    Saves an uploaded file to the designated quantifier directory.
    Returns (filename, absolute_file_path).
    """
    ext = file_storage.filename.rsplit(".", 1)[1].lower() if "." in file_storage.filename else "jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    clean_filename = secure_filename(file_storage.filename)
    stem = Path(clean_filename).stem if clean_filename else quantifier
    
    saved_filename = f"{quantifier}_{timestamp}_{unique_id}_{stem}.{ext}"
    target_dir = UPLOAD_DIRS[quantifier]
    save_path = target_dir / saved_filename
    file_storage.save(str(save_path))
    
    # Update latest pointer
    latest_uploads[quantifier] = str(save_path)
    return saved_filename, str(save_path)


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "AlephNull Identity Verification API",
        "endpoints": {
            "/upload": "POST (accepts 'file' with quantifier 'document' or 'person')",
            "/verify_photo": "POST (compares face in person photo with document photo)",
            "/extract_text": "POST (runs OCR on document photo)"
        },
        "latest_uploads": {
            "person": bool(latest_uploads["person"]),
            "document": bool(latest_uploads["document"])
        }
    }), 200


@app.route("/upload", methods=["POST"])
def upload_image():
    """
    Upload endpoint supporting quantifiers: 'document' and 'person'.
    
    Usage:
    1. Single upload:
       - File key: 'file' or 'image'
       - Form/Query param: 'type', 'quantifier', or 'image_type' set to 'document' or 'person'
    2. Multi-key upload:
       - File key 'person': uploaded as person quantifier
       - File key 'document': uploaded as document quantifier
    """
    # Check if direct quantifier-named files were provided (e.g., person and/or document)
    handled_files = {}
    
    for quantifier in ["person", "document"]:
        if quantifier in request.files:
            file_item = request.files[quantifier]
            if file_item and file_item.filename != "":
                if not is_allowed_file(file_item.filename):
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
        return jsonify({
            "status": "success",
            "message": f"Uploaded {', '.join(handled_files.keys())} successfully",
            "uploads": handled_files
        }), 201

    # Standard upload with quantifier parameter
    quantifier = (
        request.form.get("type") 
        or request.form.get("quantifier") 
        or request.form.get("image_type") 
        or request.args.get("type") 
        or request.args.get("quantifier")
    )

    if not quantifier:
        return jsonify({
            "error": "Missing quantifier. Specify 'type' or 'quantifier' as 'document' or 'person'."
        }), 400

    quantifier = quantifier.strip().lower()
    if quantifier not in ["document", "person"]:
        return jsonify({
            "error": f"Invalid quantifier '{quantifier}'. Allowed values are 'document' and 'person'."
        }), 400

    # Retrieve uploaded file
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
    """
    Verifies person photo against document photo using FaceVerification.
    
    Accepts:
    - JSON payload: {"person_path": "...", "document_path": "..."}
    - Form/Query params: 'person_path' and 'document_path'
    - Direct multipart files: 'person' and 'document'
    - Or falls back to the most recently uploaded 'person' and 'document' images.
    """
    if FaceVerification is None:
        return jsonify({
            "error": "FaceVerification module is not available. Please ensure dependencies (deepface, etc.) are installed."
        }), 500

    person_img_path = None
    doc_img_path = None

    # 1. Direct file upload inside /verify_photo
    if "person" in request.files and "document" in request.files:
        p_file = request.files["person"]
        d_file = request.files["document"]
        if p_file.filename and d_file.filename:
            _, person_img_path = save_image_file(p_file, "person")
            _, doc_img_path = save_image_file(d_file, "document")

    # 2. Check JSON payload
    if not person_img_path or not doc_img_path:
        req_json = request.get_json(silent=True) or {}
        person_img_path = req_json.get("person_path") or req_json.get("person_image")
        doc_img_path = req_json.get("document_path") or req_json.get("document_image")

    # 3. Check Form / Query parameters
    if not person_img_path:
        person_img_path = request.form.get("person_path") or request.args.get("person_path")
    if not doc_img_path:
        doc_img_path = request.form.get("document_path") or request.args.get("document_path")

    # 4. Fallback to latest uploads
    if not person_img_path:
        person_img_path = latest_uploads.get("person")
    if not doc_img_path:
        doc_img_path = latest_uploads.get("document")

    # Validation
    if not person_img_path or not doc_img_path:
        return jsonify({
            "error": "Both person image and document image are required for verification.",
            "missing": {
                "person_image": not bool(person_img_path),
                "document_image": not bool(doc_img_path)
            },
            "hint": "Upload images first via /upload (with type=person and type=document) or pass person_path and document_path."
        }), 400

    if not os.path.exists(person_img_path):
        return jsonify({"error": f"Person image file does not exist: {person_img_path}"}), 404
    if not os.path.exists(doc_img_path):
        return jsonify({"error": f"Document image file does not exist: {doc_img_path}"}), 404

    # Optional model configuration parameters
    model_name = request.args.get("model_name") or (request.json.get("model_name") if request.is_json else None) or "Facenet512"
    detector_backend = request.args.get("detector_backend") or (request.json.get("detector_backend") if request.is_json else None) or "opencv"
    distance_metric = request.args.get("distance_metric") or (request.json.get("distance_metric") if request.is_json else None) or "euclidean_l2"
    enforce_detection = request.args.get("enforce_detection", "true").lower() != "false"
    
    face_strictness = request.args.get("face_strictness") or (request.json.get("face_strictness") if request.is_json else None)
    face_strictness = int(face_strictness) if face_strictness is not None else 50

    try:
        verifier = FaceVerification(
            model_name=model_name,
            detector_backend=detector_backend,
            distance_metric=distance_metric,
            enforce_detection=enforce_detection
        )
        result = verifier.verify_identity(person_img_path, doc_img_path, strictness=face_strictness)

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
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/extract_text", methods=["POST", "GET"])
def extract_text():
    """
    Extracts text from the latest uploaded document image.
    Accepts:
    - JSON payload: {"document_path": "...", "type": "passport"}
    - Form/Query params: 'document_path', 'type'
    - Or falls back to the most recently uploaded 'document' image.
    """
    if DocumentOCR is None:
        return jsonify({
            "error": "DocumentOCR module is not available. Please ensure dependencies are installed."
        }), 500

    doc_img_path = None
    
    # 1. Direct file upload inside /extract_text
    if "document" in request.files:
        d_file = request.files["document"]
        if d_file.filename:
            _, doc_img_path = save_image_file(d_file, "document")

    # 2. Check JSON payload
    if not doc_img_path:
        req_json = request.get_json(silent=True) or {}
        doc_img_path = req_json.get("document_path") or req_json.get("document_image")

    # 3. Check Form / Query parameters
    if not doc_img_path:
        doc_img_path = request.form.get("document_path") or request.args.get("document_path")

    # 4. Fallback to latest uploads
    if not doc_img_path:
        doc_img_path = latest_uploads.get("document")

    if not doc_img_path:
        return jsonify({
            "error": "Document image is required for OCR.",
            "hint": "Upload a document image first."
        }), 400

    if not os.path.exists(doc_img_path):
        return jsonify({"error": f"Document image file does not exist: {doc_img_path}"}), 404

    doc_type = request.args.get("type") or (request.json.get("type") if request.is_json else None) or "passport"
    
    ocr_strictness = request.args.get("ocr_strictness") or (request.json.get("ocr_strictness") if request.is_json else None)
    ocr_strictness = int(ocr_strictness) if ocr_strictness is not None else 50

    try:
        ocr = DocumentOCR()
        # Note: doc_type was removed in the new implementation, just passing strictness
        result = ocr.process_document(doc_img_path, strictness=ocr_strictness)

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/uploads/<quantifier>/<filename>", methods=["GET"])
def get_uploaded_image(quantifier, filename):
    """
    Serves uploaded images.
    """
    if quantifier not in UPLOAD_DIRS:
        return jsonify({"error": "Invalid quantifier directory"}), 404
    return send_from_directory(str(UPLOAD_DIRS[quantifier]), filename)


def get_or_create_ssl_cert() -> tuple[str, str]:
    """
    Generates or loads a self-signed SSL certificate for local LAN / mobile camera usage.
    Mobile browsers (Android Chrome, iOS Safari) strictly require HTTPS for in-browser camera streaming.
    """
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
                format=serialization.PrivateFormat.TraditionalOpenSSL,
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
        print(f"\n🔐 Starting AlephNull Verification API with SSL (HTTPS) on port {port}...")
        print(f"👉 Mobile In-Browser Camera URL: https://<your-machine-ip>:{port}")
        print("   (Accept the self-signed certificate warning on your phone to unlock live camera viewfinders)\n")
        app.run(host="0.0.0.0", port=port, debug=True, ssl_context=(cert_path, key_path))
    else:
        print(f"\n🌐 Starting AlephNull Verification API on http://0.0.0.0:{port}...")
        print("💡 Note for Mobile: Android/iOS browsers disable live camera streaming on plain HTTP.")
        print("   To open the live camera & biometric viewfinder directly in your mobile browser, run:")
        print(f"   python api/src/main.py --ssl\n")
        app.run(host="0.0.0.0", port=port, debug=True)
