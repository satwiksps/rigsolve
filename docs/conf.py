from __future__ import annotations

import inspect
import os
import re
import sys
from dataclasses import is_dataclass
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
    "sphinx_immaterial",
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
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
autodoc_docstring_signature = False
autodoc_preserve_defaults = True
autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "packaging": ("https://packaging.pypa.io/en/stable/", None),
}

html_theme = "sphinx_immaterial"
html_title = "rigsolve"
html_baseurl = (
    os.environ.get(
        "READTHEDOCS_CANONICAL_URL",
        "https://rigsolve.readthedocs.io/en/latest/",
    ).rstrip("/")
    + "/"
)
html_logo = "assets/rigsolve-mark.svg"
html_favicon = "assets/rigsolve-mark.svg"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "site_url": html_baseurl,
    "repo_url": "https://github.com/satwiksps/rigsolve",
    "repo_name": "satwiksps/rigsolve",
    "edit_uri": "edit/main/docs/",
    "globaltoc_collapse": False,
    "toc_title": "On this page",
    "font": False,
    "icon": {
        "repo": "fontawesome/brands/github",
        "edit": "material/file-edit-outline",
    },
    "features": [
        "content.action.edit",
        "content.code.copy",
        "navigation.sections",
        "navigation.expand",
        "navigation.top",
        "navigation.footer",
        "search.highlight",
        "search.share",
        "search.suggest",
        "toc.follow",
        "toc.sticky",
    ],
    "palette": [
        {
            "media": "(prefers-color-scheme: dark)",
            "scheme": "slate",
            "primary": "custom",
            "accent": "custom",
            "toggle": {
                "icon": "material/weather-sunny",
                "name": "Use light mode",
            },
        },
        {
            "media": "(prefers-color-scheme: light)",
            "scheme": "default",
            "primary": "custom",
            "accent": "custom",
            "toggle": {
                "icon": "material/weather-night",
                "name": "Use dark mode",
            },
        },
    ],
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


def _prepare_page_urls(_app, pagename, _templatename, context, _doctree):
    page = context.get("page")
    pageurl = context.get("pageurl")
    if isinstance(page, dict) and pageurl:
        page["canonical_url"] = pageurl
    if isinstance(page, dict):
        if pagename.startswith("_modules/"):
            page["edit_url"] = None
        elif isinstance(page.get("edit_url"), str):
            page["edit_url"] = page["edit_url"].replace("\\", "/")


def _normalize_autodoc_signature(
    _app,
    _what,
    _name,
    _obj,
    _options,
    signature,
    return_annotation,
):
    if signature:
        signature = re.sub(r"(?<==)\s*<[^<>]+>", "...", signature)
    return signature, return_annotation


def _remove_generated_dataclass_docstring(
    _app,
    what,
    _name,
    obj,
    _options,
    lines,
):
    if what != "class" or not is_dataclass(obj):
        return
    generated = f"{obj.__name__}{inspect.signature(obj)}".replace(" -> None", "")
    if "\n".join(lines).strip() == generated:
        lines.clear()


def setup(app):
    app.connect("autodoc-process-signature", _normalize_autodoc_signature)
    app.connect(
        "autodoc-process-docstring",
        _remove_generated_dataclass_docstring,
        priority=100,
    )
    app.connect("html-page-context", _prepare_page_urls, priority=800)


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
