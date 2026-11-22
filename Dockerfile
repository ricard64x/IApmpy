# Use a supported Node.js runtime for Vite 7 without replacing Python 3.11.
FROM node:22-bookworm AS node-runtime
FROM python:3.11-bookworm

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
  && node --version && npm --version

# Install uv from its pinned upstream image.
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Cache dependencies.
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY backend/pyproject.toml backend/uv.lock ./backend/

RUN npm ci \
  && npm ci --prefix frontend \
  && cd backend && uv sync --frozen

COPY . .

EXPOSE 3000 5001

# Existing development-server architecture; not a production server.
CMD ["npm", "run", "dev"]
