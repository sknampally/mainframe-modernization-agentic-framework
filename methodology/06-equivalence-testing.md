# 06 — Equivalence testing and release readiness

Purpose: compare controlled legacy and target behavior, then establish operational readiness. A test plan or source review alone cannot prove equivalence.

## Inputs and prerequisites

Pinned source and target revisions, authorized legacy and target environments, validated oracles, identical controlled fixtures and initial state, agreed tolerances, operational objectives, and a bounded execution budget. If a legacy environment is unavailable, mark differential verification BLOCKED rather than inventing baseline results.

## Procedure

1. Freeze code, data fixtures, environment/tool versions, business clock, configuration, and external dependencies for the comparison. Record allowed normalization rules in advance; never normalize away a discrepancy after observing it without review.
2. Run matched cases against both systems. Compare observable outputs, persisted state, record counts/control totals, return codes, ordering, and relevant audit effects.
3. Cover positive, rejection, numeric/encoding boundaries, authorization, online transaction behavior, concurrency, duplicate requests, and batch sequencing where applicable. Record justified exclusions and gaps.
4. Test interruption, restart/rerun, checkpoint recovery, duplicate posting, scheduler failures, GDG or equivalent version rollback, and reconciliation where applicable.
5. Measure load, latency, throughput, error behavior, recovery objectives, and rollback under agreed conditions. State environment and denominator; do not extrapolate a small pilot to an application portfolio.
6. Record every discrepancy with expected/actual results, impacted requirements, severity, reproduction, and owner. Separate defects from explicitly approved behavior changes.
7. Re-run affected comparisons after fixes and obtain fresh independent review. Obtain business/operations acceptance of residual risk and the exact release/environment decision.

## Result record

For each case, record requirement and test IDs, fixture revision, initial state, legacy/target revisions, environment, expected and actual results, normalization applied, PASS/FAIL/BLOCKED/NOT RUN, discrepancy IDs, and reviewer. Keep private execution records outside the public checkout.

## Exit: G5 and G6

G5 requires executed comparisons and operational evidence meeting agreed criteria, with critical/high discrepancies resolved. G6 additionally requires rehearsed cutover and rollback, named operational owners, monitoring and rollback triggers, and explicit human release authorization.

After release, verify the approved health and reconciliation checks. If rollback criteria trigger, follow the authorized runbook and record actual outcomes. This guide authorizes no deployment, resource creation, production-data use, or cutover.
