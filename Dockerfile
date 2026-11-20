FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AA_SERVER=1 AA_DATA_DIR=/data AA_STATIC_DIR=/app/frontend/dist
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd -u 10001 -m assistant && mkdir /data && chown assistant:assistant /data
COPY --chown=assistant:assistant backend/ ./backend/
COPY --chown=assistant:assistant --from=frontend /build/dist/ ./frontend/dist/
USER assistant
EXPOSE 8765
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')"
CMD ["python", "backend/launcher.py"]
