# Trust and verification model

rigsolve separates three questions that are commonly collapsed:

1. **Does an artifact or documented build axis exist?**
2. **Can it install and import in a particular environment?**
3. **Did a real kernel run on a particular GPU?**

The answer to the first question must never be presented as an answer to the third.

## Verification tiers

| Tier | Name | Minimum evidence |
|---:|---|---|
| 0 | Derived | Parsed upstream artifact metadata or an upstream documented constraint |
| 1 | Installs | Successful installation in a recorded isolated environment |
| 2 | Imports | Successful import with the available build metadata recorded in that environment |
| 3 | Runs | Successful minimal real kernel on a recorded GPU architecture |

Each plan reports its weakest participating tier. If ten facts are tier 3 and one is tier 0, the plan is tier 0.

Tier is evidence depth, not a probability and not a quality score. Tier 3 on one environment does not establish universal compatibility. OS, architecture, Python ABI, glibc, driver, CUDA runtime, torch version, extension build, and container image can all be load-bearing.

## Provenance

Every admissible fact has:

- a lowercase source kind;
- an ISO harvest date;
- at least one stable locator: an HTTPS URL or `owner/repository`;
- optional tag, path, ETag, SHA-256 digest, or confirmation count.

The schema rejects missing provenance. Human review then asks whether the source supports the exact scope of the fact. A GitHub release asset can support “this named wheel existed”; it cannot, without execution evidence, support “this wheel runs on an RTX 4090.”

## Unknown values

Unknown means unconstrained or not demonstrated, depending on context. It does not mean:

- CPU-only;
- compatible with every value;
- incompatible with every value;
- supported by the upstream project.

For example, a wheel with no recorded `archs` field does not claim kernels for all architectures. A PyPI filename with no CUDA marker does not prove the project is CPU-only.

## Negative facts

`known_broken` facts are first-class because an artifact can exist, install, and still fail. Each negative fact has a narrow match table, symptom, workaround, and source. It excludes matching solver assignments and becomes a direct checker violation when the installed metadata is sufficient to match it.

Anecdotes are useful issue reports but should not become broad negative facts without reproducible detail. Confirmation count strengthens provenance; it does not automatically widen scope.

## Local verification

`rigsolve verify` uses child processes so a native crash is isolated. A successful import can establish tier 2. Only probes with real GPU code can establish tier 3, and only when that code returns successfully. Today, real kernel probes exist for torch and flash-attn; other built-in probes are import-only.

`--contribute` serializes the result and machine profile locally. It does not attest the host, sign the payload, or upload it. Maintainer review is required before converting that payload into matrix data.

## Current seed

As of matrix `2026.08.15`, the bundle has 114 facts and every fact is tier 0. It includes one narrowly scoped `known_broken` fact for the flash-attn `2.8.3.post1` filename edge. This is an auditable starting point, not production-grade coverage.

Use the installed copy as the source of truth:

```bash
rigsolve matrix stats --json
rigsolve matrix show --package flash-attn
```

Cached updates may make local counts differ from the bundled seed.
