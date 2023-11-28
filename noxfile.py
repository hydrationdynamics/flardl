"""Nox sessions."""
import os
import random
import shutil
import sys
from pathlib import Path

import nox


os.environ.update({"PDM_IGNORE_SAVED_PYTHON": "1"})

package = "flardl"
python_versions = ["3.12", "3.11", "3.10", "3.9"]
nox.needs_version = ">= 2021.10.1"
nox.options.sessions = (
    "pre-commit",
    "safety",
    "mypy",
    "tests",
    "typeguard",
    "xdoctest",
    "docs-build",
)


@nox.session(name="pre-commit", python=python_versions[0])
def precommit(session: nox.Session) -> None:
    """Lint using pre-commit."""
    args = session.posargs or [
        "run",
        "--all-files",
        "--hook-stage=manual",
        "--show-diff-on-failure",
    ]
    session.run_always("pdm", "install", "-G", "pre-commit", external=True)
    session.run("pre-commit", *args)


@nox.session(python=python_versions[0])
def safety(session: nox.Session) -> None:
    """Scan dependencies for insecure packages."""
    session.run_always("pdm", "install", "-G", "safety", external=True)
    session.run_always("pdm", "export", "-o", "requirements.txt", "--without-hashes")
    session.run("safety", "check", "--full-report")
    Path("requirements.txt").unlink()


@nox.session(python=python_versions)
def mypy(session: nox.Session) -> None:
    """Type-check using mypy."""
    args = session.posargs or ["src"]
    session.run_always("pdm", "install", "-G", "tests",
                       "-G", "mypy", external=True)
    session.run("mypy", *args)
    if not session.posargs:
        session.run(
            "mypy",
            f"--python-executable={sys.executable}",
            "--check-untyped-defs",
            "noxfile.py",
        )


@nox.session(python=python_versions)
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.run_always("pdm", "install", "-G", "tests",
                       "-G", "coverage", external=True)
    try:
        session.run("coverage", "run", "-m", "pytest", *session.posargs)
        cov_path = Path(".coverage")
        if cov_path.exists():
            cov_path.rename(f".coverage.{random.randrange(100000)}")  # noqa: S311
    finally:
        if session.interactive:
            session.notify("coverage", posargs=[])


@nox.session(python=python_versions[0])
def coverage(session: nox.Session) -> None:
    """Produce the coverage report."""
    args = session.posargs or ["report"]
    session.run_always("pdm", "install",
                       "-G", "coverage", external=True)

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")
    session.run("coverage", *args)


@nox.session(python=python_versions)
def typeguard(session: nox.Session) -> None:
    """Runtime type checking using Typeguard."""
    session.run_always("pdm", "install", "-G", "tests",
                       "-G", "typeguard", external=True)
    session.run("pytest", f"--typeguard-packages={package}", *session.posargs)


@nox.session(python=python_versions)
def xdoctest(session: nox.Session) -> None:
    """Run examples with xdoctest."""
    if session.posargs:
        args = [package, *session.posargs]
    else:
        args = [f"--modname={package}", "--command=all"]
        if "FORCE_COLOR" in os.environ:
            args.append("--colored=1")
    session.run_always("pdm", "install",
                       "-G", "xdoctest", external=True)
    session.run("python", "-m", "xdoctest", *args)


@nox.session(name="docs-build", python=python_versions[0])
def docs_build(session: nox.Session) -> None:
    """Build the documentation."""
    args = session.posargs or ["docs", "docs/_build"]
    if not session.posargs and "FORCE_COLOR" in os.environ:
        args.insert(0, "--color")
    session.run_always("pdm", "install",
                       "-G", "docs", external=True)
    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    session.run("sphinx-build", *args)


@nox.session(python=python_versions[0])
def docs(session: nox.Session) -> None:
    """Build and serve the documentation with live reloading on file changes."""
    args = session.posargs or ["--open-browser", "docs", "docs/_build"]
    session.run_always("pdm", "install",
                       "-G", "docs", external=True)
    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    session.run("sphinx-autobuild", *args)
