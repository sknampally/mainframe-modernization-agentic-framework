# Reusable modernization prompts

These are vendor-neutral, copyable task instructions for manual use. They are not installed Codex skills, executable agents, a model router, or a tested orchestration service. They have not yet been validated in an end-to-end modernization pilot.

## Choose a prompt

| Prompt | Use it to | Required guide |
| --- | --- | --- |
| [Executor](01-executor.md) | Produce one bounded, evidence-linked candidate | [Implementation](../methodology/05-implementation.md) |
| [Independent reviewer](02-independent-reviewer.md) | Challenge a candidate against primary evidence | [Requirements validation](../methodology/02-requirements-validation.md) |
| [Orchestrator](03-orchestrator.md) | Coordinate manual task state, budgets, review, and decisions | [Workflow](../architecture/multi-agent-workflow.md) |
| [Rule-validation pilot](04-rule-validation-pilot.md) | Validate one source-derived rule before target implementation | [Discovery](../methodology/01-discovery.md) and [validation](../methodology/02-requirements-validation.md) |

## Before using any prompt

1. Copy the task text into an approved environment. Replace every angle-bracket placeholder with approved values; unresolved placeholders block execution.
2. Supply the completed [task contract](../contracts/task-contract.yaml), pinned baseline, acceptance criteria, budget, and permitted tools/actions. Empty permission lists authorize no tool use or external mutation.
3. Keep sensitive source, manifests, outputs, access references, and operational records outside this public checkout. Use only tools and model services approved for the evidence classification.
4. Assign a separate reviewer with independent source access. No prompt authorizes an agent to approve itself or supply a human decision.
5. Inspect the output and use the [review](../contracts/review-record.yaml) and [approval](../contracts/approval-record.yaml) templates. They are manual records, not enforced schemas.

Start with one public-source rule using the pilot prompt. Pass its source-backed output to a separate reviewer; only then consider a target implementation task. Do not run all prompts against an entire application and call the result validated.
