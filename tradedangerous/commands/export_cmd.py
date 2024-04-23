from ..csvexport import exportTableToFile
from .parsing import ParseArgument, MutuallyExclusiveGroup
from .exceptions import CommandLineError
from pathlib import Path

import sqlite3

######################################################################
# TradeDangerous :: Commands :: Export
#
# Generate the CSV files for the master data of the database.
#
######################################################################
# CAUTION: If the database structure gets changed this script might
#          need some corrections.
######################################################################

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
            help="Specify a different save location of the CSV files than the default.",
            type=str,
            default=None
        ),
    MutuallyExclusiveGroup(
        ParseArgument('--tables', "-T",
                help='Specify comma separated tablenames to export.',
                metavar='TABLE[,TABLE,...]',
                type=str,
                default=None
            ),
        ParseArgument('--all-tables',
                help='Include the price tables for export.',
                dest='allTables',
                action='store_true',
                default=False
            ),
        ),
    ParseArgument('--delete-empty',
            help='Delete CSV files without content.',
            dest='deleteEmpty',
            action='store_true',
            default=False
        ),
]

######################################################################
# Perform query and populate result set

def run(results, cmdenv, tdb):
    # check database exists
    if not tdb.dbPath.is_file():
        raise CommandLineError("Database '{}' not found.".format(tdb.dbPath))
    
    # check export path exists
    if cmdenv.path:
        # the "--path" overwrites the default path of TD
        exportPath = Path(cmdenv.path)
    else:
        exportPath = Path(cmdenv.dataDir)
    if not exportPath.is_dir():
        raise CommandLineError("Save location '{}' not found.".format(str(exportPath)))
    
    # connect to the database
    cmdenv.NOTE("Using database '{}'", tdb.dbPath)
    conn = tdb.getDB()
    conn.row_factory = sqlite3.Row
    
    # some tables might be ignored
    ignoreList = []
    
    # extract tables from command line
    if cmdenv.tables:
        bindValues = cmdenv.tables.split(',')
        tableStmt = " AND name COLLATE NOCASE IN ({})".format(",".join("?" * len(bindValues)))
        cmdenv.DEBUG0(tableStmt)
    else:
        bindValues = []
        tableStmt = ''
        if not cmdenv.allTables:
            ignoreList.append("StationItem")
    
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
            cmdenv.NOTE("Ignore Table '{table}'", table=tableName)
            continue
        
        cmdenv.NOTE("Export Table '{table}'", table=tableName)
        
        # create CSV files
        lineCount, filePath = exportTableToFile(tdb, cmdenv, tableName, exportPath)
        if cmdenv.deleteEmpty and lineCount == 0:
            # delete file if emtpy
            filePath.unlink()
            cmdenv.DEBUG0("Delete empty file {file}'".format(file=filePath))
    
    return None
