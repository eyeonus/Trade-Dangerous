#!/usr/bin/env python

import tradedb
tdb = tradedb.TradeDB()

names = set()

for sys in tdb.systemByID.values():
    for stn in sys.stations:
        names.add(stn.name().upper())

mutators = {
        'D': [ 'O', '0' ],
        'W': [ 'VV' ],
}

def mutate(text, pos):
    for i in range(pos, len(text)):
        char = text[i]
        if char not in mutators:
            continue
        yield from mutate(text, i+1)
        for mutant in mutators[char]:
            t2 = text[:i] + mutant + text[i+1:]
            yield from mutate(t2, i+1)
            yield t2

for name in names:
    for mutant in mutate(name, 0):
        if mutant in names:
            print("{} <-> {}".format(name, mutant))

