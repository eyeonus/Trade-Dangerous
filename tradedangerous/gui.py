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
import sys
import traceback
import threading

from pathlib import Path
from appJar import gui
import appJar
from . import commands
from . import plugins
from .commands import exceptions
from .version import __version__

from . import tradedb
from .plugins import PluginException

WIDGET_NAMES = appJar.appjar.WIDGET_NAMES
WidgetManager = appJar.appjar.WidgetManager
# Plugins available to the 'import' command are stored here.
# The list is populated by scanning the plugin folder directly,
# so it updates automagically at start as plugins are added or removed.
#
# Any other command with available plugins must have a similar list.
importPlugs = [ plug.name[0:plug.name.find('_plug.py')]
             for plug in os.scandir(sys.modules['tradedangerous.plugins'].__path__[0])
             if plug.name.endswith("_plug.py")
             ]


def get(self, widgetType, title):
    return eval('self.get' + str(widgetType) + '("' + str(title) + '")')


gui.get = get


# @Override
def _populateSpinBox(self, spin, vals, reverse = True):
    # make sure it's a list
    #  reverse it, so the spin box functions properly
    # if reverse:
    #    vals = list(vals)
    #    vals.reverse()
    vals = tuple(vals)
    spin.config(values = vals)


gui._populateSpinBox = _populateSpinBox


# @Override
def setSpinBoxPos(self, title, pos, callFunction = True):
    spin = self.widgetManager.get(WIDGET_NAMES.SpinBox, title)
    vals = spin.cget("values")  # .split()
    vals = self._getSpinBoxValsAsList(vals)
    pos = int(pos)
    if pos < 0 or pos >= len(vals):
        raise Exception("Invalid position: " + str(pos) + ". No position in SpinBox: " + 
                    title + "=" + str(vals))
    #    pos = len(vals) - 1 - pos
    val = vals[pos]
    self._setSpinBoxVal(spin, val, callFunction)


gui.setSpinBoxPos = setSpinBoxPos


# @Override
def _configOptionBoxList(self, title, options, kind):
    """ Tidies up the list provided when an OptionBox is created/changed
    
    :param title: the title for the OptionBox - only used by TickOptionBox to calculate max size
    :param options: the list to tidy
    :param kind: The kind of option box (normal or ticks)
    :returns: a tuple containing the maxSize (width) and tidied list of items
    """
    
    # deal with a dict_keys object - messy!!!!
    if not isinstance(options, list):
        options = list(options)
    
    # make sure all options are strings
    options = [str(i) for i in options]
    
    # check for empty strings, replace first with message, remove rest
    # NO. Let's not do this annoying thing.
#    found = False
#    newOptions = []
#    for pos, item in enumerate(options):
#        if str(item).strip() == "":
#            if not found:
#                newOptions.append("- options -")
#                found = True
#        else:
#            newOptions.append(item)
#    
#    options = newOptions
    
    # get the longest string length
    try:
        maxSize = len(str(max(options, key = len)))
    except:
        try:
            maxSize = len(str(max(options)))
        except:
            maxSize = 0
    
    # increase if ticks
    if kind == "ticks":
        if len(title) > maxSize:
            maxSize = len(title)
    
    # new bug?!? - doesn't fit anymore!
    if self.platform == self.MAC:
        maxSize += 3
    return maxSize, options


gui._configOptionBoxList = _configOptionBoxList


def getOptionBox(self, title):
    """ Gets the selected item from the named OptionBox
    
    :param title: the OptionBox to check
    :returns: the selected item in an OptionBox or a dictionary of all items and their status for a TickOptionBox
    :raises ItemLookupError: if the title can't be found
    """
    box = self.widgetManager.get(WIDGET_NAMES.OptionBox, title)
    
    if box.kind == "ticks":
        val = self.widgetManager.get(WIDGET_NAMES.TickOptionBox, title, group = WidgetManager.VARS)
        retVal = {}
        for k, v in val.items():
            retVal[k] = bool(v.get())
        return retVal
    else:
        val = self.widgetManager.get(WIDGET_NAMES.OptionBox, title, group = WidgetManager.VARS).get()
#        val = val.get().strip()
        # set to None if it's a divider
#        if val.startswith("-") or len(val) == 0:
#            val = None
        return val


gui.getOptionBox = getOptionBox


def main(argv = None):

    class IORedirector(object):

        def __init__(self, TEXT_INFO):
            self.TEXT_INFO = TEXT_INFO
    
    class StdoutRedirector(IORedirector):
        
        def write(self, string):
            self.TEXT_INFO.config(text = self.TEXT_INFO.cget('text').rsplit('\r', 1)[0] + string)
        
        def flush(self):
            
            sys.__stdout__.flush()
    
    def chooseType(arg):
        if arg.kwargs.get('action') == 'store_true' or arg.kwargs.get('action') == 'store_const':
            return {'type':'check'}
        if arg.kwargs.get('type') == int:
            return {'type':'spin', 'range': 4096}
        if arg.kwargs.get('choices'):
            if arg.kwargs.get('choices')[0] != 'S':
                return {'type':'combo', 'list':['Y', 'N', '?']}
            else:
                return {'type':'combo', 'list':['S', 'M', 'L', '?']}
        if arg.kwargs.get('type') == 'planetary':
            return {'type':'combo', 'sub':'ticks', 'list':['Y', 'N', '?']}
        if arg.kwargs.get('type') == 'padsize':
            return {'type':'combo', 'sub':'ticks', 'list':['S', 'M', 'L', '?']}
        if arg.args[0] == '--plug':
            return {'type':'combo', 'list': [''] + importPlugs}
        # TODO: Implement 'option' in makeWidget.
        # if arg.args[0] == '--option':
        #    return {'type':'option'}
        if arg.kwargs.get('type') == float:
            return {'type':'entry', 'sub':'numeric'}
        if arg.kwargs.get('type') == 'credits':
            return {'type':'entry', 'sub':'credits'}
        return {'type':'entry'}
    
    def makeWidget(name, arg, sticky = 'ew', label = True, **kwargs):
        kwargs['sticky'] = sticky
        kwargs['label'] = label
        kwargs['change'] = updArgs
        kwargs['tooltip'] = arg['help']
        
        widget = arg['widget']
        # print(name + ': ' + str(widget))
        if widget['type'] == 'button':
            kwargs.pop('change')
            kwargs.pop('label')
            win.button(name, widget['func'], **kwargs)
        elif widget['type'] == 'check':
            win.check(name, argVals[name] or arg.get('default'), text = name, **kwargs)
        elif widget['type'] == 'spin':
            kwargs['item'] = argVals[name] or arg.get('default') or 0
            win.spin(name, 0 - widget['range'], endValue = widget['range'], **kwargs)
        elif widget['type'] == 'combo':
            kwargs['sticky'] = 'w'
            if widget.get('sub'):
                kwargs['kind'] = widget['sub']
                kwargs.pop('label')
            win.combo(name, widget['list'], **kwargs)
            
            # If we're switching to the 'station' command from another command,
            # this argument needs to be cleared from allArgs to not mess things up.
            if not widget.get('sub'):
                if argVals[name] != str:
                    argVals[name] = None
                default = '?' if arg.get('choices') else ''
                win.combo(name, argVals[name] or arg.get('default') or default, callFunction = False)
            else:
            # If we're switching to another command from the 'station' command,
            # this argument needs to be cleared from allArgs to not mess things up.
                if argVals[name] == str:
                    argVals[name] = None
                if argVals[name]:
                    for val in argVals[name]:
                        win.setOptionBox(name, val, value = argVals[name][val], callFunction = False)
        
        elif widget['type'] == 'option':
            # TODO: Implement, use subwindow.
            pass 
        elif widget['type'] == 'entry':
            if widget.get('sub'):
                if widget.get('sub') == 'credits':
                    # TODO: Handle 'credits' type.
                    pass
                else:
                    kwargs['kind'] = 'numeric'
            
            win.entry(name, argVals[name] or arg.get('default'), **kwargs)
    
    def updArgs(name):
    
        def getWidgetType(name):
            for widgetType in [WIDGET_NAMES.Entry, WIDGET_NAMES.Button, WIDGET_NAMES.CheckBox,
                               WIDGET_NAMES.RadioButton, WIDGET_NAMES.SpinBox, WIDGET_NAMES.OptionBox]:
                try:
                    win.widgetManager.get(widgetType, name)
                    return WIDGET_NAMES.widgets[widgetType]
                except:
                    pass
            return None
    
        # Update the stored value of the argument that's been changed.
        argVals[name] = win.get(getWidgetType(name), name)
        print('Changed: "' + name + '" [' + str(argVals[name]) + ']')
        
        if allArgs.get(name):
            excluded = allArgs[name].get('excludes')
            argBase = allArgs
        else:
            try:
                excluded = allArgs[win.combo("Command")]['opt'][name].get('excludes')
                argBase = allArgs[win.combo("Command")]['opt']
            except KeyError:
                excluded = None
        
        # Reset any arguments excluded by this one if it's been set.
        
        # print("'" + str(argVals[name]) + "': " + str(argVals[name] == True)
        #       + "': " + str(not argVals[name]) + " : " + str(not not argVals[name])
        #      )
        
        # Apparently, with strings, 'not not ""' != '""' when considered as a boolean.
        if excluded and not not argVals[name]:
            for exclude in excluded:
                widgetType = argBase[exclude]['widget']['type']
                if widgetType == 'combo':
                    win.combo(exclude, mode = 'clear', callFunction = False)
                elif widgetType == 'spin':
                    win.spin(exclude, mode = 'clear', callFunction = False)
                elif widgetType == 'entry':
                    win.setEntry(exclude, '', callFunction = False)
                elif widgetType == 'check':
                    win.check(exclude, False, callFunction = False)
    
    def updCmd():
        cmd = win.combo("Command")
        # print(cmd)
        
        win.message("helpText", cmdHelp[cmd])
        win.emptyScrollPane('req')
        win.emptyScrollPane('opt')
        if cmd == 'help':
            return
        if allArgs[cmd]['req']:
            with win.scrollPane('req', disabled = 'horizontal'):
                win.label('Required:', sticky = 'w')
                for key in allArgs[cmd]['req']:
                    makeWidget(key, allArgs[cmd]['req'][key])
        
        if allArgs[cmd]['opt']:
            with win.scrollPane('opt', disabled = 'horizontal'):
                win.label('Optional:', sticky = 'w')
                for key in allArgs[cmd]['opt']:
                    makeWidget(key, allArgs[cmd]['opt'][key])
        
    def changeCWD():
        """
        Opens a folder select dialog.
        """
        cwd = win.directoryBox("Select the top-level folder for TD to work in...", dirName = argVals['--cwd'])
        if cwd:
            argVals['--cwd'] = str(Path(cwd))
        win.label('cwd', argVals['--cwd'])
    
    def changeDB():
        """
        Opens a file select dialog.
        """
        db = win.openBox("Select the TD database file to use...", dirName = str(Path(argVals['--db']).parent),
                          fileTypes = [('Data Base File', '*.db')])
        if db:
            argVals['--db'] = str(Path(db))
        win.label('db', argVals['--db'])
    
    def runTD():
        """
        Executes the TD command selected in the GUI.
        """
        
        from . import tradeexcept
        
        def getVals(arg, argBase):
            curArg = argVals[arg]
            vals = []
            # See string weirdness, above.
            if not not curArg and curArg != argBase[arg].get('default'):
                if arg in ['--detail', '--debug', '--quiet'] or argBase == allArgs[cmd]['req']:
                    pass
                else:
                    vals.append(str(arg))
                widget = argBase[arg]['widget']
                if widget['type'] == 'check':
                    return vals
                if widget.get('sub') == 'ticks':
                    choices = ''
                    for choice in curArg:
                        if argVals[choice]:
                            choices = choices + choice
                    vals.append(choices)
                    return vals
                if widget.get('sub') == 'credits':
                    # TODO: Handle 'credits' type
                    pass
                vals.append(str(curArg))
            if vals == []:
                return None
            return vals
        
        def runTrade():
            # Can't allow the Run button to do anything when a command is running.
            win.button('Run', lambda x : x)
            outputText = win.widgetManager.get(WIDGET_NAMES.Message, 'outputText')
            # Redirect output to the Output tab in the GUI
            oldout = sys.stdout
            sys.stdout = StdoutRedirector(outputText)
            
            try:
                try:
                    try:
                        if "CPROF" in os.environ:
                            import cProfile
                            cProfile.run("trade(argv)")
                        else:
                            trade(argv)
                    except PluginException as e:
                        print("PLUGIN ERROR: {}".format(e))
                        if 'EXCEPTIONS' in os.environ:
                            raise e
                        sys.exit(1)
                    except tradeexcept.TradeException as e:
                        print("%s: %s" % (argv[0], str(e)))
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
            except SystemExit as e:
                print(e)
            
            # Set the output back to normal
            sys.stdout = oldout
            # Allow the Run button to do something again.
            win.button('Run', runTD)
        
        win.setTabbedFrameSelectedTab('tabFrame', 'Output')
        
        cmd = win.combo("Command")
        argv = ['trade', cmd ]
        if cmd != 'help':
            for arg in allArgs[cmd]['req']:
                result = getVals(arg, allArgs[cmd]['req'])
                if result:
                    argv = argv + result
            
            for arg in allArgs[cmd]['opt']:
                result = getVals(arg, allArgs[cmd]['opt'])
                if result:
                    argv = argv + result
            
            for arg in allArgs:
                if arg in Commands:
                    continue
                result = getVals(arg, allArgs)
                if result:
                    argv = argv + result
        
        sys.argv = argv
        
        print('TD command: ' + str(argv))
        win.message('outputText', '')
        threading.Thread(target = runTrade, name = "TDThread").start()
    
    # All available commands
    Commands = ['help'] + [ cmd for cmd, module in sorted(commands.commandIndex.items()) ]
    # Used to run TD cli commands.
    cmdenv = commands.CommandIndex().parse
    # 'help' output, required & optional arguments, for each command
    cmdHelp = {}
    
    dbS = str(Path((os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data')) / Path('TradeDangerous.db')))
    cwdS = str(Path(os.getcwd()))
    allArgs = {
        '--debug': { 'help': 'Enable/raise level of diagnostic output.',
                    'default':  0, 'required': False, 'action': 'count',
                    'widget': {'type':'combo', 'list': ['', '-w', '-ww', '-www']}
                    },
        '--detail':{ 'help': 'Increase level of detail in output.',
                    'default': 0, 'required': False, 'action': 'count',
                    'excludes': ['--quiet'], 'widget': {'type':'combo', 'list': ['', '-v', '-vv', '-vvv']}
                    },
        '--quiet':{ 'help': 'Reduce level of detail in output.',
                   'default': 0, 'required': False, 'action': 'count',
                   'excludes': ['--detail'], 'widget': {'type':'combo', 'list': ['', '-q', '-qq', '-qqq']}
                   },
        '--db':{ 'help': 'Specify location of the SQLite database.',
                'default': dbS, 'dest': 'dbFilename', 'type': str,
                'widget': {'type':'button', 'func':changeDB}
                },
        '--cwd':{ 'help': 'Change the working directory file accesses are made from.',
                 'default': cwdS, 'type': str, 'required': False,
                 'widget': {'type':'button', 'func':changeCWD}
                 },
        '--link-ly':{ 'help': 'Maximum lightyears between systems to be considered linked.',
                     'default': 30,
                     'widget': {'type':'entry', 'sub':'numeric'}
                     }
           }
    
    # Used to save the value and the type of widget of the arguments.
    argVals = {'--debug': '',
               '--detail': '',
               '--quiet': '',
               '--db': dbS,
               '--cwd': cwdS,
               '--link-ly': 30
               }
    
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
        index = commands.commandIndex[cmd]
        
        allArgs[cmd] = {'req': {}, 'opt': {}}
        if index.arguments:
            for arg in index.arguments:
                # print(arg.args[0])
                argVals[arg.args[0]] = arg.kwargs.get('default') or None

                allArgs[cmd]['req'][arg.args[0]] = {kwarg : arg.kwargs[kwarg] for kwarg in arg.kwargs}
                allArgs[cmd]['req'][arg.args[0]]['widget'] = chooseType(arg)
        # print(allArgs[cmd]['req'])

        if index.switches:
            for arg in index.switches:
                try:
                    argVals[arg.args[0]] = arg.kwargs.get('default') or None
                    
                    allArgs[cmd]['opt'][arg.args[0]] = {kwarg : arg.kwargs[kwarg] for kwarg in arg.kwargs}
                    allArgs[cmd]['opt'][arg.args[0]]['widget'] = chooseType(arg)
                    
                    if arg.args[0] == '--option':
                        # Currently only the 'import' cmd has the '--plug' option,
                        # but this could no longer be the case in future.
                        if cmd == 'import':
                            plugOptions = {
                                plug: plugins.load(cmdenv(['trade', cmd, '--plug', plug, '-O', 'help']).plug,
                                                    "ImportPlugin").pluginOptions for plug in importPlugs
                                }
                            allArgs[cmd]['opt'][arg.args[0]]['options'] = plugOptions
                
                except AttributeError:
                    for argGrp in arg.arguments:
                        argVals[argGrp.args[0]] = argGrp.kwargs.get('default') or None
                        
                        allArgs[cmd]['opt'][argGrp.args[0]] = {kwarg : argGrp.kwargs[kwarg] for kwarg in argGrp.kwargs}
                        allArgs[cmd]['opt'][argGrp.args[0]]['widget'] = chooseType(argGrp)
                        
                        allArgs[cmd]['opt'][argGrp.args[0]]['excludes'] = [excl.args[0] for excl in arg.arguments 
                                                                   if excl.args[0] != argGrp.args[0]]
                        if argGrp.args[0] == '--plug':
                            # Currently only the 'import' cmd has the '--plug' option,
                            # but this could no longer be the case in future.
                            if cmd == 'import':
                                allArgs[cmd]['opt'][argGrp.args[0]]['plugins'] = importPlugs
        # print(allArgs[cmd]['opt'])
    # print(allArgs)
    # print(argVals)
    
    with gui('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,)) as win:
        win.setFont(size = 8, family = 'Courier')
        win.combo('Command', Commands, change = updCmd, tooltip = 'Trade Dangerous command to run.',
                  stretch = 'none', sticky = 'ew', width = 10, row = 0, column = 0, colspan = 5)
        with win.scrollPane('req', disabled = 'horizontal', row = 1, column = 0, colspan = 10) as pane:
            pane.configure(width = 200, height = 75)
        
        with win.scrollPane('opt', disabled = 'horizontal', row = 2, column = 0, colspan = 10) as pane:
            pane.configure(width = 200, height = 345)
        
        with win.tabbedFrame('tabFrame', disabled = 'horizontal', row = 1, column = 10, rowspan = 2, colspan = 40) as tabFrame:
            with win.tab('Help'):
                with win.scrollPane('helpPane', disabled = 'horizontal') as pane:
                    pane.configure(width = 560, height = 420)
                    win.message('helpText', cmdHelp['help'])
            
            with win.tab('Output'):
                with win.scrollPane('outPane', disabled = 'horizontal') as pane:
                    pane.configure(width = 560, height = 420)
                    win.message('outputText', '', width = 560, height = 420)
        
        makeWidget('--link-ly', allArgs['--link-ly'], sticky = 'w', width = 4, row = 3, column = 2)

        makeWidget('--quiet', allArgs['--quiet'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 46)
        
        makeWidget('--detail', allArgs['--detail'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 47)
        
        makeWidget('--debug', allArgs['--debug'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 48)
        
        win.button('Run', runTD, tooltip = 'Execute the selected command.',
                   sticky = 'w', row = 3, column = 49)
        
        makeWidget('--cwd', allArgs['--cwd'], width = 4, row = 4, column = 0)
        with win.scrollPane('CWD', disabled = 'vertical', row = 4, column = 1, colspan = 49) as pane:
            pane.configure(width = 500, height = 20)
            win.label('cwd', argVals['--cwd'], sticky = 'w')
        
        makeWidget('--db', allArgs['--db'], width = 4, row = 5, column = 0)
        with win.scrollPane('DB', disabled = 'vertical', row = 5, column = 1, colspan = 49) as pane:
            pane.configure(width = 500, height = 20)
            win.label('db', argVals['--db'], sticky = 'w')
        
    # End of window


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
