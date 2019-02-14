from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

import os
import traceback
import sys
_ROOT = os.path.abspath(os.path.dirname(__file__))

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
        'dataDir': os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data'),
        'tmpDir': os.environ.get('TD_TMP') or os.path.join(os.getcwd(), 'tmp'),
        'templateDir': os.path.join(_ROOT, 'templates'),
        'cwDir': os.getcwd()
    }
    
    encoding = sys.stdout.encoding
    if str(sys.stdout.encoding).upper() != 'UTF-8':
        def uprint(self, *args, **kwargs):
            try:
                print(*args, **kwargs)
            except UnicodeEncodeError as e:
                if not self.quiet:
                    print(
                        "CAUTION: Your terminal/console couldn't handle some "
                        "text I tried to print."
                    )
                    if 'EXCEPTIONS' in os.environ:
                        traceback.print_exc()
                    else:
                        print(str(e))
                strs = [
                    str(arg).
                        encode(TradeEnv.encoding, errors='replace').
                        decode(TradeEnv.encoding)
                    for arg in args
                ]
                print(*strs, **kwargs)
    else:
        uprint = print
    
    def __init__(self, properties=None, **kwargs):
        properties = properties or dict()
        self.__dict__.update(self.defaults)
        if properties:
            self.__dict__.update(properties.__dict__)
        if kwargs:
            self.__dict__.update(kwargs)
    
    def __getattr__(self, key):
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
                self.uprint(
                    "NOTE:", str(outText).format(*args, **kwargs),
                    file=file,
                )
            
            def __NOTE_DISABLED(*args, **kwargs):
                pass
            
            # Tried to call "NOTE" but it hasn't been called yet,
            if not self.quiet:
                noteFn = __NOTE_ENABLED
            else:
                noteFn = __NOTE_DISABLED
            setattr(self, key, noteFn)
            return noteFn
        
        if key == "WARN":
            def _WARN_ENABLED(outText, *args, file=None, **kwargs):
                self.uprint(
                    "WARNING:", str(outText).format(*args, **kwargs),
                    file=file
                )
            
            def _WARN_DISABLED(*args, **kwargs):
                pass
            
            noteFn = _WARN_DISABLED if self.quiet > 1 else _WARN_ENABLED
            setattr(self, key, noteFn)
            return noteFn
        
        return None