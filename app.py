"""Drop2Share - anonymous, short-lived file sharing."""

import os
import re
import secrets
import shutil
import time
import zipfile
from collections import defaultdict, deque
from threading import Lock

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads/")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "512"))
RATE_LIMIT_UPLOADS = int(os.environ.get("RATE_LIMIT_UPLOADS", "30"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "3600"))
RETENTION_HOURS = int(os.environ.get("RETENTION_HOURS", "24"))
# The GlusterFS brick shares /dev/sda1 with the node root filesystem, so a
# full upload directory takes the whole swarm down, not just this service.
MIN_FREE_GB = float(os.environ.get("MIN_FREE_GB", "3"))

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# Behind Nginx Proxy Manager: trust exactly one hop, otherwise download links
# are generated as http:// and X-Forwarded-For spoofing breaks the rate limit.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# 8 bytes -> 16 hex chars (64 bit), optional short alphanumeric extension.
STORED_NAME_RE = re.compile(r"\A[0-9a-f]{16}(\.[A-Za-z0-9]{1,12})?\Z")
BATCH_SUFFIX = ".d2sbatch"
MAX_BATCH_FILES = 200
EXTENSION_RE = re.compile(r"\A\.[A-Za-z0-9]{1,12}\Z")

_hits: "defaultdict[str, deque]" = defaultdict(deque)
_hits_lock = Lock()


def _rate_limited(client_ip):
    """Per-IP sliding window. ponytail: in-process only - each of the 3 swarm
    replicas counts on its own, so the effective limit is 3x. Move to Redis
    only if that ever turns out to matter."""
    now = time.time()
    with _hits_lock:
        if len(_hits) > 5000:
            for ip in [ip for ip, q in _hits.items() if not q]:
                del _hits[ip]
        window = _hits[client_ip]
        while window and now - window[0] > RATE_LIMIT_WINDOW:
            window.popleft()
        if len(window) >= RATE_LIMIT_UPLOADS:
            return True
        window.append(now)
    return False


def _stored_name(original_filename):
    """Random storage name; keep a sanitised extension for convenience only."""
    extension = os.path.splitext(original_filename or "")[1]
    if not EXTENSION_RE.match(extension):
        extension = ""
    return secrets.token_hex(8) + extension.lower()


def _upload_path(stored):
    return os.path.join(app.config["UPLOAD_FOLDER"], stored)


def _write_manifest(entries):
    """One tiny file next to the uploads, so the existing 24h cleanup expires
    the manifest together with the files it points at. No extra state to reap."""
    token = secrets.token_hex(8) + BATCH_SUFFIX
    with open(_upload_path(token), "w", encoding="utf-8") as handle:
        for stored, name in entries:
            handle.write(f"{stored}\t{name}\n")
    return token


def _read_manifest(token):
    try:
        with open(_upload_path(token), encoding="utf-8") as handle:
            rows = [line.rstrip("\n").split("\t", 1) for line in handle if line.strip()]
    except OSError:
        return None
    return [(s, n) for s, n in rows if STORED_NAME_RE.match(s)]


def _unique_names(entries):
    """Two uploads can share a filename; a zip with duplicates confuses tools."""
    seen, out = {}, []
    for stored, name in entries:
        if name in seen:
            seen[name] += 1
            root, ext = os.path.splitext(name)
            name = f"{root} ({seen[name]}){ext}"
        else:
            seen[name] = 0
        out.append((stored, name))
    return out


class _ChunkSink:
    """Unseekable sink for ZipFile; we drain it as the archive is written."""

    def __init__(self):
        self.buffer = bytearray()

    def write(self, data):
        self.buffer.extend(data)
        return len(data)

    def flush(self):
        pass


def _stream_zip(entries):
    sink = _ChunkSink()
    # ZIP_STORED, not DEFLATE: uploads are arbitrary (often already compressed)
    # and the service runs on a 0.5 CPU limit. Speed beats a few percent.
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED) as archive:
        for stored, name in entries:
            path = _upload_path(stored)
            if not os.path.isfile(path):
                continue
            with archive.open(name, "w", force_zip64=True) as target, open(path, "rb") as source:
                while True:
                    chunk = source.read(65536)
                    if not chunk:
                        break
                    target.write(chunk)
                    if len(sink.buffer) >= 262144:
                        yield bytes(sink.buffer)
                        sink.buffer.clear()
            if sink.buffer:
                yield bytes(sink.buffer)
                sink.buffer.clear()
    yield bytes(sink.buffer)


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'; object-src 'none'",
    )
    return response


@app.errorhandler(HTTPException)
def handle_http_error(error):
    """JSON for the API, never a traceback - the debugger is gone for good."""
    if request.path.startswith(("/upload", "/batch")) or request.accept_mimetypes.best == "application/json":
        return jsonify({"error": error.name, "message": error.description}), error.code
    return error


@app.route("/")
def index():
    return render_template(
        "index.html", max_upload_mb=MAX_UPLOAD_MB, retention_hours=RETENTION_HOURS
    )


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/upload", methods=["POST"])
def upload():
    if _rate_limited(request.remote_addr or "unknown"):
        return jsonify({"error": "Too Many Requests", "message": "Slow down and try again later."}), 429

    free_bytes = shutil.disk_usage(app.config["UPLOAD_FOLDER"]).free
    if free_bytes < MIN_FREE_GB * 1024**3:
        return jsonify({"error": "Insufficient Storage", "message": "Storage is full, try again later."}), 507

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Bad Request", "message": "No file was submitted."}), 400

    stored = _stored_name(uploaded.filename)
    uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], stored))

    display_name = secure_filename(uploaded.filename) or stored
    download_link = request.host_url.rstrip("/") + f"/uploads/{stored}/{display_name}"

    return jsonify(
        {
            "id": stored,
            "filename": uploaded.filename,
            "download_link": download_link,
            "expires_in_hours": RETENTION_HOURS,
        }
    )


def _send_upload(stored, download_name):
    if stored.endswith(BATCH_SUFFIX) or not STORED_NAME_RE.match(stored):
        return jsonify({"error": "Not Found", "message": "Unknown file."}), 404

    response = send_from_directory(
        app.config["UPLOAD_FOLDER"],
        stored,
        as_attachment=True,
        download_name=download_name or stored,
    )
    # Uploads are attacker-controlled: never render them on this origin.
    response.headers["Content-Security-Policy"] = "sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/uploads/<stored>/<download_name>")
def download_named(stored, download_name):
    return _send_upload(stored, secure_filename(download_name))


@app.route("/uploads/<stored>")
def download(stored):
    """Legacy link shape - keeps links from earlier builds alive."""
    return _send_upload(stored, stored)


@app.route("/batch", methods=["POST"])
def batch():
    """Bundle an already-uploaded set into one shareable zip link."""
    if _rate_limited(request.remote_addr or "unknown"):
        return jsonify({"error": "Too Many Requests", "message": "Slow down and try again later."}), 429

    payload = request.get_json(silent=True) or {}
    items = payload.get("files")
    if not isinstance(items, list) or not 2 <= len(items) <= MAX_BATCH_FILES:
        return jsonify({"error": "Bad Request", "message": "Between 2 and 200 files are required."}), 400

    entries = []
    for item in items:
        stored = (item or {}).get("id", "") if isinstance(item, dict) else ""
        if stored.endswith(BATCH_SUFFIX) or not STORED_NAME_RE.match(stored):
            return jsonify({"error": "Bad Request", "message": "Unknown file in batch."}), 400
        if not os.path.isfile(_upload_path(stored)):
            return jsonify({"error": "Not Found", "message": "A file in the batch has expired."}), 404
        name = secure_filename(str(item.get("name") or "")) or stored
        entries.append((stored, name))

    token = _write_manifest(_unique_names(entries))
    archive_name = f"drop2share-{len(entries)}-files.zip"
    return jsonify(
        {
            "zip_link": request.host_url.rstrip("/") + f"/zip/{token}/{archive_name}",
            "file_count": len(entries),
            "expires_in_hours": RETENTION_HOURS,
        }
    )


def _send_zip(token, archive_name):
    if not token.endswith(BATCH_SUFFIX) or not STORED_NAME_RE.match(token):
        return jsonify({"error": "Not Found", "message": "Unknown archive."}), 404

    entries = _read_manifest(token)
    if not entries:
        return jsonify({"error": "Not Found", "message": "Unknown or expired archive."}), 404

    response = app.response_class(_stream_zip(entries), mimetype="application/zip")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{secure_filename(archive_name) or "drop2share.zip"}"'
    )
    response.headers["Content-Security-Policy"] = "sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/zip/<token>/<archive_name>")
def download_zip_named(token, archive_name):
    return _send_zip(token, archive_name)


@app.route("/zip/<token>")
def download_zip(token):
    return _send_zip(token, "drop2share.zip")


if __name__ == "__main__":
    # Local development only. Production runs gunicorn (see Dockerfile).
    app.run(host="127.0.0.1", port=5000, debug=False)
