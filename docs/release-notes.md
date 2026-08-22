# Release notes

rigsolve follows semantic versioning. The documented public API and serialized formats are stable within the 1.x line. Backward-incompatible changes require a major release.

For the authoritative entry list, see the repository [CHANGELOG.md](https://github.com/satwiksps/rigsolve/blob/main/CHANGELOG.md).

## 1.0.0

- Establishes the stable 1.x CLI, Python API, lockfile, matrix-schema, and JSON-output contracts.
- Rejects empty execution overrides, invalid verification timeouts, unsupported probes, and package filters that match no facts.
- Checks lockfiles against toolkit, runtime, ABI, Python, and platform details.
- Uses atomic replacement for matrix, cache, lockfile, and verification-output writes.
- Adds the versioned documentation site and hardens the website and release workflow.

## 0.1.2

- Published the Python package and console entry point.
- Expanded the bundled matrix to 114 sourced facts.
- Added stricter evidence validation, known-broken scoping, platform checks, and lockfile validation.
- Hardened execution guards and plan rendering.
- Added local verification and release automation.

## 0.1.1

- Added package and documentation corrections made after the initial release.
- Aligned public project metadata and installation guidance.

## 0.1.0

- Initial public alpha with machine detection, constraint solving, diagnosis, verification, matrix tooling, and multiple plan formats.

## Versioned documentation

Read the Docs builds the default branch as `latest`. Release tags are activated as immutable documentation versions. The `stable` alias should point to the newest supported release tag.
