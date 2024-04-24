from .commandenv import CommandEnv
from textwrap import TextWrapper

import argparse  # For parsing command line args.
import os
import pathlib
import sys

thismodule = sys.modules[__name__]
from . import exceptions
from . import parsing

from . import buildcache_cmd
from . import buy_cmd
from . import export_cmd
from . import import_cmd
from . import local_cmd
from . import market_cmd
from . import nav_cmd
from . import olddata_cmd
from . import rares_cmd
from . import run_cmd
from . import sell_cmd
from . import shipvendor_cmd
from . import station_cmd
from . import trade_cmd
from . import update_cmd

commandIndex = {
    cmd[0:cmd.find('_cmd')]: getattr(thismodule, cmd)
    for cmd in thismodule.__dir__() if cmd.endswith("_cmd")
}

######################################################################
# Helpers


class HelpAction(argparse.Action):
    """
        argparse action helper for printing the argument usage,
        because Python 3.4's argparse is ever-so subtly very broken.
    """
    
    def __call__(self, parser, namespace, values, option_string = None):
        raise exceptions.UsageError(
                "TradeDangerous help",
                parser.format_help()
        )


def addArguments(group, options, required, topGroup = None):
    """
        Registers a list of options to the specified group. Nodes
        are either an instance of ParseArgument or a list of
        ParseArguments. The list form is considered to be a
        mutually exclusive group of arguments.
    """
    for option in options:
        if isinstance(option, parsing.MutuallyExclusiveGroup):
            exGrp = (topGroup or group).add_mutually_exclusive_group()
            parsing.registerParserHelpers(exGrp)
            addArguments(exGrp, option.arguments, required, topGroup = group)
        else:
            assert required not in option.kwargs
            if option.args[0][0] == '-':
                group.add_argument(*(option.args), required = required, **(option.kwargs))
            else:
                if required:
                    group.add_argument(*(option.args), **(option.kwargs))
                else:
                    group.add_argument(*(option.args), nargs = '?', **(option.kwargs))


def _findFromFile(cmd, prefix = '.tdrc'):
    if cmd:
        # check the current directory, fall back to home
        filename = '{}_{}'.format(prefix, cmd)
        for dirname in '.', os.path.expanduser('~'):
            cmdPath = pathlib.Path(dirname) / filename
            if cmdPath.exists():
                return cmdPath.resolve()
    return None


class CommandIndex:
    
    def usage(self, argv):
        """
            Generate the outlying usage text for TD.
            This tells the user the list of current
            commands, generated programatically,
            and the outlying command functionality.
        """
        
        text = (
            "Usage: {prog} <command>\n\n"
            "Where <command> is one of:\n\n"
                .format(prog = argv[0])
        )
        
        # Figure out the pre-indentation
        cmdFmt = '  {:<12s}  '
        cmdFmtLen = len(cmdFmt.format(''))
        # Generate a formatter which will produce nicely formatted text
        # that wraps at column 78 but puts continuation text one character
        # indented from where the previous text started, e.g
        #   cmd1    Cmd1 help text stuff
        #            continued cmd1 text
        #   cmd2    Cmd2 help text
        tw = TextWrapper(
                subsequent_indent = ' ' * (cmdFmtLen + 1),
                width = 78,
                drop_whitespace = True,
                expand_tabs = True,
                fix_sentence_endings = True,
                break_long_words = False,
                break_on_hyphens = True,
                )
        
        # List each command with its help text
        lastCmdName = None
        for cmdName, cmd in sorted(commandIndex.items()):
            tw.initial_indent = cmdFmt.format(cmdName)
            text += tw.fill(cmd.help) + "\n"
            lastCmdName = cmdName
        
        # Epilog
        text += (
            "\n"
            "For additional help on a specific command, such as '{cmd}' use\n"
            "  {prog} {cmd} -h"
                .format(prog = argv[0], cmd = lastCmdName)
            )
        return text
    
    def parse(self, argv, fromfile_prefix = '+'):
        if len(argv) <= 1 or argv[1] == '--help' or argv[1] == '-h':
            raise exceptions.UsageError(
                    "TradeDangerous provides a set of trade database "
                    "facilities for Elite:Dangerous.", self.usage(argv))
        
        # ## TODO: Break this model up a bit more so that
        # ## we just try and import the command you specify,
        # ## and only worry about an index when that fails or
        # ## the user requests usage.
        cmdName, cmdModule = argv[1].casefold(), None
        try:
            cmdModule = commandIndex[cmdName]
        except KeyError:
            pass
        
        if not cmdModule:
            candidates = []
            for name, module in commandIndex.items():
                if name.startswith(cmdName):
                    candidates.append([name, module])
            if not candidates:
                raise exceptions.CommandLineError(
                        "Unrecognized command, '{}'".format(cmdName),
                        self.usage(argv)
                )
            if len(candidates) > 1:
                raise exceptions.CommandLineError(
                        "Ambiguous command, '{}', "
                        "could match: {}".format(
                            cmdName,
                            ', '.join(c[0] for c in candidates)
                        ),
                        self.usage(argv)
                )
            argv[1] = cmdName = candidates[0][0]
            cmdModule = candidates[0][1]
        
        class ArgParser(argparse.ArgumentParser):
            
            def error(self, message):
                raise exceptions.CommandLineError(message, self.format_usage())
        
        parser = ArgParser(
                    description = "TradeDangerous: " + cmdName,
                    add_help = False,
                    epilog = 'Use {prog} {cmd} -h for more help'.format(
                            prog = argv[0], cmd = argv[1]
                        ),
                    fromfile_prefix_chars = fromfile_prefix,
                )
        parser.set_defaults(_editing = False)
        parsing.registerParserHelpers(parser)
        
        subParsers = parser.add_subparsers(title = 'Command Options')
        subParser = subParsers.add_parser(cmdModule.name,
                                    help = cmdModule.help,
                                    add_help = False,
                                    epilog = cmdModule.epilog,
                                    )
        parsing.registerParserHelpers(subParser)
        
        arguments = cmdModule.arguments
        if arguments:
            argParser = subParser.add_argument_group('Required Arguments')
            addArguments(argParser, arguments, True)
        
        switches = cmdModule.switches
        if switches:
            switchParser = subParser.add_argument_group('Optional Switches')
            addArguments(switchParser, switches, False)
        
        # Arguments common to all subparsers.
        stdArgs = subParser.add_argument_group('Common Switches')
        stdArgs.add_argument('--help', '-h',
                    help = 'Show this help message and exit.',
                    action = HelpAction, nargs = 0,
                )
        stdArgs.add_argument('--debug', '-w',
                    help = 'Enable/raise level of diagnostic output.',
                    default = 0, required = False, action = 'count',
                )
        stdArgs.add_argument('--detail', '-v',
                    help = 'Increase level of detail in output.',
                    default = 0, required = False, action = 'count',
                )
        stdArgs.add_argument('--color', '-c',
                    help = 'Add color to output for enhanced readability.',
                    default = False, action = 'store_true',
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
        
        fromfilePath = _findFromFile(cmdModule.name)
        if fromfilePath:
            argv.insert(2, '{}{}'.format(fromfile_prefix, fromfilePath))
        properties = parser.parse_args(argv[1:])
        
        parsed = CommandEnv(properties, argv, cmdModule)
        parsed.DEBUG0("Command line was: {}", argv)
        
        return parsed
