"""This module should handle filesystem related operations
"""
from shutil import copy as shcopy
from os import makedirs, PathLike
from pathlib import Path

__all__ = ['copy', 'copyallfiles', 'touch', 'ensurefolder', 'file_line_count']

def pathify(*args):
    if len(args) > 1 or not isinstance(args[0], Path):
        return Path(*args)
    return args[0]

def copy(src, dst):
    """
    copy src to dst
    takes string or Path object as input
    returns Path(dst) on success
    raises FileNotFoundError if src does not exist
    """
    srcPath = pathify(src).resolve()
    dstPath = pathify(dst)
    shcopy(str(srcPath), str(dstPath))
    return dstPath

def copy_if_newer(src, dst):
    """
    copy src to dst if src is newer
    takes string or Path object as input
    returns Path(dst) on success
    returns Path(src) if not newer
    raises FileNotFoundError if src does not exist
    """
    srcPath = pathify(src).resolve()
    dstPath = pathify(dst)
    if dstPath.exists() and dstPath.stat().st_mtime >= srcPath.stat().st_mtime:
        return srcPath
    
    shcopy(str(srcPath), str(dstPath))
    return dstPath

def copyallfiles(srcdir, dstdir):
    """
    Copies all files in srcdir to dstdir
    """
    srcPath = pathify(srcdir)
    dstPath = pathify(dstdir)
    
    for p in srcPath.glob('*.*'):
        if p.is_file():
            copy(p, dstPath / p.name)

def touch(filename):
    """
    Creates file if it doesn't exist.
    Always modifies utime.
    Returns a Path(filename)
    """
    path = pathify(filename)
    path.touch(exist_ok=True)
    return path

def ensureflag(flagfile, action=None):
    """Checks if flagfile exist and IF NOT the action function
    will be executed. The flagfile will be 'touched' at the end
    
    Parameters
    ----------
    flagfile : string
        path to the file used as flag
    action : callable
        this will be called if the flagfile doesn't exist
    
    Returns
    -------
    Path(flagfile)
    """
    flagPath = pathify(flagfile)
    if not flagPath.exists() and callable(action):
        action()
    return touch(flagPath)

def ensurefolder(folder):
    """Creates the folder if it doesn't exist
    
    Parameters
    ----------
    folder : string|pathlib.Path
        path to the folder
    
    Returns
    -------
    pathlib.Path
        Resolved path of the folder
    """
    folderPath = pathify(folder)
    try:
        makedirs(str(folderPath))
    except FileExistsError:
        pass
    return folderPath.resolve()


def file_line_count(from_file: PathLike, buf_size: int = 128 * 1024, *, missing_ok: bool = False) -> int:
    """ counts the number of newline characters in a given file. """
    if not isinstance(from_file, Path):
        from_file = Path(from_file)
    
    if missing_ok and not from_file.exists():
        return 0
    
    # Pre-allocate a buffer so that we aren't putting pressure on the garbage collector.
    buf = bytearray(buf_size)
    
    # Capture it's counting method, so we don't have to keep looking that up on
    # large files.
    counter = buf.count
    
    total = 0
    with from_file.open("rb") as fh:
        # Capture the 'readinto' method to avoid lookups.
        reader = fh.readinto
        
        # read into the buffer and capture the number of bytes fetched,
        # which will be 'size' until the last read from the file.
        read = reader(buf)
        while read == buf_size:  # nominal case for large files
            total += counter(b'\n')
            read = reader(buf)
        
        # when 0 <= read < buf_size we're on the last page of the
        # file, so we need to take a slice of the buffer, which creates
        # a new object, thus we also have to lookup count. it's trivial
        # but if you have to do it 10,000x it's definitely not a rounding error.
        return total + buf[:read].count(b'\n')


