# Node 24 chạy thẳng file .ts (type stripping) — không cần bước build
FROM node:24.22.0-bookworm-slim
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
USER node
CMD ["node", "src/index.ts"]
