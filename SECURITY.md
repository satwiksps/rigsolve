# Security policy

## Supported versions

rigsolve is pre-1.0. Security fixes are provided for the current `0.1.x` line and the latest commit on `main`.

| Version | Supported |
|---|---|
| `0.1.x` | Yes |
| `< 0.1` | No |

## Reporting a vulnerability

Do not open a public issue for a vulnerability, exposed credential, malicious matrix source, command-injection path, unsafe plan execution, cache-integrity failure, or privacy leak.

Use [GitHub private vulnerability reporting](https://github.com/satwiksps/rigsolve/security/advisories/new). If that form is unavailable, contact [@satwiksps](https://github.com/satwiksps) and request a private channel before sending details.

Include, when safe:

- the affected rigsolve version and platform;
- the exact command or matrix input;
- the impact and a minimal reproduction;
- whether the issue requires an untrusted package, URL, or matrix;
- a suggested mitigation, if known.

The target response times are an acknowledgement within 7 days and an initial assessment within 14 days. These are best-effort targets for a volunteer-maintained project. Disclosure timing will be coordinated with the reporter when practical, and reporters may request credit or anonymity.

## Security boundaries

rigsolve produces review-first plans. Rendering a plan does not install software. Only an explicit `solve --execute` invocation against the detected local environment authorizes installation.

The compatibility matrix can contain artifact and index URLs that later become install commands. The project therefore treats schema validation, HTTPS-only executable URLs, provenance, artifact hashes where available, and atomic cache replacement as security boundaries. A valid tier-0 fact records sourced metadata; it is not an endorsement of an artifact.

The scheduled harvester has read-only repository permissions. It emits candidate data for human review and cannot create a branch, pull request, commit, or merge.

`rigsolve verify --contribute` writes a local JSON file and transmits nothing. Review the payload before sharing it because it can contain GPU, driver, platform, and installed-package metadata.

Ordinary compatibility bugs, false positives, and missing matrix coverage should use the public issue templates unless they enable code execution, data exposure, or a supply-chain attack.
