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

from appJar import gui
from _ast import arg


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
    cmdHelp, reqArg, optArg, comArg = dict(), dict(), dict(), dict()
    """
        stdArgs = subParser.add_argument_group('Common Switches')
        stdArgs.add_argument('-h', '--help',
                    help = 'Show this help message and exit.',
                    action = HelpAction, nargs = 0,
                )
        stdArgs.add_argument('--debug', '-w',
                    help = 'Enable/raise level of diagnostic output.',
                    default = 0, required = False, action = 'count',
                )
        stdArgs.add_argument('--detail', '-v',
                    help = 'Increase level  of detail in output.',
                    default = 0, required = False, action = 'count',
                )
        stdArgs.add_argument('--quiet', '-q',
                    help = 'Reduce level of detail in output.',
                    default = 0, required = False, action = 'count',
                )
        stdArgs.add_argument('--db',
                    help = 'Specify location of the SQLite database.',
                    default = None, dest = 'dbFilename', type = str,
                )
        stdArgs.add_argument('--cwd', '-C',
                    help = 'Change the working directory file accesses are made from.',
                    type = str, required = False,
                )
        stdArgs.add_argument('--link-ly', '-L',
                    help = 'Maximum lightyears between systems to be considered linked.',
                    type = float,
                    default = None, dest = 'maxSystemLinkLy',
                )
    """
    try:
        cmdenv(['help'])
    except exceptions.UsageError as e:
        cmdHelp['help'] = str(e)
    for cmd in Commands:
        print(cmd)
        if cmd == 'help':
            continue
        try:
            cmdenv(['trade', cmd, '-h'])
        except exceptions.UsageError as e:
            cmdHelp[cmd] = str(e)
        index = cmdIndex[cmd]
        
        if index.arguments:
            reqArg[cmd] = [{arg.args[0]: arg.kwargs} for arg in index.arguments]
            # print(reqArg[cmd])
        
        if index.switches:
            optArg[cmd] = list()
            for arg in index.switches:
                try:
                    optArg[cmd].append({arg.args[0]: arg.kwargs})
                except AttributeError:
                    optArg[cmd].append([{argGrp.args[0]: argGrp.kwargs} for argGrp in arg.arguments])
            # print(optArg[cmd])
    
    def updCmd():
        print(win.combo("Command"))
        win.message("helpText", cmdHelp[win.combo("Command")])
    
    with gui('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,)) as win:
        win.label('TODO', '## TODO: Make this window.', colspan = 50)
        win.combo("Command", Commands, change = updCmd, stretch = "none", sticky = "W", width = 10)
    
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
