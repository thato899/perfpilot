# Image for the `web` service — the Next.js *development* server, per
# docs/development/local-development.md's planned layout ("web | Next.js dev
# server, apps/web"). This is not a production build; `render.yaml` is what
# describes deployment.
#
# Build context is the repository root: apps/web is a pnpm workspace member
# (pnpm-workspace.yaml) and imports packages/schemas/typescript, so the
# lockfile and workspace manifest have to come from the root.
#
# apps/web is Thato's surface (CODEOWNERS). This file only containerises what
# is already there — it changes nothing inside apps/web.

# node:20 to match CI exactly (.github/workflows/ci.yml pins node-version 20
# across ts-lint/ts-format/ts-test/build), so a dependency that resolves here
# resolves there.
FROM node:20-alpine

# corepack activates the exact pnpm version pinned in the root package.json's
# `packageManager` field, instead of whatever pnpm happens to be newest.
RUN corepack enable

WORKDIR /app

# Manifests + lockfile first so a source-only change doesn't reinstall the
# whole dependency tree.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json

RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000

# --hostname 0.0.0.0: Next binds to localhost by default, which inside a
# container means the published port answers nothing from the host.
#
# `--filter web exec next dev ...` rather than `--filter web dev ...`:
# everything after `exec` goes to the command verbatim, so `--hostname`
# can't be swallowed by pnpm's own argument parsing.
CMD ["pnpm", "--filter", "web", "exec", "next", "dev", "--hostname", "0.0.0.0"]
