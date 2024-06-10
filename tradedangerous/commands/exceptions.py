from ..tradeexcept import TradeException


######################################################################
# Exceptions

class UsageError(TradeException):
    def __init__(self, title, usage):
        self.title, self.usage = title, usage
    
    def __str__(self):
        return self.title + "\n\n" + self.usage


class CommandLineError(TradeException):
    """
        Raised when you provide invalid input on the command line.
        Attributes:
            errorstr       What to tell the user.
    """
    def __init__(self, errorStr, usage=None):
        self.errorStr, self.usage = errorStr, usage
    
    def __str__(self):
        if self.usage:
            return "ERROR: {}\n\n{}".format(self.errorStr, self.usage)
        else:
            return "ERROR: {}".format(self.errorStr)


class NoDataError(TradeException):
    """
        Raised when a request is made for which no data can be found.
        Attributes:
            errorStr        Describe the problem to the user.
    """
    def __init__(self, errorStr):
        self.errorStr = errorStr
    
    def __str__(self):
        return f"""Error: {self.errorStr}
Possible causes:
- No profitable runs or routes meet your criteria,
- Missing Systems or Stations along the route (see "local -vv"),
- Missing price data (see "market -vv" or "update -h"),

If you are not sure where to get data from, consider using a crowd-sourcing
project such as EDDBlink (https://github.com/eyeonus/EDDBlink).

For more help, see the TradeDangerous Wiki:
    https://github.com/eyeonus/Trade-Dangerous/wiki
"""


class PadSizeError(CommandLineError):
    """ Raised when an invalid pad-size option is given. """
    def __init__(self, value):
        super().__init__(
            "Invalid --pad-size '{}': Use a combination of one or more "
            "from 'S' for Small, 'M' for Medium, 'L' for Large or "
            "'?' for unknown, e.g. 'SML?' matches any pad size while "
            "'M?' matches medium or unknown or 'L' matches only large."
            .format(value)
        )


class PlanetaryError(CommandLineError):
    """ Raised when an invalid planetary option is given. """
    def __init__(self, value):
        super().__init__(
            "Invalid --planetary '{}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-planetary stations."
            .format(value)
        )


class FleetCarrierError(CommandLineError):
    """ Raised when an invalid fleet-carrier option is given. """
    def __init__(self, value):
        super().__init__(
            "Invalid --fleet-carrier '{}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-fleet-carrier stations."
            .format(value)
        )

class OdysseyError(CommandLineError):
    """ Raised when an invalid odyssey option is given. """
    def __init__(self, value):
        super().__init__(
            "Invalid --odyssey '{}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-odyssey stations."
            .format(value)
        )
