# --- Backend stage ---
FROM python:3.11-slim AS backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/

RUN uv pip install --system --no-cache .

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --- Frontend stage ---
FROM node:20-alpine AS frontend

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts || npm install

COPY frontend/ ./
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
