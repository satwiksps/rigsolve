# Resolve package compatibility

`rigsolve solve` selects a complete package assignment and renders an ordered installation plan.

## Requirement syntax

Pass one or more PEP 508 package requirements after `--want`:

```console
$ rigsolve solve --want torch torchvision torchaudio
$ rigsolve solve --want 'torch>=2.8,<3' 'flash-attn==2.8.3'
```

Exact PyTorch local versions such as `torch==2.9.0+cu126` are interpreted as a public version pin plus a CUDA build constraint. Environment markers and extras are rejected when they cannot be preserved safely. rigsolve never silently drops requirement semantics.

## Preference policies

Use `--prefer` to choose among valid assignments:

| Policy | Behavior |
|---|---|
| `verified` | Prefer the strongest effective evidence, then deterministic tie-breakers |
| `newest` | Prefer newer public package versions |
| `stable` | Prefer stable releases over prereleases |
| `minimal-change` | Prefer installed versions and matching CUDA, index, ABI, and artifact identity |

The default is `verified`. A policy changes ranking, not compatibility constraints.

```console
$ rigsolve solve --want torch --prefer newest
```

## Dimensions considered

Depending on available facts and profile fields, resolution considers:

- Python implementation and ABI tags;
- operating system, CPU architecture, and manylinux compatibility;
- CUDA runtime line and exact toolkit information;
- NVIDIA minor-compatibility driver floors;
- all target GPU compute capabilities;
- torch version and CUDA build coupling;
- C++11 ABI;
- torchvision and torchaudio release sets;
- known-broken scopes;
- source-build prerequisites.

An unavailable dimension remains unknown. Native packages with insufficient compatibility axes are not treated as a complete GPU answer merely because a generic artifact exists.

## Source builds

Source builds are disabled by default:

```console
$ rigsolve solve --want 'flash-attn==2.8.3' --allow-source-build
```

A source candidate is considered only when the matrix contains an explicit source-build fact and the target satisfies its prerequisites. Plans preserve build requirements, flags, `CUDA_HOME`, `TORCH_CUDA_ARCH_LIST`, deterministic job guidance, estimated duration, and RAM-per-job guidance when the source establishes those values.

Source plans are supported by pip, TOML lockfile, JSON, Docker, and Colab renderers where their semantics can be represented. Unsupported combinations fail rather than dropping build settings.

## Output formats

```console
$ rigsolve solve --want torch --output pip
$ rigsolve solve --want torch --output uv
$ rigsolve solve --want torch --output toml
$ rigsolve solve --want torch --output docker
$ rigsolve solve --want torch --output json
$ rigsolve solve --want torch --output colab
```

See {doc}`plans` for the contract of each renderer.

## Use another Python version

```console
$ rigsolve solve --want torch --python 3.13
```

This overlays a planning-only Python target on the detected profile. It cannot be combined with `--execute` because execution always uses the current interpreter.

## Use another matrix

The global `--matrix` option must appear before the command:

```console
$ rigsolve --matrix candidate.toml solve --want torch
```

The complete matrix is validated before resolution.

## Unsatisfiable requests

An unsatisfiable result contains:

- a concise machine summary;
- a reduced set of conflicting constraints;
- citations associated with those constraints;
- missing-coverage notes when the requested release is not modeled;
- suggestions that were checked by solving the modified request.

Use `why` when you need only the explanation surface:

```console
$ rigsolve why 'torch==2.9.0' 'torchvision==0.21.0' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux'
```

Exit status `1` means no compatible assignment was found. See {doc}`../reference/exit-codes`.
