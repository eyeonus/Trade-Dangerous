# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Command Line App :: Main Module
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
from __future__ import annotations
import os
import sys
import traceback

from .commands import exceptions
from .plugins import PluginException
from . import commands
from . import tradeexcept
from .tradeorm import TradeORM

if "CPROF" in os.environ:
    import cProfile
else:
    cProfile = None  # type: ignore


def main(argv: list[str] | None = None) -> int:
    """ standard entry point, taking an optional argument list or defaulting to sys.argv. """
    if argv is None:
        argv = sys.argv
    if sys.version_info < (3, 12):
        raise SystemExit(
            "Sorry: TradeDangerous requires Python 3.12 or higher.\n"
            "For assistance, see:\n"
            "\tBug Tracker: https://github.com/eyeonus/Trade-Dangerous/issues\n"
            "\tDocumentation: https://github.com/eyeonus/Trade-Dangerous/wiki\n"
            "\tEDForum Thread: https://forums.frontier.co.uk/showthread.php/441509\n"
        )
    
    try:
        try:
            if cProfile and "CPROF" in os.environ:
                cProfile.runctx("trade(argv)", globals(), locals())
                return 0
            return trade(argv)
        except PluginException as e:
            print("PLUGIN ERROR: {}".format(e))
            if 'EXCEPTIONS' in os.environ:
                raise e
            return 1
        except tradeexcept.TradeException as e:
            print("%s: %s" % (argv[0], str(e)))
            if 'EXCEPTIONS' in os.environ:
                raise e
            return 1
    except (UnicodeEncodeError, UnicodeDecodeError):
        print("-----------------------------------------------------------")
        print("ERROR: Unexpected unicode error in the wild!")
        print()
        print(traceback.format_exc())
        print(
            "Please report this bug (http://github.com/eyeonus/Trade-Dangerous/issues). You may be "
            "able to work around it by using the '-q' parameter. Windows "
            "users may be able to use 'chcp.com 65001' to tell the console "
            "you want to support UTF-8 characters."
        )
        return 1

def trade(argv):
    """
    This method represents the trade command.
    """
    import time
    
    total_started = time.perf_counter()
    parse_started = total_started
    cmdIndex = commands.CommandIndex()
    cmdenv = cmdIndex.parse(argv)
    cmdenv.DEBUG0(
        "TIMING parse: {:.3f}ms",
        (time.perf_counter() - parse_started) * 1000.0,
    )
    
    try:
        # Phase A: preflight/fast validation (must run before any heavy TradeDB load)
        with cmdenv.time_block("preflight", level=0):
            if (preflight := getattr(cmdenv, "preflight", None)) and callable(preflight):
                preflight()
        
        # Phase B1: ORM resolver — only for commands that declare Needs.RESOLVER.
        torm = None
        tdb = None
        if cmdenv.needs_resolver:
            # Build/bootstrap commands (buildcache) create the DB themselves, so
            # they set allowMissingDB to construct the handle without a db file.
            allow_missing = getattr(cmdenv._cmd, "allowMissingDB", False)
            with cmdenv.time_block("TradeORM.__init__", level=0):
                torm = TradeORM(tdenv=cmdenv, require_db=not allow_missing)
            tdb = torm

        if cmdenv.usesTradeData and tdb is not None:
            tsc = tdb.tradingStationCount
            if tsc == 0:
                raise exceptions.NoDataError(
                    "There is no trading data for ANY station in "
                    "the local database. Please enter or import "
                    "price data."
                )
            if tsc == 1:
                raise exceptions.NoDataError(
                    "The local database only contains trading data "
                    "for one station. Please enter or import data "
                    "for additional stations."
                )
            if tsc < 8:
                cmdenv.NOTE(
                    "The local database only contains trading data "
                    "for {} stations. Please enter or import data "
                    "for additional stations.".format(
                        tsc
                    )
                )
        
        results = None
        try:
            with cmdenv.time_block("command_run", level=0):
                results = cmdenv.run(tdb)
            if results:
                with cmdenv.time_block("render", level=0):
                    results.render()
        except tradeexcept.SimpleAbort as e:
            cmdenv.console.print(f"\n{e}\n", style="red")
            sys.exit(1)
        finally:
            if tdb is not None:
                tdb.close(final=True)
            if torm is not None and torm is not tdb:
                torm.close()
    finally:
        cmdenv.DEBUG0(
            "TIMING total: {:.3f}ms",
            (time.perf_counter() - total_started) * 1000.0,
        )