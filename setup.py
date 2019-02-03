#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
"""Setup for trade-dangerous"""

from setuptools import setup, find_packages

package = "tradedangerous"

exec(open("tradedangerous/version.py").read()) #pylint: disable=W0122

setup(name=package,
        version=__version__, #pylint: disable=E0602
        install_requires=["requests"],
        setup_requires=["pytest-runner"],
        tests_require=["pytest"],
        packages=find_packages(exclude=["tests"]),
        url="https://github.com/eyeonus/Trade-Dangerous",
        project_urls={
            "Bug Tracker": "https://github.com/eyeonus/Trade-Dangerous/issues",
            "Documentation": "https://github.com/eyeonus/Trade-Dangerous/wiki",
            "Source Code": "https://github.com/eyeonus/Trade-Dangerous",
        },
        author="eyeonus",
        author_email="eyeonus@gmail.com",
        description="Trade-Dangerous is set of powerful trading tools for Elite Dangerous, organized around one of the most powerful trade run optimizers available.",
        keywords=["trade", "elite", "elite-dangerous"],
        classifiers=[
            "Intended Audience :: Developers",
            "Programming Language :: Python :: 3"
            "Programming Language :: Python :: 3.5"
            "Programming Language :: Python :: 3.6"
        ],
        license="MPL",
        test_suite="tests",
        package_data={"tradedangerous": ["data/TradeDangerous.sql", "data/Added.csv", "data/RareItem.csv"]},
        entry_points={
            "console_scripts": [
                "trade=tradedangerous.cli:main"
            ]
        },
        zip_safe=False
)
