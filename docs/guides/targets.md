# Describe a target machine

`--target` resolves for a hypothetical machine without reading local GPU state. It is useful for CI images, remote servers, deployment planning, and documentation examples.

## Basic syntax

Target expressions are comma-separated. A GPU name may be the first bare value:

```text
RTX 4090,driver=580.65,python=3.12,linux
```

Equivalent explicit form:

```text
gpu=RTX 4090,driver=580.65,python=3.12,os=linux
```

Quote the full expression in a shell because GPU names contain spaces and commas separate fields.

## Supported fields

| Canonical field | Common aliases | Example |
|---|---|---|
| `gpu_name` | `gpu`, `name` | `gpu=A100` |
| `gpu_count` | `count` | `count=8` |
| `compute_capability` | `sm`, `cc`, `compute_cap` | `sm=80` |
| `memory_total_mib` | `memory`, `vram` | `vram=24GiB` |
| `driver_version` | `driver` | `driver=580.65` |
| `cuda_runtime` | `cuda`, `max_cuda` | `cuda=13.0` |
| `toolkit_version` | `nvcc`, `toolkit` | `nvcc=12.6` |
| `toolkit_path` | `cuda_home`, `cuda_path` | `cuda_home=/usr/local/cuda-12.6` |
| `os` | `platform` | `os=linux` |
| `architecture` | `arch` | `arch=x86_64` |
| `glibc_version` | `glibc` | `glibc=2.35` |
| `manylinux_tag` | `manylinux` | `manylinux=manylinux_2_35_x86_64` |
| `python_version` | `python`, `py` | `python=3.12` |
| `cxx11_abi` | `abi`, `cxx11abi` | `cxx11abi=true` |
| `is_wsl` | `wsl` | `wsl=true` |
| `is_container` | `container` | `container=true` |

Bare values also accept `linux`, `windows`, `macos`, `wsl`, `container`, common CPU architectures, compute capabilities, and `cpu`.

## Examples

One A100 with an inferred compute capability:

```console
$ rigsolve solve --want torch \
    --target 'A100,driver=580.65,python=3.12,linux'
```

Eight GPUs with an explicit architecture and toolkit:

```console
$ rigsolve solve --want 'flash-attn==2.8.3' \
    --target 'gpu=A100,count=8,sm=80,driver=580.65,nvcc=12.6,python=3.12,linux'
```

WSL target:

```console
$ rigsolve solve --want torch \
    --target 'RTX 4090,driver=580.65,python=3.12,wsl'
```

Explicit CPU target:

```console
$ rigsolve solve --want transformers --target 'cpu,python=3.12,linux'
```

The current matrix is GPU-focused. CUDA-only requests on an explicit CPU target fail instead of silently selecting a CUDA build.

## Defaults and inference

When `--target` is used without a base profile, unspecified platform fields default to Linux x86_64. Known GPU names may infer compute capability. A driver may infer its advertised CUDA maximum. Inference is limited to built-in mappings and is recorded as target-sourced data.

For source builds, `cuda_home` requires an `nvcc` or toolkit version:

```text
nvcc=12.6,cuda_home=/usr/local/cuda-12.6
```

## Execution restriction

`--target` is planning-only. It cannot be combined with `--execute` because installing a plan resolved for hypothetical hardware into the local interpreter is unsafe.
