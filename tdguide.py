# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import argparse
import json
import mmap
from glob import iglob
from os import path, getcwd, remove, rename
from pprint import pprint
#from collections import defaultdict
from subprocess import call
#from tradedb import TradeDB
try:
    from PyInquirer import prompt
except ImportError:
    print('Could not find PyInquirer. Please install with "pip install pyinquirer"')
    raise

def loadConfig(file):
    data = {}
    try:
        with open(file) as f:
            data = json.load(f)
    except FileNotFoundError:
        pass
    data.setdefault('cmdr', 'Jameson')
    data.setdefault('credit', 100)
    data.setdefault('local', '')
    data.setdefault('ship', {})
    ship = data['ship']
    ship.setdefault('name', 'Unnamed')
    ship.setdefault('capacity', 10)
    ship.setdefault('empty_ly', 1)
    ship.setdefault('ly', 1)
    ship.setdefault('jumps', 6)

    data.setdefault('trade', {})
    trade = data['trade']
    trade.setdefault('age', 7)
    trade.setdefault('prune', {})
    prune = trade['prune']
    prune.setdefault('hops', 3)
    prune.setdefault('score', 20)

    data.setdefault('update', {})
    update = data['update']
    update.setdefault('args', '-wx=-40 -wy=40')

    data.setdefault('paths', {})
    paths = data['paths']
    paths.setdefault('fdevlogdir', '')
    paths.setdefault('tradedir', getcwd())

    return data

def saveConfig(file, config):
     with open(file, "w") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))

def existInFile(file, text):
    with open(file, 'rb', 0) as file, \
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
        if s.find(bytearray(text, 'utf-8')) != -1:
            return True
    return False

def cmd_config(args):
    config = loadConfig(args.file)
    print('cmdr', config['cmdr'])
    saveConfig(args.file, config)


def cmd_getstation(args):
    config = loadConfig(args.file)
    logdir = config['paths']['fdevlogdir']
    datadir = path.join(config['paths']['tradedir'], 'data')
    try:
        if not existInFile(path.join(logdir, '..', 'AppConfigLocal.xml'), 'VerboseLogging="1"'):
            print("WARNING: VerboseLogging is not enabled.")
    except FileNotFoundError:
        print("ERROR! Could not find AppConfig")
        exit(-1)

    lastLogName = sorted(iglob(path.join(logdir, 'netlog.*')), reverse=True)[0]
    print(' Log: .../{}'.format(path.basename(lastLogName)))
    with open(lastLogName, 'rb', 0) as f, \
        mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as s:
        pos = s.rfind(bytearray('FindBestIsland:', 'utf-8'))
    if pos == -1:
        print('ERROR! Could not find station in log')
        exit(-1)

def cmd_local(args):
    config = loadConfig(args.file)
    call(['python', 'trade.py', 'local', args.place, '--ly', str(args.ly)])

def cmd_run(args):
    config = loadConfig(args.file)
    call(['python', 'trade.py', 'run', '-vv', '--progress', \
        '--ly', str(config['ship']['ly']), \
        '--empty', str(config['ship']['empty_ly']), \
        '--cap', str(config['ship']['capacity']), \
        '--cr', str(config['credit']), \
        '--age', str(config['trade']['age']), \
        '--prune-score', str(config['trade']['prune']['score']), \
        '--prune-hops', str(config['trade']['prune']['hops']), \
        '--from', args.origin])
        # '--from', args.from \

def cmd_import(args):
    config = loadConfig(args.file)

    files = sorted(iglob(path.join(config['paths'][args.tool], '*.prices')))
    for file in files:
        call(['python', 'trade.py', 'import', '-vv', '--ignore-unknown', file])
        rename(file, '{}.imported'.format(file))


def main():
    parser = argparse.ArgumentParser(description='Hitchhikers Guide to Trade-Dangerous')
    parser.add_argument('--file', '-f', help="optional config file", default="tdguide.json")
    subparsers = parser.add_subparsers(title='commands', help='sub-command help')

    # config command
    parser_config = subparsers.add_parser('config', help="configure stuff")
    parser_config.set_defaults(func=cmd_config)

    parser_getstation = subparsers.add_parser('getstation', help='get station from netlog')
    parser_getstation.set_defaults(func=cmd_getstation)

    parser_local = subparsers.add_parser('local', help='get local with radious')
    parser_local.add_argument('place', help="station of origin")
    parser_local.add_argument('ly', type=float, help="search radius in LY")
    parser_local.set_defaults(func=cmd_local)

    parser_run = subparsers.add_parser('run', help='Calculate a trade run')
    parser_run.add_argument('origin', help="station where to start")
    parser_run.set_defaults(func=cmd_run)

    parser_run = subparsers.add_parser('import', help='Import prices')
    parser_run.add_argument('tool', choices=["edmarket",], help="From which tool to import")
    parser_run.set_defaults(func=cmd_import)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print('main fallback')

if __name__ == '__main__':
    main()