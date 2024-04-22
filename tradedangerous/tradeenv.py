# The runtime environment TD tools are expected to run with is encapsulated
# into a single object, the TradeEnv. See TradeEnv docstring for more.
from __future__ import annotations

import os
import sys
import traceback
import typing
from contextlib import contextmanager

# Import some utilities from the 'rich' library that provide ways to colorize and animate
# the console output, along with other useful features.
# If the user has 'EXCEPTIONS' defined to something in the environment, then we can
# immediately benefit from beautified stacktraces.
from rich.console import Console
from rich.traceback import install as install_rich_traces


if typing.TYPE_CHECKING:
    from typing import Any, Dict, Iterator


_ROOT = os.path.abspath(os.path.dirname(__file__))


# Create a single instance of the console for everyone to use, unless they really
# want to do something unusual.
CONSOLE = Console()
STDERR  = Console(stderr=True)

if os.getenv("EXCEPTIONS"):
    # This makes call stacks show additional context and do syntax highlighting
    # that can turn reading a callstack from hours into seconds.
    install_rich_traces(console=STDERR, show_locals=False, extra_lines=1)


class TradeEnv:
    """
        Container for a TradeDangerous "environment", which is a collection of operational parameters.
        
        To print debug lines, use DEBUG<N>, e.g. DEBUG0, which takes a format() string and parameters, e.g.
            
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
        'color': False,
        'dataDir': os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data'),
        'csvDir': os.environ.get('TD_CSV') or os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data'),
        'tmpDir': os.environ.get('TD_TMP') or os.path.join(os.getcwd(), 'tmp'),
        'templateDir': os.path.join(_ROOT, 'templates'),
        'cwDir': os.getcwd(),
        'console': CONSOLE,
        'stderr':  STDERR,
    }
    
    encoding = sys.stdout.encoding

    if str(sys.stdout.encoding).upper() != 'UTF-8':
        def uprint(self, *args, stderr: bool = False, style: str = None, **kwargs) -> None:
            """ unicode-handling print: when the stdout stream is not utf-8 supporting,
                we do a little extra io work to ensure users don't get confusing unicode
                errors. When the output stream *is* utf-8, tradeenv replaces this method
                with a less expensive method.
                :param stderr: report to stderr instead of stdout
                :param style: specify a 'rich' console style to use when the stream supports it
            """
            console = self.stderr if stderr else self.console
            try:
                # Attempt to print; the 'file' argument isn't spuported by rich, so we'll
                # need to fall-back on old print when someone specifies it.
                console.print(*args, style=style, **kwargs)

            except UnicodeEncodeError as e:
                # Characters in the output couldn't be translated to unicode.
                if not self.quiet:
                    self.stderr.print(
                        "[orange3][bold]CAUTION: Your terminal/console couldn't handle some "
                        "text I tried to print."
                    )
                    if 'EXCEPTIONS' in os.environ:
                        traceback.print_exc()
                    else:
                        self.stderr.print(e)

                # Try to translate each ary into a viable stirng using utf error-replacement.
                strs = [
                    str(arg)
                        .encode(TradeEnv.encoding, errors="replace")
                        .decode(TradeEnv.encoding)
                    for arg in args
                ]
                console.print(*strs, style=style, **kwargs)
    
    else:
        def uprint(self, *args, stderr: bool = False, style: str = None, **kwargs) -> None:
            """ unicode-handling print: when the stdout stream is not utf-8 supporting,
                this method is replaced with one that tries to provide users better support
                when a unicode error appears in the wild.

                :param file: [optional] stream to write to (disables styles/rich support)
                :param style: [optional] specify a rich style for the output text
            """
            console = self.stderr if stderr else self.console
            console.print(*args, style=style, **kwargs)
    

    def __init__(self, properties: Optional[Union[argparse.Namespace, Dict]] = None, **kwargs) -> None:
        # Inject the defaults into ourselves in a dict-like way
        self.__dict__.update(self.defaults)

        # If properties is a namespace, extract the dictionary; otherwise use it as-is
        if properties and hasattr(properties, '__dict__'):  # which arparse.Namespace has
            properties = properties.__dict__
        # Merge into our dictionary
        self.__dict__.update(properties or {})

        # Merge the kwargs dictionary
        self.__dict__.update(kwargs or {})

        # When debugging has been enabled on startup, enable slightly more
        # verbose rich backtraces.
        if self.__dict__['debug']:
            install_rich_traces(console=STDERR, show_locals=True, extra_lines=2)

    def __getattr__(self, key: str) -> Any:
        """ Return the default for attributes we don't have """

        # The first time the DEBUG attribute is referenced, register a method for it.
        if key.startswith("DEBUG"):
            
            # Self-assembling DEBUGN functions
            def __DEBUG_ENABLED(outText, *args, **kwargs):
                # Give debug output a less contrasted color.
                self.console.print(f"[dim]#{outText.format(*args, **kwargs)}[/dim]")
            
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
            
            def __NOTE_ENABLED(outText, *args, stderr: bool = False, **kwargs):
                self.uprint(
                    "NOTE:", str(outText).format(*args, **kwargs),
                    style="bold",
                    stderr=stderr,
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
            
            def _WARN_ENABLED(outText, *args, stderr: bool = False, **kwargs):
                self.uprint(
                    "WARNING:", str(outText).format(*args, **kwargs),
                    style="orange3",
                    stderr=stderr,
                )
            
            def _WARN_DISABLED(*args, **kwargs):
                pass
            
            noteFn = _WARN_DISABLED if self.quiet > 1 else _WARN_ENABLED
            setattr(self, key, noteFn)
            return noteFn
        
        return None
