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

from __future__ import absolute_import
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals
import os
import traceback

from . import commands
from .commands import exceptions, parsing
from .plugins import PluginException
from .version import __version__

from . import tradedb

import PySimpleGUI as sg
from _ast import arg


class Frame(sg.Frame):

    def Refresh(self, layout):
        super().__del__()
        super().Layout(layout)


def main(argv = None):
    import sys
    if not argv:
        argv = sys.argv
    if sys.hexversion < 0x03040200:
        raise SystemExit(
            "Sorry: TradeDangerous requires Python 3.4.2 or higher.\n"
            "For assistance, see:\n"
            "\tBug Tracker: https://github.com/eyeonus/Trade-Dangerous/issues\n"
            "\tDocumentation: https://github.com/eyeonus/Trade-Dangerous/wiki\n"
            "\tEDForum Thread: https://forums.frontier.co.uk/showthread.php/441509\n"
            )
    from . import tradeexcept
    
    # layout = [[sg.Text('Filename')],
    #      [sg.Input(), sg.FileBrowse()],
    #      [sg.OK(), sg.Cancel()] ]
  
    # event, (number,) = sg.Window('Get filename example').Layout(layout).Read()
    
    Commands = [''] + [ i for i, j in sorted(commands.commandIndex.items()) ]
    cmdIndex = commands.commandIndex
    cmdenv = commands.CommandIndex().parse
    
    try:
        cmdenv(['trade'])
    except exceptions.UsageError as e:
        cmdHelp = str(e)
        
    layout = [[sg.Text('## TODO: Make this window.')],
              [sg.InputCombo(Commands, readonly = True, key = '_cmd_', enable_events = True)],
              [Frame('Required Arguments', [[sg.Text('')]], key = "_req_"), Frame('Optional Switches', [[sg.Text('')]], key = "_opt_")],
              [sg.Multiline(cmdHelp, disabled = True, key = '_Output_', size = (80, 20))],
              [sg.Button('Close')]]
    window = sg.Window('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,)).Layout(layout)
    
    while True:  # Event Loop
        event, values = window.Read()
        if event is None or event == 'Close':
            break
        if event == '_cmd_':
            try:
                if values['_cmd_'] == '':
                    cmdenv(['trade'])
                else:
                    cmdenv(['trade', values['_cmd_'], '-h'])
            except exceptions.UsageError as e:
                cmdHelp = str(e)
            window.Element('_Output_').Update(disabled = False)
            window.Element('_Output_').Update(value = cmdHelp)
            window.Element('_Output_').Update(disabled = True)
            if values['_cmd_'] != '':
                print(values['_cmd_'])
                command = cmdIndex[values['_cmd_']]
                req = dict()
                if command.arguments:
                    for pargs in command.arguments:
                        arg = pargs.args[0]
                        req[arg] = pargs.kwargs
                reqFrame = []
                for key in req:
                    if req[key].get("type"):
                        if req[key]["type"] == str:
                            reqFrame.append([sg.Input(key, '', (1, 20), key = key)])
                print(reqFrame)
                    
                window.Element('_req_').Refresh(reqFrame)
                window.Element('_req_').Update(visible = True)
                print('Rows: \n' + str(window.Element('_req_').Rows))
                
                opt = dict()
                if command.switches:
                    for pargs in command.switches:
                        try:
                            arg = pargs.args[0]
                            opt[arg] = pargs.kwargs
                        except AttributeError as e:
                            for argGrp in pargs.arguments:
                                arg = argGrp.args[0]
                                opt[arg] = argGrp.kwargs
                
                print(opt.keys())

    window.Close()
#    try:
#        try:
#            if "CPROF" in os.environ:
#                import cProfile
#                cProfile.run("trade(argv)")
#            else:
#                trade(argv)
#        except PluginException as e:
#            print("PLUGIN ERROR: {}".format(e))
#            if 'EXCEPTIONS' in os.environ:
#                raise e
#            sys.exit(1)
#        except tradeexcept.TradeException as e:
#            print("%s: %s" % (argv[0], str(e)))
#            if 'EXCEPTIONS' in os.environ:
#                raise e
#            sys.exit(1)
#    except (UnicodeEncodeError, UnicodeDecodeError) as e:
#        print("-----------------------------------------------------------")
#        print("ERROR: Unexpected unicode error in the wild!")
#        print()
#        print(traceback.format_exc())
#        print(
#            "Please report this bug (http://kfs.org/td/issues). You may be "
#            "able to work around it by using the '-q' parameter. Windows "
#            "users may be able to use 'chcp.com 65001' to tell the console "
#            "you want to support UTF-8 characters."
#        )


def trade(argv):
    """
    This method represents the trade command.
    """
    cmdIndex = commands.CommandIndex()
    cmdenv = cmdIndex.parse(argv)
    
    tdb = tradedb.TradeDB(cmdenv, load = cmdenv.wantsTradeDB)
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
    
    try:
        results = cmdenv.run(tdb)
    finally:
        # always close tdb
        tdb.close()
    
    if results:
        results.render()
