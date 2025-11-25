"""Small, deterministic CSP model with first-class explanation metadata."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeAlias

Value: TypeAlias = Hashable
Assignment: TypeAlias = Mapping[str, Any]
Predicate: TypeAlias = Callable[[Assignment], bool]
Score: TypeAlias = tuple[Any, ...]
Scorer: TypeAlias = Callable[[Assignment], Score]


@dataclass(frozen=True, slots=True)
class Constraint:
    """A constraint and the user-facing reason it exists.

    ``predicate`` is called only with every variable in ``variables`` assigned.
    Keeping the prose and sources next to the predicate lets propagation retain a
    useful elimination trace rather than producing a solver-internal error.
    """

    key: str
    variables: tuple[str, ...]
    predicate: Predicate = field(compare=False, repr=False)
    summary: str = ""
    sources: tuple[Any, ...] = ()
    kind: str = "compatibility"

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("constraint key must not be empty")
        if not self.variables:
            raise ValueError(f"constraint {self.key!r} has no variables")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError(f"constraint {self.key!r} repeats a variable")

    def accepts(self, assignment: Assignment) -> bool:
        missing = set(self.variables).difference(assignment)
        if missing:
            raise KeyError(f"constraint {self.key!r} missing variables: {sorted(missing)}")
        scoped = {name: assignment[name] for name in self.variables}
        return bool(self.predicate(scoped))


@dataclass(frozen=True, slots=True)
class CSP:
    domains: Mapping[str, tuple[Value, ...]]
    constraints: tuple[Constraint, ...]

    def __post_init__(self) -> None:
        if not self.domains:
            raise ValueError("a CSP needs at least one variable")
        for name, domain in self.domains.items():
            if not name:
                raise ValueError("variable names must not be empty")
            if len(set(domain)) != len(domain):
                raise ValueError(f"domain {name!r} contains duplicate values")
        known = set(self.domains)
        for constraint in self.constraints:
            unknown = set(constraint.variables).difference(known)
            if unknown:
                raise ValueError(
                    f"constraint {constraint.key!r} references unknown variables: {sorted(unknown)}"
                )

    def with_constraints(self, constraints: tuple[Constraint, ...]) -> CSP:
        return CSP(domains=self.domains, constraints=constraints)


@dataclass(frozen=True, slots=True)
class Elimination:
    variable: str
    value: Value
    constraint_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class SolveResult:
    satisfiable: bool
    assignment: Mapping[str, Value] = field(default_factory=dict)
    score: Score = ()
    eliminations: tuple[Elimination, ...] = ()
    explored_nodes: int = 0
