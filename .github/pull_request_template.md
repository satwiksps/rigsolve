## What changed

<!-- Describe the user-visible outcome and why this is the smallest useful change. -->

## Evidence

<!-- Link issues, upstream artifacts, documentation, or reproduction output. For matrix changes, explain the exact scope each source establishes. -->

## Verification

<!-- List commands run and important output. State hardware or platforms you could not test. -->

- [ ] Tests cover the behavior or this documentation-only change does not need a test.
- [ ] `ruff`, `mypy`, and relevant `pytest` checks pass locally.
- [ ] User-facing CLI, schema, or trust changes are documented.
- [ ] Generated plans remain review-first; installation still requires explicit `--execute`.

### Matrix changes only

- [ ] Every fact has an auditable source and harvest date.
- [ ] Tier 0 is described as derived, not verified.
- [ ] Tier 3 records the tested GPU architecture and a real kernel result.
- [ ] Unknown fields remain unknown; I did not infer CPU/GPU compatibility from absence.
- [ ] A `known_broken` fact has a narrow match and tested workaround.
- [ ] The deterministic TOML diff contains no unrelated harvest-date churn.

## Privacy and safety

- [ ] I removed credentials, private URLs, usernames, hostnames, and unreviewed machine metadata.
- [ ] This is not an undisclosed security vulnerability.
