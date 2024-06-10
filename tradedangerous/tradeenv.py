# The runtime environment TD tools are expected to run with is encapsulated
# into a single object, the TradeEnv. See TradeEnv docstring for more.
from __future__ import annotations

from pathlib import Path
import os
import sys
import traceback
import typing

# Import some utilities from the 'rich' library that provide ways to colorize and animate
# the console output, along with other useful features.
# If the user has 'EXCEPTIONS' defined to something in the environment, then we can
# immediately benefit from beautified stacktraces.
from rich.console import Console
from rich.traceback import install as install_rich_traces


if typing.TYPE_CHECKING:
    import argparse
    from typing import Any, Optional, Union


_ROOT = os.path.abspath(os.path.dirname(__file__))


# Create a single instance of the console for everyone to use, unless they really
# want to do something unusual.
CONSOLE = Console()
STDERR  = Console(stderr=True)

if os.getenv("EXCEPTIONS"):
    # This makes call stacks show additional context and do syntax highlighting
    # that can turn reading a callstack from hours into seconds.
    install_rich_traces(console=STDERR, show_locals=False, extra_lines=1)


class BaseColorTheme:
    """ A way to theme the console output colors. The default is none. """
    CLOSE:      str = ""        # code to stop the last color
    dim:        str = ""        # code to make text dim
    bold:       str = ""        # code to make text bold
    italic:     str = ""        # code to make text italic
    # blink:    NEVER = "don't you dare"
    
    # style, label
    debug, DEBUG    = dim,  "#"
    note,  NOTE     = bold, "NOTE"
    warn,  WARNING  = "",   "WARNING"
    
    seq_first:  str = ""        # the first item in a sequence
    seq_last:   str = ""        # the last item in a sequence
    
    # Included as examples of how you might use this to manipulate tradecal output.
    itm_units:  str = ""        # the amount of something
    itm_name:   str = ""        # name of that unit
    itm_price:  str = ""        # how much does it cost?
    
    def render(self, renderable: Any, style: str) -> str:  # pragma: no cover, pylint: disable=unused-argument
        """ Renders the given printable item with the given style; BaseColorTheme simply uses a string transformation. """
        if isinstance(renderable, str):
            return renderable  # avoid an allocation
        return str(renderable)


class BasicRichColorTheme(BaseColorTheme):
    """ Provide's 'rich' styling without our own colorization. """
    CLOSE     = "[/]"
    bold      = "[bold]"
    dim       = "[dim]"
    italic    = "[italic]"
    
    # style, label
    debug, DEBUG   = dim,  "#"
    note,  NOTE    = bold, "NOTE"
    warn,  WARNING = "[orange3]", "WARNING"
    
    def render(self, renderable: Any, style: str) -> str:  # pragma: no cover
        style_attr = getattr(self, style, "")
        if not style_attr:
            return renderable if isinstance(renderable, str) else str(renderable)
        return f"{style_attr}{renderable}{self.CLOSE}"


class RichColorTheme(BasicRichColorTheme):
    """ Demonstrates how you might augment the rich theme with colors to be used fin e.g tradecal. """
    DEBUG = ":spider_web:"
    NOTE  = ":information_source:"
    WARNING = ":warning:"
    
    # e.g. First station
    seq_first = "[cyan]"
    # e.g. Last station
    seq_last  = "[blue]"
    
    # Included as examples of how you might use this to manipulate tradecal output.
    itm_units = "[yellow3]"
    itm_name  = "[yellow]"
    itm_price = "[bold]"


class BaseConsoleIOMixin:
    """ Base mixin for running output through rich. """
    console: Console
    stderr:  Console
    theme:   BaseColorTheme
    quiet:   bool
    
    def uprint(self, *args, stderr: bool = False, style: str = None, **kwargs) -> None:
        """
            unicode-safe print via console or stderr, with 'rich' markup handling.
        """
        console = self.stderr if stderr else self.console
        console.print(*args, style=style, **kwargs)


class NonUtf8ConsoleIOMixin(BaseConsoleIOMixin):
    """ Mixing for running output through rich with UTF8-translation smoothing. """
    def uprint(self, *args, stderr: bool = False, style: str = None, **kwargs) -> None:
        """ unicode-handling print: when the stdout stream is not utf-8 supporting,
            we do a little extra io work to ensure users don't get confusing unicode
            errors. When the output stream *is* utf-8.
            
            :param stderr: report to stderr instead of stdout
            :param style: specify a 'rich' console style to use when the stream supports it
        """
        console = self.stderr if stderr else self.console
        try:
            # Attempt to print; the 'file' argument isn't supported by rich, so we'll
            # need to fall-back on old print when someone specifies it.
            console.print(*args, style=style, **kwargs)
        
        except UnicodeEncodeError as e:
            # Characters in the output couldn't be translated to unicode.
            if not self.quiet:
                self.stderr.print(
                    f"{self.theme.WARN}{self.theme.bold}CAUTION: Your terminal/console couldn't handle some "
                    "text I tried to print."
                )
                if 'EXCEPTIONS' in os.environ:
                    traceback.print_exc()
                else:
                    self.stderr.print(e)
            
            # Try to translate each ary into a viable string using utf error-replacement.
            components = [
                str(arg)
                .encode(TradeEnv.encoding, errors="replace")
                .decode(TradeEnv.encoding)
                for arg in args
            ]
            console.print(*components, style=style, **kwargs)


# If the console doesn't support UTF8, use the more-complicated implementation.
if str(sys.stdout.encoding).upper() != 'UTF-8':
    Utf8SafeConsoleIOMixin = NonUtf8ConsoleIOMixin
else:
    Utf8SafeConsoleIOMixin = BaseConsoleIOMixin


class TradeEnv(Utf8SafeConsoleIOMixin):
    """
        TradeDangerous provides a container for runtime configuration (cli flags, etc) and io operations to
        enable normalization of things without having to pass huge sets of arguments. This includes things
        like logging and reporting functionality.
        
        To print debug lines, use DEBUG<N>, e.g. DEBUG0, which takes a format() string and parameters, e.g.
            DEBUG1("hello, {world}{}", "!", world="world")
        
        is equivalent to:
            if tdenv.debug >= 1:
                print("#hello, {world}{}".format("!", world="world"))
        
        Use "NOTE" to print remarks which can be disabled with -q.
    """
    
    defaults = {
        'debug': 0,
        'detail': 0,
        'quiet': 0,
        'color': False,
        'theme': BaseColorTheme(),
        'dataDir': os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data'),
        'csvDir': os.environ.get('TD_CSV') or os.environ.get('TD_DATA') or os.path.join(os.getcwd(), 'data'),
        'tmpDir': os.environ.get('TD_TMP') or os.path.join(os.getcwd(), 'tmp'),
        'templateDir': os.path.join(_ROOT, 'templates'),
        'cwDir': os.getcwd(),
        'console': CONSOLE,
        'stderr':  STDERR,
    }
    
    encoding = sys.stdout.encoding
    
    def __init__(self, properties: Optional[Union[argparse.Namespace, dict]] = None, **kwargs) -> None:
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
        
        self.theme = RichColorTheme() if self.__dict__['color'] else BasicRichColorTheme()
    
    def __getattr__(self, key: str) -> Any:
        """ Return the default for attributes we don't have """
        
        # The first time the DEBUG attribute is referenced, register a method for it.
        if key.startswith("DEBUG"):
            
            # Self-assembling DEBUGN functions
            def __DEBUG_ENABLED(outText, *args, **kwargs):
                # Give debug output a less contrasted color.
                self.console.print(f"{self.theme.debug}{self.theme.DEBUG}{outText.format(*args, **kwargs)}")
            
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
                    f"{self.theme.note}{self.theme.NOTE}: {str(outText).format(*args, **kwargs)}",
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
                    f"{self.theme.warn}{self.theme.WARNING}: {str(outText).format(*args, **kwargs)}",
                    stderr=stderr,
                )
            
            def _WARN_DISABLED(*args, **kwargs):
                pass
            
            noteFn = _WARN_DISABLED if self.quiet > 1 else _WARN_ENABLED
            setattr(self, key, noteFn)
            return noteFn
        
        return None
    
    def remove_file(self, *args) -> bool:
        """ Unlinks a file, as long as it exists, and logs the action at level 1. """
        path = Path(*args)
        if not path.exists():
            return False
        path.unlink()
        self.DEBUG1(":cross_mark: deleted {}", path)
        return True
    
    def rename_file(self, *, old: os.PathLike, new: os.PathLike) -> bool:
        """
        If 'new' exists, deletes it, and then attempts to rename old -> new. If new is not specified,
        then '.old' is appended to the end of the old filename while retaining the original suffix.
        
        :param old:             The current path/name of the file.
        :param new:             The path/name to rename the file to and remove before attempting.
        :returns:               True if the file existed and was renamed.
        """
        # Promote new to a guaranteed Path and remove it if it's present.
        new = Path(new)
        self.remove_file(new)
        
        # Promote new to a guaranteed Path and confirm it exists.
        old = Path(old)
        if not old.exists():
            return False
        
        # Perform the rename and log it at level 1.
        old.rename(new)
        self.DEBUG1(":recycle: moved {} to {}", old, new)
        
        return True
