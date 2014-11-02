from commands.exceptions import UsageError
from argparse import Action as ArgAction

######################################################################
# Parsing Helpers

class HelpAction(ArgAction):
    """
        argparse action helper for printing the argument usage,
        because Python 3.4's argparse is ever-so subtly very broken.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        raise UsageError("TradeDangerous help", parser.format_help())
        

class EditAction(ArgAction):
    """
        argparse action that stores a value and also flags args._editing
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, "_editing", True)
        setattr(namespace, self.dest, values or self.default)


class EditActionStoreTrue(ArgAction):
    """
        argparse action that stores True but also flags args._editing
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(EditActionStoreTrue, self).__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, "_editing", True)
        setattr(namespace, self.dest, True)


class ParseArgument(object):
    """
        Provides argument forwarding so that 'makeSubParser' can take function-like arguments.
    """
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class MutuallyExclusiveGroup(object):
    def __init__(self, *args):
        self.arguments = list(args)
