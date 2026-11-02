# Record templates

These YAML files are manually populated design templates, not machine-validated schemas or executable policies. These general YAML templates have no enforcement engine. The separate [pilot runner](../docs/running-a-pilot.md) generates and checks its own narrower JSON task manifest; it does not validate these YAML records. Replace every `REQUIRED` value before use; an incomplete record blocks its gate.

- [Task contract](task-contract.yaml): scope, baseline, permissions, acceptance criteria, and budget.
- [Review record](review-record.yaml): exact output revision, reproducible evidence, and blocking findings.
- [Approval record](approval-record.yaml): explicit human decision for one action and revision.

Keep populated operational records in an approved private location. Public examples must be synthetic and must never include private storage paths, account identifiers, access links, or raw tool outputs. Linking to a private artifact from a public file can itself disclose sensitive metadata.
