Installation
============

With some knowledge about python you should be able to follow the guide here.
Otherwise have a look at the
[Setup Guide](https://github.com/eyeonus/Trade-Dangerous/wiki/Setup-Guide "Setup Guide") 
and the [User Guide](https://github.com/eyeonus/Trade-Dangerous/wiki/User-Guide "User Guide").

With a working installation of Python >= 3.4.2. 
```bash
# Install
pip3 install tradedangerous

# run the trade command
trade --help
```

This can be done in a virtual environment (venv) if you don't want to mess
with your global python environment.

```bash
# create the virtual environment
python3 -m venv myvenv

# activate it
source myvenv/bin/activate

# install td
pip3 install tradedangerous
```

## Python 3.6 on Mac
If you get issues with invalid SSL certificates browse
to `Applications/Python 3.6` and double-click `Install Certificates.command`

This is shown when you ran the installer for python but is easily overlooked.


# Usage
This section only contains some very basic stuff.
If you need a more detailed guide please look at 
the wiki [User Guide](https://github.com/eyeonus/Trade-Dangerous/wiki/User-Guide "User Guide")

```bash
# get some general help
trade --help

# get help about buy
trade buy --help
```

## Update data
Before you can do anything useful with TradeDangerous, you'll need price data. 
By default any downloaded and/or generated data will be stored in a subfolder
of your current working directory called `data`. 
This can be overridden by setting a environment variable called `TD_DATA` to
the path were you want your information stored.
Make sure you have access to that folder as well.

__Linux__
```bash
export TD_DATA="/var/lib/td-data"
```

__Windows__
```powershell
$env:TD_DATA='C:\td-data'
```

Our recommended way of obtaining this is to use the included EDDBlink plugin
The eddblink plugin has options to pull all available data into your local database.

It is recommended to include the 'skipvend' option (, as for example, '-O clean,skipvend',) on slower computers when doing any run, including the first run.

```bash
trade import --plug=eddblink --opt=clean,skipvend
```

It is recommended to pass no options after the first run, as by default eddblink imports just the listings, (updating the item, system, and station lists if needed,) and to use '-O all' whenever changes to the game have been made (such as the addition of new ships, or the removal of commodities.)

```bash
trade import --plug=eddblink 
```
This will only download files if they are newer than your current versions. This is a merge so any local systems/stations you have added will not be lost; if you have filled in a value that is still blank/unknown in the eddb data, your value will be kept. However, if there is a conflict, for example if eddb says "Abraham Lincoln" is 150 ls-from-star and your db says it is 120, your local value will be overwritten.
