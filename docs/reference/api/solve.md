# Solver API

## Resolve a request

```{eval-rst}
.. autofunction:: rigsolve.solve.resolve

.. autoclass:: rigsolve.solve.ResolutionOutcome

.. autoclass:: rigsolve.solve.ResolutionFailure
```

`ResolutionOutcome.satisfiable` determines which payload is present. A satisfiable outcome has a plan; an unsatisfiable outcome has a failure. Do not assume both are populated.

## Constraint primitives

These types support custom policy and solver tests:

```{eval-rst}
.. autoclass:: rigsolve.solve.Constraint

.. autoclass:: rigsolve.solve.CSP

.. autoclass:: rigsolve.solve.Elimination

.. autoclass:: rigsolve.solve.SolveResult

.. autofunction:: rigsolve.solve.solve_csp

.. autofunction:: rigsolve.solve.minimal_unsatisfiable_subset
```

The built-in resolver creates the package domains and constraints. Callers using the lower-level CSP API are responsible for preserving compatibility semantics and evidence scope.
