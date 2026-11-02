# Quality gates and human authority

These are proposed policy requirements. This repository does not yet enforce them in software or GitHub settings. A checklist is not a working control.

| Gate | Required evidence | Decision owner |
| --- | --- | --- |
| G0 — scope and access | Pinned source, rights to use it, data classification, explicit tool/action permissions, budget, and exclusions | Human scope owner |
| G1 — assessment baseline | Inventory and dependency reconciliation, tool status, missing-source register, reproducible evidence manifest | Reviewer recommends; human accepts baseline with recorded gaps |
| G2 — requirements | Source-linked material rules, deterministic oracles, negative/boundary paths, unresolved ambiguity resolved | Reviewer and business owner |
| G3 — target design | Architecture decisions, data and security semantics, cost assumptions, rollback plan, agreed performance and recovery objectives | Human architecture owner |
| G4 — implementation | Review of exact revision, reproducible build and tests, requirement links, dependency/security checks | Reviewer recommends; human authorizes merge |
| G5 — equivalence | Controlled legacy/target comparisons, record and control-total reconciliation, discrepancies, restart/concurrency/load/security/recovery results | Reviewer and business/operations owners |
| G6 — release | Approved release/environment, rehearsed cutover and rollback, monitoring, owners, residual-risk decisions | Human release owner |
| P — public publication | File-by-file rights and confidentiality review, staged-diff and history secret checks, verified personal attribution, accurate capability claims | Human repository owner through PR review |

## Fail-closed behavior

Missing evidence, unsupported operations, ambiguous expected results, or unresolved critical/high findings block the affected gate. Lower-severity deferrals require an explicit risk decision and owner. Human acceptance of an assessment with known gaps does not waive the requirements or equivalence gates.

No empty API response, silence, generic approval status, model agreement, or successful tool execution is a substitute for explicit approval of a defined action. If a tool lacks a documented finalization operation, record it as pending and escalate; do not alter content simply to force completion.

The owner reviews and merges all PRs. Agents must not push directly to main. Cloud resource creation, paid execution, public publication beyond the authorized PR, production data access, deployment, and cutover need explicit scoped authority. Budget and permissions are not inferred from a general modernization objective.

Before merging this foundation, review its license, public-content boundary, synthetic-example labels, and AI disclosure. Repository protections, automated secret scanning, and executable contract validation are future setup tasks unless separately verified.
