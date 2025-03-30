import sys
from sys import argv

from tradedangerous import tradedb, commands
from tradedangerous.tradecalc import TradeCalc

this = sys.modules[__name__]
this.cmdIndex = None
this.cmdenv = None
this.local_tdb = None
this.calc = None

def init_tradecalcchunk():
    this.cmdIndex = commands.CommandIndex()
    this.cmdenv = this.cmdIndex.parse(argv)
    this.local_tdb = tradedb.TradeDB(this.cmdenv, load=True)
    this.cmdenv.initAndCheckParams(this.local_tdb)
    this.calc = TradeCalc(this.local_tdb, this.cmdenv)
    
def init_calctradechunk_thread(calc):
    this.calc = calc

def run_route(route, restrictTo=None):
    return this.calc.getBestHops(route, restrictTo=restrictTo)
