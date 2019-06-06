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

import appJar
from appJar import gui
from _ast import arg

WIDGET_NAMES = appJar.appjar.WIDGET_NAMES


def _populateSpinBox(self, spin, vals, reverse = True):
    # make sure it's a list
    #  reverse it, so the spin box functions properly
    # vals = list(vals)
    # if reverse:
    #    vals.reverse()
    vals = tuple(vals)
    spin.config(values = vals)


def setSpinBoxPos(self, title, pos, callFunction = True):
    spin = self.widgetManager.get(WIDGET_NAMES.SpinBox, title)
    vals = spin.cget("values")  # .split()
    vals = self._getSpinBoxValsAsList(vals)
    pos = int(pos)
    if pos < 0 or pos >= len(vals):
        raise Exception("Invalid position: " + str(pos) + ". No position in SpinBox: " + 
                    title + "=" + str(vals))
    # if reverse:
    #    pos = len(vals) - 1 - pos
    val = vals[pos]
    self._setSpinBoxVal(spin, val, callFunction)


gui._populateSpinBox = _populateSpinBox
gui.setSpinBoxPos = setSpinBoxPos


def main(argv = None):
    import sys
    sys.argv = ['trade']
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
    
    # All available commands
    Commands = ['help'] + [ cmd for cmd, module in sorted(commands.commandIndex.items()) ]
    # Used to run TD cli commands.
    cmdIndex = commands.commandIndex
    cmdenv = commands.CommandIndex().parse
    # 'help' output, required/optional/common arguments, for each command 
    cmdHelp, reqArg, optArg = dict(), dict(), dict()
    comArg = [
                { '--help': { 'help': 'Show this help message and exit.',
                             'action': commands.HelpAction, 'nargs': 0 } },
                { '--debug': { 'help': 'Enable/raise level of diagnostic output.',
                              'default': 0, 'required': False, 'action': 'count' } },
                { '--detail': { 'help': 'Increase level  of detail in output.',
                               'default': 0, 'required': False, 'action': 'count' } },
                { '--quiet': { 'help': 'Reduce level of detail in output.',
                              'default': 0, 'required': False, 'action': 'count' } },
                { '--db': { 'help': 'Specify location of the SQLite database.',
                           'default': None, 'dest': 'dbFilename', 'type': str } },
                { '--cwd': { 'help': 'Change the working directory file accesses are made from.',
                            'type': str, 'required': False } },
                { '--link-ly': { 'help': 'Maximum lightyears between systems to be considered linked.',
                                'type': float, 'default': None, 'dest': 'maxSystemLinkLy' } }
            ]
    
    try:
        cmdenv(['help'])
    except exceptions.UsageError as e:
        cmdHelp['help'] = str(e)
    for cmd in Commands:
        # print(cmd)
        if cmd == 'help':
            continue
        try:
            cmdenv(['trade', cmd, '-h'])
        except exceptions.UsageError as e:
            cmdHelp[cmd] = str(e)
        index = cmdIndex[cmd]
        
        if index.arguments:
            reqArg[cmd] = {arg.args[0]: arg.kwargs for arg in index.arguments}
        else:
            reqArg[cmd] = dict()
        # print(reqArg[cmd])
        
        if index.switches:
            optArg[cmd] = dict()
            for arg in index.switches:
                try:
                    # TODO: Implement plugin option handling.
                    
                    optArg[cmd][arg.args[0]] = arg.kwargs
                except AttributeError:
                    for argGrp in arg.arguments:
                        optArg[cmd][argGrp.args[0]] = argGrp.kwargs
        else:
            optArg[cmd] = dict()
        # print(optArg[cmd])
    
    def updCmd():
        cmd = win.combo("Command")
        print(cmd)
        
        win.message("helpText", cmdHelp[cmd])
        # TODO: Implement panels and procedural argument population.
        win.emptyScrollPane('reqArg')
        # win.emptyScrollPane('optArg')
        if cmd == 'help':
            return
        if reqArg[cmd]:
            with win.scrollPane('reqArg', disabled = 'horizontal', colspan = 1) as pane:
                for key in reqArg[cmd]:
                    print(key + ": " + str(reqArg[cmd][key]))
                    # TODO: Populate pane with arguments.
                    win.entry(key, label = True, tooltip = reqArg[cmd][key]['help'])
        
        if reqArg[cmd]:
            with win.scrollPane('optArg', disabled = 'horizontal', colspan = 1) as pane:
                for key in optArg[cmd]:
                    print(key + ": " + str(optArg[cmd][key]))
                    # TODO: Populate pane with arguments.
    
    with gui('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,)) as win:
        win.combo('Command', Commands, change = updCmd, stretch = 'none', sticky = 'W', width = 10)
        win.spinBox('--debug', [0, 1, 2, 3], tooltip = 'Enable/raise level of diagnostic output.',
                      label = True, selected = 0, sticky = 'w', width = 1, row = 0, column = 1)
    
        win.spinBox('--detail', 0, endValue = 3, tooltip = 'Increase level of detail in output.',
                      label = True, selected = 0, sticky = 'w', width = 1, row = 0, column = 2)
    
        with win.scrollPane('reqArg', disabled = 'horizontal', row = 1, column = 0, colspan = 2) as pane:
            pane.configure(width = 280, height = 100)
            win.label('TODO', '## TODO: Make this window.')
        
        with win.scrollPane('optArg', disabled = 'horizontal', row = 1, column = 2, colspan = 2) as pane:
            pane.configure(width = 280, height = 100)
            win.label('TODO2', '## TODO: Make this window.')
        
        with win.scrollPane('helpPane', disabled = 'horizontal', colspan = 50) as pane:
            pane.configure(width = 560, height = 420)
            win.message("helpText", cmdHelp['help'])
    
    # End of window
    
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
