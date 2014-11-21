from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
from commands.parsing import MutuallyExclusiveGroup, ParseArgument
from commands.exceptions import CommandLineError
from pathlib import Path
import sqlite3
import csv

######################################################################
# TradeDangerous :: Commands :: Export
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

######################################################################
# Default values

defaultPath = Path("./data")

# for some tables the first two columns will be reversed
reverseList = [ 'AltItemNames',
                'Item',
                'ShipVendor',
                'Station',
                'StationBuying',
                'UpgradeVendor',
]

# some tables are ignored
ignoreList = [ 'StationLink',
]

######################################################################
# Parser config

help='CSV exporter for TradeDangerous database.'
name='export'
epilog=None
wantsTradeDB=False
arguments = [
]
switches = [
    ParseArgument('--path',
            help="Specify save location of the CSV files. Default: '{}'".format(defaultPath),
            type=str,
            default=defaultPath
        ),
    ParseArgument('--tables', "-T",
            help='Specify comma separated tablenames to export.',
            metavar='TABLE[,TABLE,...]',
            type=str,
            default=None
        ),
]

######################################################################
# Helpers

def search_dict(list, key, val):
    for row in list:
        if row[key] == val: return row

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    from tradedb import TradeDB

    # check database exists
    dbFilename = cmdenv.dbFilename or TradeDB.defaultDB
    if not Path(dbFilename).is_file():
        raise CommandLineError("Database '{}' not found.".format(dbFilename))

    # check export path exists
    if not Path(cmdenv.path).is_dir():
        raise CommandLineError("Save location '{}' not found.".format(cmdenv.path))

    # connect to the database
    if not cmdenv.quiet:
        print("Using database '{}'".format(dbFilename))
    conn = sqlite3.connect(dbFilename)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # extract tables from command line
    if cmdenv.tables:
        bindValues = cmdenv.tables.split(',')
        tableStmt = " AND name COLLATE NOCASE IN ({})".format(",".join("?" * len(bindValues)))
        cmdenv.DEBUG0(tableStmt)
    else:
        bindValues = []
        tableStmt = ''

    tableCursor = conn.cursor()
    for row in tableCursor.execute("""
                                      SELECT name
                                        FROM sqlite_master
                                       WHERE type = 'table'
                                         AND name NOT LIKE 'sqlite_%'
                                             {cmdTables}
                                       ORDER BY name
                                   """.format(cmdTables=tableStmt),
                                   bindValues):
        tableName = row['name']
        if tableName in ignoreList:
            # ignore the table
            if not cmdenv.quiet:
                print("Ignore Table '{table}'".format(table=tableName))
            continue

        # create CSV files
        exportName = Path(cmdenv.path).joinpath("{table}.csv".format(table=tableName))
        if not cmdenv.quiet:
            print("Export Table '{table}' to '{file}'".format(table=tableName, file=exportName))

        with exportName.open("w") as exportFile:
            exportOut = csv.writer(exportFile, delimiter=",", quotechar="'", doublequote=True, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")

            cur = conn.cursor()
            keyList = []
            for key in cur.execute("PRAGMA foreign_key_list('%s')" % tableName):
                # ignore FKs to table StationItem
                if key['table'] != 'StationItem':
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
                    if col['name'] == 'name':
                        # name columns must be unique
                        csvHead += [ 'unq:name' ]
                        stmtOrder += [ "{}.{}".format(tableName, col['name']) ]
                    else:
                        csvHead += [ col['name'] ]
                    stmtColumn += [ "{}.{}".format(tableName, col['name']) ]

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
            cmdenv.DEBUG0("SQL: %s" % sqlStmt)

            # finally generate the csv file
            lineCount = 0
            # no quotes for header line
            exportFile.write("{}\n".format(",".join(csvHead)))
            for line in cur.execute(sqlStmt):
                lineCount += 1
                exportOut.writerow(list(line))
            cmdenv.DEBUG1("{count} {table}s exported".format(count=lineCount, table=tableName))

    return None
