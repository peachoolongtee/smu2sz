# The judges' demo web app: a production build (next build, next start) with the flags `pnpm demo` sets, calling the API on the
# same origin under /api (the proxy strips the prefix). The CSP's connect-src is then 'self' plus that origin.
FROM node:24-alpine AS build
RUN npm install -g pnpm@12.11.2
WORKDIR /web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web ./
ARG PUBLIC_ORIGIN
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=${PUBLIC_ORIGIN}/api NEXT_PUBLIC_DEMO=1 \
    NEXT_PUBLIC_STRATEGY_MVP=1 NEXT_PUBLIC_STRATEGY_ENVELOPE=1
RUN test -n "$PUBLIC_ORIGIN" && pnpm build

FROM node:24-alpine
WORKDIR /web
COPY --from=build /web ./
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
