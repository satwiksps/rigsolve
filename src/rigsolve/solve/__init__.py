"""Explainable constraint solving primitives."""

from rigsolve.solve.model import CSP, Constraint, Elimination, SolveResult
from rigsolve.solve.resolver import ResolutionFailure, ResolutionOutcome, resolve
from rigsolve.solve.search import solve_csp
from rigsolve.solve.unsat import minimal_unsatisfiable_subset

__all__ = [
    "CSP",
    "Constraint",
    "Elimination",
    "ResolutionFailure",
    "ResolutionOutcome",
    "SolveResult",
    "minimal_unsatisfiable_subset",
    "resolve",
    "solve_csp",
]
