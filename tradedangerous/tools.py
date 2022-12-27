# --------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
# Copyright (C) Bernd 'Gazelle' Gollesch 2016, 2017
# Copyright (C) Jonathan 'eyeonus' Jones 2018, 2019
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: Modules :: Tools
"""This module contains various tools that could be used
externally and internally.
"""
from . import tradedb, utils

__all__ = ['test_derp']

def test_derp(tdb=None, tdenv=None):
    """
    Test whether the station names in a trade database are free of derp.
    
    Examples:
        import tradedb
        tdb = tradedb.TradeDB()
        test_derp(tdb)
        
        python -i cache.py
        >>> test_derp()
    """
    tdb = tdb or tradedb.TradeDB()
    tdenv = tdenv or tdb.tdenv
    matches = 0
    for stn in tdb.stationByID.values():
        m = utils.checkForOcrDerp(tdenv, stn.system.dbname, stn.dbname)
        if m:
            print("Match", m.groups(1))
            matches += 1
    if not matches:
        print("Current data is free of known derp")
    tdb.close()
