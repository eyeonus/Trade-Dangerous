from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

class TradeEnv(object):
    """
        Container for a TradeDangerous "environment", which is a
        collection of operational parameters.
    """

    def __init__(self, properties=None, **kwargs):
        if not properties:
            properties = type('Properties',
                                (),
                                dict(
                                    debug=0,
                                    detail=0,
                                    quiet=0,
                                ))

        self._props = properties
        for arg, value in kwargs.items():
            setattr(self, arg, value)


    def __getattr__(self, key, default=None):
        """ Fall back to _props when accessing attributes. """
        try:
            return getattr(self._props, key, default)
        except AttributeError:
            return default


    def DEBUG(self, debugLevel, outText, *args, **kwargs):
        """
            Output text to stderr on the condition that
            the current debug setting is higher than debugLevel
        """
        if self.debug > debugLevel:
            print('#', outText.format(*args, **kwargs))

