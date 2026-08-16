# ---- Frontend Build ----
FROM node:20-alpine AS web-build
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# ---- Remotion Dependencies ----
FROM node:20-alpine AS remotion-deps
WORKDIR /remotion
COPY remotion/package*.json ./
RUN npm ci
COPY remotion/ .

# ---- Main Runtime ----
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt apscheduler rq redis

COPY shortube/ shortube/

COPY --from=remotion-deps /remotion remotion/
COPY --from=web-build /web/dist web/dist/

ENV PYTHONPATH=/app
ENV REMOTION_PROJECT_DIR=/app/remotion
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8000

EXPOSE 8000

CMD ["hypercorn", "shortube.web:app", "--bind", "0.0.0.0:8000"]
