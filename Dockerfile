# Compile the Vue application with a Vite 7-compatible Node runtime.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /workspace
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend/ ./frontend/
COPY locales/ ./locales/
RUN npm run build --prefix frontend

# Run the Flask API and the prebuilt Vue SPA from one origin and one port.
FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev \
    && uv pip install --python /app/backend/.venv/bin/python gunicorn==23.0.0
COPY backend/ ./backend/
COPY locales/ ./locales/
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
ENV PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=False \
    FLASK_PORT=3000
WORKDIR /app/backend
EXPOSE 3000
# Single worker preserves the application's in-memory simulation state.
CMD ["/app/backend/.venv/bin/gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "4", "--timeout", "300", "--graceful-timeout", "30", "wsgi:app"]
