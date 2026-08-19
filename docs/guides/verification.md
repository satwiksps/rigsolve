# Verify imports and GPU kernels

Verification answers a local question: can the installed package import or run its available probe on this machine now?

## Run the default probes

```console
$ rigsolve verify
```

Without `--package`, rigsolve probes recognized packages that are already installed.

## Select packages

Repeat `--package` for each distribution:

```console
$ rigsolve verify \
    --package torch \
    --package flash-attn \
    --package xformers
```

Distribution names and import module names are mapped by built-in probes. For example, `flashinfer-python` imports `flashinfer`.

## Import-only mode

```console
$ rigsolve verify --package torch --no-gpu
```

This disables GPU kernel execution. A successful import can establish import evidence, not GPU-run evidence.

## Timeouts and crash isolation

Each package runs in a child Python process:

```console
$ rigsolve verify --package torch --timeout 120
```

Timeouts, nonzero exits, malformed child output, native loader aborts, and signals are returned as failed results. A failed or timed-out probe does not receive a positive evidence level.

## Current kernel coverage

Real GPU-kernel probes currently exist for:

- `torch`, using a CUDA tensor operation;
- `flash-attn`, using its supported kernel probe.

Other built-in package probes are import-only. Their success does not establish kernel execution.

## Save a contribution payload

```console
$ rigsolve verify \
    --package torch \
    --package flash-attn \
    --contribute \
    --contribution-file rigsolve-verification.json
```

The payload includes the local machine profile, matrix version, and probe results. It is written locally and is not uploaded, signed, or automatically trusted.

Before submitting it:

1. review the file for hostnames, paths, or other information you do not want to share;
2. confirm the exact package artifacts and hashes when possible;
3. attach it to the verification issue form;
4. include a reproducible command and workload details.

Maintainers validate scope and provenance before converting a result into matrix evidence.
