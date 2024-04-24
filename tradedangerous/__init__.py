#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------

"""
TradeDangerous is a set of powerful trading tools for Elite Dangerous,
organized around one of the most powerful trade run optimizers available.

The TRO is a heavy hitter that can calculate complex routes with multiple stops
while taking into account the profits you make along the route
The price data in TradeDangerous is either manually entered or crowd-sourced
from a website such as [Tromador's Trading Dangerously](http://elite.ripz.org "Tromador's Trading Dangerously"), often using a plugin such as the included eddblink.
"""
from .version import *          # noqa: F401, F403

from .tradeenv import TradeEnv  # noqa: F401
