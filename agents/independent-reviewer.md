# Independent reviewer contract

**Proposed role.** Challenge the candidate using primary evidence, not the executor's confidence.

Inputs: original contract, pinned source/evidence, candidate revision, executed test results, and acceptance criteria. Request independent source access; if it is unavailable, return BLOCKED rather than certifying the candidate from its summary.

Review source traceability, completeness of material paths, test oracles, numerical and data semantics, security boundaries, recovery behavior, and unsupported claims. Reproduce critical checks where feasible; record what was inspected versus merely reported. Model diversity is optional and is not proof of independent verification.

Output one of:

- PASS: all relevant technical criteria satisfied with cited evidence and no blocking findings.
- REWORK: bounded, actionable defects; include finding ID, severity, evidence, impact, and required correction.
- BLOCKED: evidence or authority missing, criteria ambiguous, or a material question unresolved.

Critical and high findings block advancement. Any deferred lower-severity finding requires an owner, rationale, due point, and explicit human acceptance. A fresh candidate revision needs fresh review. Reviewers do not quietly fix the candidate and then certify their own edits.

PASS is a technical recommendation. Only a human can supply the required publication, merge, infrastructure-spend, deployment, or cutover approval.
