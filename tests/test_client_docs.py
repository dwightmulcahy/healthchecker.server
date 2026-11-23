"""Validate Python snippets in the integration guide without side effects."""

import ast
from pathlib import Path
import re


GUIDE = Path(__file__).resolve().parents[1] / "docs" / "client.md"


def test_client_guide_contains_parseable_python_examples():
    text = GUIDE.read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)\n```", text, re.DOTALL)
    assert len(snippets) >= 3
    for snippet in snippets:
        ast.parse(snippet)


def test_client_guide_documents_required_workflow_and_security():
    text = GUIDE.read_text(encoding="utf-8")
    for keyword in (
        "GET /health", "HealthCheckerServer", "client.monitor(",
        "client.pause()", "client.resume()", "client.stop()",
        "Zeroconf", "authorization",
    ):
        assert keyword in text
