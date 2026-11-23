"""Distribution metadata for HealthChecker.Server."""

from setuptools import find_packages, setup

setup(
    name="healthchecker-server",
    version="0.1.0",
    description="Zeroconf-discoverable health-check monitoring service and client",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Dwight Mulcahy",
    url="https://github.com/dwightmulcahy/healthchecker.server",
    packages=find_packages(include=["healthcheck", "healthcheck.*",
                                    "healthchecker_server", "healthchecker_server.*",
                                    "utils", "utils.*"]),
    python_requires=">=3.10",
    install_requires=[
        "requests",
        "zeroconf",
        "flask",
        "Flask-API.yandex",
        "transitions",
        "validators",
        "waitress",
        "apscheduler",
        "prettytable",
        "gmail",
        "click",
        "click-config-file",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
