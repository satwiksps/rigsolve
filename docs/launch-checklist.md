# Release and deployment runbook

The canonical repository is `https://github.com/satwiksps/rigsolve`. Published releases are available from PyPI and GitHub; `main` may contain changes that are not in the latest release.

## Repository and publishing prerequisites

1. Keep `main` as the default and only persistent branch. Protect it from deletion and force-pushes, and require the CI and security checks.
2. Keep private vulnerability reporting and dependency alerts enabled. Automated dependency security fixes and Actions pull-request creation should remain disabled so maintenance cannot create repository branches.
3. Keep package metadata, documentation links, matrix-update URLs, and workflow repository guards pointed at `satwiksps/rigsolve`.
4. Confirm the `rigsolve` PyPI project is owned by the expected maintainers and still uses the repository's trusted publisher.
5. Create a protected GitHub environment named `pypi`. Configure a PyPI trusted publisher for repository `satwiksps/rigsolve`, workflow `release.yml`, environment `pypi`, and the intended package name. No long-lived PyPI token belongs in GitHub secrets.

## Validate the release candidate

Run the same gates as CI from a clean checkout:

```bash
python -m pip install -e ".[dev]" twine
python -m ruff check .
python -m ruff format --check .
python -m mypy src/rigsolve
python -m pytest --cov=rigsolve --cov-report=term-missing
python .github/scripts/check_docs.py
python -m rigsolve --matrix src/rigsolve/data/matrix.toml matrix stats --json
python -m build
python -m twine check dist/*

cd site
npm ci
npm test
```

Before tagging, update the package and citation versions together, move the shipped entries from `Unreleased` into a dated changelog section, and verify that all matrix claims still match `rigsolve matrix stats`. Commit those changes directly to `main` and wait for its CI and security workflows to pass.

## Publish a tag

Create a signed or annotated `vX.Y.Z` tag that exactly matches `project.version` in `pyproject.toml`, then push only that tag. The release workflow rejects a tag whose commit is not on `main` or whose name does not match the package version.

The tag workflow repeats the full Python 3.10 through 3.14 tests, linting, formatting, strict type checking, documentation and matrix validation, and the production website build. It then builds both distributions, checks their metadata, installs the wheel into a clean environment, and runs the CLI smoke path. PyPI publishing uses trusted publishing. The GitHub release and its artifacts are created only after PyPI succeeds, preventing a partial public release.

After publication, verify:

```text
https://pypi.org/project/rigsolve/
https://github.com/satwiksps/rigsolve/releases
https://raw.githubusercontent.com/satwiksps/rigsolve/main/src/rigsolve/data/matrix.toml
```

Install the published wheel in a separate clean environment and run `rigsolve --version`, `rigsolve matrix stats`, and the README quick-start solve. Do not claim tier-1, tier-2, or tier-3 coverage unless the released matrix contains reviewed facts at those tiers.

## Deploy the website on Vercel

1. Import `satwiksps/rigsolve` into Vercel.
2. Set the project **Root Directory** to `site`.
3. Keep the auto-detected **Next.js** framework preset and default install and build commands.
4. Deploy `main` to production only after the website job passes.
5. For a custom production domain, set `NEXT_PUBLIC_SITE_URL` to the canonical HTTPS origin and add that URL to the repository About section.
6. Verify the deployed page on narrow mobile and desktop viewports, then exercise its repository, documentation, installation, and contribution links.

The website requires no database, server-side secret, or external runtime service.
