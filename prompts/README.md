# Reusable pilot prompts

Use the prompts unchanged. Each role receives **one local task-manifest path**, not a rewritten prompt containing paths, hashes, and findings. The small [pilot runner](../scripts/pilot.py) creates the shared record, meters its own operations, seals executor artifacts, and checks reviewer prerequisites.

## Start once

Follow [running a pilot](../docs/running-a-pilot.md) to initialize the manifest outside the public checkout. Then tell your coding agent:

```text
Use the repository's prompts/04-rule-validation-pilot.md.
Task manifest: <the local task.json path printed by init>
```

In a separate reviewer session:

```text
Use the repository's prompts/02-independent-reviewer.md.
Task manifest: <the SAME local task.json path>
```

Only the task path changes. The manifest and handoff carry everything else. These short invocations select the stable repository instructions; they are not new task-specific prompts.

| Instructions | Responsibility |
| --- | --- |
| [Executor](01-executor.md) | Bounded source inspection and candidate artifacts |
| [Independent reviewer](02-independent-reviewer.md) | Independent primary-source checks and review record |
| [Coordinator](03-orchestrator.md) | Route recorded states and human decisions |
| [Rule-validation pilot](04-rule-validation-pilot.md) | Derive one rule and explicit test oracles |

The runner does not call models, prove reviewer independence, validate business semantics, enforce the editor's other tools, or authorize cloud operations. Its budget counts runner operations, not all editor tool calls. Direct source/tool bypass invalidates the attempt. These prompts are not installed skills. Broader implementation work still needs its own approved contract and the [executor role](../agents/executor.md).
