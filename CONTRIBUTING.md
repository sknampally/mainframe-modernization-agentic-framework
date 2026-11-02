# Contributing

Use a feature branch and a pull request. The repository owner reviews and merges every PR. Do not push directly to main or enable automated merges without explicit owner authorization.

## Before committing

- Verify the authenticated GitHub login is the intended personal account. Check effective Git author and committer identities, including environment overrides, and verify that their email belongs to that account.
- Do not use an agent identity or add agent co-author trailers. Never forge another person's identity. If attribution cannot be verified, prepare changes without committing and ask the owner to complete identity setup.
- Disclose material AI assistance in the PR and relevant documentation. Personal commit attribution does not mean the content was written without assistance.
- Publish only original or appropriately licensed material. Link to upstream projects when redistribution is unnecessary.

## Required review

1. Read the entire diff, including filenames and hidden files. Remove confidential context and private resource metadata rather than masking selected values.
2. Check staged files and any new commits for secrets, cloud identifiers, internal paths, raw exports, client inventories, and personal data. Secret scanners support but do not replace this review.
3. Validate relative links, YAML templates, and Mermaid rendering. Mark unexecuted examples and proposed capabilities explicitly.
4. For executable changes, run checks appropriate to the behavior and report actual outcomes. Documentation-only changes do not establish runtime correctness.
5. Describe the concrete change, evidence, limitations, and AI assistance in the PR. List any checks not performed.

Do not add raw evidence dumps, vendored source, infrastructure, dependencies, or CI permissions merely to decorate the foundation. Introduce executable capabilities in separate, bounded PRs with meaningful validation.

Security reports follow [SECURITY.md](SECURITY.md). Be direct and respectful in review; challenge claims using evidence, not credentials or model confidence.
