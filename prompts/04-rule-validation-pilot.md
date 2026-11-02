# Manifest-driven one-rule validation pilot

Use the [executor prompt](01-executor.md) unchanged with one local task manifest. This specialization defines what a successful rule-validation candidate contains; it does not duplicate task paths or budgets.

## Input

One `task.json` created by [pilot initialization](../docs/running-a-pilot.md). The manifest records the selected behavior, entry point, pinned source, workspace, operation/time budgets, owner, permissions, and acceptance criteria. Unresolved task identity or missing input blocks execution.

## Source-validation procedure

1. Begin the executor role, then inspect the selected entry point and relevant callers, copybooks, constants, and dependencies through metered runner operations.
2. Establish one rule's preconditions, trigger, outputs/state, rejection behavior, and applicable numeric/data semantics. Cite repository, commit, source path, paragraph/symbol, and meaningful line spans.
3. Separate inspected facts from inferred language/runtime semantics. Missing source or unavailable compiler/runtime context must remain explicit. Do not fabricate dependencies or state effects.
4. Draft synthetic positive, rejection, and boundary cases with deterministic source-derived oracles. Assess recovery/concurrency applicability and explain exclusions. If an oracle is unresolved, label it unknown; reviewers must not PASS the affected criterion.
5. Write the candidate and traceability CSV through the runner, keeping all cases NOT RUN. Do not use the framework's synthetic example as a source rule.
6. Seal the artifacts within budget. The runner generates hashes and a handoff; no bespoke reviewer prompt is needed. A separate reviewer uses [the reusable review instructions](02-independent-reviewer.md) with the same manifest.

This pilot makes no legacy execution, target implementation, equivalence, publication, or release claim. For CardDemo, use a pinned revision of the public upstream selected during initialization; no private assessment export is needed.
