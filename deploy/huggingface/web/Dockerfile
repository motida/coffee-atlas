# --- deps ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts || npm install

# --- builder ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./

ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# --- runner ---
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=7860 \
    HOSTNAME=0.0.0.0

COPY --from=builder --chown=node:node /app/public            ./public
COPY --from=builder --chown=node:node /app/.next/standalone  ./
COPY --from=builder --chown=node:node /app/.next/static      ./.next/static

USER node
EXPOSE 7860

CMD ["node", "server.js"]
