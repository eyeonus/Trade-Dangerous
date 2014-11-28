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
# Note: This command makes some assumptions about the structure
#       of the database:
#          * The table should only have one UNIQUE index
#          * The referenced table must have one UNIQUE index
#          * The FK columns must have the same name in both tables
#          * One column primary keys will be handled by the database engine
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

def search_keyList(list, val):
    for row in list:
        if row['from'] == row['to'] == val: return row

def getUniqueIndex(conn, tableName):
    # return the first unique index
    idxCursor = conn.cursor()
    unqIndex = []
    for idxRow in idxCursor.execute("PRAGMA index_list('%s')" % tableName):
        if idxRow['unique']:
            # it's a unique index
            unqCount = 0
            unqCursor = conn.cursor()
            for unqRow in unqCursor.execute("PRAGMA index_info('%s')" % idxRow['name']):
                # count columns and remember the last name
                unqCount += 1
                unqIndex.append(unqRow['name'])
            return unqIndex
    return unqIndex

def getFKeyList(conn, tableName):
    # get all single column FKs
    keyList = []
    keyCount = -1
    keyCursor = conn.cursor()
    for keyRow in keyCursor.execute("PRAGMA foreign_key_list('%s')" % tableName):
        if keyRow['seq'] == 0:
            keyCount += 1
            keyList.append( {'table': keyRow['table'],
                             'from': keyRow['from'],
                             'to': keyRow['to']}
                          )
        if keyRow['seq'] == 1:
            # if there is a second column, remove it from the list
            keyList.remove( keyList[keyCount] )
            keyCount -= 1

    return keyList

def buildFKeyStmt(conn, tableName, key):
    unqIndex = getUniqueIndex(conn, key['table'])
    keyList  = getFKeyList(conn, key['table'])
    keyStmt = []
    for colName in unqIndex:
        # check if the column is a foreign key
        keyKey = search_keyList(keyList, colName)
        if keyKey:
            newStmt = buildFKeyStmt(conn, key['table'], keyKey)
            for row in newStmt:
                keyStmt.append(row)
        else:
            keyStmt.append( {'table': tableName, 'column': colName, 'joinTable': key['table'], 'joinColumn': key['to']} )

    return keyStmt

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

    # prefix for unique columns
    uniquePfx = "unq:"

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

            # check for single PRIMARY KEY
            pkCount = 0
            for columnRow in cur.execute("PRAGMA table_info('%s')" % tableName):
                # count the columns of the primary key
                if columnRow['pk'] > 0: pkCount += 1

            # build column list
            columnList = []
            for columnRow in cur.execute("PRAGMA table_info('%s')" % tableName):
                # if there is only one PK column, ignore it
                if columnRow['pk'] > 0 and pkCount == 1: continue
                columnList.append(columnRow)

            # reverse the first two columns for some tables
            if tableName in reverseList:
                columnList[0], columnList[1] = columnList[1], columnList[0]

            # initialize helper lists
            csvHead    = []
            stmtColumn = []
            stmtTable  = [ tableName ]
            stmtOrder  = []
            unqIndex   = getUniqueIndex(conn, tableName)
            keyList    = getFKeyList(conn, tableName)

            cmdenv.DEBUG0('UNIQUE: ' + ", ".join(unqIndex))

            # iterate over all columns of the table
            for col in columnList:
                # check if the column is a foreign key
                key = search_keyList(keyList, col['name'])
                if key:
                    # make the join statement
                    keyStmt = buildFKeyStmt(conn, tableName, key)
                    for keyRow in keyStmt:
                        if cmdenv.debug > 0:
                            print('FK-Stmt: {}'.format(keyRow))
                        # is the join for the same table
                        if keyRow['table'] == tableName:
                            csvPfx = ''
                            joinStmt = 'USING({})'.format(keyRow['joinColumn'])
                        else:
                            csvPfx = '!'
                            joinStmt = 'ON {}.{} = {}.{}'.format(keyRow['table'], keyRow['joinColumn'], keyRow['joinTable'], keyRow['joinColumn'])
                        if col['name'] in unqIndex:
                            # column is part of an unique index
                            csvPfx = uniquePfx + csvPfx
                        csvHead += [ "{}{}@{}.{}".format(csvPfx, keyRow['column'], keyRow['joinTable'], keyRow['joinColumn']) ]
                        stmtColumn += [ "{}.{}".format(keyRow['joinTable'], keyRow['column']) ]
                        if col['notnull']:
                            stmtTable += [ 'INNER JOIN {} {}'.format(keyRow['joinTable'], joinStmt) ]
                        else:
                            stmtTable += [ 'LEFT OUTER JOIN {} {}'.format(keyRow['joinTable'], joinStmt) ]
                        stmtOrder += [ "{}.{}".format(keyRow['joinTable'], keyRow['column']) ]
                else:
                    # ordinary column
                    if col['name'] in unqIndex:
                        # column is part of an unique index
                        csvHead += [ uniquePfx + col['name'] ]
                        stmtOrder += [ "{}.{}".format(tableName, col['name']) ]
                    else:
                        csvHead += [ col['name'] ]
                    stmtColumn += [ "{}.{}".format(tableName, col['name']) ]

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
