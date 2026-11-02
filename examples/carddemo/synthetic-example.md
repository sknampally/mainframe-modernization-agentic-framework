# Synthetic contract walkthrough

**Invented behavior for illustrating traceability only. Not extracted from CardDemo, not executed, and not a financial specification.** All identifiers are synthetic.

| Field | Illustrative value |
| --- | --- |
| Rule | SYN-RULE-01 |
| Source | None; synthetic specification |
| Behavior | Accept a positive whole-unit transfer only when it does not exceed the available balance |
| State | Single in-memory balance; no fees, holds, concurrency, or currency conversion |
| Rejection | No balance change; return a defined rejection result |
| Oracle | Accepted transfer subtracts the amount exactly; rejected transfer leaves balance unchanged |
| Execution status | Not run |

| Test | Initial balance | Amount | Expected result | Expected balance |
| --- | --- | --- | --- | --- |
| SYN-TEST-01 | 100 | 30 | ACCEPTED | 70 |
| SYN-TEST-02 | 100 | 100 | ACCEPTED | 0 |
| SYN-TEST-03 | 100 | 101 | REJECTED | 100 |
| SYN-TEST-04 | 100 | 0 | REJECTED | 100 |
| SYN-TEST-05 | 100 | -1 | REJECTED | 100 |

An executor could implement this bounded specification. A reviewer must check the implementation against these explicit expectations and report real execution results. Human acceptance would apply only to that reviewed revision.

A source-derived pilot also needs actual legacy semantics for precision, rounding, invalid records, authorization, persistence, atomicity, concurrency, duplicate requests, restart, and audit trails. This small example cannot establish equivalence or deployment readiness.
