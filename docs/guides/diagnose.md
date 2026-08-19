# Diagnose an installed environment

`rigsolve check` compares detected package metadata and machine facts with the compatibility matrix.

## Run a check

```console
$ rigsolve check
```

Exit status is `0` when no applicable known incompatibility is found and `2` when the environment is known to be broken. Unknown native axes remain unverified and are reported as such.

## Violation types

The checker can report:

| Type | Meaning |
|---|---|
| CUDA build mismatch | Installed packages encode incompatible CUDA lines |
| torch build mismatch | An extension targets a different torch release |
| C++ ABI mismatch | Native package ABI labels disagree |
| driver floor | The driver is below the applicable CUDA runtime floor |
| architecture | A toolkit or recorded wheel does not cover a detected GPU architecture |
| release coupling | Represented package releases are paired incorrectly |
| known broken | The installed assignment matches a narrowly scoped negative fact |
| avoidable source build | A compatible wheel is recorded for a package installed from source |
| lock drift | Installed package, artifact, build axis, or machine target differs from a lockfile |

Positive release-set facts are not treated as a complete list of every possible future release. A package version absent from the represented set remains unknown rather than being declared incompatible.

## Generate a repair plan

```console
$ rigsolve check --fix
```

The checker asks the resolver for a `minimal-change` assignment and prints it. It does not execute the plan.

Select the repair output format:

```console
$ rigsolve check --fix --output pip
$ rigsolve check --fix --output uv
$ rigsolve check --fix --output json
```

If matrix coverage is insufficient for a safe repair, the command says that no automatic repair plan is covered.

## Check against a lockfile

```console
$ rigsolve check --lockfile rigsolve.lock
```

Lock checks include:

- public package versions while allowing expected local CUDA suffixes;
- CUDA, torch, and C++ ABI build identity;
- source-build status and artifact hash;
- Python, platform, GPU count, and the full compute-capability set;
- matrix version and digest context.

Malformed lockfiles are rejected as user input. Unknown fields and wrong field types are not silently discarded.

## Read the result correctly

`healthy=True` means no applicable known violation was found. It does not mean that every package was verified. Native packages with missing CUDA, torch, ABI, platform, or architecture metadata remain explicitly unverified.

Use `rigsolve verify` after installation to test imports and available GPU kernels on the current machine.
