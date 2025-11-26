"""Generalised AC-3 propagation with an auditable elimination trace."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from itertools import product

from rigsolve.solve.model import Constraint, Elimination, Value


def _has_support(
    variable: str,
    value: Value,
    constraint: Constraint,
    domains: Mapping[str, Sequence[Value]],
) -> bool:
    others = tuple(name for name in constraint.variables if name != variable)
    if not others:
        return constraint.accepts({variable: value})
    pools = [domains[name] for name in others]
    for combination in product(*pools):
        assignment = {variable: value, **dict(zip(others, combination, strict=True))}
        if constraint.accepts(assignment):
            return True
    return False


def propagate(
    domains: MutableMapping[str, list[Value]],
    constraints: Iterable[Constraint],
    eliminations: list[Elimination] | None = None,
) -> bool:
    """Enforce generalised arc consistency in place.

    Returns ``False`` as soon as any domain is emptied. Constraint and variable
    iteration order is stable, which keeps both solutions and explanations
    reproducible for a fixed matrix.
    """

    trace = eliminations if eliminations is not None else []
    ordered_constraints = tuple(constraints)
    by_variable: dict[str, list[Constraint]] = defaultdict(list)
    for constraint in ordered_constraints:
        for variable in constraint.variables:
            by_variable[variable].append(constraint)

    queue = deque(
        (constraint, variable)
        for constraint in ordered_constraints
        for variable in constraint.variables
    )
    queued = set(queue)

    while queue:
        constraint, variable = queue.popleft()
        queued.discard((constraint, variable))
        removed = [
            value
            for value in tuple(domains[variable])
            if not _has_support(variable, value, constraint, domains)
        ]
        if not removed:
            continue
        for value in removed:
            domains[variable].remove(value)
            trace.append(
                Elimination(
                    variable=variable,
                    value=value,
                    constraint_key=constraint.key,
                    reason=constraint.summary or constraint.key,
                )
            )
        if not domains[variable]:
            return False
        for related in by_variable[variable]:
            if related is constraint:
                continue
            for neighbour in related.variables:
                if neighbour == variable:
                    continue
                arc = (related, neighbour)
                if arc not in queued:
                    queue.append(arc)
                    queued.add(arc)
    return True
