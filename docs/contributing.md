# Contributing

Contributions should be small enough to review and backed by reproducible evidence where compatibility claims are involved.

Read the complete [contribution guide](https://github.com/satwiksps/rigsolve/blob/main/CONTRIBUTING.md) before opening a pull request.

## Development setup

```console
$ git clone https://github.com/satwiksps/rigsolve.git
$ cd rigsolve
$ python -m pip install -e '.[dev]'
$ python -m pytest
```

## Required checks

```console
$ python -m pytest --cov=rigsolve
$ python -m ruff check .
$ python -m ruff format --check .
$ python -m mypy src/rigsolve
$ python -m sphinx -W --keep-going -b dirhtml docs docs/_build/dirhtml
```

Website changes also require `npm test` in `site/`.

## Documentation changes

Documentation is written in MyST Markdown and built by Sphinx. Follow these rules:

- document current behavior, not planned behavior;
- use commands that can be copied without editing hidden placeholders;
- state when an operation writes files, contacts the network, or installs packages;
- link claims to the relevant API or evidence page;
- keep headings task-oriented and paragraphs short;
- avoid universal compatibility claims;
- run the strict Sphinx build before committing.

For a local live-reload server, install `sphinx-autobuild` separately and run:

```console
$ sphinx-autobuild docs docs/_build/html
```

It is intentionally not a required build dependency.

## Compatibility evidence

Every fact needs a narrow claim, an upstream or recorded execution source, a harvest date, and the correct evidence level. Do not promote an artifact based only on a filename, issue comment, or successful result on a different build.

Read {doc}`matrix-schema`, {doc}`trust-model`, and {doc}`harvesting` before editing the bundled matrix.

## Conduct and security

Participation is governed by the [Code of Conduct](https://github.com/satwiksps/rigsolve/blob/main/CODE_OF_CONDUCT.md). Do not report vulnerabilities in a public issue. Follow {doc}`security`.
