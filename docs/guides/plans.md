# Plans, lockfiles, and execution

A solved assignment becomes one immutable `InstallPlan`. Renderers transform that plan without changing its package choices.

## pip output

```console
$ rigsolve solve --want torch --output pip
```

The renderer emits ordered `python -m pip` commands, explicit index URLs, artifact hashes when known, source-build environment variables, and warnings. The output is a reviewable shell plan.

## uv output

```console
$ rigsolve solve --want torch --output uv
```

The result is a project snippet with a Python major/minor constraint derived from the target. PyTorch indexes and package sources are kept together. A plan is rejected when uv cannot represent required source-build semantics.

## TOML lockfile

Write a lockfile independently of the selected display format:

```console
$ rigsolve solve --want torch --write-lockfile rigsolve.lock
```

The lockfile records:

- requested requirements and preference policy;
- matrix version and deterministic SHA-256 digest;
- target Python, platform, driver, toolkit, GPU count, and compute capabilities;
- ordered package versions and dependency edges;
- index and artifact URLs;
- artifact hashes;
- CUDA, torch, C++ ABI, Python, and platform build tags;
- source-build settings and evidence citations;
- plan warnings.

Use `rigsolve check --lockfile rigsolve.lock` to detect environment drift.

## Dockerfile output

```console
$ rigsolve solve --want torch --output docker > Dockerfile
```

CUDA plans select an applicable NVIDIA CUDA base image. Plans without CUDA use a Python base. The renderer is text generation only; it does not invoke Docker.

## JSON output

```console
$ rigsolve solve --want torch --output json > plan.json
```

JSON is intended for CI policy, review tools, and integrations. Treat unknown keys as forward-compatible additions during the pre-1.0 period.

## Colab output

```console
$ rigsolve solve --want torch --output colab
```

The output starts with `%%bash` and is intended for one Colab code cell. Source-build variables are set within that shell so they persist for the installation commands in the cell.

## Execute a plan

```console
$ rigsolve solve --want torch --output pip --execute
```

Execution safeguards:

- only `--output pip` can execute;
- `--target` is rejected;
- `--python` is rejected;
- the current `sys.executable` owns the installation;
- steps run in dependency order;
- verification runs after installation unless `--skip-verify` is explicit.

`--output docker --execute` and `--output uv --execute` are rejected. rigsolve does not print one backend and silently execute another.

:::{warning}
Create and activate a disposable virtual environment before the first execution. Read-only solving and rendering are safe to run from any environment.
:::
