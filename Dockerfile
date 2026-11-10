# Build the website; Node is not needed in the final running image.
FROM node:24-bookworm-slim AS website
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist \
    FRONTEND_ORIGINS="" \
    PORT=10000
WORKDIR /app/backend
COPY backend/requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt \
    && useradd --create-home --uid 10001 appuser
COPY backend/app ./app
COPY --from=website /build/dist /app/frontend/dist
USER appuser
EXPOSE 10000
CMD ["python", "-m", "app.serve"]
