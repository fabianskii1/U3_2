# Application and infrastructure integration

The user approved combining teammate commit `aafd399` with the prepared infrastructure commit `8b90d72` in a separate integration branch and PR. Preserve the teammate's application features; recover deleted infrastructure and adapt its checks to the new contracts. Keep the original checkout and remote main unchanged while preparing the PR.

## Scope

- Base: fetched `origin/main` (`aafd399` when work started). Branch: `codex/integrate-app-infra` in the managed worktree.
- Restore `k8s/`, deployment/CI guides, four deleted image smoke scripts and DB build-context exclusions from `8b90d72`.
- Preserve `BE/app`, `AI/app`, `AI/workflow`, `fe/src`, existing tests, data and feature assets. Fix build integration or defects required to combine them; do not roll features back to old code.
- BE has two Alembic heads. Add a merge revision preserving both branches, verify fresh disposable migration and all tests. Include `AI/workflow` in BE CI path filters and the Docker named build context used by the teammate Dockerfile.
- FE must boot against the EKS Service `backend:8000` while Compose keeps `be:8000`. Recover the envsubst template, use the new feature assets, run all current Vitest and production build/runtime checks.
- AI now implements equipment lookup. Adapt the restored smoke check to that actual contract; test without a real key or model request. Pin the known uv tool version consistently.
- Four workflows must run relevant main pushes, manual checks and main-targeted PR checks. Tests/build/load/runtime checks run on PRs; Harbor login/push run only on main outside a PR. Keep existing action versions, readonly GitHub permissions and amd64 target.
- Current image tags in deployment manifests remain pinned to already uploaded versions. A newly integrated source revision must pass CI and publish its own image before later deployment; do not pretend old images contain the teammate's new features.
- Wire the new BE alarm-ingest token as an optional `backend-secrets` / `ALARM_INGEST_TOKEN` reference in both slots. Register no token. Preserve the application's token-missing 503 behavior and keep other endpoints startable.
- Integration review found that default Uvicorn proxy trust hides the external HTTPS scheme from session-cookie logic. Add a default-off force-secure chat-cookie setting, enabled in both K8s slots; preserve existing local HTTP/HTTPS behavior and test the regression. Do not widen proxy-header trust.
- No live EKS mutations, schema migrations against production, image publishing, Argo sync, AI Secret registration, real keys or model calls. User explicitly deferred key registration.

## Completion

Fresh source suites pass, DB migration is a single-head graph and fresh disposable upgrade succeeds, all production images build and smoke-check where locally possible, Kustomize/Compose/workflow/ShellCheck validation pass, independent review is addressed. Push the integration branch and create a reviewable PR with exact validation and limits. Do not merge main or deploy as part of this task.
