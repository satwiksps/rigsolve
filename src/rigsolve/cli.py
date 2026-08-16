"""Command-line interface for rigsolve."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from packaging.utils import canonicalize_name

from rigsolve import __version__
from rigsolve.detect import MachineProfile, detect_machine_profile, profile_from_target
from rigsolve.diagnose import check_environment, format_check_report
from rigsolve.doctor import format_doctor, run_doctor
from rigsolve.errors import ExitCode, RigsolveError, UserInputError
from rigsolve.evidence import evidence_label
from rigsolve.matrix import (
    DEFAULT_UPDATE_URL,
    MatrixStore,
    fetch_update,
    load_with_cached_update,
    save_matrix,
)
from rigsolve.plan import render_plan
from rigsolve.plan.execute import execute_plan
from rigsolve.plan.lockfile import write_lockfile
from rigsolve.report import format_profile, format_smoke_results
from rigsolve.solve.explain import explain_failure
from rigsolve.solve.resolver import resolve
from rigsolve.verify.smoke import PROBES, contribution_payload, verify_packages


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UserInputError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="rigsolve",
        description=(
            "Resolve and explain the native compatibility matrix behind NVIDIA GPU Python stacks."
        ),
    )
    parser.add_argument("--version", action="version", version=f"rigsolve {__version__}")
    parser.add_argument(
        "--matrix", type=Path, help="use a local matrix TOML instead of bundled data"
    )
    parser.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)

    detect = commands.add_parser("detect", help="inspect this machine without importing torch")
    detect.add_argument("--json", action="store_true", help="emit a machine profile as JSON")

    solve = commands.add_parser("solve", help="produce a compatible, ordered install plan")
    solve.add_argument("--want", nargs="+", required=True, metavar="SPEC")
    solve.add_argument("--python", dest="python_version")
    solve.add_argument(
        "--target", help='hypothetical target, e.g. "A100,driver=550.54,python=3.11,linux"'
    )
    solve.add_argument(
        "--prefer",
        choices=("verified", "newest", "stable", "minimal-change"),
        default="verified",
    )
    solve.add_argument("--allow-source-build", action="store_true")
    solve.add_argument(
        "--output",
        choices=("pip", "uv", "toml", "docker", "json", "colab"),
        default="pip",
    )
    solve.add_argument("--write-lockfile", type=Path, metavar="PATH")
    solve.add_argument(
        "--execute",
        action="store_true",
        help="execute the resolved plan; without this flag rigsolve never installs",
    )
    solve.add_argument(
        "--skip-verify",
        action="store_true",
        help="with --execute, skip automatic post-install import and GPU probes",
    )

    check = commands.add_parser("check", help="diagnose an installed environment")
    check.add_argument("--fix", action="store_true", help="also print a minimal-change repair plan")
    check.add_argument("--lockfile", type=Path)
    check.add_argument("--output", choices=("pip", "uv", "json"), default="pip")

    why = commands.add_parser("why", help="explain why a set of pins cannot coexist")
    why.add_argument("spec", nargs="+")
    why.add_argument("--target")
    why.add_argument("--python", dest="python_version")
    why.add_argument("--allow-source-build", action="store_true")

    verify = commands.add_parser("verify", help="run isolated imports and available kernel probes")
    verify.add_argument("--package", action="append", dest="packages")
    verify.add_argument(
        "--no-gpu", action="store_true", help="run import checks without GPU kernels"
    )
    verify.add_argument("--timeout", type=float, default=60.0)
    verify.add_argument("--contribute", action="store_true")
    verify.add_argument(
        "--contribution-file", type=Path, default=Path("rigsolve-verification.json")
    )

    matrix = commands.add_parser("matrix", help="inspect or update compatibility facts")
    matrix_commands = matrix.add_subparsers(dest="matrix_command", required=True)
    update = matrix_commands.add_parser(
        "update", help="fetch, validate, and atomically cache facts"
    )
    update.add_argument("--url", default=DEFAULT_UPDATE_URL)
    update.add_argument("--destination", type=Path)
    update.add_argument("--no-merge", action="store_true")
    show = matrix_commands.add_parser("show", help="show matrix metadata or package facts")
    show.add_argument("--package")
    show.add_argument("--json", action="store_true")
    stats = matrix_commands.add_parser("stats", help="show coverage and evidence tiers")
    stats.add_argument("--json", action="store_true")
    add = matrix_commands.add_parser("add", help="validate and merge a contributed TOML fragment")
    add.add_argument("file", type=Path)
    add.add_argument("--destination", type=Path, required=True)

    commands.add_parser("doctor", help="check rigsolve, matrix, driver tools, and platform probes")
    return parser


def _store(path: Path | None) -> MatrixStore:
    return MatrixStore.load(path) if path else load_with_cached_update()


def _profile(target: str | None = None, python_version: str | None = None) -> MachineProfile:
    profile = detect_machine_profile(target=target) if target else detect_machine_profile()
    if python_version:
        profile = profile_from_target(f"python={python_version}", base=profile)
    return profile


def _detect_command(args: argparse.Namespace) -> int:
    profile = detect_machine_profile()
    if args.json:
        print(profile.to_json())
    else:
        print(format_profile(profile), end="")
    return int(ExitCode.OK)


def _solve_command(args: argparse.Namespace, store: MatrixStore) -> int:
    if args.skip_verify and not args.execute:
        raise UserInputError("--skip-verify is valid only with --execute")
    if args.execute and args.output != "pip":
        raise UserInputError("--execute is supported only with --output pip")
    if args.execute and args.target:
        raise UserInputError("--execute cannot use a hypothetical --target")
    if args.execute and args.python_version:
        raise UserInputError(
            "--execute cannot override --python; run rigsolve with the intended interpreter"
        )
    profile = _profile(args.target, args.python_version)
    outcome = resolve(
        args.want,
        profile,
        store,
        preference=args.prefer,
        allow_source_build=args.allow_source_build,
    )
    if not outcome.satisfiable:
        assert outcome.failure is not None
        print(explain_failure(outcome.failure, profile), end="", file=sys.stderr)
        return int(ExitCode.UNSATISFIABLE)
    assert outcome.plan is not None
    print(render_plan(outcome.plan, args.output), end="")
    if args.write_lockfile:
        write_lockfile(outcome.plan, args.write_lockfile)
        print(f"Wrote {args.write_lockfile}", file=sys.stderr)
    if args.execute:
        print("Executing the reviewed plan because --execute was supplied.", file=sys.stderr)
        execute_plan(
            outcome.plan,
            on_step=lambda step: print(
                f"Installing {step.package} {step.version}...", file=sys.stderr
            ),
        )
        if not args.skip_verify:
            packages = tuple(dict.fromkeys(step.package for step in outcome.plan.ordered_steps()))
            results = verify_packages(packages, run_gpu=True)
            print("\nPost-install verification:", file=sys.stderr)
            print(format_smoke_results(results), end="", file=sys.stderr)
            if not all(result.ok for result in results):
                return int(ExitCode.ENVIRONMENT_BROKEN)
    return int(ExitCode.OK)


def _check_command(args: argparse.Namespace, store: MatrixStore) -> int:
    profile = detect_machine_profile()
    report = check_environment(
        profile,
        store,
        lockfile=args.lockfile,
        build_repair_plan=args.fix,
    )
    print(format_check_report(report), end="")
    if args.fix:
        if report.repair_plan:
            print("\nRepair plan (review before running):")
            print(render_plan(report.repair_plan, args.output), end="")
        elif report.violations:
            print("\nNo automatic repair plan is covered by the current matrix.")
    return int(ExitCode.OK if report.healthy else ExitCode.ENVIRONMENT_BROKEN)


def _why_command(args: argparse.Namespace, store: MatrixStore) -> int:
    profile = _profile(args.target, args.python_version)
    outcome = resolve(
        args.spec,
        profile,
        store,
        allow_source_build=args.allow_source_build,
    )
    if outcome.satisfiable:
        assert outcome.plan is not None
        packages = ", ".join(
            f"{step.package}=={step.version}" for step in outcome.plan.ordered_steps()
        )
        print(f"A solution exists (evidence: {outcome.plan.evidence_label}): {packages}")
        return int(ExitCode.OK)
    assert outcome.failure is not None
    print(explain_failure(outcome.failure, profile), end="")
    return int(ExitCode.UNSATISFIABLE)


def _verify_command(args: argparse.Namespace, store: MatrixStore) -> int:
    profile = detect_machine_profile()
    packages = args.packages
    if packages is None:
        installed = {package.normalized_name for package in profile.installed.packages}
        packages = sorted(installed.intersection(PROBES))
    results = verify_packages(packages, run_gpu=not args.no_gpu, timeout=args.timeout)
    print(format_smoke_results(results), end="")
    if args.contribute:
        payload = contribution_payload(results, profile.to_dict(), store.matrix_version)
        args.contribution_file.write_text(payload, encoding="utf-8", newline="\n")
        print(
            f"Wrote {args.contribution_file}. Review it, then attach it to a verification issue; nothing was uploaded.",
            file=sys.stderr,
        )
    return int(ExitCode.OK if all(result.ok for result in results) else ExitCode.ENVIRONMENT_BROKEN)


def _matrix_command(args: argparse.Namespace, store: MatrixStore) -> int:
    if args.matrix_command == "update":
        result = fetch_update(
            args.url,
            current=store,
            destination=args.destination,
            merge=not args.no_merge,
        )
        state = (
            "not modified"
            if result.not_modified
            else ("updated" if result.changed else "unchanged")
        )
        print(f"Matrix {state}: {result.store.matrix_version} ({len(result.store.facts)} facts)")
        if result.cache_path:
            print(f"Cache: {result.cache_path}")
        return int(ExitCode.OK)
    if args.matrix_command == "stats":
        stats = store.stats().as_dict()
        if args.json:
            print(json.dumps(stats, indent=2, sort_keys=True))
        else:
            print(f"Matrix {stats['matrix_version']} | {stats['fact_count']} facts")
            print(
                "Families: "
                + ", ".join(f"{key}={value}" for key, value in stats["families"].items())
            )
            print(
                "Evidence: "
                + ", ".join(
                    f"{evidence_label(int(key))}={value}" for key, value in stats["tiers"].items()
                )
            )
            print(
                "Packages: "
                + ", ".join(f"{key}={value}" for key, value in stats["packages"].items())
            )
        return int(ExitCode.OK)
    if args.matrix_command == "show":
        facts = store.facts
        if args.package:
            name = canonicalize_name(args.package)
            facts = tuple(
                fact
                for fact in facts
                if getattr(fact, "package", None) == name
                or name in getattr(fact, "packages", ())
                or getattr(fact, "match_map", {}).get("package") == name
            )
        payload = {
            "metadata": store.metadata.to_mapping(),
            "digest": store.digest,
            "facts": [{"family": fact.__class__.__name__, **fact.to_mapping()} for fact in facts],
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Matrix {store.matrix_version} | sha256:{store.digest}")
            for fact in facts:
                package = (
                    getattr(fact, "package", None)
                    or ",".join(getattr(fact, "packages", ()))
                    or getattr(fact, "match_map", {}).get("package", "")
                )
                version = getattr(fact, "version", "")
                print(f"- {fact.__class__.__name__}: {package} {version} | tier {int(fact.tier)}")
                print(f"  {fact.source.citation()}")
        return int(ExitCode.OK)
    if args.matrix_command == "add":
        contribution = MatrixStore.load(args.file)
        merged = store.merge(contribution)
        save_matrix(args.destination, merged)
        print(f"Validated and wrote {len(merged.facts)} facts to {args.destination}")
        return int(ExitCode.OK)
    raise UserInputError(f"unknown matrix command: {args.matrix_command}")


def _doctor_command(store: MatrixStore) -> int:
    profile = detect_machine_profile()
    checks = run_doctor(profile, store)
    print(format_doctor(checks), end="")
    matrix_check = next(check for check in checks if check.name == "matrix")
    return int(ExitCode.OK if matrix_check.ok else ExitCode.MATRIX_STALE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args: argparse.Namespace | None = None
    try:
        args = parser.parse_args(argv)
        if args.command == "detect":
            return _detect_command(args)
        store = _store(args.matrix)
        if args.command == "solve":
            return _solve_command(args, store)
        if args.command == "check":
            return _check_command(args, store)
        if args.command == "why":
            return _why_command(args, store)
        if args.command == "verify":
            return _verify_command(args, store)
        if args.command == "matrix":
            return _matrix_command(args, store)
        if args.command == "doctor":
            return _doctor_command(store)
        parser.error(f"unknown command: {args.command}")
    except RigsolveError as error:
        print(f"error: {error}", file=sys.stderr)
        if args is not None and args.debug:
            traceback.print_exc()
        return int(error.exit_code)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        if args is not None and args.debug:
            traceback.print_exc()
        return int(ExitCode.ENVIRONMENT_BROKEN)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as error:
        print(
            f"internal error: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        print("rerun with --debug for a traceback and report this as a bug", file=sys.stderr)
        if args is not None and args.debug:
            traceback.print_exc()
        return int(ExitCode.INTERNAL)
    raise AssertionError("unreachable command dispatch")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
