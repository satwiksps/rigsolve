# Plan API

## Models

```{eval-rst}
.. autoclass:: rigsolve.plan.InstallStep

.. autoclass:: rigsolve.plan.InstallPlan
```

Both classes are frozen. `InstallPlan.ordered_steps()` returns a stable topological order and rejects dependency cycles.

## Rendering

```{eval-rst}
.. autofunction:: rigsolve.plan.render_plan
```

Supported output names are `pip`, `uv`, `toml`, `docker`, `json`, and `colab`.

## Lockfiles

Lockfile helpers are available from their dedicated module:

```{eval-rst}
.. autofunction:: rigsolve.plan.lockfile.write_lockfile

.. autofunction:: rigsolve.plan.lockfile.load_lockfile
```

## Execution

Programmatic execution is lower level than the CLI safety gate:

```{eval-rst}
.. autofunction:: rigsolve.plan.execute.execute_plan
```

Callers must confirm that the plan targets the current interpreter and machine. Prefer the CLI unless custom execution control is required.
