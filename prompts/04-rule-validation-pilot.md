# One-rule validation pilot prompt

This is the next practical step after a reviewed discovery baseline. It produces a candidate specification for review, not a .NET implementation or equivalence result.

For CardDemo, first pin a commit from the [public upstream](https://github.com/aws-samples/aws-mainframe-modernization-carddemo). Do not use the [synthetic walkthrough](../examples/carddemo/synthetic-example.md) as source evidence. No source commit or rule is preselected here; that selection requires direct inspection.

```text
ROLE: Executor validating one source-derived business rule.

TASK CONTRACT: <completed approved contract; read-only source inspection>
PUBLIC SOURCE REPOSITORY AND COMMIT: <repository and pinned commit>
BOUNDED BEHAVIOR: <one behavior, entry point, selected modules, exclusions>
EVIDENCE MANIFEST AND CLASSIFICATION: <approved reference and classification>
REVIEWER AND HUMAN OWNER: <separate reviewer and decision owner>
BUDGET: <attempts, calls, cost, deadline>

Validate placeholders and prerequisites before starting. If the selected
behavior has missing dependencies, record BLOCKED and identify what is needed.
Do not access private assessment bundles, cloud accounts, production data,
or external services beyond the task's explicit permissions.

1. Inspect the entry point, call context, relevant paragraphs/symbols,
   copybooks, constants, and dependencies at the pinned source revision.
2. Select one material rule. Document preconditions, trigger, outputs, state
   changes, error/rejection behavior, and applicable numeric/data semantics.
3. Cite repository, commit, file, symbol/paragraph, and meaningful line spans
   for each material claim. Separate verified, reported, inferred, proposed,
   and unknown claims. Do not invent missing behavior.
4. Derive deterministic expected results from the inspected source. Draft
   synthetic positive, rejection, and boundary cases; assess recovery and
   concurrency applicability. Explain exclusions and unknowns.
5. Record fixture inputs, initial state, expected outputs/state, source oracle,
   and test status. Mark NOT RUN unless execution was explicitly permitted
   and actually performed. Do not claim legacy/target equivalence.
6. Return a candidate specification, rule/source/test matrix, dependency gaps,
   checks performed, uncertainty, exact candidate revision, and a bounded
   independent-review request. Do not generate target code in this task.

Success means a reviewable candidate with inspectable source and explicit
oracles. It is not a verified result until separate review completes. Keep
private records outside the public repository. Publish only through a separate
sanitized, human-reviewed PR when specifically authorized.
```

Pass the fixed candidate to the [reviewer prompt](02-independent-reviewer.md). Record its actual findings before planning implementation. If the source cannot establish the oracle, ask the domain owner for the missing decision; do not strengthen the claim by generating more tests.
