from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

class TradeEnv(object):
    """
        Container for a TradeDangerous "environment", which is a
        collection of operational parameters.
    """

    defaults = {
        'debug': 0,
        'detail': 0,
        'quiet': 0,
    }

    def __init__(self, properties=None, **kwargs):
        properties = properties or dict()
        self.__dict__.update(TradeEnv.defaults)
        if properties:
            self.__dict__.update(properties.__dict__)
        if kwargs:
            self.__dict__.update(kwargs)



    def DEBUG(self, debugLevel, outText, *args, **kwargs):
        """
            Output text to stderr on the condition that
            the current debug setting is higher than debugLevel
        """
        if self.debug > debugLevel:
            print('#', outText.format(*args, **kwargs))

