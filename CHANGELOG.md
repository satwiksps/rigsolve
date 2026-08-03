# Changelog

This file records user-visible changes to rigsolve. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/satwiksps/rigsolve/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/satwiksps/rigsolve/releases/tag/v0.1.0
