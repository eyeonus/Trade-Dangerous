#!/usr/bin/env python3
# --------------------------------------------------------------------
# Copyright (C) Jonathan 'eyeonus' Jones 2018-2022

# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.
# --------------------------------------------------------------------
# TradeDangerous :: GUI App :: Main Module

# Where all the graphics happens. Uses TD CLI under the hood.

# Current features:
# ----------------
# Drop-down list of all available TD commands
# Fully populated list of all arguments and switches for each command
# Automatic setting of default value for the above which have one
# Procedural generation of all above for future proofing in the
#   event of new import plugins, switches, arguments, commands(?)
# RAM resident save-state: altered values retain new value while main
#    window remains open

# Planned features:
# ----------------
# User-defined initial values AKA tdrc files (.tdrc_run, .tdrc_trade, ..)
# Profiles AKA fromfiles (+ship1, +ship2, ..)
# Select-able output text
# graphical render of results
# send results to new window
# individual always-on-top for every window
# Data retrieval from CMDR's journal

import os
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk, filedialog

from . import commands
from . import plugins
from . import tradedb
from .commands import exceptions
from .plugins import PluginException
from .version import __version__


import tkinter as tk
from tkinter import ttk, scrolledtext

class TDWidget:
    """
    Tkinter widget wrapper supporting appJar-style context management.
    """
    
    def __init__(self, name=None, widget_type='frame', parent=None, row=0, column=0,
                 rowspan=1, columnspan=1, sticky='nw', text='', values=None,
                 command=None, width=None, height=None, **kwargs):
        self.kwargs = kwargs
        self.name = name
        self.widget_type = widget_type
        self.children = []
        
        # Parent widget
        container = parent.widget if isinstance(parent, TDWidget) else parent
        
        # Create underlying Tk widget
        if widget_type == 'frame':
            self.widget = tk.Frame(container, width=width, height=height)
        elif widget_type == 'label':
            self.widget = tk.Label(container, text=text, width=width)
        elif widget_type == 'button':
            self.widget = tk.Button(container, text=text, command=command)
        elif widget_type == 'entry':
            self.var = tk.StringVar(value=text)
            self.widget = tk.Entry(container, textvariable=self.var, width=width)
        elif widget_type == 'combo':
            self.var = tk.StringVar(value=text)
            self.widget = ttk.Combobox(container, values=values or [], textvariable=self.var, width=width)
        elif widget_type == 'spin':
            self.var = tk.IntVar(value=text)
            self.widget = tk.Spinbox(container, from_=0, to=values or 100, textvariable=self.var, width=width)
        elif widget_type == 'scrolledtext':
            self.widget = scrolledtext.ScrolledText(container, width=width, height=height)
        elif widget_type == 'notebook':
            self.widget = ttk.Notebook(container)
            self.tabs = {}
        else:
            raise ValueError(f"Unknown widget_type: {widget_type}")
        
        # Parent-child management
        self.parent = parent
        if parent and isinstance(parent, TDWidget):
            parent.children.append(self)
        
        # Grid placement
        self.widget.grid(row=row, column=column, rowspan=rowspan, columnspan=columnspan, sticky=sticky)
        self.row, self.column = row, column
    
    # --- Proxy methods ---
    def config(self, **kwargs):
        self.widget.config(**kwargs)
    
    def set(self, value, callFunction=True):
        if hasattr(self, 'var'):
            self.var.set(value)
            if callFunction and self.widget_type == 'combo':
                if hasattr(self.widget, 'event_generate'):
                    self.widget.event_generate("<<ComboboxSelected>>")
    
    def get(self):
        if hasattr(self, 'var'):
            return self.var.get()
        return None
    
    def add_child(self, child):
        self.children.append(child)
    
    # --- Context manager support ---
    def __enter__(self):
        # Return self so "with TDWidget(...) as w:" works
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Nothing special to clean up
        pass
    
    # --- Notebook/tab support ---
    def tab(self, tab_name):
        """Create a new tab inside a notebook TDWidget"""
        if self.widget_type != 'notebook':
            raise RuntimeError("tab() can only be called on notebook widgets")
        frame = tk.Frame(self.widget)
        self.widget.add(frame, text=tab_name)
        self.tabs[tab_name] = frame
        return TDWidget(parent=self, widget_type='frame', row=0, column=0, columnspan=1, widget=frame)


# Plugins available to the 'import' command are stored here.
# The list is populated by scanning the plugin folder directly,
# so it updates automagically at start as plugins are added or removed.

# Any other command with available plugins must have a similar list.
importPlugs = [ plug.name[0:plug.name.find('_plug.py')]
             for plug in os.scandir(sys.modules['tradedangerous.plugins'].__path__[0])
             if plug.name.endswith("_plug.py")
             ]

widgets = {}

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
    # Create a new subwindow for plugin options
    sw = TDWidget.SubWindow("Plugin Options", modal=True)
    
    # Clear any previous widgets
    sw.clear()
    
    # Build dictionary of current option values
    optDict = {}
    currentOptStr = argVals.get('--option')
    if currentOptStr:
        for option in currentOptStr.split(','):
            if '=' in option:
                key, val = option.split('=', 1)
                optDict[key] = val
            elif option != '':
                optDict[option] = True
    
    # Check if a plugin is selected
    selectedPlug = sw.combo('--plug')
    if not selectedPlug:
        sw.message('No import plugin chosen.', width=170)
    else:
        plugOpts = allArgs['import']['opt']['--option']['options'].get(selectedPlug, {})
        for option, tooltip in plugOpts.items():
            if '=' in tooltip:
                sw.entry(option, value=optDict.get(option, ''), label=True, sticky='ew', tooltip=tooltip)
            else:
                sw.check(option, optDict.get(option, False), sticky='ew', tooltip=tooltip)
    
    # Add Done and Cancel buttons
    sw.button("Done", setOpts)
    sw.button("Cancel", sw.hide)
    
    # Display the subwindow
    sw.show()


def chooseType(arg):
    """
    Choose what type of TDWidget to make for the passed argument
    """
    if arg.kwargs.get('action') in ('store_true', 'store_const'):
        return {'type': 'check'}
    if arg.kwargs.get('type') == int:
        return {'type': 'spin', 'min': 0, 'max': 4096}
    if arg.kwargs.get('choices'):
        return {'type': 'ticks', 'values': list(arg.kwargs.get('choices'))}
    if arg.args[0] == '--plug':
        return {'type': 'combo', 'values': [''] + importPlugs}
    if arg.args[0] == '--option':
        return {'type': 'option', 'func': optWindow}
    if arg.kwargs.get('type') == float:
        return {'type': 'numeric'}
    if arg.kwargs.get('type') == 'credits':
        return {'type': 'credits'}
    return {'type': 'entry'}

def addWidget(widgetType, parent=None, cpos=0, rpos=0, **kwargs):
    """
    Adds a new TDWidget widget and configures it based on passed parameters
    """
    cspan = kwargs.pop('colspan', None)
    rspan = kwargs.pop('rowspan', None)
    
    # Create widget based on type
    if widgetType == 'combo':
        widget = TDWidget.Combo(parent, values=kwargs.get('values'), textvariable=kwargs.get('textvariable'))
    elif widgetType == 'ticks':
        widget = TDWidget.List(parent, values=kwargs.get('values'), selectmode=kwargs.get('selectmode'), height=kwargs.get('height'))
    elif widgetType == 'stext':
        widget = TDWidget.ScrolledText(parent, textvariable=kwargs.get('textvariable'))
    elif widgetType == 'button':
        widget = TDWidget.Button(parent, text=kwargs.get('text'), command=kwargs.get('func'))
    elif widgetType == 'frame':
        widget = TDWidget.Frame(parent)
    elif widgetType == 'tab':
        widget = TDWidget.Tab(parent)
    elif widgetType == 'label':
        widget = TDWidget.Label(parent, text=kwargs.get('text'))
    elif widgetType == 'check':
        widget = TDWidget.Check(parent, text=kwargs.get('text'), variable=kwargs.get('textvariable'),
                                onvalue=kwargs.get('onvalue', True), offvalue=kwargs.get('offvalue', False),
                                command=kwargs.get('func'))
    elif widgetType == 'spin':
        widget = TDWidget.Spin(parent, min=kwargs.get('min', 0), max=kwargs.get('max', 100),
                               textvariable=kwargs.get('textvariable'))
    else:  # default entry
        widget = TDWidget.Entry(parent, textvariable=kwargs.get('textvariable'))
    
    # Set common attributes
    if 'font' in kwargs:
        widget.font = kwargs['font']
    if 'sticky' in kwargs:
        widget.sticky = kwargs['sticky']
    if 'width' in kwargs:
        widget.width = kwargs['width']
    if 'justify' in kwargs:
        widget.justify = kwargs['justify']
    if 'height' in kwargs:
        widget.height = kwargs['height']
    if 'state' in kwargs:
        widget.state = kwargs['state']
    if 'default' in kwargs:
        widget.set(kwargs['default'])
    
    # Place widget in grid
    widget.grid(column=cpos, row=rpos, columnspan=cspan, rowspan=rspan)
    
    # Handle tabs
    if 'tab' in kwargs and hasattr(parent, 'add'):
        parent.add(widget, text=kwargs['tab'])
    
    return widget

def addWidgetFromArg(name, arg, parent):
    """
    Creates a labeled TDWidget for an argument.
    """
    widgets[name] = TDWidget.Frame(parent)
    
    kwargs = arg['widget'].copy()
    kwargs['textvariable'] = argVals[name]
    widgetType = kwargs.pop('type', None)
    
    # Handle special types
    if widgetType == 'ticks':
        kwargs['height'] = len(kwargs['values'])
        argVals[name] = value = kwargs.pop('values', None)
        kwargs['listvariable'] = argVals[name]
        kwargs['selectmode'] = 'extended'
    elif widgetType == 'numeric':
        pass
    elif widgetType == 'credits':
        pass
    
    # Create label or button for non-check widgets
    if widgetType == 'check':
        kwargs['text'] = name
        kwargs['columnspan'] = 3
    else:
        if widgetType == 'option':
            label = TDWidget.Button(widgets[name], text=name, command=kwargs.pop('func', None))
            widgetType = 'entry'
        else:
            label = TDWidget.Label(widgets[name], text=name)
        label.grid(column=0, row=0)
        kwargs['rpos'] = 0
        kwargs['cpos'] = 1
        kwargs['columnspan'] = 2
    
    # Add the actual input widget
    addWidget(widgetType, parent=widgets[name], **kwargs)
    
    # Place the container frame
    widgets[name].grid()
    
    def makeWidgets(name, arg, sticky='ew', label=True, **kwargs):
        """
        Creates and places a TDWidget for the given argument, handling all types.
        """
        kwargs['sticky'] = sticky
        kwargs['label'] = label
        kwargs['change'] = updArgs
        kwargs['tooltip'] = arg.get('help', '')
        kwargs['colspan'] = 1 if arg == allArgs.get(name) else 9
        
        widgetDef = arg['widget']
        
        # Button
        if widgetDef['type'] == 'button':
            kwargs.pop('change', None)
            kwargs.pop('label', None)
            kwargs.pop('colspan', None)
            TDWidget.Button(win, text=name, command=widgetDef.get('func'), **kwargs)
        
        # Checkbutton
        elif widgetDef['type'] == 'check':
            TDWidget.Check(win, text=name, variable=argVals[name] or arg.get('default'), **kwargs)
        
        # Spinbox
        elif widgetDef['type'] == 'spin':
            kwargs['item'] = argVals[name] or arg.get('default') or 0
            TDWidget.Spin(win, from_=-widgetDef.get('range', 0), to=widgetDef.get('range', 0), **kwargs)
        
        # Combobox / ticks
        elif widgetDef['type'] == 'combo':
            kwargs['sticky'] = 'w'
            if widgetDef.get('sub'):
                kwargs['kind'] = widgetDef['sub']
                kwargs.pop('label', None)
            
            combo = TDWidget.Combo(win, values=widgetDef.get('values', []), variable=argVals[name], **kwargs)
            
            if not widgetDef.get('sub'):
                argVals[name] = argVals[name] or arg.get('default') or '?'
                combo.set(argVals[name])
            else:
                if argVals[name]:
                    for val, vval in argVals[name].items():
                        combo.setOption(val, values=vval, callFunction=False)
        
        # Option button + entry
        elif widgetDef['type'] == 'option':
            kwargs.pop('change', None)
            kwargs.pop('label', None)
            kwargs.pop('colspan', None)
            TDWidget.Button(win, text='optionButton', command=optionsWin, name='--option', **kwargs)
            
            kwargs['sticky'] = sticky
            kwargs['change'] = updArgs
            TDWidget.Entry(win, textvariable=argVals[name] or arg.get('default'), row='p', column=1, colspan=9, **kwargs)
        
        # Entry / numeric / credits
        elif widgetDef['type'] == 'entry':
            if widgetDef.get('sub') == 'credits':
                # TODO: Implement credits type handling
                pass
            elif widgetDef.get('sub'):
                kwargs['kind'] = 'numeric'
            
            TDWidget.Entry(win, textvariable=argVals[name] or arg.get('default'), **kwargs)


def updateCommandBox(args=None):
    """
    Updates the argument panes when the selected command is changed using TDWidget.
    """
    cmd = widgets['Command'].get()
    
    # Update help pane
    helpPane = widgets['helpPane']
    helpPane.config(state='normal')
    helpPane.delete(0.0, 'end')
    helpPane.insert(0.0, cmdHelp.get(cmd, ''))
    helpPane.config(state='disabled')
    
    # Hide all currently displayed widgets in 'req' and 'opt'
    for child in widgets['req'].winfo_children():
        child.grid_forget()
    for child in widgets['opt'].winfo_children():
        child.grid_forget()
    
    if cmd == 'help':
        return
    
    # Prepend for 'station' command to avoid name conflicts
    prepend = f"{cmd}~" if cmd == 'station' else ''
    
    # Handle required arguments
    if allArgs[cmd]['req']:
        if 'Required:' not in widgets:
            widgets['Required:'] = TDWidget.Label(widgets['req'], text='Required:', sticky='nw')
        else:
            widgets['Required:'].grid()
        
        for i, key in enumerate(allArgs[cmd]['req'], start=1):
            fullKey = prepend + key
            if fullKey not in widgets:
                addWidgetFromArg(fullKey, allArgs[cmd]['req'][key], widgets['req'])
            else:
                widgets[fullKey].grid(column=0, row=i)
    
    # Handle optional arguments
    if allArgs[cmd]['opt']:
        if 'Optional:' not in widgets:
            widgets['Optional:'] = TDWidget.Label(widgets['opt'], text='Optional:', sticky='nw')
        else:
            widgets['Optional:'].grid()
        
        for i, key in enumerate(allArgs[cmd]['opt'], start=1):
            fullKey = prepend + key
            if fullKey not in widgets:
                addWidgetFromArg(fullKey, allArgs[cmd]['opt'][key], widgets['opt'])




# Setup the CLI interface and build the main window
def main(argv=None):
    class IORedirector:
        def __init__(self, TEXT_INFO):
            self.TEXT_INFO = TEXT_INFO
    
    class StdoutRedirector(IORedirector):
        def write(self, string):
            current = self.TEXT_INFO.cget('text').rsplit('\r', 1)[0]
            self.TEXT_INFO.config(text=current + string)
        
        def flush(self):
            sys.__stdout__.flush()
    
    def setOpts():
        """
        Sets the main window options entry to the checked values in the options window.
        """
        sw = widgets.get("Plugin Options")  # TDWidget window reference
        plug = argVals.get('--plug')
        plugOpts = allArgs['import']['opt']['--option']['options'].get(plug, {})
        argStr = ''
        
        if plugOpts:
            for option, val in plugOpts.items():
                w = sw.get(option)  # Retrieve the TDWidget by name
                if '=' in val:
                    if w and isinstance(w, TDWidget.Entry):
                        argStr += f"{option}={w.get()},"  # get() for TDWidget entry
                else:
                    if w and isinstance(w, TDWidget.Checkbutton) and w.get():
                        argStr += f"{option},"
            
            argStr = argStr.rstrip(',')
            if '--option' in widgets:
                widgets['--option'].set(argStr)  # Update main window entry
        
        if sw:
            sw.hide()
    
    def optionsWin():
        """
        Opens a window listing all of the options for the currently selected plugin.
        """
        # Create a new TDWidget window
        sw = TDWidget.SubWindow(title="Plugin Options", modal=True)
        widgets["Plugin Options"] = sw  # store reference for later access
        sw.clear()  # empty the container
        
        optDict = {}
        current_opts = argVals.get('--option')
        if current_opts:
            for option in current_opts.split(','):
                if '=' in option:
                    key, val = option.split('=')
                    optDict[key] = val
                elif option != '':
                    optDict[option] = True
        
        plug = argVals.get('--plug')
        if not plug:
            TDWidget.Label(sw, text="No import plugin chosen.", sticky='ew', colspan=10)
        else:
            plugOpts = allArgs['import']['opt']['--option']['options'].get(plug, {})
            for option, tooltip in plugOpts.items():
                if '=' in tooltip:
                    TDWidget.Entry(
                        sw,
                        name=option,
                        textvariable=optDict.get(option, ''),
                        label=True,
                        sticky='ew',
                        colspan=10,
                        tooltip=tooltip
                    )
                else:
                    TDWidget.Checkbutton(
                        sw,
                        name=option,
                        textvariable=optDict.get(option, False),
                        sticky='ew',
                        colspan=10,
                        tooltip=tooltip
                    )
        
        # Buttons
        TDWidget.Button(sw, text="Done", func=setOpts, column=8)
        TDWidget.Button(sw, text="Cancel", func=sw.hide, row='p', column=9)
        
        sw.show()
    
    def updArgs(name):
        """
        Updates the value of argVals[name] when the linked widget's value is changed in the window.
        """
        
        def getWidget(name):
            """
            Returns the TDWidget instance for the given argument name.
            """
            return widgets.get(name)
        
        # Clear dependent options if the plugin changed
        if name == '--plug' and argVals.get(name) != (w := getWidget(name)).get():
            option_widget = widgets.get('--option')
            if option_widget:
                option_widget.set('')
        
        # Update the stored value
        w = getWidget(name)
        if w:
            argVals[name] = w.get()
        else:
            argVals[name] = None
        
        # Determine excluded arguments for this argument
        if allArgs.get(name):
            excluded = allArgs[name].get('excludes', [])
            argBase = allArgs
        else:
            try:
                cmd = widgets['Command'].get()
                excluded = allArgs[cmd]['opt'][name].get('excludes', [])
                argBase = allArgs[cmd]['opt']
            except KeyError:
                excluded = []
        
        # Reset any arguments excluded by this one if it has a value
        if excluded and argVals.get(name):
            for exclude in excluded:
                w = widgets.get(exclude)
                if not w:
                    continue
                widgetType = argBase[exclude]['widget']['type']
    
    def updCmd():
        """
        Updates the argument panes when the selected command is changed.
        """
        cmd = widgets['Command'].get()
        
        # Update help text
        help_widget = widgets.get('helpPane')
        if help_widget:
            help_widget.set(cmdHelp.get(cmd, ''))
        
        # Clear current argument frames
        for child in widgets['req'].winfo_children():
            child.grid_forget()
        for child in widgets['opt'].winfo_children():
            child.grid_forget()
        
        # Nothing more to do for 'help' command
        if cmd == 'help':
            return
        
        # Show required arguments
        req_frame = widgets['req']
        if allArgs[cmd]['req']:
            if 'Required:' not in widgets:
                widgets['Required:'] = TDWidget.Label(req_frame, text='Required:', sticky='w')
                widgets['Required:'].grid(column=0, row=0, sticky='w')
            else:
                widgets['Required:'].grid()
            
            i = 1
            for key, arg in allArgs[cmd]['req'].items():
                if key not in widgets:
                    addWidgetFromArg(key, arg, req_frame)
                else:
                    widgets[key].grid(column=0, row=i)
                i += 1
        
        # Show optional arguments
        opt_frame = _
    
    def runTD():
        """
        Executes the TD command selected in the GUI using TDWidget.
        """
        
        from . import tradeexcept
        
        def getVals(arg, argBase):
            curArg = argVals.get(arg)
            vals = []
            
            # Skip default or empty values
            if curArg is not None and curArg != argBase[arg].get('default'):
                if arg not in ['--detail', '--debug', '--quiet']:
                    vals.append(str(arg))
                
                widget_info = argBase[arg]['widget']
                wtype = widget_info.get('type')
                sub = widget_info.get('sub')
                
                if wtype == 'check':
                    # Checkbuttons already handled by presence in argVals
                    return vals
                
                if sub == 'ticks':
                    choices = ''
                    for choice, selected in curArg.items():
                        if selected:
                            choices += choice
                    vals.append(choices)
                    return vals
                
                if sub == 'credits':
                    # TODO: Handle 'credits' type
                    pass
                
                # Default behavior: append the current value
                vals.append(str(curArg))
            
            if not vals:
                return None
            
            return vals
        
        def runTrade():
            # Disable the Run button while executing
            run_btn = widgets.get('Run')
            if run_btn:
                run_btn.disable()
            
            # Redirect stdout to the output Text widget
            output_widget = widgets.get('outputText')
            oldout = sys.stdout
            sys.stdout = StdoutRedirector(output_widget)
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
                        print(f"PLUGIN ERROR: {e}")
                        if 'EXCEPTIONS' in os.environ:
                            raise e
                        sys.exit(1)
                    except tradeexcept.TradeException as e:
                        print(f"{argv[0]}: {e}")
                        if 'EXCEPTIONS' in os.environ:
                            raise e
                        sys.exit(1)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    print("-----------------------------------------------------------")
                    print("ERROR: Unexpected unicode error in the wild!")
                    print(traceback.format_exc())
                    print(
                        "Please report this bug (http://kfs.org/td/issues). "
                        "You may be able to work around it using '-q'. "
                        "Windows users can try 'chcp.com 65001' to enable UTF-8."
                    )
            except SystemExit as e:
                print(e)
            
            print("Execution complete.")
            # Restore stdout
            sys.stdout = oldout
            # Re-enable Run button
            if run_btn:
                run_btn.enable()
        
        # Switch to the Output tab
        tab_frame = widgets.get('tabFrame')
        if tab_frame:
            tab_frame.select_tab('Output')
        
        # Build the argv list
        cmd = widgets['Command'].get()
        argv = ['trade', cmd]
        
        if cmd != 'help':
            # Required args
            for arg in allArgs[cmd]['req']:
                result = getVals(arg, allArgs[cmd]['req'])
                if result:
                    argv += result if '-' in result[0] else result[1:]
            
            # Optional args
            for arg in allArgs[cmd]['opt']:
                result = getVals(arg, allArgs[cmd]['opt'])
                if result:
                    argv += result
            
            # Global args
            for arg in allArgs:
                if arg in Commands:
                    continue
                result = getVals(arg, allArgs)
                if result:
                    argv += result
        
        # Clear previous output
        if output_widget:
            output_widget.set('')
        
        # Run trade in a separate thread
        threading.Thread(target=runTrade, name="TDThread", daemon=True).start()
    
    def makeWidgets(name, arg, sticky='ew', label=True, **kwargs):
        """
        Creates and places a widget for the given argument using TDWidget.
        """
        kwargs['sticky'] = sticky
        kwargs['label'] = label
        kwargs['change'] = updArgs
        kwargs['tooltip'] = arg.get('help', '')
        kwargs['colspan'] = 1 if arg == allArgs.get(name) else 9
        
        widget_info = arg['widget']
        wtype = widget_info['type']
        
        if wtype == 'button':
            kwargs.pop('change', None)
            kwargs.pop('label', None)
            kwargs.pop('colspan', None)
            TDWidget(
                name=name,
                widget_type='button',
                command=widget_info.get('func'),
                **kwargs
            )
        
        elif wtype == 'check':
            TDWidget(
                name=name,
                widget_type='check',
                values=argVals.get(name, arg.get('default', False)),
                text=name,
                **kwargs
            )
        
        elif wtype == 'spin':
            TDWidget(
                name=name,
                widget_type='spin',
                values=argVals.get(name, arg.get('default', 0) or 0),
                min_value=widget_info.get('min', 0),
                max_value=widget_info.get('max', 100),
                **kwargs
            )
        
        elif wtype == 'combo':
            kwargs['sticky'] = 'w'
            if widget_info.get('sub'):
                kwargs['kind'] = widget_info['sub']
                kwargs.pop('label', None)
            
            combo = TDWidget(
                name=name,
                widget_type='combo',
                values=widget_info.get('values', []),
                **kwargs
            )
            
            if not widget_info.get('sub'):
                if not isinstance(argVals.get(name), str):
                    argVals[name] = None
                default_val = '?' if arg.get('choices') else ''
                combo.set(argVals.get(name) or arg.get('default') or default_val, callFunction=False)
            else:
                if isinstance(argVals.get(name), str):
                    argVals[name] = None
                if argVals.get(name):
                    for val, vval in argVals[name].items():
                        combo.set_option(val, values=vval, callFunction=False)
        
        elif wtype == 'option':
            kwargs.pop('change', None)
            kwargs.pop('label', None)
            kwargs.pop('colspan', None)
            
            # Option button opens the plugin options window
            TDWidget(
                name='optionButton',
                widget_type='button',
                command=optionsWin,
                option_name='--option',
                **kwargs
            )
            
            kwargs['sticky'] = sticky
            kwargs['change'] = updArgs
            TDWidget(
                name=name,
                widget_type='entry',
                values=argVals.get(name) or arg.get('default', ''),
                row='p',
                column=1,
                colspan=9,
                **kwargs
            )
        
        elif wtype == 'entry':
            if widget_info.get('sub') == 'credits':
                # TODO: Handle 'credits' type
                pass
            elif widget_info.get('sub'):
                kwargs['kind'] = 'numeric'
            
            TDWidget(
                name=name,
                widget_type='entry',
                values=argVals.get(name) or arg.get('default', ''),
                **kwargs
            )
    
    sys.argv = ['trade']
    if not argv:
        argv = sys.argv
    if sys.hexversion < 0x30813F0:
        raise SystemExit(
            "Sorry: TradeDangerous requires Python 3.8.19 or higher.\n"
            "For assistance, see:\n"
            "\tBug Tracker: https://github.com/eyeonus/Trade-Dangerous/issues\n"
            "\tDocumentation: https://github.com/eyeonus/Trade-Dangerous/wiki\n"
            "\tEDForum Thread: https://forums.frontier.co.uk/showthread.php/441509\n"
            )
    
    
    buildArgDicts()
    
    # --- Root window ---
    main_win = TDWidget(name='root', widget_type='frame')
    main_win.widget.master.title('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,))
    
    # --- Command Combo ---
    widgets['Command'] = TDWidget(
        name='Command', widget_type='combo', parent=main_win,
        values=Commands, width=10, row=0, column=0, columnspan=5, sticky='ew',
        command=updCmd
    )
    
    # --- Request / Optional Scroll Frames ---
    widgets['req'] = TDWidget('req', 'frame', parent=main_win, row=1, column=0, columnspan=10, sticky='nsew')
    widgets['req'].widget.config(width=200, height=75)
    widgets['opt'] = TDWidget('opt', 'frame', parent=main_win, row=2, column=0, columnspan=10, sticky='nsew')
    widgets['opt'].widget.config(width=200, height=345)
    
    # --- Tabbed Frame ---
    tabFrame = TDWidget('tabFrame', 'notebook', parent=main_win, row=1, column=10, rowspan=2, columnspan=40, sticky='nsew')
    
    # Help tab
    help_tab = TDWidget('helpTab', 'frame', parent=tabFrame)
    tabFrame.widget.add(help_tab.widget, text='Help')
    widgets['helpPane'] = TDWidget('helpPane', 'scrolledtext', parent=help_tab, row=0, column=0, width=80, height=25)
    widgets['helpPane'].set(cmdHelp['help'])
    widgets['helpPane'].widget.config(state='disabled', width=80)
    
    # Output tab
    output_tab = TDWidget('outputTab', 'frame', parent=tabFrame)
    tabFrame.widget.add(output_tab.widget, text='Output')
    widgets['outPane'] = TDWidget('outPane', 'scrolledtext', parent=output_tab, row=0, column=0, width=80, height=25)
    widgets['outPane'].set('')
    widgets['outPane'].widget.config(state='disabled', width=80)
    
    # --- Option Widgets ---
    makeWidgets('--link-ly', allArgs['--link-ly'], sticky='w', width=4, row=3, column=2)
    makeWidgets('--quiet', allArgs['--quiet'], sticky='e', disabled=':', width=1, row=3, column=46)
    makeWidgets('--detail', allArgs['--detail'], sticky='e', disabled=':', width=1, row=3, column=47)
    makeWidgets('--debug', allArgs['--debug'], sticky='e', disabled=':', width=1, row=3, column=48)
    
    # --- Run Button ---
    TDWidget('Run', 'button', parent=main_win, text='Run', command=runTD, row=3, column=49, sticky='w')
    
    # --- CWD ---
    makeWidgets('--cwd', allArgs['--cwd'], width=4, row=4, column=0)
    cwd_scroll = TDWidget('CWD', 'scrolledtext', parent=main_win, row=4, column=1, columnspan=49, width=70, height=1)
    cwd_scroll.set(argVals['--cwd'])
    cwd_scroll.widget.config(state='disabled')
    widgets['cwd'] = TDWidget('cwd', 'label', parent=main_win, text=argVals['--cwd'], sticky='w', row=4, column=1)
    
    # --- DB ---
    makeWidgets('--db', allArgs['--db'], width=4, row=5, column=0)
    db_scroll = TDWidget('DB', 'scrolledtext', parent=main_win, row=5, column=1, columnspan=49, width=70, height=1)
    db_scroll.set(argVals['--db'])
    db_scroll.widget.config(state='disabled')
    widgets['db'] = TDWidget('db', 'label', parent=main_win, text=argVals['--db'], sticky='w', row=5, column=1)
    
    # --- Configure row/column stretching for proper layout ---
    for i in range(50):
        main_win.widget.columnconfigure(i, weight=1)
    for i in range(6):
        main_win.widget.rowconfigure(i, weight=1)
    
    # --- Show window ---
    main_win.widget.mainloop()
    
    # with gui('Trade Dangerous GUI (Beta), TD v.%s' % (__version__,), inPadding=1) as win:
    #     win.setFont(size=8, family='Courier')
    #     win.combo('Command', Commands, change=updCmd, tooltip='Trade Dangerous command to run.',
    #               stretch='none', sticky='ew', width=10, row=0, column=0, colspan=5)
    #     with win.scrollPane('req', disabled='horizontal', row=1, column=0, colspan=10) as pane:
    #         pane.configure(width=200, height=75)
    # 
    #     with win.scrollPane('opt', disabled='horizontal', row=2, column=0, colspan=10) as pane:
    #         pane.configure(width=200, height=345)
    # 
    #     with win.tabbedFrame('tabFrame', disabled='horizontal', row=1, column=10, rowspan=2, colspan=40) as tabFrame:
    #         with win.tab('Help'):
    #             with win.scrollPane('helpPane', disabled='horizontal') as pane:
    #                 pane.configure(width=560, height=420)
    #                 win.message('helpText', cmdHelp['help'])
    #                 win.widgetManager.get(WIDGET_NAMES.Message, 'helpText').config(width=560)
    # 
    #         with win.tab('Output'):
    #             with win.scrollPane('outPane', disabled='horizontal') as pane:
    #                 pane.configure(width=560, height=420)
    #                 win.message('outputText', '')
    #                 win.widgetManager.get(WIDGET_NAMES.Message, 'outputText').config(width=560)
    # 
    #     makeWidgets('--link-ly', allArgs['--link-ly'], sticky='w', width=4, row=3, column=2)
    # 
    #     makeWidgets('--quiet', allArgs['--quiet'], sticky='e', disabled=':', width=1, row=3, column=46)
    # 
    #     makeWidgets('--detail', allArgs['--detail'], sticky='e', disabled=':', width=1, row=3, column=47)
    # 
    #     makeWidgets('--debug', allArgs['--debug'], sticky='e', disabled=':', width=1, row=3, column=48)
    # 
    #     win.button('Run', runTD, tooltip='Execute the selected command.',
    #                sticky='w', row=3, column=49)
    # 
    #     makeWidgets('--cwd', allArgs['--cwd'], width=4, row=4, column=0)
    #     with win.scrollPane('CWD', disabled='vertical', row=4, column=1, colspan=49) as pane:
    #         pane.configure(width=500, height=20)
    #         widgets['cwd'] = win.label('cwd', argVals['--cwd'], sticky='w')
    # 
    #     makeWidgets('--db', allArgs['--db'], width=4, row=5, column=0)
    #     with win.scrollPane('DB', disabled='vertical', row=5, column=1, colspan=49) as pane:
    #         pane.configure(width=500, height=20)
    #         widgets['db'] = win.label('db', argVals['--db'], sticky='w')


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
