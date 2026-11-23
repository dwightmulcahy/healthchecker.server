"""Require substantive docstrings for every public module API."""

import ast
from pathlib import Path

import pytest


MODULES = [
    "healthcheck.py",
    "healthchecker_server.py",
    "iputils.py",
    "statemachine.py",
    "uptime.py",
    "monitor_validation.py",
]


def public_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node


@pytest.mark.parametrize("relative_path", MODULES)
def test_public_apis_have_docstrings(relative_path):
    root = Path(__file__).resolve().parents[1]
    syntax = ast.parse((root / relative_path).read_text(encoding="utf-8"))
    missing = []
    for node in public_nodes(syntax):
        doc = ast.get_docstring(node)
        if not doc or len(doc.splitlines()[0].strip()) < 12:
            missing.append(node.name)
    assert not missing, f"{relative_path}: missing docstrings: {missing}"
