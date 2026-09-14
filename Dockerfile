FROM python:3.13-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY templates/ ./templates/
COPY static/ ./static/


# Smoke test as a build stage: `docker build --target test .` fails the build if
# it fails. Runs on any agent, because it needs no bind mount and no socket.
FROM app AS test
COPY test_app.py ./
RUN python test_app.py


FROM app AS runtime

# The uploads directory is a bind mount in production; create it so the image
# also runs standalone, and hand it to the unprivileged runtime user.
RUN useradd --system --uid 10001 --no-create-home filedrop \
    && mkdir -p /app/uploads \
    && chown -R filedrop:filedrop /app

USER filedrop

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=4).status == 200 else 1)"

# Uploads are streamed to a shared volume, so workers block on I/O: threads
# beat extra processes here. --timeout covers slow large uploads.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--threads", "4", "--timeout", "300", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--forwarded-allow-ips", "*", \
     "app:app"]
