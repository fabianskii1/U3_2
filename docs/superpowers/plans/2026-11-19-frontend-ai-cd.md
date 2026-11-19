# Frontend and AI CD Implementation Plan

> **For agentic workers:** Use scoped implementation followed by one integration review. Steps use checkbox syntax for tracking.

**Goal:** Prepare and validate FE/AI GitOps manifests using already published CI images, then verify the first deployment after user Argo CD sync.

**Architecture:** FE Deployment/Service/root Ingress, existing AI manual Blue-Green with internal Services, separate manual Argo CD Applications. Existing BE/DB stay unchanged.

**Tech Stack:** Kubernetes, Kustomize, Nginx, FastAPI, Argo CD, Harbor.

**Spec:** `docs/superpowers/specs/2026-11-19-frontend-ai-cd-design.md`.

## Global Constraints

Use namespace/project `u3-2`, team host `u3-2.skala-us.com`, class `nginx`, Secret `team-tls`, default ServiceAccount/pull credentials and linux/amd64. No new platform resources, business API changes, raw data, database operations or exposed secret values. Actual team quota is now 4 CPU/8Gi.

## Review Focus

- Root FE routing must preserve `/api`, `/health`, SPA deep links and static assets; no host-wide rewrite.
- Default Nginx needs compatible writable locations and capabilities; do not copy Python non-root settings blindly.
- Both AI image aliases must point to the verified uploaded image and preserve independent slot selectors.
- Secret setup must filter the AI key and keep values out of logs, files and Git.
- Pod limits including FE update surge must fit the namespace quota; startup health does not prove model or BE chat integration.

## Tasks

- [x] FE: create `k8s/frontend/{deployment,service,ingress,kustomization}.yaml` and a concise deployment README; use the exact image and runtime/resource settings in the spec. Render, inspect paths and verify actual image/runtime compatibility.
- [x] AI: update both image aliases in `k8s/ai/kustomization.yaml`, remove unused external AI Ingress, refresh the README for real CI status/internal-only access. Preserve existing runtime configuration. Render and verify actual non-root startup.
- [x] Integration: independently review changes, server dry-run both directories, verify resource arithmetic and leave BE/DB paths unchanged.
- [ ] Secret: register only the existing local AI key as `ai-secrets` without displaying or writing it to a temporary file.
- [ ] Release: commit/push only reviewed deployment files/docs; guide creation of `u3-2-frontend` (path `k8s/frontend`) and `u3-2-ai` (path `k8s/ai`), manual sync, main, destination namespace/project `u3-2`.
- [ ] Live verification: check FE/AI image, readiness, endpoints, FE HTTPS/SPA/assets and unchanged BE APIs, plus internal AI health. Report remaining model/chat integration limits honestly.

## Verification notes

- Team quota confirmed via the Kubernetes API: requests/limits 4 CPU and 8Gi.
- Both rendered directories pass server dry-run. Combined steady limits with existing BE/DB are 2600m CPU / 3200Mi; FE rolling surge raises that to 2700m / 3328Mi.
- Shared-host routing, exact image tags, namespace, selectors and internal-only AI checks pass. Independent review found no actionable issue; stale FE wording in the CI guide was corrected.
- Exact AI amd64 image digest `sha256:c837dc383c679660e09dbe6a2bf32a1f0eac578c6c2df5bfa57175dd8d1658dd` passes isolated non-root UID10001/capability-free startup with 0.5 CPU/512Mi, health200 and missing-key chat503. No live model call was performed.
- Exact FE amd64 image digest `sha256:0af91638ba4fb1f80634b90d54839b012f74fbe865c9356e8db47b40d4144a74` passes isolated root/assets/SPA/API-proxy checks with the proposed runtime permissions and 100m/128Mi. Master/worker UIDs and graceful shutdown pass. Local QEMU emits an unsupported `io_setup` message; native EKS logs remain part of live verification, not a locally clean log claim.
- Secret registration has not occurred: automatic approval review rejected local AI key transfer to EKS because explicit approval of that source and destination is required. Ask for that approval after completing the unaffected preparation.
