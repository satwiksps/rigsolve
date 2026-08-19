# rigsolve

**Resolve, inspect, and explain compatibility across PyTorch, CUDA, NVIDIA drivers, Python, and native extensions.**

rigsolve detects a machine without importing torch, resolves package combinations from sourced compatibility facts, and produces a reviewable installation plan. It does not install anything unless `--execute` is supplied.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} Install and run
:link: getting-started/installation
:link-type: doc

Install rigsolve from PyPI and inspect the current machine.
:::

:::{grid-item-card} Solve a GPU stack
:link: getting-started/quickstart
:link-type: doc

Resolve torch, CUDA, and extension versions for a real or hypothetical target.
:::

:::{grid-item-card} Diagnose an environment
:link: guides/diagnose
:link-type: doc

Find driver, CUDA, ABI, package coupling, and lockfile conflicts.
:::

:::{grid-item-card} Understand the evidence
:link: trust-model
:link-type: doc

See exactly what derived, install, import, and GPU-run evidence establish.
:::
::::

## Start here

Install the current release:

```console
$ python -m pip install rigsolve
$ rigsolve --version
```

Inspect the machine without importing torch:

```console
$ rigsolve detect
```

Resolve a stack for a target machine:

```console
$ rigsolve solve \
    --want 'flash-attn==2.8.3' \
    --target 'RTX 4090,driver=580.65,python=3.12,linux'
```

The default command prints a plan. Review it before using `--execute`.

:::{important}
rigsolve reports what its evidence supports. An unrecorded combination remains unknown. A successful solve is not a guarantee that every workload will run.
:::

## Documentation map

```{toctree}
:caption: Getting started
:maxdepth: 2

getting-started/installation
getting-started/quickstart
getting-started/concepts
```

```{toctree}
:caption: User guide
:maxdepth: 2

guides/detect
guides/targets
guides/solve
guides/diagnose
guides/plans
guides/verification
guides/matrix
guides/recipes
```

```{toctree}
:caption: Explanation
:maxdepth: 2

trust-model
architecture
matrix-schema
```

```{toctree}
:caption: Reference
:maxdepth: 2

cli
reference/python-api
reference/environment-and-files
reference/exit-codes
```

```{toctree}
:caption: Project
:maxdepth: 2

troubleshooting
faq
contributing
harvesting
maintainers/read-the-docs
launch-checklist
release-notes
security
```
