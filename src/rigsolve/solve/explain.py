"""Human-readable satisfiability reports designed for copy/paste and screenshots."""

from __future__ import annotations

from rigsolve.detect import MachineProfile
from rigsolve.solve.resolver import ResolutionFailure


def _machine_line(profile: MachineProfile) -> str:
    parts = []
    if profile.gpu_name:
        parts.append(profile.gpu_name)
    if profile.compute_capability:
        parts.append(profile.compute_capability)
    if profile.driver_version:
        parts.append(f"driver {profile.driver_version}")
    if profile.python_version:
        parts.append(f"Python {profile.python_version}")
    return " | ".join(parts) if parts else "unknown / unconstrained target"


def explain_failure(failure: ResolutionFailure, profile: MachineProfile) -> str:
    lines = ["No solution.", "", f"  You requested: {', '.join(failure.requested)}"]
    lines.append(f"  Your machine: {_machine_line(profile)}")
    lines.extend(("", "  Conflict:"))
    if failure.missing_packages:
        gaps = {gap.package: gap for gap in failure.coverage_gaps}
        for package in failure.missing_packages:
            gap = gaps.get(package)
            requested = gap.requested if gap is not None else package
            lines.append(f"    - the bundled matrix has no admissible artifacts for {requested}")
            if gap is not None and gap.modeled_versions:
                lines.append("      modeled versions: " + ", ".join(gap.modeled_versions))
                for source in gap.sources[:2]:
                    citation = source.citation() if hasattr(source, "citation") else str(source)
                    lines.append(f"      source: {citation}")
        lines.append("      This is missing coverage, not a claim that the package is impossible.")
    seen_citations: set[str] = set()
    for constraint in failure.core:
        lines.append(f"    - {constraint.summary or constraint.key}")
        emitted = 0
        for source in constraint.sources:
            citation = source.citation() if hasattr(source, "citation") else str(source)
            if citation in seen_citations:
                continue
            lines.append(f"      source: {citation}")
            seen_citations.add(citation)
            emitted += 1
            if emitted == 2:
                break
    if not failure.missing_packages and not failure.core:
        lines.append("    - the available matrix domains have no mutually compatible assignment")
    if failure.suggestions:
        lines.extend(("", "  Options, cheapest first:"))
        lines.extend(
            f"    {index}. {suggestion}"
            for index, suggestion in enumerate(failure.suggestions, start=1)
        )
    return "\n".join(lines) + "\n"
