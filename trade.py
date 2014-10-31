#!/usr/bin/env python
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
# Imports

import argparse             # For parsing command line args.
import sys                  # Inevitably.
import time
import pathlib              # For path
import os
import math

######################################################################
# The thing I hate most about Python is the global lock. What kind
# of idiot puts globals in their programs?
import errno

######################################################################
# Database and calculator modules.

from tradeexcept import TradeException
from tradeenv import *
from tradedb import TradeDB, AmbiguityError
from tradecalc import Route, TradeCalc, localedNo

######################################################################
# Definitions for the sub-commands we support and their arguments.

from subcommands.buy import subCommand_BUY
from subcommands.local import subCommand_LOCAL
from subcommands.nav import subCommand_NAV
from subcommands.run import subCommand_RUN
from subcommands.update import subCommand_UPDATE

subCommandParsers = [
	subCommand_BUY,
	subCommand_LOCAL,
	subCommand_NAV,
	subCommand_RUN,
	subCommand_UPDATE,
]

######################################################################
# main entry point


def main():
	# load arguments/environment
	tdenv = TradeEnv('TradeDangerous: ED trading database tools.', subCommandParsers)

	# load the database
	tdb = TradeDB(tdenv, buildLinks=False, includeTrades=False)

	tdenv.parse(tdb)


######################################################################


if __name__ == "__main__":
	try:
		main()
	except (TradeException) as e:
		print("%s: %s" % (sys.argv[0], str(e)))

