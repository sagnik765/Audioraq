FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json ./
COPY frontend/package-lock.json ./
COPY frontend/postcss.config.js ./
COPY frontend/tailwind.config.js ./
COPY frontend/vite.config.mjs ./
COPY frontend/index.html ./
COPY frontend/components.json ./
COPY frontend/jsconfig.json ./
COPY frontend/public ./public
COPY frontend/src ./src

RUN npm ci
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg espeak-ng && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.prod.txt ./backend/requirements.prod.txt
RUN pip install --no-cache-dir -r backend/requirements.prod.txt

COPY backend ./backend
COPY memory ./memory
COPY --from=frontend-build /app/frontend/build ./frontend/build

EXPOSE 8001

CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT}"]
