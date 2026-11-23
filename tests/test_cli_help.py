"""Check that Click help metadata remains complete without starting the server."""

import ast
from pathlib import Path


def test_every_cli_option_has_meaningful_help():
    source = Path(__file__).resolve().parents[1] / "healthchecker_server.py"
    syntax = ast.parse(source.read_text(encoding="utf-8"))
    main = next(
        node for node in syntax.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    expected = {"--verbose", "--test", "--debug", "--gmail_token",
                "--bind_addr", "--port"}
    found = set()
    for decorator in main.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        option_name = decorator.args[0]
        if not isinstance(option_name, ast.Constant) or option_name.value not in expected:
            continue
        help_kw = next((kw.value for kw in decorator.keywords if kw.arg == "help"), None)
        assert isinstance(help_kw, ast.Constant), option_name.value
        assert isinstance(help_kw.value, str) and len(help_kw.value) >= 20, option_name.value
        found.add(option_name.value)
    assert found == expected
