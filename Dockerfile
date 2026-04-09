FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json ./
COPY frontend/craco.config.js ./
COPY frontend/postcss.config.js ./
COPY frontend/tailwind.config.js ./
COPY frontend/components.json ./
COPY frontend/jsconfig.json ./
COPY frontend/public ./public
COPY frontend/src ./src
COPY frontend/plugins ./plugins

RUN npm install
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001

WORKDIR /app

COPY backend/requirements.prod.txt ./backend/requirements.prod.txt
RUN pip install --no-cache-dir -r backend/requirements.prod.txt

COPY backend ./backend
COPY memory ./memory
COPY --from=frontend-build /app/frontend/build ./frontend/build

EXPOSE 8001

CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT}"]
