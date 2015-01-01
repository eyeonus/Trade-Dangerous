from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

class TradeEnv(object):
    """
        Container for a TradeDangerous "environment", which is a
        collection of operational parameters.

        To print debug lines, use DEBUG<N>, e.g. DEBUG0, which
        takes a format() string and parameters, e.g.

            DEBUG1("hello, {world}{}", "!", world="world")

        is equivalent to:

            if tdenv.debug >= 1:
                print("#hello, {world}{}".format(
                        "!", world="world"
                ))

        Use "NOTE" to print remarks which can be disabled with -q.
    """

    defaults = {
        'debug': 0,
        'detail': 0,
        'quiet': 0,
        'dataDir': './data',
    }

    def __init__(self, properties=None, **kwargs):
        properties = properties or dict()
        self.__dict__.update(self.defaults)
        if properties:
            self.__dict__.update(properties.__dict__)
        if kwargs:
            self.__dict__.update(kwargs)


    def __getattr__(self, key, default=None):
        """ Return the default for attributes we don't have """
        if key.startswith("DEBUG"):
            # Self-assembling DEBUGN functions
            def __DEBUG_ENABLED(outText, *args, **kwargs):
                print('#', outText.format(*args, **kwargs))

            def __DEBUG_DISABLED(*args, **kwargs):
                pass

            # Tried to call a .DEBUG<N> function which hasn't
            # been called before; create a stub.
            debugLevel = int(key[5:])
            if self.debug > debugLevel:
                debugFn = __DEBUG_ENABLED
            else:
                debugFn = __DEBUG_DISABLED
            setattr(self, key, debugFn)
            return debugFn

        if key == "NOTE":
            def __NOTE_ENABLED(outText, *args, file=None, **kwargs):
                print("NOTE:", outText.format(*args, **kwargs), file=file)

            def __NOTE_DISABLED(*args, **kwargs):
                pass

            # Tried to call "NOTE" but it hasn't been called yet,
            if not self.quiet:
                noteFn = __NOTE_ENABLED
            else:
                noteFn = __NOTE_DISABLED
            setattr(self, key, noteFn)
            return noteFn

        return default


