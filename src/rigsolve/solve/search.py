"""MRV backtracking search and deterministic optimisation."""

from __future__ import annotations

from dataclasses import dataclass, field

from rigsolve.solve.model import CSP, Elimination, Score, Scorer, SolveResult, Value
from rigsolve.solve.propagate import propagate


@dataclass(slots=True)
class _SearchState:
    best_assignment: dict[str, Value] = field(default_factory=dict)
    best_score: Score = ()
    explored_nodes: int = 0
    stopped: bool = False
    found: bool = field(default_factory=bool)

    def has_solution(self) -> bool:
        return self.found


def _default_score(_assignment: dict[str, Value]) -> Score:
    return ()


def _copy_domains(domains: dict[str, list[Value]]) -> dict[str, list[Value]]:
    return {name: list(values) for name, values in domains.items()}


def _complete(domains: dict[str, list[Value]]) -> bool:
    return all(len(values) == 1 for values in domains.values())


def _assignment(domains: dict[str, list[Value]]) -> dict[str, Value]:
    return {name: values[0] for name, values in domains.items()}


def _choose_mrv(domains: dict[str, list[Value]]) -> str:
    return min(
        (name for name, values in domains.items() if len(values) > 1),
        key=lambda name: (len(domains[name]), name),
    )


def solve_csp(
    csp: CSP,
    *,
    scorer: Scorer | None = None,
    value_order: dict[str, tuple[Value, ...]] | None = None,
    max_solutions: int | None = None,
) -> SolveResult:
    """Solve ``csp``, optionally maximising a lexicographic score.

    With no scorer, the first deterministic solution is returned. With a scorer,
    all reachable solutions are considered unless ``max_solutions`` is supplied.
    This is intentional: rigsolve's domains are small, and a correct preference is
    more important than a fast but approximate answer.
    """

    scoring = scorer or _default_score
    optimise = scorer is not None
    domains = {name: list(values) for name, values in csp.domains.items()}
    if any(not values for values in domains.values()):
        return SolveResult(satisfiable=False)
    initial_trace: list[Elimination] = []
    if not propagate(domains, csp.constraints, initial_trace):
        return SolveResult(
            satisfiable=False,
            eliminations=tuple(initial_trace),
            explored_nodes=0,
        )

    state = _SearchState()
    solutions = 0

    def visit(current: dict[str, list[Value]]) -> None:
        nonlocal solutions
        if state.stopped:
            return
        state.explored_nodes += 1
        if _complete(current):
            candidate = _assignment(current)
            score = scoring(candidate)
            solutions += 1
            if not state.found or score > state.best_score:
                state.best_assignment = candidate
                state.best_score = score
                state.found = True
            if not optimise or (max_solutions is not None and solutions >= max_solutions):
                state.stopped = True
            return

        variable = _choose_mrv(current)
        preferred = value_order.get(variable, ()) if value_order else ()
        rank = {value: index for index, value in enumerate(preferred)}
        values = sorted(
            current[variable],
            key=lambda value: (rank.get(value, len(rank)), repr(value)),
        )
        for value in values:
            branch = _copy_domains(current)
            branch[variable] = [value]
            if propagate(branch, csp.constraints):
                visit(branch)

    visit(domains)
    if not state.has_solution():
        return SolveResult(
            satisfiable=False,
            eliminations=tuple(initial_trace),
            explored_nodes=state.explored_nodes,
        )
    return SolveResult(
        satisfiable=True,
        assignment=state.best_assignment,
        score=state.best_score,
        eliminations=tuple(initial_trace),
        explored_nodes=state.explored_nodes,
    )


def is_satisfiable(csp: CSP) -> bool:
    return solve_csp(csp).satisfiable
