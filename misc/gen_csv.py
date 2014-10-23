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

import sqlite3
import csv

def search_dict(list, key, val):
    for row in list:
        if row[key] == val: return row

def main(debug=0):
    # load the database
    conn = sqlite3.connect("../data/TradeDangerous.db")
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
    for row in tCursor.execute("""
                                  SELECT name
                                    FROM sqlite_master
                                   WHERE type = 'table'
                                     AND name NOT LIKE 'sqlite_%'
                                   ORDER BY name
                               """):
        tableName = row['name']
        exportName = "{table}.csv".format(table=tableName)

        # create CSV files
        print("Export Table {table} to {file}".format(table=tableName, file=exportName))
        with open(exportName, "w") as exportFile:
            exportOut = csv.writer(exportFile, delimiter=",", quotechar="'", doublequote=True)

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
            if debug:
                print("SQL: %s" % sqlStmt)

            # finally generate the csv file
            lineCount = 0
            exportOut.writerow(csvHead)
            for line in cur.execute(sqlStmt):
                lineCount += 1
                exportOut.writerow(list(line))
            print("* {count} {table}s exported".format(count=lineCount, table=tableName))
            print()


if __name__ == "__main__":
    main()
