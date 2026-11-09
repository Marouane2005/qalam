FROM node:22-bookworm-slim AS build

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:22-bookworm-slim

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin qalam

COPY --from=build --chown=qalam:qalam /app/.next/standalone ./
COPY --from=build --chown=qalam:qalam /app/.next/static ./.next/static
COPY --from=build --chown=qalam:qalam /app/public ./public

USER qalam
EXPOSE 3000
CMD ["node", "server.js"]
