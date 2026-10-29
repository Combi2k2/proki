"""Every folder under proki/ with an __init__.py must be listed as a package in pyproject.toml."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_all_packages_are_listed():
    listed = set(tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]["packages"])
    found = {"proki" + "".join("." + part for part in init.parent.relative_to(ROOT / "proki").parts)
             for init in (ROOT / "proki").rglob("__init__.py") if "__pycache__" not in init.parts}
    assert found == listed, f"missing: {found - listed}, extra: {listed - found}"
