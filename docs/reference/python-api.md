# Python API

The command-line interface is the primary user interface. The Python API is useful for CI policy, custom front ends, matrix tooling, and programmatic inspection.

Public names are exported from `rigsolve.detect`, `rigsolve.matrix`, `rigsolve.solve`, `rigsolve.plan`, and `rigsolve.verify`. Import from those modules rather than internal files. The documented public API follows semantic versioning; backward-incompatible changes require a major release.

## Minimal example

```python
from rigsolve.detect import profile_from_target
from rigsolve.matrix import load_bundled
from rigsolve.solve import resolve

profile = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
matrix = load_bundled()
outcome = resolve(("torch", "flash-attn==2.8.3"), profile, matrix)

if outcome.satisfiable:
    assert outcome.plan is not None
    for step in outcome.plan.ordered_steps():
        print(step.requirement)
else:
    assert outcome.failure is not None
    print(outcome.failure)
```

```{toctree}
:maxdepth: 2

api/detect
api/matrix
api/solve
api/plan
api/verify
api/errors
```

## Stability rules

- Names listed in a package's `__all__` are public for the installed minor release.
- Frozen dataclasses may gain optional fields before 1.0.
- Serialized profile, plan, and matrix formats carry explicit schema or lock versions where applicable.
- Internal modules and underscore-prefixed names are not compatibility promises.
- CLI exit codes and documented safety restrictions are treated as stable automation contracts.
