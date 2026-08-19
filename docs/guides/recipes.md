# Recipes

## Plan for a remote GPU server

```console
$ rigsolve solve \
    --want torch torchvision torchaudio \
    --target 'A100,count=8,driver=580.65,python=3.12,linux' \
    --output pip
```

This reads no local GPU state because the target is explicit.

## Generate a Dockerfile

```console
$ rigsolve solve \
    --want 'torch==2.9.0' 'flash-attn==2.8.3' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux' \
    --output docker > Dockerfile
```

Review the selected base image and all package URLs before building.

## Compare preference policies

```console
$ rigsolve solve --want torch --prefer verified --output json > verified.json
$ rigsolve solve --want torch --prefer newest --output json > newest.json
```

Compare package choices, effective evidence, and warnings. Both outputs must satisfy the same hard constraints.

## Explain a requirements conflict

```console
$ rigsolve why \
    'torch==2.9.0' \
    'torchvision==0.21.0' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux'
```

Use the cited release-set facts to decide which pin to change.

## Detect drift in CI

Create a lockfile on the intended target:

```console
$ rigsolve solve \
    --want torch torchvision torchaudio \
    --target 'A100,driver=580.65,python=3.12,linux' \
    --write-lockfile rigsolve.lock > install.sh
```

On the matching runner or image:

```console
$ rigsolve check --lockfile rigsolve.lock
```

Use exit status `2` as a known-broken or drift signal. Preserve command output as a CI artifact.

## Inspect a package before filing an issue

```console
$ rigsolve detect --json > machine.json
$ rigsolve matrix show --package flash-attn --json > facts.json
$ rigsolve verify --package flash-attn \
    --contribute --contribution-file verification.json
```

Attach the relevant files after reviewing them for sensitive local information.

## Check without a working torch import

```console
$ rigsolve detect
$ rigsolve check
```

Both commands inspect metadata without importing torch. Then run `verify --package torch` to capture the import failure in an isolated child process.

## Plan an explicit source build

```console
$ rigsolve solve \
    --want 'flash-attn==2.8.3' \
    --target 'A100,driver=580.65,nvcc=12.6,cuda_home=/usr/local/cuda-12.6,python=3.13,linux' \
    --allow-source-build \
    --output pip
```

The source path is used only when covered by an explicit source-build fact and when its environment requirements pass.
