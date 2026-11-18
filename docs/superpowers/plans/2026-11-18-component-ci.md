# Component CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give BE, FE, and AI the same test-before-publish CI structure as the prepared DB workflow.

**Architecture:** Keep separate path-filtered GitHub Actions workflows. Each runs existing tests, builds a linux/amd64 image, checks the actual container, and publishes the tested image to Harbor with the source SHA. Deployment manifests and running services remain unchanged.

**Tech Stack:** GitHub Actions, Docker Buildx, pytest/uv, Vitest/npm, PostgreSQL/TimescaleDB, Nginx.

**Spec:** User request in this chat: unify BE CI and add FE/AI CI; existing `.github/workflows/build-db.yaml` establishes the pattern.

## Global Constraints

- Harbor paths: `harbor.skala-us.com/u3-2/{backend,frontend,ai,db}:<github.sha>`.
- Use `linux/amd64`, existing `HARBOR_USERNAME`/`HARBOR_PASSWORD`, and `contents: read`.
- Publish only after tests succeed, on main push with relevant path changes or manual main execution.
- Never use production DB credentials, dumps, EKS, or real OpenAI calls in CI.
- Preserve BE and AI business logic and existing BE/AI contract mismatch; this task does not resolve chat integration.
- Do not commit, push, publish an image, or change live manifests as part of local implementation.
- Preserve unrelated untracked `k8s/ai` work and the existing DB CI files.

## Review Focus

- Failed tests must prevent Harbor login/push; disposable fixtures must be cleaned up.
- Linux paths must use lowercase `fe`; component filters must include dependencies used by their tests.
- FE must boot with the real EKS backend Service name and retain local Compose compatibility.
- Python integration tests must use an isolated migrated database, and AI tests must not require an API key.
- Image checks must exercise the actual production image and not silently bypass startup errors.

### Task 1: BE CI

**Files:** `.github/workflows/build.yaml`, `BE/deploy/ci-smoke.sh`, BE documentation as needed.

**Interfaces:** Keeps Harbor `backend` and port 8000. Consumes an isolated PostgreSQL fixture with TimescaleDB/vector, runs migrations and the complete existing pytest suite, and checks `/health` plus a read endpoint in the built image.

- [x] Establish existing test behavior against disposable DB fixtures.
- [x] Add path filters/manual execution, tests, build/load, image check, and gated publish using the DB workflow's action versions.
- [x] Validate workflow syntax and run source/image checks without production data.

### Task 2: FE CI

**Files:** `.github/workflows/build-fe.yaml`, `fe/deploy/*` and FE documentation as needed. Parent owns `compose.yaml` integration.

**Interfaces:** Harbor `frontend`, port 80, `BACKEND_UPSTREAM` host:port defaults to `backend:8000`; Compose explicitly supplies `be:8000`.

- [x] Run existing Vitest/build checks and demonstrate the current Nginx upstream-name startup constraint.
- [x] Add templated upstream configuration and CI test/build/load/check/publish flow.
- [x] Check static assets, SPA fallback and API proxy behavior with an isolated fixture; no EKS or production API calls.

### Task 3: AI CI

**Files:** `.github/workflows/build-ai.yaml`, `AI/deploy/ci-smoke.sh`, AI deployment docs/config only as needed.

**Interfaces:** Harbor `ai`, port 8001, existing plain-chat API and `/health`; no real model key.

- [x] Run complete existing pytest and Ruff checks with frozen dependencies.
- [x] Add path-filtered/manual build/load/check/publish workflow.
- [x] Check real container health and safe missing-key chat failure; report architecture limitations honestly.

### Task 4: Integration and documentation

**Files:** `compose.yaml`, CI guide, this plan's completion marks.

- [x] Fix lowercase FE build context and Compose `BACKEND_UPSTREAM=be:8000` compatibility.
- [x] Review all four workflows for consistent tags, secrets, trigger scope and failure gates.
- [x] Run actionlint/ShellCheck and the relevant complete suites and container checks.
- [x] Document activation by commit/push and manual image-tag promotion; do not modify live image versions.

## Verification evidence

- BE: Ruff and all 4 pytest tests pass against a fresh migrated TimescaleDB/vector fixture. The unchanged production Dockerfile builds for linux/amd64; actual-image health and seeded hierarchy/equipment reads pass.
- FE: All 25 Vitest tests pass on Node 22 with explicit mock mode. Production amd64 build and actual-image assets, SPA, API path/query and both default/overridden upstream checks pass.
- AI: Ruff and all 10 pytest tests pass without model calls. The pinned native arm64 image passes health and missing-key 503 checks. Local amd64 builds stop during uv sync with a QEMU signal 11, both before and after pinning uv. Native GitHub Actions amd64 build/smoke remains to be run after push; it is not claimed as locally verified.
- DB: Actual amd64 image passes extension operation checks. Disabling vector in a temporary negative fixture correctly makes the check fail.
- Integration: All four workflows pass actionlint 1.7.12; all four image-check scripts pass ShellCheck. Compose parses with env-file loading and interpolation disabled. Whitespace checks pass. Independent review found no actionable issues.
- GitHub-hosted runs, Harbor uploads, manifest changes and live deployments are not performed by this local implementation.
