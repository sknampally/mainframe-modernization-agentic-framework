# 04 — UI and data design

Purpose: make observable interfaces and data semantics explicit before implementation. Screen resemblance and schema conversion alone do not establish equivalence.

## Inputs and prerequisites

Validated behavior, approved target decisions, relevant BMS/copybooks and record/database layouts, synthetic fixtures, and authorization/data ownership requirements.

## Procedure

1. Describe each selected online interaction: input fields, validation, navigation, messages/status, session state, authorization, and commit/rollback behavior. Separate intentional UX changes from required compatibility.
2. Define API/domain contracts with error semantics, ordering, idempotency, and transaction boundaries. Record which requirements each contract implements.
3. Map source fields to target representations, including encoding, length, sign, decimal precision/scale, rounding/truncation, date rules, null/blank handling, and invalid input behavior.
4. Characterize COMP/COMP-3, REDEFINES, OCCURS, variable record formats, and collating sequences where applicable. Check byte-level fixtures and round-trip behavior; never infer semantics from a display value alone.
5. Map VSAM keys and alternate indexes or database constraints to target uniqueness, lookup, ordering, and consistency behavior. Record inferred relationships as inferred until verified.
6. Specify conversion/reconciliation controls: record counts, rejected records, duplicate keys, control totals, hashes where meaningful, and explicit tolerances. Explain any lossy conversion and require approval.
7. Define restartable conversion, checkpoint and duplicate handling, rollback boundaries, and access controls. Use synthetic fixtures; production data is outside the default scope.

## Deliverables

UI/API contracts; field-level mapping; transaction and authorization matrix; synthetic encoding/numeric fixtures; conversion and reconciliation plan; failure/recovery cases; reviewed unresolved gaps.

## Exit: G3 design readiness

Material fields and interactions have explicit semantics and testable expectations. Data and security owners review intentional deviations. A fixture set is not conversion evidence until the conversion has actually run.

Next: [implementation](05-implementation.md).
