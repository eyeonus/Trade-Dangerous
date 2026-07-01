#!/usr/bin/env python

import tradedb
tdb = tradedb.TradeDB()

names = set()

for sys in tdb.systemByID.values():
    for stn in sys.stations:
        names.add(stn.name().upper())

mutators = {
        'D': [ 'O', '0', ],
        'W': [ 'VV', ],
        'R': [ 'IT' ],
        'L': [ 'II' ],
        '&': [ '6' ],
}

def mutate(text, pos):
    for i in range(pos, len(text)):
        char = text[i]
        if char not in mutators:
            continue
        bef, aft = text[:i], text[i+1:]
        for mutant in mutators[char]:
            t2 = bef + mutant + aft
            yield t2
            yield from mutate(str(t2), i+len(mutant))


for name in names:
    for mutant in mutate(name, 0):
        if mutant in names:
            print("{} <-> {}".format(name, mutant))
