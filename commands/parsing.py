from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

######################################################################
# Parsing Helpers

class ParseArgument(object):
    """
        Provides argument forwarding so that 'makeSubParser' can take function-like arguments.
    """
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class MutuallyExclusiveGroup(object):
    def __init__(self, *args):
        self.arguments = list(args)


######################################################################
# Derived Parsers


class CreditParser(int):
    """
    argparse helper for parsing numeric prefixes, i.e.
    'k' for thousand, 'm' for million and 'b' for billion.
    """
    suffixes = {'k': 10**3, 'm': 10**6, 'b': 10**9}
    def __new__(cls, val, **kwargs):
        if isinstance(val, str):
            if val[-1] in CreditParser.suffixes:
                val = int(float(val[:-1]) * CreditParser.suffixes[val[-1]])
        return super().__new__(cls, val, **kwargs)


class PadSizeArgument(int):
    """
    argparse helper for --pad-size
    """
    class PadSizeParser(str):
        def __new__(cls, val, **kwargs):
            invalid = None
            if not isinstance(val, str):
                invalid = val
            else:
                for v in val:
                    if "SML?".find(v.upper()) < 0:
                        invalid = v
                        break
            if invalid:
                raise CommandLineError(
                    "Unrecognized --pad-size option '{}'. Use any "
                    "combination of one or more of S, M, L or ?."
                    .format(invalid)
                )
            return super().__new__(cls, val, **kwargs)

    def __init__(self):
        self.args = ('--pad-size', '-p',)
        self.kwargs = {
            'help': (
                'Limit to stations with one of the specified pad sizes, '
                'e.g. --pad SML? matches any pad, --pad M matches only '
                'medium pads.'
            ),
            'dest': 'padSize',
            'metavar': 'PADSIZES',
            'type': 'padsize',
        }


__tdParserHelpers = {
    'credits': CreditParser,
    'padsize': PadSizeArgument.PadSizeParser,
}

def registerParserHelpers(into):
    for typeName, helper in __tdParserHelpers.items():
        into.register('type', typeName, helper)
