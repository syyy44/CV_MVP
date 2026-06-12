# --- Stage 1: build the React SPA -------------------------------------------
FROM node:22-slim AS ui-build

WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python API (serves the built SPA) ------------------------------
FROM python:3.12-slim

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
COPY fixtures ./fixtures
COPY scripts ./scripts

RUN pip install --no-cache-dir ".[langfuse]"

# Static SPA built in stage 1, served by FastAPI at "/".
COPY --from=ui-build /ui/dist ./frontend/dist

ENV DEMO_MODE=replay \
    DATABASE_URL=sqlite:///data/recruiting.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
