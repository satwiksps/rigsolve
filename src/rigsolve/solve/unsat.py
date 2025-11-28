"""Minimal unsatisfiable core extraction."""

from __future__ import annotations

from rigsolve.solve.model import CSP, Constraint
from rigsolve.solve.search import is_satisfiable


def minimal_unsatisfiable_subset(csp: CSP) -> tuple[Constraint, ...]:
    """Return a deterministic irreducible unsatisfiable constraint set.

    The result is inclusion-minimal (removing any returned constraint restores
    satisfiability), which is the useful property for a concise explanation. It
    is not promised to be the smallest core by cardinality.
    """

    if is_satisfiable(csp):
        return ()
    core = list(csp.constraints)
    changed = True
    while changed:
        changed = False
        for constraint in tuple(core):
            candidate = tuple(item for item in core if item is not constraint)
            if not candidate:
                continue
            if not is_satisfiable(csp.with_constraints(candidate)):
                core.remove(constraint)
                changed = True
    return tuple(core)
