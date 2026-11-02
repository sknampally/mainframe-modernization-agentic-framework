# 01 — Scope and discovery

Purpose: establish what can be analyzed and what remains unknown before treating an assessment as a baseline. This is a manual guide; no discovery adapter is supplied.

## Inputs and prerequisites

An approved task contract, rights to inspect the source, a pinned commit, selected modules, evidence classification, and tool/action permissions. Use the [task template](../contracts/task-contract.yaml). Keep private evidence outside the checkout.

## Procedure

1. Record source repository and commit, selected directories, exclusions and reasons, relevant tool versions, and the owner of the scope decision.
2. Inventory online and batch entry points, COBOL and copybooks, BMS/maps, JCL/PROCs, scheduler definitions, datasets, database objects, messaging, utilities, assembler, and external calls. Count from inspected source; label tool-only counts as reported.
3. Resolve each selected entry point's reachable dependencies. Separate present, excluded, missing, and unresolved artifacts. Optional modules do not become in scope merely because a tool discovered them.
4. Record data layouts and access paths: keys, alternate indexes, record lengths, encoding, numeric representations, transaction boundaries, and known external ownership.
5. Reconcile the assessment output with source. Keep tool completion status separate from evidence completeness. Domain seeds alone do not establish complete decomposition.
6. Build an unknowns register. Record impact, affected behavior, evidence needed, and owner; prioritize missing dependencies that can change an oracle.
7. Submit the baseline for independent review. A human may accept a baseline with explicit gaps; those gaps still block affected downstream decisions.

## Deliverables

| Record | Required contents |
| --- | --- |
| Source manifest | Pinned revision, selected scope, exclusions, tool versions |
| Dependency map | Entry point, dependency, source reference, resolution status |
| Unknowns register | Gap, impact, affected scope, next evidence, owner |
| Assessment reconciliation | Source observation versus tool claim, discrepancies, status |

## Exit: G0 and G1

Scope/access authority is explicit; selected source is pinned; counts and dependencies reconcile or have recorded gaps; baseline review and human decision are captured. Missing source must never be silently replaced with a guessed rule.

Next: [requirements validation](02-requirements-validation.md). See [gates](../quality-gates/README.md).
