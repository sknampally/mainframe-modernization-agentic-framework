# Mainframe Modernization Agentic Framework

An evidence-driven reference framework for modernizing mainframe applications to C#/.NET, with independent review and human-controlled delivery gates.

**Status: framework foundation — documentation, contracts, and templates.** This repository does not yet contain an executable orchestrator, AWS Transform adapter, generated .NET application, or an equivalence test harness. It makes no production-readiness or migration-success claim.

## Why this framework exists

Generated documentation is useful input, but it does not prove business behavior. A credible modernization must connect source evidence to validated requirements, implementation, and measured equivalence. This framework defines that chain and the decisions people must retain.

## Evidence and capability status

| Capability | Evidence status | Public repository status |
| --- | --- | --- |
| CardDemo assessment and draft test planning with AWS Transform | Reported in a prior private workflow; not independently reproduced here | Sanitized lessons only; no raw outputs |
| Business-rule validation against pinned source | Required next step; not demonstrated here | Method and review contract |
| Executor/reviewer/orchestrator collaboration | Proposed automation | Role contracts and workflow diagrams |
| .NET generation, data conversion, and equivalence | Not demonstrated | Delivery and acceptance methodology |
| Deployment, rollback, and autonomous operation | Not demonstrated | Human approval boundaries only |

A service reporting a completed assessment step does not establish correct requirements. A generated test plan is not an executed test suite. See [limitations](docs/limitations.md).

## Reference architecture — proposed

```mermaid
flowchart TD
    S[Approved pinned mainframe source] --> A[Assessment tools including AWS Transform]
    A --> E[Private evidence store]
    S --> E
    E --> O[Orchestrator: scope and state]
    O --> X[Executor: candidate output]
    X --> R[Independent reviewer: source and test checks]
    E --> R
    R --> G{Quality gate}
    G -->|Rework| O
    G -->|Missing evidence or disagreement| H[Human decision]
    G -->|Pass| H
    H -->|Approve scoped next stage| T[Target design and .NET implementation]
    T --> V[Equivalence and operational verification]
    V --> D[Human release decision]
```

Arrows describe intended responsibilities, not implemented integrations. The target stack is a design decision: C#/.NET and AWS are the intended direction; UI, storage, hosting, and migration strategy require evidence and architecture decisions.

## Start here

1. Read the [methodology](methodology/modernization.md) and [quality gates](quality-gates/README.md).
2. Define a bounded task using the [task contract](contracts/task-contract.yaml).
3. Assign the [orchestrator](agents/orchestrator.md), [executor](agents/executor.md), and [reviewer](agents/independent-reviewer.md) responsibilities. A person can perform each role today; automated coordination is future work.
4. Walk through the [synthetic CardDemo skeleton](examples/carddemo/README.md). Pin upstream source before making source-specific claims.
5. Record evidence, unresolved gaps, review results, and human decisions. Missing evidence blocks the relevant gate.

## Repository map

| Path | Purpose |
| --- | --- |
| [architecture](architecture/multi-agent-workflow.md) | Intended workflow, trust boundaries, and recovery |
| [methodology](methodology/modernization.md) | Discovery through cutover and rollback |
| [agents](agents/orchestrator.md) | Bounded role instructions |
| [contracts](contracts/README.md) | Task, review, and approval record templates |
| [quality-gates](quality-gates/README.md) | Evidence required to advance |
| [examples/carddemo](examples/carddemo/README.md) | Sanitized case-study skeleton and synthetic example |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Attribution, validation, and PR process |
| [SECURITY.md](SECURITY.md) | Publication boundaries and vulnerability reporting |

## Delivery roadmap

- Foundation: document the method, roles, gates, and public boundaries (this change).
- Validation pilot: pin public source and validate one rule with independently reviewed evidence.
- Automation pilot: implement and test one task adapter, durable state, bounded retries, and approval enforcement.
- Implementation pilot: build one vertical .NET slice with measured equivalence and failure-path tests.
- Operational pilot: rehearse migration, recovery, observability, and rollback before any release claim.

Each milestone requires its own reviewed evidence; the roadmap is not a list of working features.

## Responsible publication and attribution

Publish original framework material and approved synthetic examples only. Never add employer or client inventories, credentials, cloud resource identifiers, private assessment exports, or raw AWS Transform artifacts. Redacting a few names from an internal export is insufficient.

This foundation was prepared with AI assistance using Codex. AI assistance does not imply independent validation. The repository owner reviews and decides what to merge; commit identity must match the owner's verified personal GitHub identity, without agent co-author attribution or concealment of assistance.

Original framework material is covered by the [MIT license](LICENSE). [AWS CardDemo](https://github.com/aws-samples/aws-mainframe-modernization-carddemo) is a separate upstream project with its own license; no application source or datasets are bundled here. See [third-party guidance](THIRD_PARTY.md).
