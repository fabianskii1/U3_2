# Application and Infrastructure Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Preserve teammate features and recover/adapt infrastructure on a separate reviewable branch.

**Architecture:** Existing four path-filtered CI workflows and GitOps manifests, extended with non-publishing PR validation; disposable DB integration testing; separate BE named build context for the shared workflow package.

**Tech Stack:** Git, GitHub Actions, Docker Buildx, uv/pytest/Ruff, npm/Vitest/Vite, Alembic, Kustomize.

**Spec:** `docs/superpowers/specs/2026-11-19-app-infra-integration-design.md`.

## Global Constraints

Preserve teammate functional code/assets/tests. Use linux/amd64 and existing action/uv pins. Never use real env files/keys, production data, EKS writes or model calls. Do not register the deferred AI Secret. Publish neither images nor main; create an integration PR only.

## Review Focus

- Both Alembic branches must execute without losing schema/data operations; an already-stamped branch must also be able to reach the merged head.
- BE source dependencies and image named build context must include the new shared workflow package and trigger CI when it changes.
- Equipment-lookup smoke assertions must exercise the new request/response and safe keyless behavior rather than the removed plain-chat endpoint.
- FE image and feature assets must work with both EKS and Compose backend names; root routing must preserve existing API paths.
- PRs must validate all selected components without Harbor credentials or publishing; restored image pins must not silently deploy the new code.

## Tasks

- [x] Create managed worktree/branch at latest remote main and restore only deleted infrastructure/check files from `8b90d72`.
- [x] BE: reproduce multiple-head failure, merge migration branches, adapt source/build/runtime CI for shared workflow and current schema, run full suite and image checks.
- [x] FE: restore envsubst proxy and smoke behavior, retain teammate assets, run all tests/build/image checks, add non-publishing PR validation.
- [x] AI: adapt smoke to equipment lookup, keep current features, test full suite/image without keys, add non-publishing PR validation.
- [x] DB/integration: validate restored DB smoke and exclusions, add non-publishing PR validation, render deployment paths and update live docs.
- [x] Review: inspect combined diff against `origin/main`, run workflow/shell/Compose checks and independent review; resolve findings.
- [ ] Delivery: commit scoped changes, push integration branch, create/attach a PR, observe native CI checks and report unresolved limits. No merge/deployment.

## Verification evidence

- BE: original multiple-head error reproduced; no-op merge `9a6d82f0c713` preserves both branches. Fresh upgrade and real upgrades from either previous head pass. Final frozen Ruff and all 12 tests pass, including three cookie regression cases. Final named-context amd64 image builds and passes DB/API/Secure-cookie smoke.
- FE: all 35 tests across 12 files pass on Node22; production build and amd64 image smoke pass for EKS/Compose upstreams, assets/SPA/API paths and preserved standalone console. Synthetic private env files are excluded. Source/tests/assets are unchanged.
- AI: all 10 tests and Ruff pass with frozen dependencies in native Linux. Current equipment-lookup smoke passes on the native arm64 production image. One bounded amd64 build hits local QEMU's uv-sync segmentation fault; native PR CI is required for amd64 proof. AI source/tests/workflow package are unchanged.
- DB: amd64 build and disposable extension operations pass. All four workflows pass actionlint and shell scripts pass ShellCheck. Compose parses without loading/interpolating real env files. All four Kustomize directories render.
- PR event parity and main-only publisher conditions are asserted for all workflows. BE shared dependency trigger and named build context are checked.
- Only two BE application files have mechanical lint compatibility edits (Column.key iteration and explicit reexports/import order), preserving tested behavior. No rules or tests were disabled.
- Review found one production cookie issue behind HTTPS ingress. Added a default-off force-secure setting and enabled it in both K8s slots. The forced-HTTP regression failed before the fix, then all local HTTP/HTTPS/forced cases passed. Full suite and actual image cookie headers pass; proxy trust was not broadened. Corrected the stale DB guide quota text.
