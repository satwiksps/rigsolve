# Quickstart

This walkthrough detects a machine, resolves a package set, inspects the evidence, and checks the installed environment. Commands are read-only unless the final optional execution step is used.

## 1. Inspect the machine

```console
$ rigsolve detect
```

Detection collects:

- NVIDIA GPU name, compute capability, memory, and driver information;
- the driver-advertised maximum CUDA runtime;
- an optional local CUDA toolkit from `nvcc`;
- Python, ABI, operating system, CPU architecture, glibc, WSL, and container information;
- installed package metadata and discoverable torch build markers.

Use JSON for automation:

```console
$ rigsolve detect --json > machine-profile.json
```

Detection does not import torch. It remains useful when importing torch already crashes or fails to load a native library.

## 2. Resolve a package set

For the current machine:

```console
$ rigsolve solve --want torch torchvision torchaudio
```

For a machine that is not available locally:

```console
$ rigsolve solve \
    --want 'flash-attn==2.8.3' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux'
```

The plan is deterministic for the same request, profile, matrix digest, and preference. It includes ordered package steps, artifact or index URLs when known, evidence citations, and warnings for unknown axes.

## 3. Ask why

Use `why` before changing pins in a requirements file:

```console
$ rigsolve why \
    'flash-attn==2.8.3' \
    'torch==2.10' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux'
```

If the set is satisfiable, `why` prints the selected versions. If not, it prints the reduced conflicting constraints, relevant citations, and counterfactual suggestions that were re-solved before being shown.

## 4. Save a reproducible plan

```console
$ rigsolve solve \
    --want 'flash-attn==2.8.3' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux' \
    --output json > plan.json

$ rigsolve solve \
    --want 'flash-attn==2.8.3' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux' \
    --write-lockfile rigsolve.lock
```

The lockfile records the complete target dimensions used by the solver, package build axes, artifact hashes when available, matrix version, and matrix digest.

## 5. Check an existing environment

```console
$ rigsolve check
$ rigsolve check --lockfile rigsolve.lock
```

To print a minimal-change repair plan:

```console
$ rigsolve check --fix
```

`--fix` does not install anything.

## 6. Verify native imports and kernels

```console
$ rigsolve verify --package torch --package flash-attn
```

Each probe runs in a child interpreter. A native loader crash is returned as a failed result rather than crashing the parent process. Real GPU-kernel probes currently exist for torch and flash-attn. Other built-in probes are import checks.

## 7. Execute only after review

Execution is deliberately narrow:

```console
$ rigsolve solve --want torch --output pip --execute
```

Execution is allowed only for pip output on the detected local machine. It cannot be combined with `--target` or `--python`. Post-install verification runs automatically unless `--skip-verify` is supplied.

:::{warning}
Review the printed plan and activate the intended virtual environment before using `--execute`. The command mutates the Python environment running rigsolve.
:::
