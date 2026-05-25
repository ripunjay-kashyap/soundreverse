# ── SoundReverse API — Docker image (for self-hosting / Docker-based deploys) ─
# Render uses render.yaml runtime: python (native build), not this Dockerfile.
# Python 3.11-slim keeps the image small; no audio libraries needed here
# (Demucs/CLAP run inside the Modal-hosted MCP, never in this container).

FROM python:3.11-slim

# ── Non-root user (security best practice) ───────────────────────────────────
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# ── Deps layer (cached unless requirements.txt changes) ───────────────────────
# Copying requirements.txt first means code-only edits skip the slow pip install.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
# Frontend is deployed separately on Vercel — not included here.
COPY agents/   agents/
COPY schemas/  schemas/
COPY rules/    rules/
COPY utils/    utils/
COPY output/   output/
COPY cache/    cache/
COPY api.py    .

# ── Ephemeral runtime directories ─────────────────────────────────────────────
# Both live under /tmp so they survive container restarts within a session but
# are never part of the image layer (safe for secrets/PII in uploaded audio).
RUN mkdir -p /tmp/soundreverse/outputs /tmp/soundreverse/uploads \
    && chown -R appuser:appgroup /tmp/soundreverse /app

# ── Runtime environment defaults ──────────────────────────────────────────────
# Override at deploy time via your platform's env var dashboard.
ENV OUTPUT_DIR=/tmp/soundreverse/outputs \
    UPLOAD_DIR=/tmp/soundreverse/uploads \
    ENV=production

# ── Switch to non-root ────────────────────────────────────────────────────────
USER appuser

# ── Platform injects $PORT at runtime (defaults to 8000) ─────────────────────
EXPOSE 8000

# ── Liveness probe — matches GET /health in api.py ───────────────────────────
# interval: how often Koyeb checks; timeout: max wait per check; start-period:
# grace window after container start (Modal cold-start needs ~15s to settle).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')"

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
