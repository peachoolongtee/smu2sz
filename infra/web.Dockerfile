FROM node:22-alpine AS build
WORKDIR /web
COPY apps/web/package.json apps/web/pnpm-lock.yaml* apps/web/package-lock.json* ./
RUN corepack enable && (pnpm install --frozen-lockfile || npm ci)
COPY apps/web ./
ARG NEXT_PUBLIC_API_MODE=live
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
RUN (pnpm build || npm run build)
FROM node:22-alpine
WORKDIR /web
COPY --from=build /web ./
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
