FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS build

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d

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
