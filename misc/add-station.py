#! /usr/bin/env python

### EXPERIMENTAL TOOL FOR ADDING STATIONS.
#
# Usage:
#
#  add-station.py <system name> /


import re
import sqlite3
import sys
import time


class AddStationError(Exception):
    pass


def grepl(regex, filename):
    """
    Search a file for a regex, return -1 if not found,
    otherwise returns the line number of the first match.
    """

    lineNo = 0
    with open(filename, "rU") as fh:
        for line in fh:
            if regex.search(line):
                return lineNo
            lineNo += 1
    return -1


def lookupSystem(conn, sysName):
    cur = conn.cursor()
    cur.execute("""
            SELECT  system_id, name
              FROM  System
             WHERE  name LIKE ?
    """, [sysName])
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    return None, None


def lookupStation(conn, systemID, stnName):
    cur = conn.cursor()
    cur.execute("""
            SELECT  station_id
              FROM  Station
             WHERE  system_id = ?
               AND  name LIKE ?
    """, [systemID, stnName])
    row = cur.fetchone()
    return row[0] if row else None


def addStation(conn, sysName, stnName, distLs, blackMarket):
    """
    Adds a station to the csv and db if not already present.
    """

    assert isinstance(distLs, int)
    assert blackMarket in [ '?', 'Y', 'N' ]

    sysName = sysName.upper()
    stnName = stnName.title()
    stnName = re.sub(r"'S\b", "'s", stnName)

    # Check the database
    systemID, sysName = lookupSystem(conn, sysName)
    if not systemID:
        raise AddStationError(
                "Unrecognized system {}.".format(sysName)
        )

    stationID = lookupStation(conn, systemID, stnName)
    if stationID:
        raise AddStationError(
                "Station matching {}/{} found in db cache.".format(
                    sysName, stnName,
        ))

    sysCsvName = sysName.replace("'", "''")
    stnCsvName = stnName.replace("'", "''")

    # Does it already exist in the .csv file?
    grepRe = re.compile(r"'{}','{}',".format(
                sysCsvName, stnCsvName
            ), re.IGNORECASE
    )

    csvFile = "data/Station.csv"
    matchLine = grepl(grepRe, csvFile)
    if matchLine >= 0:
        raise AddStationError(
                "{}/{} found in {} at line {}".format(
                    sysCsvName, stnCsvName, csvFile, matchLine,
        ))

    # Add to the .csv first.
    with open(csvFile, "ab") as fh:
        fh.write("'{}','{}',{},'{}'\n".format(
                sysCsvName,
                stnCsvName,
                distLs,
                blackMarket,
        ).encode())

    # Now insert into the DB.
    cur = conn.cursor()
    cur.execute("""
            INSERT  INTO Station
                    (system_id, name, ls_from_star)
            VALUES  (?, ?, ?)
    """, [systemID, stnName, distLs])
    stationID = cur.lastrowid
    conn.commit()

    print("ADDED: #{}: {}/{} ls={}, bm={}".format(
            stationID,
            sysName, stnName,
            distLs, blackMarket
    ))


def usage():
    raise SystemExit(
            "Usage: "
            "{} System Name "
                "/ Station Name "
                "[/ ls:###] "
                "[/ bm:y | / bm:n]"
            "\n"
            "ls:###  (e.g. ls:0 or ls:1001)\n"
                "    Distance in light seconds from star to station.\n"
            "bm:y\n"
                "    Station has confirmed black market.\n"
            "bm:n\n"
                "    Station has confirmed absence of black market."
    )

def main():
    conn = sqlite3.connect("data/TradeDangerous.db")

    dist = 0
    blackMarket = '?'

    if len(sys.argv) <= 1 or \
            sys.argv[1] in ('--help', '-h', '-?', '/?', '/help'):
        usage()

    # Join args together into a string, then break them
    # apart on /s and remove padding
    argStr = ' '.join(sys.argv[1:]).replace('::', '/')
    values = [ s.strip() for s in argStr.split('/') ]

    if len(values) < 2:
        print("ERROR: Unrecognized syntax!\n")
        usage()

    for i in range(2, len(values)):
        val = values[i].lower()
        if val.startswith('ls:'):
            dist = val[3:]
            try:
                dist = int(dist)
            except ValueError:
                raise AddStationError(
                        "Expecting integer value after 'ls:', got %s" % dist
                )
        elif val.startswith('bm:'):
            if val == 'bm:y':
                blackMarket = 'Y'
            elif val == 'bm:n':
                blackMarket = 'N'
            elif val == 'bm:?':
                blackMarket = '?'
            else:
                raise AddStationError(
                        "Unrecognized blackmarket switch: %s" % val
                )
        else:
            raise AddStationError(
                    "Unrecognized station option: {}".format(val)
            )

    addStation(conn, values[0], values[1], dist, blackMarket)


if __name__ == "__main__":
    try:
        main()
    except AddStationError as e:
        raise SystemExit("ERROR: {}".format(str(e)))

