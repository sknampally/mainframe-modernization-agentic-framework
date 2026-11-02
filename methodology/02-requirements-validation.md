# 02 — Requirements validation

Purpose: turn extracted candidates into independently checked behavioral specifications. This is the recommended first practical pilot after discovery; generating more documentation is not a substitute.

## Inputs and prerequisites

A reviewed baseline, one bounded behavior with complete source dependencies, candidate rules if available, and a human domain owner. Use the [rule-validation prompt](../prompts/04-rule-validation-pilot.md). If evidence is incomplete, return BLOCKED for affected claims.

## Procedure

1. Select one behavior and its observable inputs, outputs, state, and error responses. Start small enough for independent review; do not select an arbitrary rule count as a quality goal.
2. Inspect the caller, paragraph/symbol, copybooks, constants, called routines, and relevant control flow at the pinned revision. Record repository, commit, path, symbol, and meaningful line spans.
3. Rewrite each candidate as preconditions, trigger, result, state changes, and failure conditions. Distinguish business behavior from incidental implementation details and intentional future changes.
4. Inspect positive, rejection, equality/boundary, invalid-data, and recovery paths. Classify a path as applicable, excluded with reason, or unknown; do not assert full coverage from a happy-path test.
5. Establish the oracle from source and, where available, controlled legacy execution. Record precision, rounding, ordering, return/status codes, and transaction semantics that affect the result.
6. Create synthetic test inputs with explicit expected outputs and state changes. Derive expected results independently of the target implementation. Mark tests NOT RUN until executed.
7. Ask a separate reviewer to inspect the primary source and challenge each claim. Resolve disagreements with evidence or an explicit domain-owner decision; model consensus does not resolve ambiguity.

## Required traceability matrix

| Field | Required value |
| --- | --- |
| Rule and status | Stable ID; verified, reported, inferred, proposed, or unknown |
| Source anchor | Repository, commit, path, paragraph/symbol, line span |
| Behavior | Preconditions, event, outputs, state changes, error behavior |
| Oracle | Source or controlled run supporting the expected result |
| Scenarios | Positive, negative, boundary, recovery; applicability and exclusions |
| Validation | Reviewer, exact candidate revision, decision, findings |
| Gaps | Missing dependencies, ambiguity, impact, owner |

## Exit: G2

Every material claim in the selected slice has inspected source evidence and deterministic expectations. Critical/high findings are resolved; assumptions and intentional behavior changes have domain-owner decisions. Review applies to an exact revision. Tests that were designed but not run remain unexecuted.

If legacy execution is unavailable, a source-backed specification can be reviewed, but behavioral equivalence remains unproven. State this limitation explicitly.

Next: [target architecture](03-target-architecture.md).
