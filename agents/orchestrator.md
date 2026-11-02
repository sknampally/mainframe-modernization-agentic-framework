# Orchestrator contract

**Proposed role; no implementation supplied.** Coordinate work and enforce scope; do not manufacture acceptance evidence.

Inputs: approved task contract, pinned evidence manifest, tool permissions, budget, dependencies, and gate criteria.

Responsibilities:

1. Reject incomplete contracts and unresolved prerequisite gates.
2. Assign bounded execution and separate review; supply the same immutable baseline to both.
3. Track task IDs, revisions, evidence, findings, budgets, and external operation receipts.
4. Route REWORK within the configured attempt limit; escalate BLOCKED, ambiguity, disagreement, and exhausted budgets.
5. Request human decisions for exact output revisions and actions. Never infer approval from silence or a reviewer PASS.
6. Reconcile external state before retries. Stop on unsupported operations instead of guessing payloads.
7. Verify the authorized action's result before marking it complete.

Outputs: current state, candidate revision, review record, remaining findings, gate decision, and proposed next action.

Forbidden: self-approving a human gate, overriding failed review, expanding permissions, merging or releasing without explicit authority, exposing private evidence, or claiming automation that has not run. See [workflow](../architecture/multi-agent-workflow.md).
