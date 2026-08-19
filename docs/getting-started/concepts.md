# Core concepts

Understanding five objects is enough to reason about rigsolve.

## Machine profile

A machine profile is an immutable description of the environment used for resolution. It can come from local detection or a hypothetical target string.

Important fields include:

- every detected GPU and compute capability;
- NVIDIA driver version and driver-advertised CUDA maximum;
- local toolkit version and path, when `nvcc` exists;
- Python version and ABI tag;
- operating system, CPU architecture, glibc, and manylinux tag;
- installed package versions and native build markers;
- detection issues and unknown values.

Unknown is a first-class state. It is different from `false`, zero GPUs, or compatibility.

## Compatibility fact

The matrix is a collection of small, sourced facts. A fact may describe a wheel artifact, a PyTorch build axis, a driver floor, a package release tuple, a known failure, an architecture window, or a source-build recipe.

Facts remain narrow. A filename that contains `cu126` establishes an encoded CUDA build label. It does not establish that the wheel imports on every Linux distribution or contains kernels for every GPU architecture.

## Candidate and constraint

The solver constructs package candidates from matrix facts, then applies constraints from:

- requested package specifiers;
- Python and platform tags;
- driver and CUDA relationships;
- GPU architecture windows;
- package release coupling;
- torch, CUDA, and C++ ABI build axes;
- known-broken exclusions;
- source-build prerequisites.

A candidate is retained only if all applicable hard constraints accept it.

## Installation plan

A successful solve becomes an immutable plan. The plan holds selected package versions, dependency order, artifact or index locations, build settings, target data, warnings, provenance, and the exact matrix digest.

Plan rendering is pure. Rendering as pip, uv, TOML, Docker, JSON, or Colab does not perform installation.

## Evidence level

Evidence levels describe what was observed:

| Level | Label | Establishes |
|---:|---|---|
| 0 | Derived | An upstream artifact, release record, or documented build axis exists |
| 1 | Installs | The exact artifact installed in a recorded isolated environment |
| 2 | Imports | The installed package imported and available build configuration was recorded |
| 3 | Runs | A real kernel ran on the recorded GPU |

The plan reports the weakest evidence used by any selected artifact or applicable constraint. The level is evidence depth, not a probability score.

Read {doc}`../trust-model` before interpreting solver output in automated deployment systems.
