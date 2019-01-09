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

from __future__ import absolute_import
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals
import os
import traceback

from . import commands
from .commands import exceptions
from .plugins import PluginException


from . import tradedb


def main():
    import sys
    if sys.hexversion < 0x03040200:
        raise SystemExit(
            "Sorry: TradeDangerous requires Python 3.4.2 or higher.\n"
            "For assistance, see:\n"
            "\tFacebook Group: http://kfs.org/td/group\n"
            "\tBitbucket Page: http://kfs.org/td/source\n"
            "\tEDForum Thread: http://kfs.org/td/thread\n"
            )
    from . import tradeexcept

    try:
        try:
            if "CPROF" in os.environ:
                import cProfile
                cProfile.run("main(sys.argv)")
            else:
                trade(sys.argv)
        except PluginException as e:
            print("PLUGIN ERROR: {}".format(e))
            if 'EXCEPTIONS' in os.environ:
                raise e
            sys.exit(1)
        except tradeexcept.TradeException as e:
            print("%s: %s" % (sys.argv[0], str(e)))
            if 'EXCEPTIONS' in os.environ:
                raise e
            sys.exit(1)
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        print("-----------------------------------------------------------")
        print("ERROR: Unexpected unicode error in the wild!")
        print()
        print(traceback.format_exc())
        print(
            "Please report this bug (http://kfs.org/td/issues). You may be "
            "able to work around it by using the '-q' parameter. Windows "
            "users may be able to use 'chcp.com 65001' to tell the console "
            "you want to support UTF-8 characters."
        )


def trade(argv):
    cmdIndex = commands.CommandIndex()
    cmdenv = cmdIndex.parse(argv)

    tdb = tradedb.TradeDB(cmdenv, load=cmdenv.wantsTradeDB)
    if cmdenv.usesTradeData:
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

    results = cmdenv.run(tdb)
    if results:
        tdb.close()
        results.render()


