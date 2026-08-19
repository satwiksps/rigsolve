# Contributing to rigsolve

rigsolve depends on precise compatibility evidence. A narrowly scoped fact with a reproducible source is more useful than a broad claim that cannot be audited.

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.

## Before opening an issue

- Search existing issues and the bundled matrix for the same package and failure.
- Include the exact command, exit code, sanitized output, operating system, Python version, and matrix version.
- Remove credentials, private index URLs, usernames, hostnames, and other identifying data.
- Separate a compatibility defect from missing evidence. Unknown coverage is not proof of incompatibility.

Feature proposals should describe the user problem, the expected CLI behavior, and how the result can remain deterministic and explainable.

## Development setup

rigsolve supports Python 3.10 and newer. No NVIDIA GPU is required for the unit suite; detection tests use recorded fixtures.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install -r docs/requirements.txt
```

PowerShell activation uses:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install -r docs/requirements.txt
```

Run the project checks before submitting a change:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src/rigsolve
python -m pytest --cov=rigsolve --cov-report=term-missing
python -m build
python .github/scripts/check_docs.py
python -m sphinx -W --keep-going -b dirhtml docs docs/_build/dirhtml
```

For website changes, also run `npm ci` and `npm test` from `site/`.

## Code changes

- Keep changes focused and add regression tests for behavioral fixes.
- Preserve documented exit codes and machine-readable output contracts.
- Do not make rendering install packages. Only explicit execution may mutate an environment.
- Treat missing profile or matrix fields as unknown, never as implicit compatibility.
- Keep plans deterministic: do not derive lockfile content from unrelated host state.
- Update user documentation when commands, schemas, or trust claims change.

## Compatibility evidence

Matrix facts are claims with defined scope. Before editing matrix data, read
[the matrix schema](docs/matrix-schema.md) and [the trust model](docs/trust-model.md).

Every fact must have provenance, an honest verification tier, and only the axes established by its source. In particular:

- artifact names and upstream build scripts establish tier 0 only;
- installation evidence must identify the exact artifact and environment;
- import evidence must record the available build configuration;
- tier 3 requires a real kernel run on the recorded GPU architecture;
- negative evidence needs a precise symptom and a useful workaround;
- one GPU, OS, Python ABI, or container result must not be generalized to another.

To report a known-broken combination, start from
[`examples/known-broken.toml`](examples/known-broken.toml). Validate the proposed merge into a temporary destination before opening a pull request:

```bash
rigsolve --matrix src/rigsolve/data/matrix.toml \
  matrix add examples/known-broken.toml \
  --destination /tmp/rigsolve-matrix.toml
rigsolve --matrix /tmp/rigsolve-matrix.toml matrix stats
```

Replace the example source and placeholder values with evidence from the real report.

## Verification reports

`rigsolve verify --contribute` writes `rigsolve-verification.json` locally and uploads nothing. Review the file before sharing it; a profile can contain GPU, driver, platform, and installed-package metadata.

Attach the sanitized payload and reproduction steps to a
[verification report](https://github.com/satwiksps/rigsolve/issues/new?template=verification.yml). Maintainers decide whether the evidence is reproducible and narrowly scoped enough for the bundled matrix.

## Pull requests

A pull request should state:

1. the problem and user-visible result;
2. the tests or evidence that support the change;
3. any hardware, platform, or package combinations not tested;
4. documentation or schema changes included with it.

Small changes are easier to audit. Maintainers may ask for matrix-data changes to be separated from solver changes so the evidence diff remains reviewable.

By contributing, you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE).
