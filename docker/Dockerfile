# --- stage 1: build the React frontend -------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: backend (serves the API and the built SPA) -------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JOBAGENT_HOST=0.0.0.0 JOBAGENT_BROWSER_HEADLESS=true
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m agent && mkdir -p /app/data /app/documents /app/logs && chown -R agent /app
USER agent
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
