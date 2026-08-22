# Changelog

This file records user-visible changes to rigsolve. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-22

### Added

- Published versioned Sphinx documentation with tutorials, task guides, troubleshooting, CLI and Python API references, and offline PDF and EPUB builds.

### Changed

- Established the documented CLI, Python API, lockfile, matrix-schema, and JSON-output contracts for the 1.x line.
- Clarified the supported platform scope and the network and code-execution boundaries of verification.
- Updated the README, project site, package metadata, and CI to use the canonical documentation and release identity.

### Fixed

- Rejected empty execution overrides and non-finite verification timeouts instead of bypassing safeguards or returning internal errors.
- Made zero-result and unsupported verification requests fail clearly without writing false contribution evidence.
- Checked lockfiles against toolkit, runtime, ABI, Python, platform, and artifact details.
- Rejected invalid matrix filters, malformed update URLs, incomplete offline harvest caches, invalid CUDA labels, and unsupported driver operating systems with actionable errors.
- Replaced matrix, cache, lockfile, and verification output files atomically so failed writes preserve existing state.
- Reported failed website clipboard operations and rejected malformed production origins.

### Security

- Required annotated release tags from `main`, cross-checked all version metadata, pinned build tooling, and prevented release artifacts from being overwritten on retry.

## [0.1.2] - 2026-08-16

### Added

- Codecov reporting with OIDC authentication.
- Grouped monthly Dependabot updates.
- Wide and square social cards plus an SVG README banner.

### Changed

- Shortened the README, landing page, package description, and browser title.
- Removed decorative arrows and em dashes from public copy.

## [0.1.1] - 2026-08-16

### Added

- `solve --execute` now runs isolated import checks and available GPU kernel probes after installation.
- `--skip-verify` supports deliberate install-only workflows.

### Changed

- Human-readable output uses `metadata-backed`, `install-tested`, `import-tested`, and `GPU-tested` labels instead of exposing internal numeric evidence levels.
- Documentation now separates matrix evidence depth from local installation readiness.

## [0.1.0] - 2026-08-16

### Added

- Machine profiling for NVIDIA GPUs, drivers, CUDA toolkits, Python, platform, and installed package metadata without importing torch.
- Evidence-backed resolution for torch, CUDA, Python, platform, GPU architecture, C++ ABI, native-extension coupling, and known-broken combinations.
- `detect`, `solve`, `check`, `why`, `verify`, `matrix`, and `doctor` commands.
- Deterministic pip, uv, TOML lockfile, Dockerfile, JSON, and Colab plan output.
- Minimal-change repair planning and reduced conflict explanations with source citations.
- Crash-isolated import checks and GPU smoke probes for torch and flash-attn.
- A provenance-enforced compatibility matrix with verification tiers and immutable artifact hashes where upstream supplies them.
- Read-only upstream harvesting that produces reviewable workflow artifacts without creating branches or pull requests.
- A Next.js project site and complete contributor, conduct, security, and citation documentation.

### Security

- Installation is opt-in: plan rendering never installs packages, and execution requires an explicit `solve --execute` invocation against the detected local environment.
- Executable artifact and index URLs require HTTPS, and matrix updates are validated before atomic replacement.

[Unreleased]: https://github.com/satwiksps/rigsolve/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/satwiksps/rigsolve/compare/v0.1.2...v1.0.0
[0.1.2]: https://github.com/satwiksps/rigsolve/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/satwiksps/rigsolve/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/satwiksps/rigsolve/releases/tag/v0.1.0
