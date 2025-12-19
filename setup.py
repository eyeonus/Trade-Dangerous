#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Stefan 'Tromador' Morrell 2025
# Copyright (C) Jonathan 'eyeonus' Jones 2018 - 2025
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
"""Setup for trade-dangerous"""
import sys
from setuptools import find_packages, setup

try:
    from semantic_release import setup_hook
    setup_hook(sys.argv)
except ImportError:
    pass

with open("README.md", "r") as fh:
    long_description = fh.read()

package = "tradedangerous"

exec(open("tradedangerous/version.py").read())  # pylint: disable=W0122

setup(
    name=package,
    version=__version__,  # pylint: disable=E0602
    packages=find_packages(include=["tradedangerous", "tradedangerous.*"]),
    py_modules=["trade", "tradegui"],
    url="https://github.com/eyeonus/Trade-Dangerous",
    project_urls={
        "Bug Tracker": "https://github.com/eyeonus/Trade-Dangerous/issues",
        "Documentation": "https://github.com/eyeonus/Trade-Dangerous/wiki",
        "Source Code": "https://github.com/eyeonus/Trade-Dangerous",
    },
    author="eyeonus",
    author_email="eyeonus@gmail.com",
    description=(
        "Trade-Dangerous is a set of powerful trading tools for Elite Dangerous, "
        "organized around one of the most powerful trade run optimizers available."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords=["trade", "elite", "elite-dangerous"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ],
    license="MPL-2.0",
    python_requires=">=3.10",
    test_suite="tests",
    package_data={
        "tradedangerous": [
            "templates/TradeDangerous.sql",
            "templates/Added.csv",
            "templates/Category.csv",
            "templates/RareItem.csv",
            "templates/database_changes.json",
            "tradeenv.pyi",
            "py.typed",
        ]
    },
    zip_safe=False,
)
