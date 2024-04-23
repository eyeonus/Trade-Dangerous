#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2022
#
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: GUI App :: Main Module
# 
# Where all the graphics happens. Uses TD CLI under the hood.
# 
# Current features:
# ----------------
# Drop-down list of all available TD commands
# Fully populated list of all arguments and switches for each command
# Automatic setting of default value for the above which have one
# Procedural generation of all above for future proofing in the 
#   event of new import plugins, switches, arguments, commands(?)
# RAM resident save-state: altered values retain new value while main
#    window remains open
# 
# Planned features:
# ----------------
# Code overhaul to utilize tk directly rather than via appJar
# User-defined initial values AKA tdrc files (.tdrc_run, .tdrc_trade, ..)
# Profiles AKA fromfiles (+ship1, +ship2, ..)
# Select-able output text
# graphical render of results
# send results to new window
# individual always-on-top for every window
# Data retrieval from CMDR's journal

import os
import sys
import traceback
import threading

from pathlib import Path

from appJar import gui
import appJar

# from tkinter import *
# import tkinter.font as font
# import tkinter.scrolledtext as scrolledtext
# from tkinter.ttk import *

from . import commands
from . import plugins
from .commands import exceptions
from .version import __version__

from . import tradedb
from .plugins import PluginException

# ==================
# BEGIN appJar fixes
# ==================

WIDGET_NAMES = appJar.appjar.WIDGET_NAMES
WidgetManager = appJar.appjar.WidgetManager

def get(self, widgetType, title):
    return eval('self.get' + str(widgetType) + '("' + str(title) + '")')


gui.get = get

# @Override
def _populateSpinBox(self, spin, vals, reverse = False):
    # make sure it's a list
    if reverse:
        vals = list(vals)
        vals.reverse()
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
        raise RuntimeError(
            f"Invalid position: {pos}. No position in SpinBox: {title}={vals}"
        )
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
    except:  # noqa: E722
        try:
            maxSize = len(str(max(options)))
        except:  # noqa: E722
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

# ================
# END appJar fixes
# ================



# Plugins available to the 'import' command are stored here.
# The list is populated by scanning the plugin folder directly,
# so it updates automagically at start as plugins are added or removed.
#
# Any other command with available plugins must have a similar list.
importPlugs = [ plug.name[0:plug.name.find('_plug.py')]
             for plug in os.scandir(sys.modules['tradedangerous.plugins'].__path__[0])
             if plug.name.endswith("_plug.py")
             ]

widgets = dict()

# All available commands
Commands = ['help'] + [ cmd for cmd, module in sorted(commands.commandIndex.items()) ]
# Used to run TD cli commands.
cmdenv = commands.CommandIndex().parse
# 'help' output, required & optional arguments, for each command
cmdHelp = {}

# Path of the database
dbS = str(Path((os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data')) / Path('TradeDangerous.db')))
# Path of the current working directory
cwdS = str(Path(os.getcwd()))

def changeCWD():
    """
    Opens a folder select dialog for choosing the current working directory.
    """
    cwd = filedialog.askdirectory(title = "Select the top-level folder for TD to work in...",
                                  initialdir = argVals['--cwd'])
    # cwd = win.directoryBox("Select the top-level folder for TD to work in...", dirName = argVals['--cwd'])
    if cwd:
        argVals['--cwd'] = str(Path(cwd))
    widgets['cwd']['text'] = argVals['--cwd']

def changeDB():
    """
    Opens a file select dialog for choosing the database file.
    """
    db = filedialog.askopenfilename(title = "Select the TD database file to use...",
                                    initialdir = str(Path(argVals['--db']).parent),
                                    filetypes = [('Data Base File', '*.db')])
    if db:
        argVals['--db'] = str(Path(db))
    widgets['db']['text'] = argVals['--db']        


# A dict of all arguments in TD (mostly auto-generated)
# Manually add the global arguments for now, maybe figure out how to auto-populate them as well.
allArgs = {
    '--debug': { 'help': 'Enable/raise level of diagnostic output.',
                'default':  0, 'required': False, 'action': 'count',
                'widget': {'type':'combo', 'values': ['', '-w', '-ww', '-www']}
                },
    '--detail':{ 'help': 'Increase level of detail in output.',
                'default': 0, 'required': False, 'action': 'count',
                'excludes': ['--quiet'], 'widget': {'type':'combo', 'values': ['', '-v', '-vv', '-vvv']}
                },
    '--quiet':{ 'help': 'Reduce level of detail in output.',
               'default': 0, 'required': False, 'action': 'count',
               'excludes': ['--detail'], 'widget': {'type':'combo', 'values': ['', '-q', '-qq', '-qqq']}
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
                 'default': '30',
                 'widget': {'type':'entry', 'sub':'numeric'}
                 }
    }

# Used to save the value of the arguments.
argVals = {'--debug': '',
           '--detail': '',
           '--quiet': '',
           '--db': dbS,
           '--cwd': cwdS,
           '--link-ly': '30'
           }

def buildArgDicts():
    """
    Procedurally generates the contents of allArgs and argVals
    """
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
                
                allArgs[cmd]['req'][arg.args[0]] = {kwarg: arg.kwargs[kwarg] for kwarg in arg.kwargs}
                allArgs[cmd]['req'][arg.args[0]]['widget'] = chooseType(arg)
        # print(allArgs[cmd]['req'])
        
        if index.switches:
            for arg in index.switches:
                try:
                    argVals[arg.args[0]] = arg.kwargs.get('default') or None
                    
                    allArgs[cmd]['opt'][arg.args[0]] = {kwarg: arg.kwargs[kwarg] for kwarg in arg.kwargs}
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
                        
                        allArgs[cmd]['opt'][argGrp.args[0]] = {kwarg: argGrp.kwargs[kwarg] for kwarg in argGrp.kwargs}
                        allArgs[cmd]['opt'][argGrp.args[0]]['widget'] = chooseType(argGrp)
                        
                        allArgs[cmd]['opt'][argGrp.args[0]]['excludes'] = [excl.args[0] for excl in arg.arguments 
                                                                   if excl.args[0] != argGrp.args[0]]
                        if argGrp.args[0] == '--plug':
                            # Currently only the 'import' cmd has the '--plug' option,
                            # but this could no longer be the case in the future.
                            if cmd == 'import':
                                allArgs[cmd]['opt'][argGrp.args[0]]['plugins'] = importPlugs


def optWindow():
    """
    Opens a window listing all of the options for the currently selected plugin.
    """
    # with win.subWindow("Plugin Options", modal = True) as sw:
    #     win.emptyCurrentContainer()
    #     optDict = {}
    #     if argVals['--option']:
    #         for option in enumerate(argVals['--option'].split(',')):
    #             if '=' in option[1]:
    #                 optDict[option[1].split('=')[0]] = option[1].split('=')[1]
    #             else:
    #                 if option[1] != '':
    #                     optDict[option[1]] = True
    #     # print(optDict)
    #     if not win.combo('--plug'):
    #         win.message('No import plugin chosen.', width = 170, colspan = 10)
    #     else:
    #         plugOpts = allArgs['import']['opt']['--option']['options'][win.combo('--plug')]
    #         for option in plugOpts:
    #             # print(option + ': ' + plugOpts[option])
    #             if '=' in plugOpts[option]:
    #                 win.entry(option, optDict.get(option) or '', label = True, sticky = 'ew', colspan = 10, tooltip = plugOpts[option])
    #             else:
    #                 win.check(option, optDict.get(option) or False, sticky = 'ew', colspan = 10, tooltip = plugOpts[option])
    #         # print(plugOpts)
    #     win.button("Done", setOpts, column = 8)
    #     win.button("Cancel", sw.hide, row = 'p', column = 9)
    #     sw.show()

def chooseType(arg):
    """
    Choose what type of widget to make for the passed argument
    """
    if arg.kwargs.get('action') == 'store_true' or arg.kwargs.get('action') == 'store_const':
        return {'type':'check'}
    if arg.kwargs.get('type') == int:
        return {'type':'spin', 'min': 0, 'max': 4096}
    if arg.kwargs.get('choices'):
        return {'type':'ticks', 'values':[val for val in arg.kwargs.get('choices')]}
    if arg.args[0] == '--plug':
        return {'type':'combo', 'values': [''] + importPlugs}
    if arg.args[0] == '--option':
        return {'type':'option', 'func': optWindow}
    if arg.kwargs.get('type') == float:
        return {'type':'numeric'}
    if arg.kwargs.get('type') == 'credits':
        return {'type':'credits'}
    return {'type':'entry'}

def addWidget(type, parent = None, cpos = 0, rpos = 0, **kwargs):
    """
    Adds a new tk widget and configures it based on passed parameters
    """
    cspan = kwargs.pop('colspan', None)
    rspan = kwargs.pop('rowspan', None)
    
    if type == 'combo':
        widget = Combobox(parent, textvariable = kwargs.pop('textvariable', None))
        if 'bind' in kwargs:
            widget.bind('<<ComboboxSelected>>', kwargs['bind'] )
    
    elif type == 'ticks':
        widget = Listbox(parent, listvariable = kwargs.pop('listvariable', None), 
                         selectmode = kwargs.pop('selectmode', None), height = kwargs.pop('height', None))
    
    elif type == 'stext':
        widget = scrolledtext.ScrolledText(parent, textvariable = kwargs.pop('textvariable', None))
    
    elif type == 'button':
        widget = Button(parent, text = kwargs.pop('text', None), textvariable = kwargs.pop('textvariable', None), command = kwargs.pop('func', None))
    
    elif type == 'frame':
        widget = Frame(parent, textvariable = kwargs.pop('textvariable', None))
    
    elif type == 'tab':
        widget = Notebook(parent, textvariable = kwargs.pop('textvariable', None))
    
    elif type == 'label':
        widget = Label(parent, text = kwargs.pop('text', None), textvariable = kwargs.pop('textvariable', None))
    
    elif type == 'check':
        widget = Checkbutton(parent, text = kwargs.pop('text', None), variable = kwargs.pop('textvariable', None), 
                             onvalue = kwargs.pop('onvalue', None), offvalue = kwargs.pop('offvalue', None), 
                             command = kwargs.pop('func', None))
    
    elif type == 'spin':
        widget = Spinbox(parent, from_ = kwargs.pop('min', None), to = kwargs.pop('max', None), textvariable = kwargs.pop('textvariable', None))
    
    else: # default for unimplemented types
        widget = Entry(parent, textvariable = kwargs.pop('textvariable', None))
    
    if 'font' in kwargs:
        widget['font'] = kwargs['font']
    if 'sticky' in kwargs:
        widget.sticky = kwargs['sticky']
    if 'values' in kwargs:
        widget['values'] = kwargs['values']
    if 'width' in kwargs:
        widget.width = kwargs['width']
    if 'justify' in kwargs:
        widget['justify'] = kwargs['justify']
    if 'height' in kwargs:
        widget['height'] = kwargs['height']
    if 'default' in kwargs:
        try:
            widget.set(kwargs['default'])
        except Exception as e:
            try:
                widget.insert(0, kwargs['default'])
            except:
                widget.insert(kwargs['default'][0], kwargs['default'][1])
    
    if 'state' in kwargs:
        widget['state'] = kwargs['state']
    
    widget.grid(column = cpos, row = rpos, columnspan = cspan, rowspan = rspan)
    
    if 'tab' in kwargs:
        parent.add(widget, text = kwargs['tab'])
    
    return widget

def addWidgetFromArg(name, arg, parent):
    """
    Creates a labeled widget for an argument.
    """
    widgets[name] = Frame(parent)
    
    kwargs = arg['widget']
    kwargs['textvariable'] = argVals[name]
    type = kwargs.pop('type', None)
    
    sub = kwargs.pop('sub', None)
    if type == 'ticks':
        kwargs['height'] = len(kwargs['values'])
        argVals[name] = value = kwargs.pop('values', None)
        kwargs['listvariable'] = argVals[name]
        kwargs['selectmode'] = 'extended'
    #numeric
    if type == 'numeric':
        pass
    #credits
    if type == 'credits':
        pass
    
    if type == 'check':
        kwargs['text'] = name
        kwargs['columnspan'] = 3
    else:
        if type == 'option':
            label = Button(widgets[name], text = name, command = kwargs.pop('func', None))
            type = 'entry'
        else:
            label = Label(widgets[name], text = name)
        label.grid(column = 0, row = 0)
        kwargs['rpos'] = 0
        kwargs['cpos'] = 1
        kwargs['columnspan'] = 2
    
    addWidget(type, widgets[name], **kwargs)
    widgets[name].grid()
    
    def makeWidgets(name, arg, sticky = 'ew', label = True, **kwargs):
        kwargs['sticky'] = sticky
        kwargs['label'] = label
        kwargs['change'] = updArgs
        kwargs['tooltip'] = arg['help']
        if arg == allArgs.get(name):
            kwargs['colspan'] = 1
        else:
            kwargs['colspan'] = 9
        
        widget = arg['widget']
        # print(name + ': ' + str(widget))
        if widget['type'] == 'button':
            kwargs.pop('change')
            kwargs.pop('label')
            kwargs.pop('colspan')
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
            win.combo(name, widget['values'], **kwargs)
            
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
            kwargs.pop('change')
            kwargs.pop('label')
            kwargs.pop('colspan')
            win.button('optionButton', optionsWin, name = '--option', **kwargs)
            kwargs['sticky'] = sticky
            kwargs['change'] = updArgs
            win.entry(name, argVals[name] or arg.get('default'), row = 'p' , column = 1, colspan = 9, **kwargs)
        elif widget['type'] == 'entry':
            if widget.get('sub'):
                if widget.get('sub') == 'credits':
                    # TODO: Handle 'credits' type.
                    pass
                else:
                    kwargs['kind'] = 'numeric'
            
            win.entry(name, argVals[name] or arg.get('default'), **kwargs)


def updateCommandBox(args = None):
    """
    Updates the argument panes when the selected command is changed.
    """
    
    cmd = widgets['Command'].get()
    
    widgets['helpPane']['state'] = 'normal'
    widgets['helpPane'].delete(0.0, 'end')
    widgets['helpPane'].insert(0.0, cmdHelp[cmd])
    widgets['helpPane']['state'] = 'disabled'
    
    # Hide all of the widgets currently displayed in 'req' and 'opt'
    for widget in widgets['req'].winfo_children():
        widget.grid_forget()
    
    for widget in widgets['opt'].winfo_children():
        widget.grid_forget()
    
    # Nothing more needs done for the 'help' command.
    if cmd == 'help':
        return
    
    # The 'station' command has arguments with the same names
    # as arguments for other command, such as 'planetary',
    # but in 'station' they are to set the value, whereas
    # in the other command they are used to exclude certain values,
    # meaning that 'station' needs unique names to prevent conflicts.
    prepend = ''
    if cmd == 'station':
        prepend = cmd + '~'
    else:
        prepend = ''
    #That was a lot of explanation for 5 lines of code.
    
    # Show the widgets for all required arguments of the current command
    # If the argument's widget does not exist, make it.
    if allArgs[cmd]['req']:
        if not 'Required:' in widgets:
            widgets['Required:'] = addWidget('label', widgets['req'], sticky = 'nw', text = 'Required:')
        else:
            widgets['Required:'].grid()
        
        i = 0
        for key in allArgs[cmd]['req']:
            i += 1
            if not (prepend + key) in widgets:
                addWidgetFromArg(prepend + key, allArgs[cmd]['req'][key], widgets['req'])
            else:
                widgets[prepend + key].grid(column = 0, row = i)
    
    if allArgs[cmd]['opt']:
        if not 'Optional:' in widgets:
            widgets['Optional:'] = addWidget('label', widgets['opt'], sticky = 'nw', text = 'Optional:')
        else:
            widgets['Optional:'].grid()
        
        i=0
        for key in allArgs[cmd]['opt']:
            i+=1
            if not (prepend + key) in widgets:
                addWidgetFromArg(prepend + key, allArgs[cmd]['opt'][key], widgets['opt'])
            else:
                widgets[prepend + key].grid(column =  0, row = i)



# Setup the CLI interface and build the main window
def main(argv = None):
    
    class IORedirector:
        
        def __init__(self, TEXT_INFO):
            self.TEXT_INFO = TEXT_INFO
    
    class StdoutRedirector(IORedirector):
        
        def write(self, string):
            self.TEXT_INFO.config(text = self.TEXT_INFO.cget('text').rsplit('\r', 1)[0] + string)
        
        def flush(self):
            
            sys.__stdout__.flush()
    
    #TODO: Implement in tk
    def setOpts():
        """
        Sets the main window options entry to the checked values in the options window.
        """
        sw = win.widgetManager.get(WIDGET_NAMES.SubWindow, "Plugin Options")
        plugOpts = allArgs['import']['opt']['--option']['options'].get(win.combo('--plug'))
        argStr = ''
        # print(plugOpts)
        if plugOpts:
            for option in plugOpts:
                # print(option + ': ' + plugOpts[option])
                if '=' in plugOpts[option]:
                    if win.entry(option):
                        argStr = argStr + option + '=' + win.entry(option) + ','
                elif win.check(option):
                    argStr = argStr + option + ','
            # print(argStr)
            argStr = argStr.rsplit(',', 1)[0]
            win.entry('--option', argStr)
        sw.hide()
    
    #TODO: Implement in tk
    def optionsWin():
        """
        Opens a window listing all of the options for the currently selected plugin.
        """
        with win.subWindow("Plugin Options", modal = True) as sw:
            win.emptyCurrentContainer()
            optDict = {}
            if argVals['--option']:
                for option in enumerate(argVals['--option'].split(',')):
                    if '=' in option[1]:
                        optDict[option[1].split('=')[0]] = option[1].split('=')[1]
                    else:
                        if option[1] != '':
                            optDict[option[1]] = True
            # print(optDict)
            if not win.combo('--plug'):
                win.message('No import plugin chosen.', width = 170, colspan = 10)
            else:
                plugOpts = allArgs['import']['opt']['--option']['options'][win.combo('--plug')]
                for option in plugOpts:
                    # print(option + ': ' + plugOpts[option])
                    if '=' in plugOpts[option]:
                        win.entry(option, optDict.get(option) or '', label = True, sticky = 'ew', colspan = 10, tooltip = plugOpts[option])
                    else:
                        win.check(option, optDict.get(option) or False, sticky = 'ew', colspan = 10, tooltip = plugOpts[option])
                # print(plugOpts)
            win.button("Done", setOpts, column = 8)
            win.button("Cancel", sw.hide, row = 'p', column = 9)
            sw.show()
    
    #TODO: Implement in tk
    def updArgs(name):
        """
        Updates the value of argVals[name] when the linked widget's value is changed in the window.
        """
        
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
        if name == '--plug' and argVals[name] != win.get(getWidgetType(name), name):
            win.entry('--option', '')
        
        argVals[name] = win.get(getWidgetType(name), name)
        # print('Changed: "' + name + '" [' + str(argVals[name]) + ']')
        
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
    
    #TODO: REMOVE
    def updCmd():
        """
        Updates the argument panes when the selected command is changed.
        """
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
                    makeWidgets(key, allArgs[cmd]['req'][key])
        
        if allArgs[cmd]['opt']:
            with win.scrollPane('opt', disabled = 'horizontal'):
                win.label('Optional:', sticky = 'w')
                for key in allArgs[cmd]['opt']:
                    makeWidgets(key, allArgs[cmd]['opt'][key])
    
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
                if arg in ['--detail', '--debug', '--quiet']:
                    pass
                else:
                    vals.append(str(arg))
                widget = argBase[arg]['widget']
                if widget['type'] == 'check':
                    return vals
                if widget.get('sub') == 'ticks':
                    choices = ''
                    for choice in curArg:
                        if curArg[choice]:
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
            # Redirect output to the Output tab in the GUI
            outputText = win.widgetManager.get(WIDGET_NAMES.Message, 'outputText')
            oldout = sys.stdout
            sys.stdout = StdoutRedirector(outputText)
            print('TD command: "' + ' '.join(argv) + '"')
            
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
            
            print("Execution complete.")
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
                    #not all required args don't include the arg name
                    argv = argv + (result if '-' in result[0] else result[1:])
            
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
        
        win.message('outputText', '')
        threading.Thread(target = runTrade, name = "TDThread", daemon = True).start()
    
    # TODO: replace
    def makeWidgets(name, arg, sticky = 'ew', label = True, **kwargs):
        kwargs['sticky'] = sticky
        kwargs['label'] = label
        kwargs['change'] = updArgs
        kwargs['tooltip'] = arg['help']
        if arg == allArgs.get(name):
            kwargs['colspan'] = 1
        else:
            kwargs['colspan'] = 9
        
        widget = arg['widget']
        # print(name + ': ' + str(widget))
        if widget['type'] == 'button':
            kwargs.pop('change')
            kwargs.pop('label')
            kwargs.pop('colspan')
            win.button(name, widget['func'], **kwargs)
        elif widget['type'] == 'check':
            win.check(name, argVals[name] or arg.get('default'), text = name, **kwargs)
        elif widget['type'] == 'spin':
            kwargs['item'] = argVals[name] or arg.get('default') or 0
            win.spin(name, widget['min'] - widget['max'], endValue = widget['max'], **kwargs)
        elif widget['type'] == 'combo':
            kwargs['sticky'] = 'w'
            if widget.get('sub'):
                kwargs['kind'] = widget['sub']
                kwargs.pop('label')
            win.combo(name, widget['values'], **kwargs)
            
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
            kwargs.pop('change')
            kwargs.pop('label')
            kwargs.pop('colspan')
            win.button('optionButton', optionsWin, name = '--option', **kwargs)
            kwargs['sticky'] = sticky
            kwargs['change'] = updArgs
            win.entry(name, argVals[name] or arg.get('default'), row = 'p' , column = 1, colspan = 9, **kwargs)
        elif widget['type'] == 'entry':
            if widget.get('sub'):
                if widget.get('sub') == 'credits':
                    # TODO: Handle 'credits' type.
                    pass
                else:
                    kwargs['kind'] = 'numeric'
            
            win.entry(name, argVals[name] or arg.get('default'), **kwargs)


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
    
    
    buildArgDicts()

#    window = Tk()
#    window.title('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,))
#    window.iconbitmap(resource_filename(__name__, "../tradedangerouscrest.ico"))
#    
#    widgets['Command'] = addWidget('combo', window, 3, 0, values = Commands, bind = updateCommandBox, 
#                width = 10, state = 'readonly', height = len(Commands), default = Commands[0], columnspan = 4,
#                justify = 'center', sticky = 'ew', tooltip = 'Trade Dangerous command to run.')
#    widgets['req'] = addWidget('frame', window, 0, 1, width = 200, height = 175, columnspan = 10, sdir = 'v')
#    widgets['opt'] = addWidget('frame', window, 0, 2, width = 200, height = 345, columnspan = 10, sdir = 'v')
#    
#    widgets['tabFrame'] = addWidget('tab', window, 10, 1, rowspan = 2, columnspan = 40, width = 560, height = 520)
#    widgets [ 'helpPane'] = addWidget('stext', widgets['tabFrame'], width = 80, font = font.Font(family = 'Courier New', size=10),
#              #'fixed', 'oemfixed', 'ansifixed', 'systemfixed', 'TkFixedFont'
#              default = (0.0, cmdHelp['help']), state = 'disabled', tab = 'Help')
#    widgets['outPane'] = addWidget('stext', widgets['tabFrame'], width = 80, state = 'disabled', tab = 'Output')
#    
#        makeWidget('--link-ly', allArgs['--link-ly'], sticky = 'w', width = 4, row = 3, column = 2)
#        
#        makeWidget('--quiet', allArgs['--quiet'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 46)
#        
#        makeWidget('--detail', allArgs['--detail'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 47)
#        
#        makeWidget('--debug', allArgs['--debug'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 48)
#        
#        win.button('Run', runTD, tooltip = 'Execute the selected command.',
#                   sticky = 'w', row = 3, column = 49)
#        
#        makeWidget('--cwd', allArgs['--cwd'], width = 4, row = 4, column = 0)
#        with win.scrollPane('CWD', disabled = 'vertical', row = 4, column = 1, colspan = 49) as pane:
#            pane.configure(width = 500, height = 20)
#            win.label('cwd', argVals['--cwd'], sticky = 'w')
#        
#        makeWidget('--db', allArgs['--db'], width = 4, row = 5, column = 0)
#        with win.scrollPane('DB', disabled = 'vertical', row = 5, column = 1, colspan = 49) as pane:
#            pane.configure(width = 500, height = 20)
#            win.label('db', argVals['--db'], sticky = 'w')
#    
#    window.mainloop()
    
    with gui('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,), inPadding = 1) as win:
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
                    win.widgetManager.get(WIDGET_NAMES.Message, 'helpText').config(width = 560)
            
            with win.tab('Output'):
                with win.scrollPane('outPane', disabled = 'horizontal') as pane:
                    pane.configure(width = 560, height = 420)
                    win.message('outputText', '')
                    win.widgetManager.get(WIDGET_NAMES.Message, 'outputText').config(width = 560)
        
        makeWidgets('--link-ly', allArgs['--link-ly'], sticky = 'w', width = 4, row = 3, column = 2)
        
        makeWidgets('--quiet', allArgs['--quiet'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 46)
        
        makeWidgets('--detail', allArgs['--detail'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 47)
        
        makeWidgets('--debug', allArgs['--debug'], sticky = 'e', disabled = ':', width = 1, row = 3, column = 48)
        
        win.button('Run', runTD, tooltip = 'Execute the selected command.',
                   sticky = 'w', row = 3, column = 49)
        
        makeWidgets('--cwd', allArgs['--cwd'], width = 4, row = 4, column = 0)
        with win.scrollPane('CWD', disabled = 'vertical', row = 4, column = 1, colspan = 49) as pane:
            pane.configure(width = 500, height = 20)
            widgets['cwd'] = win.label('cwd', argVals['--cwd'], sticky = 'w')
        
        makeWidgets('--db', allArgs['--db'], width = 4, row = 5, column = 0)
        with win.scrollPane('DB', disabled = 'vertical', row = 5, column = 1, colspan = 49) as pane:
            pane.configure(width = 500, height = 20)
            widgets['db'] = win.label('db', argVals['--db'], sticky = 'w')
    
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
