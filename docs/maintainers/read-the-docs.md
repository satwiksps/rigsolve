# Publish on Read the Docs

The repository contains everything required for a reproducible Read the Docs build:

- `.readthedocs.yaml` selects Ubuntu 24.04, Python 3.12, Sphinx, strict warnings, PDF, and EPUB;
- `docs/requirements.txt` pins the documentation toolchain;
- `docs/conf.py` configures MyST Markdown, Furo, search, API reference generation, source links, and offline formats.

## Import the project

1. Sign in at [app.readthedocs.org](https://app.readthedocs.org/) with the GitHub account that can administer `satwiksps/rigsolve`.
2. Select **Add project** or **Import a Project**.
3. Choose `satwiksps/rigsolve`.
4. Use the project slug `rigsolve` if it is available.
5. Keep the default branch as `main`.
6. Confirm the configuration file path is `.readthedocs.yaml`.
7. Build the `latest` version.

The expected public URL is `https://rigsolve.readthedocs.io/`. If the slug is unavailable, update `html_baseurl`, the README links, and `project.urls.Documentation` before announcing the site.

## Version settings

In the Read the Docs dashboard:

1. keep `latest` mapped to `main`;
2. activate released `v*` tags;
3. point `stable` to the newest supported release;
4. hide obsolete development branches from the version selector;
5. enable pull request builds only if preview documentation is wanted.

The repository does not require preview builds for production documentation.

## Build locally

```console
$ python -m pip install -e .
$ python -m pip install -r docs/requirements.txt
$ python -m sphinx -W --keep-going -b dirhtml docs docs/_build/dirhtml
```

Open `docs/_build/dirhtml/index.html` after the build.

Build the same additional formats requested from Read the Docs:

```console
$ python -m sphinx -W --keep-going -b epub docs docs/_build/epub
$ python -m sphinx -W --keep-going -b latex docs docs/_build/latex
```

Read the Docs performs the PDF compilation after Sphinx generates LaTeX.

## Production checklist

- the strict HTML build has no warnings;
- the Read the Docs build uses `.readthedocs.yaml` version 2;
- the version selector shows `latest` and released tags only;
- search returns CLI commands, target fields, and common errors;
- source links point to the matching Git tag or branch;
- PDF and EPUB downloads complete;
- the GitHub README Documentation link opens the production docs;
- the PyPI Documentation project URL opens the production docs.

Configuration follows the official [Read the Docs configuration reference](https://docs.readthedocs.com/platform/stable/config-file/v2.html).
