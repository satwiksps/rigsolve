from __future__ import annotations

import os
import sys
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "rigsolve"
author = "rigsolve contributors"
copyright = "2026, rigsolve contributors"
release = version("rigsolve")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "assets"]
templates_path = ["_templates"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_url_schemes = ("http", "https", "mailto")

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_preserve_defaults = True
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "packaging": ("https://packaging.pypa.io/en/stable/", None),
}

html_theme = "furo"
html_title = "rigsolve"
html_baseurl = os.environ.get(
    "READTHEDOCS_CANONICAL_URL",
    "https://rigsolve.readthedocs.io/en/latest/",
)
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "source_repository": "https://github.com/satwiksps/rigsolve/",
    "source_branch": os.environ.get("READTHEDOCS_GIT_COMMIT_HASH", "main"),
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#155eef",
        "color-brand-content": "#155eef",
    },
    "dark_css_variables": {
        "color-brand-primary": "#7aa2ff",
        "color-brand-content": "#8bb0ff",
    },
}
html_context = {
    "display_github": True,
    "github_user": "satwiksps",
    "github_repo": "rigsolve",
    "github_version": "main",
    "conf_py_path": "/docs/",
    "READTHEDOCS": os.environ.get("READTHEDOCS", "False") == "True",
}
html_show_sourcelink = True
html_show_sphinx = False
html_copy_source = False

copybutton_prompt_text = r"^\$ |^>>> |^\.\.\. "
copybutton_prompt_is_regexp = True

nitpicky = True
nitpick_ignore = [
    ("py:class", "PathLike"),
    ("py:class", "_F"),
    ("py:class", "_P"),
    ("py:class", "_T"),
    ("py:class", "rigsolve.detect._command.CommandRunner"),
    ("py:class", "rigsolve.solve.resolver.CoverageGap"),
]
suppress_warnings = ["epub.unknown_project_files", "myst.header"]

linkcheck_anchors = True
linkcheck_timeout = 15
linkcheck_retries = 2
linkcheck_ignore = [
    r"https://github\.com/satwiksps/rigsolve/issues/new.*",
]

latex_documents = [(master_doc, "rigsolve.tex", "rigsolve Documentation", author, "manual")]
epub_title = "rigsolve Documentation"
epub_author = author
epub_exclude_files = ["search.html"]
