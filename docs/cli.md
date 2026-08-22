# CLI reference

This reference describes rigsolve 1.x. Global options precede the subcommand.

```text
rigsolve [--matrix PATH] [--version] COMMAND ...
```

| Global option | Meaning |
|---|---|
| `--matrix PATH` | Use a local matrix TOML instead of the bundled data plus validated cache |
| `--version` | Print the installed rigsolve version |
| `-h`, `--help` | Print help |

An internal `--debug` switch includes tracebacks for expected failures; it is intentionally omitted from normal help and should not be relied on as a stable interface.

## `detect`

```text
rigsolve detect [--json]
```

Profiles the current machine without importing torch. Human-readable output is the default; `--json` emits the machine profile for automation or a report you can inspect before sharing.

## `solve`

```text
rigsolve solve --want SPEC [SPEC ...]
  [--python VERSION]
  [--target TARGET]
  [--prefer verified|newest|stable|minimal-change]
  [--allow-source-build]
  [--output pip|uv|toml|docker|json|colab]
  [--write-lockfile PATH]
  [--execute]
  [--skip-verify]
```

`SPEC` accepts a package name or a PEP 440-style version request such as `torch==2.8.0` or `flash-attn>=2.8`.

`--target` accepts a comma-separated hypothetical profile. A typical value is:

```text
A100,driver=570.00,python=3.12,linux
```

The first free token is the GPU name. Recognized key/value tokens include `driver`, `python`, `nvcc`/`toolkit`, and `cuda_home`/`toolkit_path`; platform tokens such as `linux` can be supplied directly. Supply the toolkit version with a target toolkit path, for example `nvcc=12.4,cuda_home=/opt/cuda-12.4`. Unknown dimensions remain unconstrained.

Preference policies:

| Policy | Objective |
|---|---|
| `verified` | Prefer the deepest available evidence, then version preference |
| `newest` | Prefer newer compatible versions after core validity |
| `stable` | Prefer non-prerelease and non-development versions, then apply the normal evidence scoring |
| `minimal-change` | Penalize changes to discoverable installed versions |

`--allow-source-build` only creates source candidates when the matrix contains a matching `source_build` fact. Source steps carry available flags, toolkit paths, time estimates, and per-compiler-job RAM guidance through every applicable plan format and the TOML lockfile. A detected `.../bin/nvcc` path becomes `CUDA_HOME`; an explicit target can provide `cuda_home`. Host RAM is not part of `MachineProfile` (GPU VRAM is a different resource), so a known RAM-per-job requirement uses the deterministic conservative default `MAX_JOBS=1` instead of host-dependent probing.

The default output is `pip`. `--write-lockfile` writes the same resolved plan as deterministic TOML in addition to normal output. Dockerfile and Colab output require a Linux target. A source-build plan that cannot be represented faithfully as a uv project snippet is rejected with a recommendation to use pip, TOML, JSON, or Docker output.

`--execute` is the only solve option that installs; without it, every format is printed for review. Execution is intentionally limited to `--output pip` for the detected machine. It rejects hypothetical `--target` values and `--python` overrides so a plan cannot be executed against a different host. After installation, rigsolve runs isolated import checks and available GPU kernels for the selected packages. A failed probe returns exit code 2. `--skip-verify` disables only this post-install step and is valid only with `--execute`.

## `check`

```text
rigsolve check [--fix] [--lockfile PATH] [--output pip|uv|json]
```

Evaluates discoverable installed metadata against every applicable matrix fact. A clean report means “no violation was found among applicable known facts,” not “this environment has been GPU-tested.”

`--lockfile` also checks package versions, CUDA and torch build markers, C++ ABI, matrix identity, and the target dimensions recorded by a rigsolve TOML plan. Unknown local metadata is reported as a warning instead of being treated as proof of compatibility. `--fix` asks for a minimal-change repair plan and prints it; it never applies the plan. `--output` controls that repair-plan format and has an effect only with `--fix`.

## `why`

```text
rigsolve why SPEC [SPEC ...]
  [--target TARGET]
  [--python VERSION]
  [--allow-source-build]
```

Runs the same resolver as `solve`. A satisfiable request prints the chosen packages and a plain-language evidence label. An unsatisfiable request prints the reduced conflict, citations carried by its constraints, and available alternatives. Suggestions are bounded by the facts currently in the matrix and should be reviewed like an install plan.

## `verify`

```text
rigsolve verify
  [--package NAME]...
  [--no-gpu]
  [--timeout SECONDS]
  [--contribute]
  [--contribution-file PATH]
```

Each package import runs in a child interpreter. Without `--package`, rigsolve probes the intersection of installed distributions and built-in probes. Repeat `--package` to choose an explicit set.

`--no-gpu` stops at import verification. Otherwise, a package is reported as GPU-tested only if its probe contains and successfully runs a real GPU kernel. The current kernel probes are torch and flash-attn; the other built-ins are import-only.

`--contribute` writes a JSON payload, by default `rigsolve-verification.json`. At least one probe must run; when no supported installed package is found, `verify` exits nonzero and writes no contribution file. A failed probe still counts as a result. Nothing is uploaded. Review the file before sharing it.

## `matrix`

```text
rigsolve matrix update [--url URL] [--destination PATH] [--no-merge]
rigsolve matrix show [--package NAME] [--json]
rigsolve matrix stats [--json]
rigsolve matrix add FILE --destination PATH
```

- `update` conditionally fetches with ETag/Last-Modified metadata, validates the entire response, and atomically updates the user cache. By default the selected result merges over the current matrix. `--no-merge` selects the remote matrix alone.
- `show` prints metadata, digest, facts, tiers, and citations. `--package` filters relevant package-bearing facts.
- `stats` reports fact-family, package, evidence-level, source-kind, and harvest-date counts.
- `add` loads `FILE` as an independently valid matrix, merges it with the selected current matrix, validates the result, and atomically writes `--destination`.

## `doctor`

```text
rigsolve doctor
```

Reports the health of rigsolve's own probes, matrix, platform detection, and available NVIDIA tooling. It does not repair the machine. Missing optional NVIDIA commands are reported without making the command fail; a matrix older than the safety window exits with status 4 and recommends `rigsolve matrix update`.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Satisfiable request or healthy/applicable check |
| 1 | Unsatisfiable request or matrix-domain failure |
| 2 | Installed environment or smoke probe is broken |
| 3 | Detection failure |
| 4 | Matrix-staleness condition (reserved by the current error model) |
| 64 | Invalid user input or command usage |
| 70 | Unexpected internal error |
| 130 | Interrupted by the user |

Argument-parser failures are normalized to status 64, so invalid usage cannot be confused with a broken environment (status 2).
