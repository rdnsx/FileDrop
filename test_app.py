"""Smoke test for the behaviours that used to be broken or exploitable.

Run: python test_app.py
"""

import io
import json
import os
import tempfile
import zipfile

TMP = tempfile.mkdtemp(prefix="filedrop-test-")
os.environ.update(
    UPLOAD_FOLDER=TMP,
    MAX_UPLOAD_MB="1",
    RATE_LIMIT_UPLOADS="500",
    RATE_LIMIT_WINDOW="3600",
    MIN_FREE_GB="0",
)

import app as filedrop  # noqa: E402

filedrop.app.config["TESTING"] = True
client = filedrop.app.test_client()

HTTPS = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "drop2share.de"}


def upload(name, data=b"hello", headers=HTTPS, expect=200):
    response = client.post(
        "/upload",
        data={"file": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
        headers=headers,
    )
    if expect is not None:
        assert response.status_code == expect, f"{name}: {response.status_code} {response.get_data()[:120]}"
    return response


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
    assert upload("big.bin", b"x" * (2 * 1024 * 1024), expect=None).status_code == 413


def test_rate_limit_kicks_in():
    filedrop._hits.clear()
    original = filedrop.RATE_LIMIT_UPLOADS
    filedrop.RATE_LIMIT_UPLOADS = 5
    try:
        codes = [upload(f"f{i}.txt", expect=None).status_code for i in range(7)]
    finally:
        filedrop.RATE_LIMIT_UPLOADS = original
        filedrop._hits.clear()
    assert codes.count(429) >= 1, codes


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


def _batch(uploads):
    return client.post(
        "/batch",
        json={"files": [{"id": u["id"], "name": u["filename"]} for u in uploads]},
        headers=HTTPS,
    )


def test_batch_returns_one_zip_link_for_several_uploads():
    ups = [upload("one.txt", b"first").get_json(), upload("two.txt", b"second").get_json()]
    body = _batch(ups).get_json()
    assert body["file_count"] == 2, body
    assert body["zip_link"].startswith("https://drop2share.de/zip/"), body
    assert body["zip_link"].endswith("drop2share-2-files.zip"), body


def test_zip_contains_every_file_under_its_original_name():
    ups = [upload("notes.txt", b"alpha").get_json(), upload("data.bin", b"beta").get_json()]
    link = _batch(ups).get_json()["zip_link"]
    response = client.get(link.split("drop2share.de")[1], headers=HTTPS)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"
    assert response.headers["Content-Disposition"].startswith("attachment")
    archive = zipfile.ZipFile(io.BytesIO(response.get_data()))
    assert archive.namelist() == ["notes.txt", "data.bin"], archive.namelist()
    assert archive.read("notes.txt") == b"alpha"
    assert archive.read("data.bin") == b"beta"
    assert archive.testzip() is None


def test_zip_disambiguates_duplicate_filenames():
    ups = [upload("report.txt", b"v1").get_json(), upload("report.txt", b"v2").get_json()]
    link = _batch(ups).get_json()["zip_link"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(link.split("drop2share.de")[1], headers=HTTPS).get_data()))
    assert archive.namelist() == ["report.txt", "report (1).txt"], archive.namelist()
    assert archive.read("report.txt") == b"v1"
    assert archive.read("report (1).txt") == b"v2"


def test_batch_rejects_junk_and_single_files():
    one = upload("solo.txt").get_json()
    assert _batch([one]).status_code == 400
    assert client.post("/batch", json={"files": [{"id": "../../app.py"}, {"id": "x"}]},
                       headers=HTTPS).status_code == 400
    missing = client.post("/batch", json={"files": [{"id": "a" * 16 + ".txt"}, {"id": "b" * 16 + ".txt"}]},
                          headers=HTTPS)
    assert missing.status_code == 404, missing.status_code


def test_manifest_is_not_downloadable_and_unknown_archives_404():
    ups = [upload("a.txt").get_json(), upload("b.txt").get_json()]
    token = _batch(ups).get_json()["zip_link"].split("/zip/")[1].split("/")[0]
    assert client.get(f"/uploads/{token}", headers=HTTPS).status_code == 404
    assert client.get(f"/uploads/{token}/x.txt", headers=HTTPS).status_code == 404
    assert client.get("/zip/" + "c" * 16 + ".d2sbatch", headers=HTTPS).status_code == 404


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
