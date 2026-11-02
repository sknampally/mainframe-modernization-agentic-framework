# Mainframe Modernization Agentic Framework

An evidence-driven reference framework for modernizing mainframe applications to C#/.NET, with independent review and human-controlled delivery gates.

**Status: reference framework with a local pilot runner and Kiro workflow controller.** The controller implements two-role handoffs/rework, existing local/S3 assessment input, and a resumable AWS Transform job adapter. Offline checks pass; live Kiro/AWS integration is not yet verified. There is no generated .NET application or equivalence harness, and no production-readiness or migration-success claim.

## Why this framework exists

Generated documentation is useful input, but it does not prove business behavior. A credible modernization must connect source evidence to validated requirements, implementation, and measured equivalence. This framework defines that chain and the decisions people must retain.

## Evidence and capability status

| Capability | Evidence status | Public repository status |
| --- | --- | --- |
| AWS Transform assessment | Prior assessment reported; new adapter tested with fixtures, not live AWS | Existing local/S3 input or new job with persisted identity and resume |
| Business-rule validation against pinned source | Required next step; not demonstrated here | Phase guide, rule-validation prompt, and review contract |
| Executor/reviewer coordination | Kiro controller implemented; offline fixtures verified, live run pending | Automatic source requests, candidate handoff, review, and bounded rework |
| .NET generation, data conversion, and equivalence | Not demonstrated | Delivery and acceptance methodology |
| Deployment, rollback, and autonomous operation | Not demonstrated | Human approval boundaries only |

A service reporting a completed assessment step does not establish correct requirements. A generated test plan is not an executed test suite. See [limitations](docs/limitations.md).

## Reference architecture — proposed

![Proposed reference architecture showing evidence discovery, executor and independent reviewer roles, bounded rework, human approval, and controlled delivery](docs/images/reference-architecture.svg)

[Open the full-size architecture diagram](docs/images/reference-architecture.svg).

<details>
<summary>Mermaid architecture view</summary>

```mermaid
flowchart LR
    subgraph Discover["1. Discover and ground"]
        direction TB
        S["Pinned mainframe source"] --> A["AWS Transform: candidate knowledge"]
        A --> E["Private evidence baseline"]
    end
    subgraph Validate["2. Execute and challenge"]
        direction TB
        O["Orchestrator: scope, budget, state"] --> X["Executor"]
        O --> R["Independent reviewer"]
        X -->|Candidate handoff| R
        X -->|Candidate and tests| G["Quality gate"]
        R -->|Independent review| G
        G -->|Bounded rework| O
        G -->|Missing evidence| B["BLOCK and escalate"]
    end
    subgraph Deliver["3. Approve and deliver"]
        direction TB
        H["Human approval: exact revision and action"] --> T["Target implementation: .NET on AWS"]
        T --> V["Equivalence and operational verification"]
        V --> D["Human release decision"]
    end
    E --> O
    G -->|Technical pass| H
```

</details>

Arrows describe intended responsibilities, not implemented integrations. The executor hands its candidate to the reviewer; the reviewer checks it against independently accessed pinned source and private evidence. Both the candidate and the review are required at the quality gate. A reviewer recommends technical acceptance; a human authorizes the next action. Missing evidence blocks advancement until resolved. The [detailed workflow](architecture/multi-agent-workflow.md) shows the execution/review sequence, rework, escalation, and approval invalidation.

C#/.NET and AWS are the intended direction. Blazor, storage, hosting, and migration strategy remain architecture decisions. Stable [task prompts](prompts/README.md) consume one shared local manifest. The [pilot runner](docs/running-a-pilot.md) manages evidence paths and handoff checks. Installed skills and an executable skill library remain future work. Kiro role orchestration is implemented in the separate controller; live integration remains unverified.

## Start here

The six phase guides and copyable prompts are available now. Use them with a shared task manifest; end-to-end model-driven execution and equivalence have not been demonstrated.

| Phase | Guide |
| --- | --- |
| 1 | [Scope and discovery](methodology/01-discovery.md) |
| 2 | [Requirements validation](methodology/02-requirements-validation.md) |
| 3 | [Target architecture](methodology/03-target-architecture.md) |
| 4 | [UI and data design](methodology/04-ui-and-data-design.md) |
| 5 | [Incremental implementation](methodology/05-implementation.md) |
| 6 | [Equivalence testing and release readiness](methodology/06-equivalence-testing.md) |

**Automated path:** follow [Kiro automation setup](docs/kiro-automation.md). Configure runtime/AWS access once; supply source plus optional local/S3 findings. The controller starts the two roles and manages their handshake. Omit findings to request a new authorized AWS assessment, then return later with `resume`.

**Manual diagnostic path:** the [pilot runner](docs/running-a-pilot.md) remains available for inspecting individual role operations. It is not the default fully coordinated workflow.

1. Read the [methodology](methodology/modernization.md) and [quality gates](quality-gates/README.md).
2. Define a bounded task using the [task contract](contracts/task-contract.yaml).
3. Assign the [orchestrator](agents/orchestrator.md), [executor](agents/executor.md), and [reviewer](agents/independent-reviewer.md) responsibilities. The Kiro controller dispatches the pilot roles; people can also use the manual role instructions.
4. Walk through the [synthetic CardDemo skeleton](examples/carddemo/README.md). Pin upstream source before making source-specific claims.
5. Record evidence, unresolved gaps, review results, and human decisions. Missing evidence blocks the relevant gate.

## Repository map

The current foundation contains the following files. The tree includes documentation and the initial controllers; code presence does not establish live-service acceptance.

```text
mainframe-modernization-agentic-framework/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── THIRD_PARTY.md
├── .gitignore
├── .github/
│   └── pull_request_template.md
├── architecture/
│   └── multi-agent-workflow.md
├── methodology/
│   ├── modernization.md
│   ├── 01-discovery.md
│   ├── 02-requirements-validation.md
│   ├── 03-target-architecture.md
│   ├── 04-ui-and-data-design.md
│   ├── 05-implementation.md
│   └── 06-equivalence-testing.md
├── prompts/
│   ├── README.md
│   ├── 01-executor.md
│   ├── 02-independent-reviewer.md
│   ├── 03-orchestrator.md
│   ├── 04-rule-validation-pilot.md
│   └── automated/
│       ├── executor.md
│       └── reviewer.md
├── agents/
│   ├── orchestrator.md
│   ├── executor.md
│   └── independent-reviewer.md
├── contracts/
│   ├── README.md
│   ├── task-contract.yaml
│   ├── review-record.yaml
│   └── approval-record.yaml
├── quality-gates/
│   └── README.md
├── examples/
│   ├── config/
│   │   └── kiro-settings.example.json
│   └── carddemo/
│       ├── README.md
│       └── synthetic-example.md
├── scripts/
│   ├── pilot.py
│   └── kiro_workflow.py
├── tests/
│   ├── test_pilot.py
│   ├── test_kiro_workflow.py
│   ├── test_mcp_transport.py
│   └── fixtures/
│       └── mcp_server.py
└── docs/
    ├── images/
    │   └── reference-architecture.svg
    ├── kiro-automation.md
    ├── limitations.md
    └── running-a-pilot.md
```

Installed `skills/` and `docs/lessons-learned.md` remain future additions; they are not part of the current tree. Lessons learned require actual reviewed execution evidence.

| Path | Purpose |
| --- | --- |
| [architecture](architecture/multi-agent-workflow.md) | Intended workflow, trust boundaries, and recovery |
| [methodology](methodology/modernization.md) | Discovery through cutover and rollback |
| [agents](agents/orchestrator.md) | Bounded role instructions |
| [prompts](prompts/README.md) | Stable role instructions consuming one task manifest |
| [Kiro automation](docs/kiro-automation.md) | Start/resume, existing or new assessments, two-role handoff and rework |
| [pilot runner](docs/running-a-pilot.md) | Manual diagnostic operations and record-integrity checks |
| [contracts](contracts/README.md) | Task, review, and approval record templates |
| [quality-gates](quality-gates/README.md) | Evidence required to advance |
| [examples/carddemo](examples/carddemo/README.md) | Sanitized case-study skeleton and synthetic example |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Attribution, validation, and PR process |
| [SECURITY.md](SECURITY.md) | Publication boundaries and vulnerability reporting |

## Delivery roadmap

- Foundation: method, roles, gates, diagrams, public boundaries, phase guides, and stable prompts are supplied.
- Local pilot runner: shared manifest, metered operations, sealing, and review preflight are implemented for manual diagnostics.
- Validation pilot: pin public source and validate one rule with independently reviewed evidence.
- Kiro controller: two-role dispatch, bounded rework, saved state, and AWS adapter implemented; real Kiro/AWS acceptance run pending.
- Implementation pilot: build one vertical .NET slice with measured equivalence and failure-path tests.
- Operational pilot: rehearse migration, recovery, observability, and rollback before any release claim.

Each milestone requires its own reviewed evidence; the roadmap is not a list of working features.

## Responsible publication and attribution

Publish original framework material and approved synthetic examples only. Never add employer or client inventories, credentials, cloud resource identifiers, private assessment exports, or raw AWS Transform artifacts. Redacting a few names from an internal export is insufficient.

This foundation was prepared with AI assistance using Codex. AI assistance does not imply independent validation. The repository owner reviews and decides what to merge; commit identity must match the owner's verified personal GitHub identity, without agent co-author attribution or concealment of assistance.

Original framework material is covered by the [MIT license](LICENSE). [AWS CardDemo](https://github.com/aws-samples/aws-mainframe-modernization-carddemo) is a separate upstream project with its own license; no application source or datasets are bundled here. See [third-party guidance](THIRD_PARTY.md).
