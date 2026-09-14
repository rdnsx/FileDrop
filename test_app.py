"""Smoke test for the behaviours that used to be broken or exploitable.

Run: python test_app.py
"""

import io
import os
import tempfile

TMP = tempfile.mkdtemp(prefix="filedrop-test-")
os.environ.update(
    UPLOAD_FOLDER=TMP,
    MAX_UPLOAD_MB="1",
    RATE_LIMIT_UPLOADS="5",
    RATE_LIMIT_WINDOW="3600",
    MIN_FREE_GB="0",
)

import app as filedrop  # noqa: E402

filedrop.app.config["TESTING"] = True
client = filedrop.app.test_client()

HTTPS = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "drop2share.de"}


def upload(name, data=b"hello", headers=HTTPS):
    return client.post(
        "/upload",
        data={"file": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
        headers=headers,
    )


def test_link_is_https_behind_the_proxy():
    body = upload("notes.txt").get_json()
    assert body["download_link"].startswith("https://drop2share.de/uploads/"), body
    assert body["filename"] == "notes.txt"
    assert body["expires_in_hours"] == 24


def test_stored_name_is_random_and_original_name_survives():
    body = upload("holiday photo.JPG").get_json()
    stored = body["download_link"].rsplit("/", 2)[1]
    assert stored not in ("holiday photo.JPG", "holiday_photo.JPG"), stored
    assert len(stored.split(".")[0]) == 16, stored
    assert body["download_link"].endswith("holiday_photo.JPG"), body


def test_uploaded_html_cannot_run_on_our_origin():
    link = upload("evil.html", b"<script>alert(1)</script>").get_json()["download_link"]
    response = client.get(link.split("drop2share.de")[1], headers=HTTPS)
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment"), response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Security-Policy"] == "sandbox"


def test_legacy_link_shape_still_works():
    stored = upload("old.txt").get_json()["download_link"].rsplit("/", 2)[1]
    assert client.get(f"/uploads/{stored}", headers=HTTPS).status_code == 200


def test_path_traversal_and_junk_names_are_rejected():
    for path in ("/uploads/..%2f..%2fapp.py", "/uploads/app.py", "/uploads/zzzz/x"):
        assert client.get(path, headers=HTTPS).status_code in (400, 404), path


def test_missing_file_part_is_a_clean_400():
    response = client.post("/upload", data={}, content_type="multipart/form-data", headers=HTTPS)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Bad Request"


def test_oversized_upload_is_refused():
    response = upload("big.bin", b"x" * (2 * 1024 * 1024))
    assert response.status_code == 413, response.status_code


def test_rate_limit_kicks_in():
    filedrop._hits.clear()
    codes = [upload(f"f{i}.txt").status_code for i in range(7)]
    assert codes.count(429) >= 1, codes
    filedrop._hits.clear()


def test_security_headers_on_the_page():
    headers = client.get("/", headers=HTTPS).headers
    for header in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
                   "Referrer-Policy", "Permissions-Policy"):
        assert header in headers, header


def test_page_is_responsive_and_healthcheck_answers():
    page = client.get("/", headers=HTTPS).get_data(as_text=True)
    assert 'name="viewport"' in page and "width=device-width" in page
    assert 'charset="utf-8"' in page and 'lang="en"' in page
    assert client.get("/healthz").get_json() == {"status": "ok"}


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as error:
                failures += 1
                print(f"FAIL {name}: {error}")
    print(f"\n{failures} failure(s)")
    raise SystemExit(1 if failures else 0)
