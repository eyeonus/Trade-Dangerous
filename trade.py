#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2022
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Command Line App :: Main Module
#
# This is the main entry point into the native TD CLI.
#
# TradeDangerous is a powerful set of tools for traders in Frontier
# Development's game "Elite: Dangerous". It's main function is
# calculating the most profitable trades between either individual
# stations or working out "profit runs".
#
# I wrote TD because I realized that the best trade run - in terms
# of the "average profit per stop" was rarely as simple as going
# Chango -> Dahan -> Chango.
#
# E:D's economy is complex; sometimes you can make the most profit
# by trading one item A->B and flying a second item B->A.
# But more often you need to fly multiple stations, especially since
# as you are making money different trade options are coming into
# your affordable range.
#
# END USERS: If you are a user looking to find out how to use TD,
# please consult the file "README.md".
#
# DEVELOPERS: If you are a programmer who wants TD to do something
# cool, please see the TradeDB and TradeCalc modules. TD is designed
# to empower other programmers to do cool stuff.
import os
import sys

from tradedangerous.version import __version__ as TDVER


if __name__ == "__main__":
    # Import errors could put users outside their comfort zone; be supportive.
    try:
        # For testing
        if os.environ.get("TD_FAIL_IMPORT"):
            import tradedangerous.yaboono  # noqa   # pylint:disable=unused-import

        from tradedangerous import cli, SimpleAbort

    except ImportError as e:
        sys.stderr.write(f"** {e.__class__.__name__}: {e}\n")
        if sys.stderr.isatty():
            sys.stderr.write("\x1b[1m")  # bold mode
        sys.stderr.write(
            "## You may need to install/update one or more dependency: ##\n"
            "\n"
            "    pip install --upgrade --user -r requirements.txt\n\n"
        )

        # if the variable 'VIRTUAL_ENV' is set, --user would break.
        env = getattr(os, "environ", [])
        if "VIRTUAL_ENV" in env:
            sys.stderr.write("or\n\n    pip install --upgrade -r requirements.txt\n\n")
        if "CONDA_EXE" in env:
            sys.stderr.write("or\n\n    conda install --yes --file requirements.txt\n\n")
        if "MAMBA_EXE" in env:
            sys.stderr.write("or\n\n    mamba install --yes --file requirements.txt\n\n")

        if sys.stderr.isatty():
            sys.stderr.write("\x1b[0m")  # unbold mode
        sys.stderr.write("(* exact command may vary if using package managers)\n")
        sys.stderr.write(f"-- TradeDangerous v{TDVER}\n")

        if 'EXCEPTIONS' in os.environ:
            raise e  # raise it as it was

        sys.exit(1)


    # Back to business

    
    def main(argv = None):
        cli.main(argv or sys.argv)

    try:
        cli.main(sys.argv)
    except SimpleAbort as e:
        print(str(e))
