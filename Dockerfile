# --- Backend ---
FROM python:3.14-slim AS backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY ontology/ ./ontology/

RUN uv pip install --system --no-cache .

RUN useradd -m -u 1000 user && \
    mkdir -p /app/data && \
    chown -R user:user /app

USER user

ENV PYTHONUNBUFFERED=1 \
    HOME=/home/user

EXPOSE 8000
CMD ["sh", "-c", "python -m backend.db.bootstrap && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"]


# --- Frontend deps ---
FROM node:20-alpine AS frontend-deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts || npm install


# --- Frontend builder ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ ./

ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build


# --- Frontend runner ---
FROM node:20-alpine AS frontend
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=frontend-builder --chown=node:node /app/public            ./public
COPY --from=frontend-builder --chown=node:node /app/.next/standalone  ./
COPY --from=frontend-builder --chown=node:node /app/.next/static      ./.next/static

USER node
EXPOSE 3000

CMD ["node", "server.js"]
