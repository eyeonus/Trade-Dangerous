from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
import argparse             # For parsing command line args.
import sys
import pathlib
import os
import importlib

import commands.exceptions
import commands.parsing
from commands.commandenv import CommandEnv

commandList = [

    'buildcache',
    'buy',
    'export',
    'import',
    'local',
    'nav',
    'run',
    'sell',
    'update',

]

######################################################################
# Helpers

class HelpAction(argparse.Action):
    """
        argparse action helper for printing the argument usage,
        because Python 3.4's argparse is ever-so subtly very broken.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        raise exceptions.UsageError("TradeDangerous help", parser.format_help())


def addArguments(group, options, required, topGroup=None):
    """
        Registers a list of options to the specified group. Nodes
        are either an instance of ParseArgument or a list of
        ParseArguments. The list form is considered to be a
        mutually exclusive group of arguments.
    """
    for option in options:
        if isinstance(option, parsing.MutuallyExclusiveGroup):
            exGrp = (topGroup or group).add_mutually_exclusive_group()
            addArguments(exGrp, option.arguments, required, topGroup=group)
        else:
            assert not required in option.kwargs
            if option.args[0][0] == '-':
                group.add_argument(*(option.args), required=required, **(option.kwargs))
            else:
                group.add_argument(*(option.args), **(option.kwargs))


def import_module(cmdName):
    """ Import the module for a give command name. """
    return importlib.import_module("commands.{}_cmd".format(cmdName.lower()))


class CommandIndex(object):
    def usage(self, argv):
        """
            Generate the outlying usage text for TD.
            This tells the user the list of current
            commands, generated programatically,
            and the outlying command functionality.
        """

        index = {}
        for command in commandList:
            module = import_module(command)
            index[command] = module

        from textwrap import TextWrapper

        text = (
            "Usage: {prog} <command>\n\n"
            "Where <command> is one of:\n\n"
                .format(prog=argv[0])
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
                subsequent_indent=' '*(cmdFmtLen + 1),
                width=78,
                drop_whitespace=True,
                expand_tabs=True,
                fix_sentence_endings=True,
                break_long_words=False,
                break_on_hyphens=True,
                )

        # List each command with its help text
        lastCmdName = None
        for cmdName, cmd in sorted(index.items()):
            tw.initial_indent = cmdFmt.format(cmdName)
            text += tw.fill(cmd.help) + "\n"
            lastCmdName = cmdName

        # Epilog
        text += (
            "\n"
            "For additional help on a specific command, such as '{cmd}' use\n"
            "  {prog} {cmd} -h"
                .format(prog=argv[0], cmd=lastCmdName)
            )
        return text


    def parse(self, argv):
        if len(argv) <= 1 or argv[1] == '--help' or argv[1] == '-h':
            raise exceptions.UsageError(
                    "TradeDangerous provides a set of trade database "
                    "facilities for Elite:Dangerous.", self.usage(argv))

        ### TODO: Break this model up a bit more so that
        ### we just try and import the command you specify,
        ### and only worry about an index when that fails or
        ### the user requests usage.
        cmdName = argv[1].lower()
        if cmdName not in commandList:
            raise exceptions.CommandLineError("Unrecognized command, '{}'".format(cmdName), self.usage(argv))

        cmdModule = import_module(cmdName)

        class ArgParser(argparse.ArgumentParser):
            def error(self, message):
                raise exceptions.CommandLineError(message, self.format_usage())

        parser = ArgParser(
                    description="TradeDangerous: "+cmdName,
                    add_help=False,
                    epilog='Use {prog} {cmd} -h for more help'.format(
                            prog=argv[0], cmd=argv[1]
                        )
                )
        parser.set_defaults(_editing=False)

        subParsers = parser.add_subparsers(title='Command Options')
        subParser = subParsers.add_parser(cmdModule.name,
                                    help=cmdModule.help,
                                    add_help=False,
                                    epilog=cmdModule.epilog,
                                    )

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
        stdArgs.add_argument('-h', '--help',
                    help='Show this help message and exit.',
                    action=HelpAction, nargs=0,
                )
        stdArgs.add_argument('--debug', '-w',
                    help='Enable diagnostic output.',
                    default=0, required=False, action='count',
                )
        stdArgs.add_argument('--detail', '-v',
                    help='Increase level  of detail in output.',
                    default=0,required=False, action='count',
                )
        stdArgs.add_argument('--quiet', '-q',
                    help='Reduce level of detail in output.',
                    default=0, required=False, action='count',
                )
        stdArgs.add_argument('--db',
                    help='Specify location of the SQLite database.',
                    default=None, dest='dbFilename', type=str,
                )
        stdArgs.add_argument('--cwd', '-C',
                    help='Change the working directory file accesses are made from.',
                    type=str, required=False,
                )
        stdArgs.add_argument('--link-ly', '-L',
                    help='Maximum lightyears between systems to be considered linked.',
                    default=None, dest='linkLy',
                )

        properties = parser.parse_args(argv[1:])

        return CommandEnv(properties, argv, cmdModule)

