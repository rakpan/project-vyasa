# Optimized multi-stage Dockerfile for faster builds
# Build context: src/console
# Stage 1: Dependencies
FROM node:18-slim AS deps
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm --force --yes

# Copy dependency files (handle both pnpm and npm lock files)
COPY package.json pnpm-lock.yaml* package-lock.json* yarn.lock* ./

# Install dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm config set auto-install-peers true && \
    if [ -f pnpm-lock.yaml ]; then \
        pnpm install --no-optional --frozen-lockfile || pnpm install --no-optional --no-frozen-lockfile; \
    elif [ -f package-lock.json ]; then \
        npm ci --no-optional || npm install --no-optional; \
    elif [ -f yarn.lock ]; then \
        yarn install --frozen-lockfile --production=false || yarn install --production=false; \
    else \
        pnpm install --no-optional --no-frozen-lockfile; \
    fi

# Stage 2: Builder
FROM node:18-slim AS builder
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm --force --yes

# Copy node_modules and package files from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/package.json ./package.json
# Note: Lock files not needed in builder stage, dependencies already resolved in deps stage

# Copy source code (build context is src/console, so copy everything)
COPY . ./

# Set build environment variables
ENV NEXT_TELEMETRY_DISABLED 1
ENV NODE_ENV production

# Build with cache mount for Next.js cache
RUN --mount=type=cache,target=/app/.next/cache \
    pnpm build

# Stage 3: Production runtime
FROM node:18-slim AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy necessary files from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Create data directory for query logs with proper permissions
RUN mkdir -p /app/data && chown -R nextjs:nodejs /app/data

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
