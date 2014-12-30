from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from tradeexcept import TradeException
import sys

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
        return "Error: {}\n".format(self.errorStr) + ("""
This can either indicate a lack of data (such as missing
price information, station data, etc) or that there was no
data matching your criteria.

See '{} update -h' for help entering/updating prices, or
obtain a crowd-sourced '.prices' file from the web, such
as maddavo's (http://www.davek.com.au/td/)".

For more help, see the TradeDangerous Wiki:
    http://kfs.org/td/wiki
""").format(sys.argv[0])


