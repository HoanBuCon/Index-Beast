# Bước 1: build web React; bước 2: Caddy phục vụ file tĩnh + proxy /api
FROM node:24.22.0-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM caddy:2.11.7-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /web/dist /srv/web
