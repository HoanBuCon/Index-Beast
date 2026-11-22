# Live review prompt — TV3 Jina reranker

## Mission and fixed point

Act as the tech lead orchestrating a read-only review and controlled live evaluation of the uncommitted Jina reranker change in `D:\Index-Beast`. The fixed point is `65a9b7301b90755ea55d69844a157e8176ade0da` on branch `feature/s4-tv3-api-reranker`. Review `git diff HEAD` plus the untracked `backend/tests/unit/test_reranker*.py` and `docs/handover/2026-11-16_s4-tv3_jina-reranker.md`. There are no commits since the fixed point in this review scope.

The user authorized review, fixes when justified, reproducible regression tests for fixes, and the bounded live run described below. Preserve all pre-existing local work, including `.env` and user keys. Do not expose, copy, print, log, or include secrets in reports. Do not commit, push, merge, or alter the fixed point.

## Independent review roles

Run two isolated reviews, then reconcile them:

1. **Standards review:** Read `docs/AGENTS.md`, `docs/quy_uoc.md`, `backend/pyproject.toml`, and the installed `code-review` and `code-review-and-quality` skill instructions. Report only substantiated documented breaches as hard findings, citing file and the exact rule. Treat Fowler smells as judgment calls, using only: Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest. Repo rules override smells. Ignore tooling-only nits. Verify reachable callers, guards, and tests before reporting. Distinguish pre-existing issues from regressions.
2. **Spec review:** Compare implementation and tests with this prompt and the handover. Check optional/default-off Jina behavior, no-key handling, provider payload/response validation and fallback, candidate cap/tail behavior, preservation of hit provenance/score, single shared client with app lifespan cleanup, bounded provider quota/timeouts, integration through both Agent and compatibility paths, and documentation accuracy.

Use focused findings with severity, evidence, and a concrete remedy. Do not invent findings. No external API calls, tests, builds, network access, or other mutation during review. Do not inspect or display `.env` contents.

## Authorized corrections

If a high-confidence defect is found, fix only that defect and add a deterministic local reproduction test that fails before and passes after the fix. Do not broaden scope. Keep the user's changes intact and report each changed file and verification command/result accurately. Do not run unrelated suites or builds.

## Bounded live evaluation

Use the existing live runner and configured Jina, DeepSeek, and Tavily integrations only for a maximum of **5 MAIN E2E questions total, including any follow-up turns**. Count a main question and every clarification/follow-up in that question's budget. No standalone billable probes, smoke calls, retries, or exploratory calls outside those cases. Select a small, representative set that can assess generalization; add a controlled regression case only if needed and within the same five-question cap. Use only locally cached embedding assets. Do not download models, reindex, or alter the corpus. Preserve current API quota/timeouts and avoid parallel calls that multiply spend.

Report the exact question count, follow-up count, configurations, outputs/artifact paths, provider errors, and what the results can and cannot establish. Never claim quality improvement without a valid comparison. Separate static review, local reproduction tests, and live outcomes; state clearly which steps were actually performed. If a live case fails, do not silently retry it or replace it with another billable request.

## Final report

Summarize standards and spec findings separately, then fixes and their local regression evidence, then the bounded E2E results. State the fixed point and scope, preserve confidentiality, identify unresolved risks, and make no commit/push/merge claim other than accurately stating none was performed.
