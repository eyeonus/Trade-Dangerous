#!/usr/bin/env python3
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
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
# please consult the file "README.txt".
#
# DEVELOPERS: If you are a programmer who wants TD to do something
# cool, please see the TradeDB and TradeCalc modules. TD is designed
# to empower other programmers to do cool stuff.

######################################################################
# main entry point


def main(argv):
    import commands
    cmdIndex = commands.CommandIndex()
    cmdenv = cmdIndex.parse(sys.argv)

    from tradedb import TradeDB
    if cmdenv.wantsTradeDB:
        # load the database
        tdb = TradeDB(cmdenv, buildLinks=False, includeTrades=False)
    else:
        tdb = TradeDB

    results = cmdenv.run(tdb)
    if results:
        results.render()


######################################################################


if __name__ == "__main__":
    import tradeexcept
    import sys

    try:
        main(sys.argv)
    except tradeexcept.TradeException as e:
        print("%s: %s" % (sys.argv[0], str(e)))
        sys.exit(1)

