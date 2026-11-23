"""Check README links, critical limitations and fenced Python examples."""

import ast
from pathlib import Path
import re


def test_readme_examples_and_links():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for relative in ("docs/client.md", "example/healthcheck_example.py"):
        assert (root / relative).exists()
        assert relative in readme
    snippets = re.findall(r"```python\n(.*?)\n```", readme, re.DOTALL)
    assert snippets
    for snippet in snippets:
        ast.parse(snippet)


def test_readme_warns_about_legacy_runtime_and_unprotected_controls():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "not verified as published on PyPI" in readme
    assert "untrusted networks" in readme
    assert "90% coverage across the entire server" in readme
