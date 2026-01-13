from ..tradeexcept import TradeException


######################################################################
# Exceptions

class UsageError(TradeException):
    def __init__(self, title, usage):
        self.title, self.usage = title, usage
    
    def __str__(self):
        return f"{self.title}\n\n{self.usage}"


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
            return f"ERROR: {self.errorStr}\n\n{self.usage}"
        return f"ERROR: {self.errorStr}"


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

class GameDataError(TradeException):
    """
        Raised when imported or journal data is internally inconsistent
        or clearly invalid (e.g. cargo load exceeds cargo capacity).

        Attributes:
            errorStr    A short description of the inconsistency.
    """
    def __init__(self, errorStr):
        self.errorStr = errorStr

    def __str__(self):
        return f"""Error: {self.errorStr}
Possible causes:
- The journal data was incomplete or out of sync when read,
- You recently changed ships or game state and journals are still updating,
- The wrong journals or save files are being read (check your journal path),
- Or the data on disk has been corrupted.

Try again after the game has fully updated, or re-run the command with
--full-load to ignore current cargo occupancy if appropriate.

For more help, see the TradeDangerous Wiki:
    https://github.com/eyeonus/Trade-Dangerous/wiki
"""

class PadSizeError(CommandLineError):
    """ Raised when an invalid pad-size option is given. """
    def __init__(self, value):
        super().__init__(
            f"Invalid --pad-size '{value}': Use a combination of one or more "
            "from 'S' for Small, 'M' for Medium, 'L' for Large or "
            "'?' for unknown, e.g. 'SML?' matches any pad size while "
            "'M?' matches medium or unknown or 'L' matches only large."
        )


class PlanetaryError(CommandLineError):
    """ Raised when an invalid planetary option is given. """
    def __init__(self, value):
        super().__init__(
            f"Invalid --planetary '{value}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-planetary stations."
        )


class FleetCarrierError(CommandLineError):
    """ Raised when an invalid fleet-carrier option is given. """
    def __init__(self, value):
        super().__init__(
            f"Invalid --fleet-carrier '{value}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-fleet-carrier stations."
        )

class OdysseyError(CommandLineError):
    """ Raised when an invalid odyssey option is given. """
    def __init__(self, value):
        super().__init__(
            f"Invalid --odyssey '{value}': Use a combination of one or more "
            "from 'Y' for Yes, 'N' for No or '?' for unknown, "
            "e.g. 'YN?' matches any station while 'Y?' matches "
            "yes or unknown, or 'N' matches only non-odyssey stations."
        )
