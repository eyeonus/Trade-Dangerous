#! /usr/bin/env python
# Small tool for comparing two system.csv files.
# Usage:
#  misc/compare-system-csvs.py <old file> <new file>
# Checks for stars that changed names, stars that moved
# and conflicts where two stars occupy the same space.

# Writes output suitable for "corrections.py" to stderr,
# so you could do something like:
#  $ diff-system-csvs.py oldSystem.csv newSystem.csv 2>corrections.txt

import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: {} <old file> <new file>".format(
                sys.argv[0]
            ))

import csv
import re
from pathlib import Path
from collections import namedtuple

class Loc(namedtuple('Loc', [ 'x', 'y', 'z' ])):
    def __str__(self):
        return "{},{},{}".format(self.x, self.y, self.z)


class Item(namedtuple('Item', [ 'norm', 'name', 'loc' ])):
    pass


normalizeRe = re.compile('[^A-Za-z0-9\' ]')


def readFile(filename):
    path = Path(filename)
    if not path.exists():
        raise SystemExit("File not found: {}".format(filename))
    
    names, locs = dict(), dict()
    
    with path.open("r", encoding="utf-8") as fh:
        csvin = csv.reader(fh, delimiter=',', quotechar='\'', doublequote=True)
        # skip headings
        next(csvin)
        
        for line in csvin:
            name = line[0]
            x = float(line[1])
            y = float(line[2])
            z = float(line[3])
            
            normalized = normalizeRe.sub('', name).upper()
            try:
                prevEntry = names[normalized]
            except KeyError:
                pass
            else:
                print("Name clash: {}, this entry: {}, prev entry: {}".format(
                            normalized,
                            name,
                            prevEntry.name
                        ))
            item = Item(normalized, name, Loc(x, y, z))
            names[normalized] = item
            if item.loc in locs:
                print("{}: Duplicate location: {} and {} at {}".format(
                            filename, locs[item.loc].name, name, item.loc
                        ))
            else:
                locs[item.loc] = item
    
    return names, locs


oldNames, oldLocs = readFile(sys.argv[1])
newNames, newLocs = readFile(sys.argv[2])

for oldName, oldItem in oldNames.items():
    try:
        # Look the item up in the new names dict
        newItem = newNames[oldItem.norm]
    except:
        pass
    else:
        if oldItem.name != newItem.name:
            if oldItem.name.upper() == oldItem.name.upper():
                # Case changed, we can live with this.
                print("CAUTION: {} changed to {}".format(
                            oldItem.name,
                            newItem.name,
                        ))
            else:
                # Punctuation or something else, we need
                # a correction.
                print("{} became {}".format(
                            oldItem.name, newItem.name
                        ))
                print("  \"{}\": \"{}\",".format(
                            oldItem.name.upper(),
                            newItem.name,
                        ), file=sys.stderr)
        
        # Name didn't change, did the position?
        if oldItem.loc != newItem.loc:
            print("{} moved from {} -> {}".format(
                        oldItem.name, oldItem.loc, newItem.loc
                    ))
        
        # We don't need to do a location check on this one.
        try:
            del newLocs[newItem.loc]
        except KeyError:
            pass
        continue
    
    # We didn't find the old name in the new list, check
    # to see if there is a new star at the old position.
    try:
        newItem = newLocs[oldItem.loc]
    except:
        pass
    else:
        # we found something at the exact loc, which I
        # assume means the name changed.
        try:
            # we know it's there, we can remove it
            del newLocs[oldItem.loc]
        except KeyError:
            pass
        print("{} ({}) changed name to {}".format(
                    oldItem.name,
                    oldItem.loc,
                    newItem.name
                ))
        print("  \"{}\": \"{}\",".format(
                    oldItem.name.upper(),
                    newItem.name,
                ), file=sys.stderr)
        continue
    
    # we didn't find it, so as best we can tell it
    # has been removed. there's no easy way for us
    # to catch the case of a move and a minor reloc.
    print("{} ({}) was removed".format(
                oldItem.name,
                oldItem.loc
            ))
    print("  \"{}\": DELETED,".format(
                oldItem.name.upper(),
            ), file=sys.stderr)


for newLoc, newItem in newLocs.items():
    if newLoc in oldLocs:
        continue
    print("{} ({}) was added".format(newItem.name, newLoc))

