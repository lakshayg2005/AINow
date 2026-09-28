# Runs the API. Background jobs (ingest/compose/deliver) run
# inside the same process, started from /admin or by the
# scheduled GitHub Actions workflow (see .github/workflows).
FROM python:3.13-slim

WORKDIR /app

# Installed separately from the rest of the source so this
# layer is cached across deploys that don't touch dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# $PORT is set by the host (Render, Railway, ...); 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
