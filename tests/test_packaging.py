"""Validate distribution metadata and importable module contents."""

import importlib
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "healthcheck", "healthchecker_server", "http_status", "iputils",
    "statemachine", "uptime", "monitor_validation", "monitor_store",
    "status_page",
}


def metadata():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_metadata_has_valid_build_backend_and_identity():
    data = metadata()
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    project = data["project"]
    assert project["name"] == "healthchecker-server"
    assert project["requires-python"].startswith(">=")
    assert project["scripts"]["healthchecker-server"] == "healthchecker_server:main"
    assert "README.md" == project["readme"]
    assert "flask>=3,<4" in project["dependencies"]
    assert not any("Flask-API" in entry for entry in project["dependencies"])


def test_every_production_module_is_included_in_distribution():
    data = metadata()
    declared = set(data["tool"]["setuptools"]["py-modules"])
    assert declared == MODULES
    for module in declared:
        assert (ROOT / (module + ".py")).is_file()


@pytest.mark.parametrize("module", ["http_status", "monitor_store", "monitor_validation", "status_page"])
def test_pure_modules_import_without_optional_runtime_dependencies(module):
    assert importlib.import_module(module) is not None


def test_http_status_is_consistent_with_stdlib():
    from http import HTTPStatus
    from http_status import status

    assert status.HTTP_200_OK == HTTPStatus.OK
    assert status.HTTP_201_CREATED == HTTPStatus.CREATED
    assert status.HTTP_400_BAD_REQUEST == HTTPStatus.BAD_REQUEST
    assert status.HTTP_503_SERVICE_UNAVAILABLE == HTTPStatus.SERVICE_UNAVAILABLE
