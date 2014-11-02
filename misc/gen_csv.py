#!/usr/bin/env python
######################################################################
# Copyright (C) Bernd Gollesch 2014 <bgollesch@speed.at>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
######################################################################
# CAUTION: NOT INTENDED FOR GENERAL END-USER OPERATION.
# If you don't know what this script is for, you can safely ignore it.
######################################################################
# TradeDangerous :: Misc :: CSV Exporter
#
# Generate the CSV files for the master data of the database.
#
# Note: This script makes some assumptions about the structure
# of the database:
#   * The column name of an foreign key reference must be the same
#   * The referenced table must have a column named "name"
#     which is UNIQUE
#   * One column primary keys will be handled by the database engine
#
######################################################################
# CAUTION: If the database structure gets changed this script might
#          need some corrections.
######################################################################

import argparse
import sqlite3
import csv
import sys
import errno
from pathlib import Path

def search_dict(list, key, val):
    for row in list:
        if row[key] == val: return row

######################################################################
# Main

def exportTables(dbFilename, exportPath, exportTable=None, quiet=True, debug=0):
    # load the database
    if not quiet: print("Using database '{}'".format(dbFilename))
    conn = sqlite3.connect(str(dbFilename))
    conn.row_factory = sqlite3.Row

    # for some tables the first two columns will be reversed
    reverseList = [ 'AltItemNames',
                    'Item',
                    'Price',
                    'ShipVendor',
                    'Station',
                    'UpgradeVendor'
                  ]

    # iterate over all tables
    tCursor = conn.cursor()
    tableStmt = "NOT LIKE 'sqlite_%'" if not exportTable else "= '{}'".format(exportTable)
    for row in tCursor.execute("""
                                  SELECT name
                                    FROM sqlite_master
                                   WHERE type = 'table'
                                     AND name {} COLLATE NOCASE
                                   ORDER BY name
                               """.format(tableStmt)):
        tableName = row['name']
        exportName = Path(exportPath).joinpath("{table}.csv".format(table=tableName))

        # create CSV files
        if not quiet: print("Export Table '{table}' to '{file}'".format(table=tableName, file=exportName))
        with exportName.open("w") as exportFile:
            exportOut = csv.writer(exportFile, delimiter=",", quotechar="'", doublequote=True, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")

            cur = conn.cursor()
            keyList = []
            for key in cur.execute("PRAGMA foreign_key_list('%s')" % tableName):
                # only support FK joins with the same column name
                if key['from'] == key['to']:
                    keyList += [ {'table': key['table'], 'column': key['from']} ]

            pkCount = 0
            for col in cur.execute("PRAGMA table_info('%s')" % tableName):
                # count the columns of the primary key
                if col['pk'] > 0: pkCount += 1

            # initialize helper lists
            csvHead    = []
            stmtColumn = []
            stmtTable  = [ tableName ]
            stmtWhere  = []
            stmtOrder  = []

            # iterate over all columns of the table
            for col in cur.execute("PRAGMA table_info('%s')" % tableName):
                # if there is only one PK column, ignore it
                if col['pk'] > 0 and pkCount == 1: continue

                # check if the column is a foreign key
                key = search_dict(keyList, 'column', col['name'])
                if key:
                    # there must be a "name" column in the referenced table
                    csvHead += [ "name@{}.{}".format(key['table'], key['column']) ]
                    stmtColumn += [ "{}.name".format(key['table']) ]
                    stmtWhere += [ "{}.{} = {}.{}".format(tableName, col['name'], key['table'], key['column']) ]
                    stmtTable += [ key['table'] ]
                    stmtOrder += [ "{}.name".format(key['table']) ]
                else:
                    # ordinary column
                    csvHead += [ col['name'] ]
                    stmtColumn += [ "{}.{}".format(tableName, col['name']) ]
                    if col['name'] == 'name':
                        stmtOrder += [ "{}.{}".format(tableName, col['name']) ]

            # reverse the first two columns for some tables
            if tableName in reverseList:
                csvHead[0], csvHead[1] = csvHead[1], csvHead[0]
                stmtColumn[0], stmtColumn[1] = stmtColumn[1], stmtColumn[0]
                if len(stmtOrder) > 1:
                    stmtOrder[0], stmtOrder[1] = stmtOrder[1], stmtOrder[0]

            # build the SQL statement
            sqlStmt = "SELECT {} FROM {}".format(",".join(stmtColumn),",".join(stmtTable))
            if len(stmtWhere) > 0:
                sqlStmt += " WHERE {}".format(" AND ".join(stmtWhere))
            if len(stmtOrder) > 0:
                sqlStmt += " ORDER BY {}".format(",".join(stmtOrder))
            if debug == 1:
                print("* SQL: %s" % sqlStmt)

            # finally generate the csv file
            lineCount = 0
            # no quotes for header line
            exportFile.write("{}\n".format(",".join(csvHead)))
            for line in cur.execute(sqlStmt):
                lineCount += 1
                exportOut.writerow(list(line))
            if debug == 1:
                print("* {count} {table}s exported".format(count=lineCount, table=tableName))


if __name__ == "__main__":
    # some defaults
    defaultDB   = Path("../data/TradeDangerous.db")
    defaultPath = Path(".")

    # command line arguments
    parser = argparse.ArgumentParser(description='CSV exporter for TradeDangerous database.')
    parser.add_argument('--db', help="Specify location of the SQLite database. Default: '{}'".format(defaultDB), type=str, default=defaultDB)
    parser.add_argument('--path', help="Specify save location of the CSV files. Default: '{}'".format(defaultPath), type=str, default=defaultPath)
    parser.add_argument('--table', help='Specify a single tablename to export.', type=str, default=None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--debug', '-w', help='Enable debug output.', default=0, action='count')
    group.add_argument('--quiet', '-q', help='No output.', default=False, action='store_true')
    args = parser.parse_args()

    # some checks
    if not Path(args.db).is_file():
        print("error: database '{}' not found.".format(args.db))
        sys.exit(errno.ENOENT)
    if not Path(args.path).is_dir():
        print("error: save location '{}' not found.".format(args.path))
        sys.exit(errno.ENOENT)

    exportTables(dbFilename=args.db, exportPath=args.path, exportTable=args.table, quiet=args.quiet, debug=args.debug)
