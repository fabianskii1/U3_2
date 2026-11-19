# Image Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a successful main image build/push, update the corresponding FE/BE/AI deployment tag for Argo CD.

**Architecture:** Retain the three component CI workflows and reuse one manifest publishing job. Update only the active backend Green, AI Blue, or frontend image. Main requires a PR and one approval. The user selected a separate deployment branch: publish component snapshots to `gitops/dev`, retaining main protection and DB's main/Manual connection. The alternative of automatically creating reviewed release PRs was discussed and not selected.

**Tech Stack:** GitHub Actions, Git, Python standard library, existing Kustomize manifests.

**Spec:** The user's approval in this chat to implement automatic image-tag updates. Main protection discovered through the repository rules API on 2026-11-19.

## Global Constraints

- Only main builds that finish tests and Harbor push may publish; PR builds stay read-only.
- Use full source commit SHAs. Do not deploy source revisions that have been superseded for that component.
- Preserve unrelated concurrent component updates; use ordinary fast-forward pushes and retry conflicts, never force push.
- Do not change DB manifests, Secrets, Argo settings or cluster resources from CI.
- Retain dormant backend Blue and AI Green definitions and existing Service selectors.
- No new package dependency, PAT, AWS key, Argo token or production fixture is required for shared local validation.

## Review Focus

- Failed or PR CI must not publish a deployment.
- Concurrent FE/BE/AI publications must all survive.
- A delayed older successful build must not replace a newer deployed tag.
- Missing/duplicate aliases and invalid SHA input must fail without editing a manifest.
- Branch protection and GitHub write permissions must match the actual publication destination.

### Task 1: Shared tag editing

**Files:** `.github/scripts/update_image_tag.py`, `.github/scripts/test_update_image_tag.py`.

**Interface:** CLI `python update_image_tag.py MANIFEST ALIAS FULL_SHA`; expose `update_tag(text, alias, sha)` for the publisher. Reject ambiguous/missing aliases and non-SHA tags before writes; retain formatting and every other image.

- [x] Write and run the CLI behavior tests; observe the missing implementation fail.
- [x] Implement the editor and run the complete script test suite.

### Task 2: Publication and workflow integration

**Files:** publisher script/tests, one reusable workflow, existing BE/FE/AI workflows, `docs/ci.md`, deployment guides as needed.

- [x] Resolve the destination using the user's answer; preserve main rules and document the decision.
- [x] Write real temporary Git repository tests for publication, retry, stale source and idempotency; observe failure.
- [x] Implement publication with stale checks and conflict retries, then run all script tests.
- [x] Add main-only, successful-build-dependent reusable jobs; keep build job permissions read-only.
- [x] Validate workflow syntax, render manifests, review the diff and request a fresh focused review.
- [ ] Commit and create a PR. Leave main merge and Argo web changes to the user.

## Verification and review record

- Complete script suite: 16 tests pass using disposable local Git repositories; tests first failed without the editor/publisher.
- All workflows pass actionlint 1.7.12; all four Kustomize roots render. DB workflow and every Kubernetes YAML manifest remain byte-identical to base.
- Fresh independent review found three issues. Fixed the README-only freshness mismatch (regression RED→GREEN), ambiguous alias parsing/out-of-section edits (regressions RED→GREEN), and moving-main publisher checkout (pinned to the checked source SHA; actionlint passes).
- No GitHub Actions run, Harbor upload, GitOps branch publication or EKS update has been claimed as verified by these local checks. PR CI and first main publication are subsequent activation checks.
- No unresolved review findings, deferred minor items or unapproved policy changes.
