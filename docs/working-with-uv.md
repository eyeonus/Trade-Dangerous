# Introduction

`uv` is an extremely fast Python package and project manager.

# Table of Contents

- [UV](#uv)
- [RunBook](#runbook)
- - [Installation](#installation)
- - [Creating the virtual environment](#creating-the-virtual-environment)
- - [Using the virtual environment](#using-the-virtual-environment)
- - - [Using uv run](#using-uv-run)
- - - [Activate venv in Powershell](#activate-venv-in-powershell)
- - - [Activate venv in CMD](#activate-venv-in-cmd)
- - - [Activate venv in zsh](#activate-venv-in-zsh)
- - - [Activate venv in other shells](#activate-venv-in-other-shells)
- - [Dependencies](#dependencies)
- - - [Installing developer-only dependencies](#installing-developer-only-dependencies)
- - - [Installing publish-only dependencies](#installing-publish-only-dependencies)
- - [Configuration](#configuration)
- - - [Confing File pyproject.toml](#config-file-pyprojecttoml)
- - - [Adding/changing dependencies](#addingchanging-dependencies)
- - - [Lock File uv.lock](#lock-file-uvlock)
- - - [Changing Supported Python Versions](#changing-supported-python-versions)
- - - [Specifying local Python version](#specifying-local-python-version)
- - [Build distribution](#build-distribution)


---

# uv

`uv` is an extremely fast Python package and project manager.

https://github.com/astral-sh/uv

A single tool to replace pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv, etc.

Key advantage: It's not written in python so it can bootstrap python environments from scratch,
even if Python isn't installed.

Since `pyproject.toml` is part of the Python spec itself now, configuring it to work with `uv`
should also work with other standard-supporting tool chains. (See section on pyproject.toml below)

_[Table Of Contents](#table-of-contents)_

---

# RunBook

## Installation

See their website: https://github.com/astral-sh/uv

But most commonly:

- windows: `winget install uv`
- windows: `choco install uv`
- macos:   `brew install uv`
- macos:   `sudo port install uv`
- ubuntu:  `apt install uv`  (* recent ubuntu only)
- linux:   `snap install --classic uv`
- alpine:  `apk update && apk add uv`

Can also be installed with Python pip-based tools:
- for yourself: `pip install --user uv`
- or your environment: `pip install uv`

Or you can use tools like pipx to run it:
- pipx run uv ...

_[Table Of Contents](#table-of-contents)_

---

## Creating the virtual environment

```
$ uv sync
```

This will ensure that the `.venv` directory has the appropriate Python based on
`.python-version` file and `pyproject.toml`'s `project.requires-python` setting.

If will update/create a file called `uv.lock` with a complete "dependency solution"
for all supported platforms/python version.

And then it will ensure the `.venv` is upto date with the dependencies.

_[Table Of Contents](#table-of-contents)_

---

## Using the virtual environment

You can either run the appropriate 'activate' script from ./.venv, or you can
use the `uv` command as a wrapper.

If you use the "activate" approach, you may need to re-run `uv sync` after
getting latest. When you use the `uv` prefix approach, it will automatically
update dependencies as needed.


### Using `uv run`

You can use `uv run` to run scripts in the current directory:
```
uv run trade.py
```

or you can use `uv run` or `uv tool` to install tools that were installed by
dependencies or globally by uv.

```
uv run tox -e flake8
```
or
```
uv tool run tox -e flake8
```

*`uv tool` will fallback to global tools, `uv run` will only use the current environment.*


### Activate venv in Powershell

Using Windows Powershell or Powershell core on Windows, MacOS, Linux, Rapsbian, or BSD:
```pwsh
PS> . ./.venv/scripts/activate.ps1
```

### Activate venv in CMD
```bat
C:\Wibble> call ./.venv/scripts/activate.bat
```

### Activate venv in zsh
```zsh
$ source ./.venv/bin/activate.zsh
```

### Activate venv in other shells
```sh
# One of
$ source ./.venv/bin/activate.bash
$ source ./.venv/bin/activate.sh
$ source ./.venv/bin/activate.fish
```

Others TBD - probably `. ./.venv/bin/activate.{something}`

_[Table Of Contents](#table-of-contents)_

---

## Dependencies

### Installing developer-only dependencies

```sh
uv sync --dev
```

### Installing publish-only dependencies
```sh
uv sync --group publish
```

_[Table Of Contents](#table-of-contents)_

---

## Configuration

### Config File: `PyProject.toml`

This is a standard python config file that replaces things like setup.py, setup.cfg, etc, etc.

See https://packaging.python.org/en/latest/guides/writing-pyproject-toml/


### Adding/changing dependencies

`uv` uses the standard Python pyproject.toml dependencies specification,
https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements

TLDR: It's like requirements.txt but it's in a toml list and you can't do the "-r" trick

```
[project]
dependencies = [
  "beer",
  "sleep>=6.0.0",
]
```

- the default/core dependencies are defined in `pyproject.toml` under `project.dependencies`,
- additional groups can be specified under `[dependency-groups]`,
- the name `dev` is reserved for developer-only tools and has it's own `--dev` flag,
- optional dependencies can be assigned group names under `[project.optional-dependencies]',


### Lock File: `uv.lock`

Instead of having to read, evaluate, and solve the dependency problem every incovation,
`uv` aims to provide a stable, reproducible environment with a file called `uv.lock`.

This contains the dependency solution for all platform+version combinations constrained
by `pyproject.toml`, so it can reasonably be checked in to the repository.

To just refresh/update that file, run the command
```
uv lock
```

### Changing supported Python versions

1- Change `pyproject.toml`'s `python-requires` field,
2- Run `uv lock`
3- Run `uv sync`


### Specifying local Python version

1- Change the `.python-version` file,
2- Run `uv sync`


## Build Distribution

This is still formally done through `setup.py` etc, but `uv` includes support for various
package building ecosystems - including `setup.py`, so you can do:

```sh
uv build
```

I've not done anything about the appJar build.

_[Table Of Contents](#table-of-contents)_

---
