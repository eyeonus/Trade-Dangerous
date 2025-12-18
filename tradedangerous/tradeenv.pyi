# pylint: disable=multiple-statements-on-one-line
# flake8: noqa: E704
# 
# Because TradeEnv on-the-fly constructs the various logging methods
# etc, most IDEs and linters struggle with the types of many of its
# methods and built-in properties.
#
# This is a python header unit that forward declares stuff so that
# the IDEs are less of a wall of squiggles.

from pathlib import Path
from typing import Any
from rich.console import Console
import argparse


class BaseColorTheme:
    CLOSE: str
    dim: str
    bold: str
    italic: str
    debug: str
    DEBUG: str
    note: str
    NOTE: str
    info: str
    INFO: str
    warn: str
    WARN: str
    seq_first: str
    seq_last: str
    itm_units: str
    itm_name: str
    itm_price: str
    def render(self, renderable: Any, style: str) -> str: ...


class BasicRichColorTheme(BaseColorTheme):
    CLOSE: str
    bold: str
    dim: str
    italic: str
    debug: str
    DEBUG: str
    note: str
    NOTE: str
    info: str
    INFO: str
    warn: str
    WARN: str
    def render(self, renderable: Any, style: str) -> str: ...


class RichColorTheme(BasicRichColorTheme):
    DEBUG: str
    NOTE: str
    WARN: str
    INFO: str
    seq_first: str
    seq_last: str
    itm_units: str
    itm_name: str
    itm_price: str


class BaseConsoleIOMixin:
    console: Console
    stderr: Console
    theme: BaseColorTheme
    quiet: int
    def uprint(self, *args: Any, stderr: bool = False, style: str | None = None, **kwargs: Any) -> None: ...


class NonUtf8ConsoleIOMixin(BaseConsoleIOMixin):
    def uprint(self, *args: Any, stderr: bool = False, style: str | None = None, **kwargs: Any) -> None: ...


class TradeEnv(BaseConsoleIOMixin):
    debug: int
    detail: int
    color: bool
    theme: BaseColorTheme
    persist: bool
    dataDir: str
    csvDir: str
    tmpDir: str
    templateDir: str
    cwDir: str
    console: Console
    stderr: Console
    quiet: int
    
    encoding: str
    
    def __init__(self, properties: dict[str, Any] | argparse.Namespace | None = None, **kwargs: Any) -> None: ...
    
    # Dynamically-generated log methods with full type hints
    def DEBUG0(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def DEBUG1(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def DEBUG2(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def DEBUG3(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def DEBUG4(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def INFO(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def NOTE(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    def WARN(self, outText: str, *args: Any, stderr: bool = False, **kwargs: Any) -> None: ...
    
    # File operations
    def remove_file(self, *args: str | Path) -> bool: ...
    def rename_file(self, *, old: str | Path, new: str | Path) -> bool: ...
    
    def uprint(self, *args: Any, stderr: bool = False, style: str | None = None, **kwargs: Any) -> None: ...
