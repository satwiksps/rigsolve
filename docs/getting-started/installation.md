# Installation

## Requirements

rigsolve requires Python 3.10 or newer. The package itself is pure Python. NVIDIA tools are optional: detection records missing tools as unknown instead of failing the whole profile.

The bundled compatibility data currently focuses on Linux x86_64, NVIDIA CUDA, PyTorch, and selected native extensions. You can install the CLI on another platform to inspect data, but the solver fails closed when the matrix does not cover the requested platform.

## Install from PyPI

Use the Python interpreter that owns the environment you want to inspect:

```console
$ python -m pip install --upgrade rigsolve
$ rigsolve --version
```

Using `python -m pip` avoids installing into a different Python environment by mistake.

## Install with pipx

`pipx` is suitable for read-only inspection and hypothetical solves:

```console
$ pipx install rigsolve
$ rigsolve doctor
```

Do not use a pipx installation with `solve --execute`. Execution installs into the interpreter running rigsolve, which is the isolated pipx environment rather than your project environment.

## Install with uv

Install the CLI as a tool:

```console
$ uv tool install rigsolve
```

Or add it to a development environment:

```console
$ uv add --dev rigsolve
$ uv run rigsolve detect
```

## Install in a Conda environment

Activate the intended environment, then install from PyPI:

```console
$ conda activate my-gpu-env
$ python -m pip install rigsolve
$ python -m rigsolve detect
```

rigsolve emits pip, uv, Docker, TOML, JSON, and Colab plans. It does not emit Conda environment files in the current release.

## Install from source

Use an editable install only when developing rigsolve:

```console
$ git clone https://github.com/satwiksps/rigsolve.git
$ cd rigsolve
$ python -m pip install -e '.[dev]'
$ python -m pytest
```

## Confirm the installation

Run these checks before resolving packages:

```console
$ rigsolve --version
$ rigsolve doctor
$ rigsolve matrix stats
```

`doctor` checks the package, bundled matrix, driver tools, and platform probes. Missing optional NVIDIA tools are reported separately from an invalid compatibility matrix.

## Upgrade and remove

```console
$ python -m pip install --upgrade rigsolve
$ python -m pip uninstall rigsolve
```

Matrix updates are cached outside the installed package. See {doc}`../reference/environment-and-files` if you also want to remove that cache.
