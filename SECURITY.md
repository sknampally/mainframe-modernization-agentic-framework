# Security and public-content policy

This is a public documentation foundation with no deployed service or executable runtime. Security reporting and publication discipline still apply.

## Never publish

Credentials, tokens, private keys, session data, account/bucket/role identifiers, private endpoints, employer or client inventories, personal/customer data, internal logs, raw AWS Transform artifacts, or private artifact locations. Renaming an internal export does not make it public-safe. Use newly authored generic text and clearly labeled synthetic examples.

Keep private evidence outside the checkout, including ignored files. `.gitignore` is a convenience, not a security control; it does not protect already tracked files or history. Check diffs and commits before publication. Do not include sensitive details in issue bodies, PR descriptions, screenshots, or commit messages.

## Report privately

Do not open a public issue containing an exploit, secret, or private data. Use the repository's **Security > Report a vulnerability** option if available. Private vulnerability reporting has not been verified as enabled for this foundation. If unavailable, ask the owner through a public issue for a private reporting channel, without describing the sensitive finding or attaching evidence. No monitored security email or response SLA is claimed.

## If material is exposed

Stop further publication, notify the owner privately, and revoke or rotate exposed credentials immediately. Assess scope and access; coordinate any history cleanup with the owner. Deleting a file in a later commit does not remove it from Git history, forks, caches, or downloads. Do not republish the sensitive value in the cleanup report.

For future integrations, use least privilege, explicit tool scopes, bounded budgets, auditable human decisions, and external secret storage. These are design requirements, not implemented controls in this release.
