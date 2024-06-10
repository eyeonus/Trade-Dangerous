from .exceptions import (
    FleetCarrierError, OdysseyError, PadSizeError, PlanetaryError,
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
            if val[-1] in CreditParser.suffixes:
                val = int(float(val[:-1]) * CreditParser.suffixes[val[-1]])
        return super().__new__(cls, val, **kwargs)


class PadSizeArgument(int):
    """
    argparse helper for --pad-size
    """
    class PadSizeParser(str):
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise PadSizeError(val)
            for v in val:
                if "SML?".find(v.upper()) < 0:
                    raise PadSizeError(val.upper())
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


class BlackMarketSwitch(SwitchArgument):
    switches = ['--black-market', '--bm']
    dest = 'blackMarket'
    help = 'Require stations known to have a black market.'


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


class NoPlanetSwitch(SwitchArgument):
    switches = ['--no-planet']
    dest = 'noPlanet'
    help = 'Require stations to be in space.'


class PlanetaryArgument(int):
    """
    argparse helper for --planetary
    """
    class PlanetaryParser(str):
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise PlanetaryError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise PlanetaryError(val.upper())
            return super().__new__(cls, val, **kwargs)
    
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
    class FleetCarrierParser(str):
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise FleetCarrierError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise FleetCarrierError(val.upper())
            return super().__new__(cls, val, **kwargs)
    
    def __init__(self):
        self.args = ['--fleet-carrier', '--fc']
        self.kwargs = {
            'help': (
                'Limit to stations with one of the specified fleet-carrier, '
                'e.g. --fc YN? matches any station, --fc Y matches only '
                'fleet-carrier stations.'
            ),
            'dest': 'fleet',
            'metavar': 'FLEET',
            'type': 'fleet',
        }

class OdysseyArgument(int):
    """
    argparse helper for --odyssey
    """
    class OdysseyParser(str):
        def __new__(cls, val, **kwargs):
            if not isinstance(val, str):
                raise OdysseyError(val)
            for v in val:
                if "YN?".find(v.upper()) < 0:
                    raise OdysseyError(val.upper())
            return super().__new__(cls, val, **kwargs)
    
    def __init__(self):
        self.args = ['--odyssey', '--od']
        self.kwargs = {
            'help': (
                'Limit to stations with one of the specified odyssey, '
                'e.g. --od YN? matches any station, --od Y matches only '
                'odyssey stations.'
            ),
            'dest': 'odyssey',
            'metavar': 'ODYSSEY',
            'type': 'odyssey',
        }


__tdParserHelpers = {
    'credits': CreditParser,
    'padsize': PadSizeArgument.PadSizeParser,
    'planetary': PlanetaryArgument.PlanetaryParser,
    'fleet': FleetCarrierArgument.FleetCarrierParser,
    'odyssey': OdysseyArgument.OdysseyParser,
}

def registerParserHelpers(into):
    for typeName, helper in __tdParserHelpers.items():
        into.register('type', typeName, helper)
