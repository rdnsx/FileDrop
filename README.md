# FileDrop / drop2share.de

A small Flask app for sharing a file without an account: drop a file, get a link,
the file is deleted automatically after 24 hours. Runs at
[drop2share.de](https://drop2share.de).

## What it does and does not do

- Transport is encrypted (TLS, terminated by the reverse proxy) and HSTS is preloaded.
- Stored files are **not** encrypted at rest. Anyone with filesystem access to the
  upload volume can read them. Do not describe this service as encrypted storage.
- Filenames are replaced with 16 random hex characters (64 bit), so a link cannot
  be guessed and the name leaks nothing. The original name is only used as the
  download name.
- There is no authentication. Anyone who can reach the site can upload, subject to
  a per-IP rate limit and a size limit.
- Uploads are always served as `Content-Disposition: attachment` with `nosniff` and
  a `sandbox` CSP, so uploaded HTML or SVG cannot execute on the drop2share origin.

## Configuration

All settings come from environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `UPLOAD_FOLDER` | `uploads/` | Where files are written. |
| `MAX_UPLOAD_MB` | `512` | Per-request size limit; larger uploads get HTTP 413. |
| `RETENTION_HOURS` | `24` | Shown on the page; must match the cleanup cron. |
| `RATE_LIMIT_UPLOADS` | `30` | Uploads per IP per window (per replica). |
| `RATE_LIMIT_WINDOW` | `3600` | Rate-limit window in seconds. |
| `MIN_FREE_GB` | `3` | Refuse uploads below this free space (HTTP 507). |

`MIN_FREE_GB` is not cosmetic: in production the GlusterFS brick shares a
filesystem with the node root, so filling the upload volume stops the whole swarm.

## Local development

```bash
git clone https://github.com/rdnsx/FileDrop.git
cd FileDrop
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5000/
python test_app.py       # smoke test
```

`python app.py` starts the Flask development server bound to localhost with the
debugger off. Never expose it: production runs gunicorn, see the `Dockerfile`.

## Docker

```bash
docker build -t rdnsx/filedrop .
docker run -d -p 3266:5000 -v /path/to/uploads:/app/uploads --name FileDrop rdnsx/filedrop
```

The container runs as uid `10001`, so the mounted upload directory must be
writable by that uid (`chown -R 10001:10001 /path/to/uploads`).

## Production

`jenkins.groovy` builds the image, runs the smoke test, copies
`docker-compose-swarm.yml` and `delete2share.sh` to the swarm and deploys the
stack. The app sits behind Nginx Proxy Manager, which terminates TLS and sets
`X-Forwarded-*`; `ProxyFix` trusts exactly one hop so links are generated as
`https://`.

`delete2share.sh` runs hourly from cron on the swarm and deletes uploads older
than `RETENTION_MINUTES` (1440 by default). It is currently scheduled on a single
node — if that node is down, files are not removed.

Set `client_max_body_size` in the proxy to at least `MAX_UPLOAD_MB`, otherwise the
proxy rejects large uploads before the app can return a useful error.

## License

MIT.
