from .exceptions import (
    FleetCarrierError, SettlementError, PadSizeError, PlanetaryError,
)

######################################################################
# Parsing Helpers

class ParseArgument:
    """
        Provides argument forwarding so that 'makeSubParser' can take function-like arguments.
    """
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs


class MutuallyExclusiveGroup:
    def __init__(self, *args):
        self.arguments = list(args)


######################################################################
# Derived Parsers


class CreditParser(int):
    """
    argparse helper for parsing numeric prefixes, i.e.
    'k' for thousands, 'm' for millions and 'b' for billions.
    """
    suffixes = {'k': 10**3, 'm': 10**6, 'b': 10**9}
    
    def __new__(cls, val, **kwargs):
        if isinstance(val, str):
            if val[-1].lower() in CreditParser.suffixes:
                val = int(float(val[:-1]) * CreditParser.suffixes[val[-1].lower()])
        return super().__new__(cls, val, **kwargs)


class PadSizeArgument(int):
    """
    argparse helper for --pad-size
    """
    class PadSizeParser(str):  # noqa: SLOT000  # str is immutable
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise PadSizeError(val)
            for v in val:
                if "SML?".find(v.upper()) < 0:
                    raise PadSizeError(val.upper())
            return super().__new__(cls, val.upper(), **kwargs)
    
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


class AvoidPlacesArgument(ParseArgument):
    def __init__(self):
        self.args = ['--avoid']
        self.kwargs = {
            'action': 'append',
            'help': (
                "Don't list results for the specified systems or stations.\n"
                "Names can be one-per '--avoid' or comma separated, e.g. "
                "'--avoid a,b,c' or '--avoid a,b --avoid c'"
            ),
        }


class SwitchArgument(ParseArgument):
    def __init__(self, help=None):
        if isinstance(self.switches, (tuple, list)):
            self.args = self.switches
        else:
            self.args = (self.switches,)
        help = help or self.help
        self.kwargs = {'action': 'store_true', 'dest': self.dest, 'help': help}


class BlackMarketSwitch(ParseArgument):
    """argparse helper for --black-market"""

    class BlackMarketParser(str):  # noqa: SLOT000  # str is immutable
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise ValueError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise ValueError(val.upper())
            return super().__new__(cls, val.upper(), **kwargs)
    
    def __init__(self):
        self.args = ['--black-market', '--bm']
        self.kwargs = {
            'help': (
                'Limit by black-market status: Y = known black market, '
                'N = known no black market, ? = unknown black-market state.'
            ),
            'dest': 'blackMarket',
            'metavar': 'BLACKMARKET',
            'type': BlackMarketSwitch.BlackMarketParser,
        }


class ShipyardSwitch(SwitchArgument):
    switches = ['--shipyard']
    dest = 'shipyard'
    help = 'Require stations known to have a Shipyard.'


class OutfittingSwitch(SwitchArgument):
    switches = ['--outfitting']
    dest = 'outfitting'
    help = 'Require stations known to have Outfitting.'


class RearmSwitch(SwitchArgument):
    switches = ['--rearm']
    dest = 'rearm'
    help = 'Require stations known to sell munitions.'


class RefuelSwitch(SwitchArgument):
    switches = ['--refuel']
    dest = 'refuel'
    help = 'Require stations known to sell fuel.'


class RepairSwitch(SwitchArgument):
    switches = ['--repair']
    dest = 'repair'
    help = 'Require stations known to offer repairs.'


class PlanetaryArgument(int):
    """
    argparse helper for --planetary
    """
    class PlanetaryParser(str):  # noqa: SLOT000  # str is immutable
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise PlanetaryError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise PlanetaryError(val.upper())
            return super().__new__(cls, val.upper(), **kwargs)
    
    def __init__(self):
        self.args = ['--planetary']
        self.kwargs = {
            'help': (
                'Limit to stations with one of the specified planetary, '
                'e.g. --pla YN? matches any station, --pla Y matches only '
                'planetary stations.'
            ),
            'dest': 'planetary',
            'metavar': 'PLANETARY',
            'type': 'planetary',
        }


class FleetCarrierArgument(int):
    """
    argparse helper for --fleet-carrier
    """
    class FleetCarrierParser(str):  # noqa: SLOT000  # str is immutable
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise FleetCarrierError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise FleetCarrierError(val.upper())
            return super().__new__(cls, val.upper(), **kwargs)
    
    def __init__(self):
        self.args = ['--fleet-carrier', '--fc']
        self.kwargs = {
            'help': (
                'Limit by fleet-carrier status: Y = known fleet carriers, '
                'N = known non-fleet-carriers, ? = unknown station type. '
                'e.g. --fc Y matches only fleet carriers, --fc N excludes them.'
            ),
            'dest': 'fleet',
            'metavar': 'FLEET',
            'type': 'fleet',
        }

class SettlementArgument(int):
    """
    argparse helper for --settlement
    """
    class SettlementParser(str):  # noqa: SLOT000  # str is immutable
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise SettlementError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise SettlementError(val.upper())
            return super().__new__(cls, val.upper(), **kwargs)

    def __init__(self):
        self.args = ['--settlement', '--stl']
        self.kwargs = {
            'help': (
                'Limit by settlement status: Y = settlements, '
                'N = non-settlements, ? = unknown station type. '
                'Settlements are planetary locations, but not all planetary '
                'stations are settlements. e.g. --settlement Y matches only '
                'settlements, --settlement N excludes them.'
            ),
            'dest': 'settlement',
            'metavar': 'SETTLEMENT',
            'type': 'settlement',
        }


__tdParserHelpers = {
    'credits': CreditParser,
    'padsize': PadSizeArgument.PadSizeParser,
    'planetary': PlanetaryArgument.PlanetaryParser,
    'fleet': FleetCarrierArgument.FleetCarrierParser,
    'settlement': SettlementArgument.SettlementParser,
}

def registerParserHelpers(into):
    for typeName, helper in __tdParserHelpers.items():
        into.register('type', typeName, helper)
