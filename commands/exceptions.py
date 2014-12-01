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
        return "Error: {}\n".format(self.errorStr) + (
                "This can happen when there are no profitable trades"
                " matching your criteria, or if you have not yet entered"
                " any price data for the station(s) involved.\n"
                "\n"
                "See '{} update -h' for help entering/updating prices, or"
                " obtain a '.prices' file from the web, such as maddavo's:"
                " http://www.davek.com.au/td/\n"
                "\n"
                "See https://bitbucket.org/kfsone/tradedangerous/wiki/"
                    "Price%20Data"
                " for more help."
            ).format(sys.argv[0])


