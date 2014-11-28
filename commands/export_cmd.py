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
epilog=(
        "CAUTION: If you don't specify a different path, the current "
        "CSV files in the data directory will be overwritten with "
        "the current content of the database.\n "
        "If you have changed any CSV file and didn't rebuild the "
        "database, they will be lost.\n "
        "Use the 'buildcache' command first to rebuild the database."
)
wantsTradeDB=False           # because we don't want the DB to be rebuild
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
    ParseArgument('--delete-empty',
            help='Delete CSV files without content.',
            dest='deleteEmpty',
            action='store_true',
            default=False
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

        lineCount = 0
        with exportName.open("w", encoding='utf-8', newline="\n") as exportFile:
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
                    if col['notnull']:
                        stmtTable += [ 'INNER JOIN {} USING({})'.format(key['table'], key['column']) ]
                    else:
                        stmtTable += [ 'LEFT OUTER JOIN {} USING({})'.format(key['table'], key['column']) ]
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
            sqlStmt = "SELECT {} FROM {}".format(",".join(stmtColumn)," ".join(stmtTable))
            if len(stmtOrder) > 0:
                sqlStmt += " ORDER BY {}".format(",".join(stmtOrder))
            cmdenv.DEBUG0("SQL: %s" % sqlStmt)

            # finally generate the csv file
            # write header line without quotes
            exportFile.write("{}\n".format(",".join(csvHead)))
            for line in cur.execute(sqlStmt):
                lineCount += 1
                cmdenv.DEBUG2("{count}: {values}".format(count=lineCount, values=list(line)))
                exportOut.writerow(list(line))
            cmdenv.DEBUG1("{count} {table}s exported".format(count=lineCount, table=tableName))
        if cmdenv.deleteEmpty and lineCount == 0:
            # delete file if emtpy
            exportName.unlink()
            if not cmdenv.quiet:
                print("Delete empty file {file}'".format(file=exportName))

    return None
