from shutil import copy as shcopy
from os import makedirs, path, utime
from pathlib import Path

__all__ = ['copy', 'copyallfiles', 'touch', 'ensurefolder']

def pathify(*args):
    if len(args) > 1 or not isinstance(args[0], Path):
        return Path(*args)
    return args[0]


def copy(src, dst):
    """
    copy src to dst and takes string or Path object as input
    returns Path(dst) on success
    raises FileNotFoundError if src does not exist
    """
    srcPath = pathify(src).resolve()
    dstPath = pathify(dst)
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
    Creates file if it doesn't exist but always modifies utime.
    Returns a Path(filename)
    """
    path = pathify(filename)
    path.touch(exist_ok=True)
    return path


def ensureflag(flagfile, action=None):
    """
    Checks if flagfile exist and IF NOT the action function will be executed.
    The flagfile will be 'touched' at the end
    Returns Path(flagfile)
    """
    flagPath = pathify(flagfile)
    if not flagPath.exists() and callable(action):
        action()
    return touch(flagPath)


def ensurefolder(folder):
    folderPath = pathify(folder)
    try:
        makedirs(str(folderPath))
    except FileExistsError:
        pass
    return folderPath.resolve()



