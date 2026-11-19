# FE and AI first deployment

User intent: continue the existing GitOps rollout with FE and AI after BE/DB. The user has expanded the namespace quota to 4 CPU / 8Gi; the actual quota has been checked.

## Agreed context and implementation choices

- Existing EKS cluster/namespace/project: `skala-us` / `u3-2` / `u3-2`.
- Argo CD reads `https://github.com/fabianskii1/U3_2.git`, revision `main`, separate manual Applications.
- FE: one `frontend` Deployment with rolling updates, one internal Service, HTTPS `/` Prefix Ingress at `u3-2.skala-us.com`, class `nginx`, TLS `team-tls`. Preserve BE's existing `/api` and `/health` Ingress paths; use no rewrite/regex.
- FE image: `harbor.skala-us.com/u3-2/frontend:33e74a2bfb9294d4467bd4802cf2ade741a7dba0`, verified successful CI. The existing image listens on 80 and uses `BACKEND_UPSTREAM=backend:8000`. Keep image behavior compatible, including Nginx runtime permissions.
- FE initial resources: request 50m/64Mi, limit 100m/128Mi, replicas 1, maxSurge 1, maxUnavailable 0. These are starting allocations, not throughput guarantees.
- AI: keep two existing manual Blue-Green Deployments and `ai` / `ai-preview` internal Services on 8001. Both initial images use `harbor.skala-us.com/u3-2/ai:67117a2d12d688e030080e4c20e965bcad85eb36`, verified successful CI. Initial active slot is Blue.
- AI resources remain request 100m/128Mi, limit 500m/512Mi per slot. UID/GID 10001, probes and current security settings must work with the actual image.
- AI is reached by BE on `http://ai:8001`; do not expose a separate AI Ingress or keep a rewrite that can affect the shared host.
- Register only the AI API key in `ai-secrets` / `OPENAI_API_KEY`, from the existing ignored local AI environment file. Do not print, commit or save secret values to scratch files. Keep the existing default model `gpt-4.1`.
- Existing BE/DB resources, images, selectors, schema and data are out of scope. BE's old equipment-lookup chat and AI's plain-chat contracts remain incompatible; do not change business code or claim full chat integration.

## Approach

Reuse existing successful images and namespace platform services. A single FE Deployment is sufficient for this first rollout; the existing manual AI Blue-Green configuration preserves the already chosen release process. No new cluster, VM, ingress controller, persistent storage, CI image or shared platform change is needed.

## Completion conditions

Render and server-validate both Kustomize directories; account for FE update surge within the 4 CPU/8Gi quota; verify actual image startup under proposed runtime settings. Push only the reviewed deployment files/docs. Because local Argo CD credentials are unavailable, ask the user to create/sync the two Applications. Afterwards verify Pod images/Ready state, FE assets/SPA and existing HTTPS APIs, and AI internal health. A paid model call is optional and must not be confused with a successful BE chat integration.
