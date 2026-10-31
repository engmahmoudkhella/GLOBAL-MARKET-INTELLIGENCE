# syntax=docker/dockerfile:1
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S gmi && adduser -S gmi -G gmi
COPY --from=build --chown=gmi:gmi /app/.next/standalone ./
COPY --from=build --chown=gmi:gmi /app/.next/static ./.next/static
USER gmi
EXPOSE 3000
CMD ["node", "server.js"]
