# Compatibility matrix schema

The compatibility matrix is TOML validated by `rigsolve.matrix.schema`. Schema version 1 is intentionally flat: each `[[family]]` table is one auditable fact with its own `[family.source]` provenance table.

The implementation, not this prose, is authoritative. Validate every contribution with the installed version of rigsolve.

```bash
rigsolve --matrix candidate.toml matrix stats
```

## Metadata

Every matrix starts with:

```toml
[meta]
schema_version = 1
matrix_version = "2026.08.15"
generated = "2026-08-15"
description = "Optional scope and trust warning."
```

| Field | Required | Meaning |
|---|---:|---|
| `schema_version` | Yes | Must equal the supported integer schema, currently `1` |
| `matrix_version` | Yes | Non-empty data release identifier |
| `generated` | Yes | ISO date; no fact may have a later harvest date |
| `description` | No | Human-readable scope and caveats |

## Shared provenance

Every fact requires a nested `source` table.

```toml
[wheel.source]
kind = "gh-release"
repo = "Dao-AILab/flash-attention"
tag = "v2.8.3"
url = "https://github.com/Dao-AILab/flash-attention/releases/tag/v2.8.3"
harvested = "2026-08-15"
etag = "optional HTTP validator"
sha256 = "optional 64-character lowercase digest of the source document"
references = ["https://example.invalid/additional-upstream-evidence"]
```

Required provenance fields:

- `kind`: lowercase slug;
- `harvested`: canonical `YYYY-MM-DD` date;
- at least one of `url` (absolute HTTP(S)) or `repo` (`owner/name`).

Optional fields are `tag`, `path`, `confirmed_by` (positive integer), `etag`, `sha256`, and `references` (an array of additional absolute HTTP(S) evidence URLs). Unknown fields are rejected.

Every fact has a `tier` from 0 to 3. Some families default omitted tiers to 0, but contributions should state the tier explicitly. See [trust-model.md](trust-model.md).

## `wheel`

Records one wheel artifact and only dimensions encoded or independently established for that artifact.

```toml
[[wheel]]
package = "flash-attn"
version = "2.8.3"
cuda_line = "12"
torch = "2.9"
cxx11abi = true
python = "cp312"
abi = "cp312"
platform = "linux_x86_64"
url = "https://example.invalid/flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl"
filename = "flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl"
build_tag = "cu12torch2.9cxx11abitrue"
size = 123456
sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
archs = ["sm_89"]
yanked = false
tier = 0
```

Required: `package`, PEP 440 `version`, HTTPS `url`, `tier`, and `source`.

Optional dimensions for tier 0 are `cuda_line`, `torch`, `cxx11abi`, PEP 425-style `python`, `abi`, `platform`, and `archs`. Optional artifact metadata is `filename`, `build_tag`, non-negative `size`, `sha256`, `yanked`, and `yanked_reason`. A yanked reason requires `yanked = true`.

Tiers 1 through 3 require an immutable `sha256`, explicit `python`/`abi`/`platform` scope, and execution provenance whose `source.kind` is respectively `install-test`, `import-test`, or `gpu-run` (stronger kinds may support lower tiers). Known native GPU packages also require their CUDA line; torch extensions require their torch axis. Tier 3 additionally requires at least one recorded architecture. Non-wheel fact families remain tier 0 because they do not bind an executed result to one immutable artifact and environment.

An omitted CUDA or architecture field is unknown. Do not infer it from package reputation.

## `torch_build`

Records one PyTorch binary build axis.

```toml
[[torch_build]]
package = "torch"
version = "2.8.0"
cuda_line = "12.6"
cuda_exact = "12.6.3"
index_url = "https://download.pytorch.org/whl/cu126"
pythons = ["3.10", "3.11", "3.12", "3.13"]
platforms = ["linux_x86_64"]
cxx11abi = true
support = "build-axis"
tier = 0
```

Required: `version`, `cuda_line`, `index_url`, `tier`, and `source`. `package` defaults to `torch`. Optional fields are `cuda_exact`, `cxx11abi`, `pythons`, `platforms`, and `support` (`build-axis`, `stable`, or `experimental`). An exact CUDA version must belong to the declared line.

Build-script harvesting intentionally leaves ABI and platform empty when the script does not establish them.

## `tested_against`

Records an exact CUDA patch named by an upstream build or test source.

```toml
[[tested_against]]
package = "torch"
version = "2.8.0"
cuda_exact = "12.6.3"
note = "Exact version declared by the tagged binary-build script."
tier = 0
```

Required: `package`, `version`, `cuda_exact`, and `source`. `note` and `tier` are optional; tier defaults to 0.

## `constraint`

Records an NVIDIA driver floor for a CUDA runtime label.

```toml
[[constraint]]
kind = "driver-min"
compatibility = "minor-compatible"
cuda_runtime = "12.x"
min_driver = { linux = "525", windows = "528" }
note = "A driver floor, not a guarantee that every feature is available."
tier = 0
```

Required: `kind = "driver-min"`, `cuda_runtime`, non-empty `min_driver`, and `source`. Supported platform keys are `linux` and `windows`. `compatibility` is `minor-compatible` or `toolkit-corresponding`; `note` and `tier` are optional.

## `couple`

Records multi-package release relationships.

```toml
[[couple]]
kind = "compatible-release-set"
packages = ["torch", "torchvision", "torchaudio"]
versions = { torch = "2.8.0", torchvision = "0.23.0", torchaudio = "2.8.0" }
note = "Published release tuple."
tier = 0
```

Required: `kind`, at least two distinct `packages`, and `source`. Kinds are:

- `exact-version-lockstep`: listed installed packages must use the same version; `versions` may be empty.
- `compatible-release-set`: `versions` must contain exactly one version for every listed package.

`note` and `tier` are optional.

## `known_broken`

Records a negative fact with an actionable workaround.

```toml
[[known_broken]]
id = "project-issue-short-symptom"
description = "The precise failure and when it occurs."
match = { package = "flash-attn", version = "2.8.3", torch = "2.9" }
workaround = "Install the explicitly named compatible artifact."
tier = 0
```

Required: lowercase slug `id`, non-empty `description`, non-empty `match`, non-empty `workaround`, and `source`. Supported match fields are `package`, `version`, `torch`, `cuda_line`, `cxx11abi`, `python`, `platform`, and `source_build`. Package names are canonicalized, version scopes are directional, and every value is validated. `source_build` is useful when a failure applies only to a wheel path or only to a local build.

Use the narrowest match that reproduces the failure. A broad negative fact can exclude valid plans.

## `architecture`

Records the CUDA window in which an NVIDIA compute capability is supported.

```toml
[[architecture]]
arch = "sm_90"
cuda_min = "11.8"
note = "Toolkit-level architecture window, not a wheel kernel list."
tier = 0
```

Required: `arch`, at least one of `cuda_min` or `cuda_max`, and `source`. `arch` must look like `sm_90` or `compute_90`. `note` and `tier` are optional.

Architecture constraints and `wheel.archs` answer different questions. The former says a toolkit line can support an architecture; the latter says kernels were recorded for a particular artifact.

## `source_build`

Records an explicit fallback recipe. Source builds never appear unless the user supplies `--allow-source-build`.

```toml
[[source_build]]
package = "flash-attn"
version_spec = ">=2.8"
requirements = ["nvcc", "torch"]
flags = ["--no-build-isolation"]
estimate_minutes = 25
ram_gb_per_job = 2.0
note = "Estimate varies by host."
tier = 0
```

Required: `package` and `source`. Optional: `version_spec`, `requirements`, `flags`, positive `estimate_minutes`, positive `ram_gb_per_job`, `note`, and `tier`.

Build duration and memory are guidance, not guarantees. Cite the basis for them.

## Cross-fact validation

After individual fields parse, matrix validation rejects:

- duplicate keys within a fact family;
- any harvest date later than `meta.generated`;
- tier-3 wheel facts without an architecture;
- malformed or unknown top-level tables.

Merging is deterministic by fact key. The normal conflict policy selects the stronger tier, then newer harvest date, then a deterministic representation. Contributors can request strict conflict errors through the Python API when auditing data.

## Schema evolution

Pre-1.0 schema changes may occur with a changelog entry and migration guidance. Once the schema is declared stable, incompatible changes require a schema-version increment. Consumers should reject unsupported versions rather than guessing.
