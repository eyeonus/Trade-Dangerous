class TradeEnv(object):
    """
        Container for a TradeDangerous "environment", which is a
        collection of operational parameters.
    """

    def __init__(self, properties=None, **kwargs):
        properties = properties or type('Properties', (), dict())

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

