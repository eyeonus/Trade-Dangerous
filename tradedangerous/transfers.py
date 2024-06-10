from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, unquote

from .tradeexcept import TradeException
from .misc import progress as pbar
from . import fs

import json
import time
import typing

import requests


if typing.TYPE_CHECKING:
    import os  # for PathLike
    from .tradeenv import TradeEnv
    from typing import Callable, Optional, Union  # noqa


######################################################################
# Helpers

class HTTP404(TradeException):
    pass

def makeUnit(value):
    """
    Convert a value in bytes into a Kb, Mb, Gb etc.
    """
    
    units = [ 'B ', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB' ]
    unitSize = int(value)
    for unit in units:
        if unitSize <= 640:
            return "{:>5.01f}{}".format(unitSize, unit)
        unitSize /= 1024
    return None


def get_filename_from_url(url: str) -> str:
    """ extracts just the filename from a url. """
    return Path(unquote(urlparse(url).path)).name


def download(
            tdenv:      TradeEnv,
            url:        str,
            localFile:  os.PathLike,
            headers:    Optional[dict] = None,
            backup:     bool = False,
            shebang:    Optional[Callable] = None,
            chunkSize:  int = 4096,
            timeout:    int = 30,
            *,
            length:     Optional[Union[int, str]] = None,
            session:    Optional[requests.Session] = None,
        ):
    """
    Fetch data from a URL and save the output
    to a local file. Returns the response headers.
    
    :param tdenv:       TradeEnv we're working under
    :param url:         URL we're fetching (http, https or ftp)
    :param localFile:   Name of the local file to open.
    :param headers:     dict() of additional HTTP headers to send
    :param shebang:     function to call on the first line
    """
    tdenv.NOTE("Requesting {}".format(url))
    
    if isinstance(length, str):
        length = int(length)
    
    # If the caller provided an existing session stream, use that the fetch the request.
    req = (session or requests).get(url, headers=headers or None, stream=True, timeout=timeout)
    req.raise_for_status()
    
    encoding = req.headers.get('content-encoding', 'uncompress')
    content_length = req.headers.get('content-length', length)
    transfer = req.headers.get('transfer-encoding', None)
    if not length and transfer != 'chunked':
        # chunked transfer-encoding doesn't need a content-length
        if content_length is None:
            print(req.headers)
            raise TradeException("Remote server replied with invalid content-length.")
        content_length = int(content_length)
        if content_length <= 0:
            raise TradeException(
                "Remote server gave an empty response. Please try again later."
            )
    
    # if the file is being compressed by the server, the headers tell us the
    # length of the compressed data, but in our loop below we will be receiving
    # the uncompressed data, which should be larger, which will cause our
    # download indicators to sit at 100% for a really long time if the file is
    # heavily compressed and large (e.g spansh 1.5gb compressed vs 9GB uncompressed)
    if length is None and encoding == "gzip" and content_length:
        length = content_length * 3
    
    if tdenv.detail > 1:
        if length:
            tdenv.NOTE("Downloading {} {}ed data", makeUnit(length), encoding)
        else:
            tdenv.NOTE("Downloading {} {}ed data", transfer, encoding)
    tdenv.DEBUG0(str(req.headers).replace("{", "{{").replace("}", "}}"))
    
    actPath = Path(localFile)
    fs.ensurefolder(tdenv.tmpDir)
    tmpPath = Path(tdenv.tmpDir, "{}.dl".format(actPath.name))
    
    fetched = 0
    started = time.time()
    filename = get_filename_from_url(url)
    with pbar.Progress(max_value=length, width=25, prefix=filename, style=pbar.CountingBar, show=not tdenv.quiet) as prog, tmpPath.open("wb") as fh:
        for data in req.iter_content(chunk_size=chunkSize):
            fh.write(data)
            fetched += len(data)
            if shebang:
                bangLine = data.decode().partition("\n")[0]
                tdenv.DEBUG0("Checking shebang of {}", bangLine)
                shebang(bangLine)
                shebang = None
            if prog:
                prog.increment(len(data))
        tdenv.DEBUG0("End of data")
    
    if not tdenv.quiet:
        elapsed = (time.time() - started) or 1
        tdenv.NOTE(
            "Downloaded {} of {}ed data {}/s",
            makeUnit(fetched), encoding,
            makeUnit(fetched / elapsed)
        )
    
    fs.ensurefolder(actPath.parent)
    
    # Swap the file into place
    if backup:
        bakPath = Path(localFile + ".bak")
        if bakPath.exists():
            bakPath.unlink()
        if actPath.exists():
            actPath.rename(localFile + ".bak")
    if actPath.exists():
        actPath.unlink()
    tmpPath.rename(actPath)
    
    req.close()
    return req.headers

def get_json_data(url, *, timeout: int = 90):
    """
    Fetch JSON data from a URL and return the resulting dictionary.
    
    Displays a progress bar as it downloads.
    """
    
    req = requests.get(url, stream=True, timeout=timeout)
    
    totalLength = req.headers.get('content-length')
    if totalLength is None:
        compression = req.headers.get('content-encoding')
        compression = (compression + "'ed") if compression else "uncompressed"
        print("Downloading {}: {}...".format(compression, url))
        jsData = req.content
    else:
        totalLength = int(totalLength)
        filename = get_filename_from_url(url)
        progBar = pbar.Progress(totalLength, 25, prefix=filename)
        
        jsData = bytes()
        for data in req.iter_content():
            jsData += data
            progBar.increment(len(data))
        progBar.clear()
    
    return json.loads(jsData.decode())
