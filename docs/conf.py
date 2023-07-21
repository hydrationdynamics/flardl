"""Sphinx configuration."""
project = "Flardl"
author = "Joel Berendzen"
copyright = "2023, Joel Berendzen"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
