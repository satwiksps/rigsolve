from __future__ import annotations

from rigsolve.solve import CSP, Constraint, minimal_unsatisfiable_subset, solve_csp


def test_arc_consistency_and_mrv_find_deterministic_solution() -> None:
    csp = CSP(
        domains={"torch": ("2.7", "2.8"), "flash": ("2.7-wheel", "2.8-wheel")},
        constraints=(
            Constraint(
                key="matching-torch",
                variables=("torch", "flash"),
                predicate=lambda a: a["torch"] == a["flash"].split("-")[0],
                summary="extension wheel must match torch",
            ),
            Constraint(
                key="pin-flash",
                variables=("flash",),
                predicate=lambda a: a["flash"] == "2.8-wheel",
                summary="flash was pinned",
            ),
        ),
    )

    result = solve_csp(csp)

    assert result.satisfiable
    assert result.assignment == {"torch": "2.8", "flash": "2.8-wheel"}
    assert any(item.variable == "torch" for item in result.eliminations)


def test_scorer_selects_global_best() -> None:
    csp = CSP(
        domains={"x": (1, 2, 3), "y": (1, 2, 3)},
        constraints=(Constraint("not-equal", ("x", "y"), lambda a: a["x"] != a["y"]),),
    )

    result = solve_csp(csp, scorer=lambda a: (a["x"] + a["y"], a["x"]))

    assert result.assignment == {"x": 3, "y": 2}
    assert result.score == (5, 3)


def test_mus_is_irreducible_and_omits_irrelevant_constraints() -> None:
    lower = Constraint("lower", ("x",), lambda a: a["x"] >= 2, "x must be >= 2")
    upper = Constraint("upper", ("x",), lambda a: a["x"] <= 1, "x must be <= 1")
    irrelevant = Constraint("positive-y", ("y",), lambda a: a["y"] > 0)
    csp = CSP(
        domains={"x": (1, 2), "y": (1, 2)},
        constraints=(lower, upper, irrelevant),
    )

    core = minimal_unsatisfiable_subset(csp)

    assert {constraint.key for constraint in core} == {"lower", "upper"}
