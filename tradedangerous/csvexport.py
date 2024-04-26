from pathlib import Path
from .tradeexcept import TradeException

import csv
import os
import sqlite3

######################################################################
# TradeDangerous :: Modules :: CSV Exporter
#
# Generate a CSV files for a table of the database.
#
# Note: This routine makes some assumptions about the structure
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

# for some tables the first two columns will be reversed
reverseList = []

######################################################################
# Helpers
######################################################################

def search_keyList(items, val):
    for row in items:
        if row['from'] == row['to'] == val:
            return row
    return None

def getUniqueIndex(conn, tableName):
    """ return all unique columns """
    idxCursor = conn.cursor()
    unqIndex = []
    for idxRow in idxCursor.execute("PRAGMA index_list('%s')" % tableName):
        if idxRow['unique']:
            # it's a unique index
            unqCursor = conn.cursor()
            for unqRow in unqCursor.execute("PRAGMA index_info('%s')" % idxRow['name']):
                unqIndex.append(unqRow['name'])
    return unqIndex

def getFKeyList(conn, tableName):
    """ get all single column FKs """
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
    """
        resolve the FK constrain with the UNIQUE index
        multicolumn UNIQUEs are allowed as long as the last one
        will be a single column one
    """
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
            keyStmt.append({
                'table': tableName,
                'column': colName,
                'joinTable': key['table'],
                'joinColumn': key['to']
            })
    
    return keyStmt

######################################################################
# Code
######################################################################

def exportTableToFile(tdb, tdenv, tableName, csvPath=None):
    """
        Generate the csv file for tableName in csvPath
        returns lineCount, exportPath
    """
    
    # path for csv file
    csvPath = csvPath or tdb.csvPath
    if not csvPath.is_dir():
        raise TradeException("Save location '{}' not found.".format(str(csvPath)))
    
    # connect to the database
    conn = tdb.getDB()
    conn.row_factory = sqlite3.Row
    
    # prefix for unique/ignore columns
    uniquePfx = "unq:"
    ignorePfx = "!"
    
    # create CSV files
    exportPath = (csvPath / Path(tableName)).with_suffix(".csv")
    tdenv.DEBUG0("Export Table '{table}' to '{file}'".format(
                    table=tableName, file=str(exportPath)
                    ))
    
    lineCount = 0
    with exportPath.open("w", encoding='utf-8', newline="\n") as exportFile:
        exportOut = csv.writer(exportFile, delimiter=",", quotechar="'", doublequote=True, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
        
        cur = conn.cursor()
        
        # check for single PRIMARY KEY
        pkCount = 0
        for columnRow in cur.execute("PRAGMA table_info('%s')" % tableName):
            # count the columns of the primary key
            if columnRow['pk'] > 0:
                pkCount += 1
        
        # build column list
        columnList = []
        for columnRow in cur.execute("PRAGMA table_info('%s')" % tableName):
            # if there is only one PK column, ignore it
            # if columnRow['pk'] > 0 and pkCount == 1: continue
            columnList.append(columnRow)
        
        if len(columnList) == 0:
            raise TradeException("No columns to export for table '{}'.".format(tableName))
        
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
        
        tdenv.DEBUG1('UNIQUE: ' + ", ".join(unqIndex))
        
        # iterate over all columns of the table
        for col in columnList:
            # check if the column is a foreign key
            key = search_keyList(keyList, col['name'])
            if key:
                # make the join statement
                keyStmt = buildFKeyStmt(conn, tableName, key)
                for keyRow in keyStmt:
                    tdenv.DEBUG1('FK-Stmt: {}'.format(list(keyRow)))
                    # is the join for the same table
                    if keyRow['table'] == tableName:
                        csvPfx = ''
                        joinStmt = 'USING({})'.format(keyRow['joinColumn'])
                    else:
                        # this column must be ignored by the importer, it's only
                        # used to resolve the FK relation
                        csvPfx = ignorePfx
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
        sqlStmt = "SELECT {} FROM {}".format(",".join(stmtColumn), " ".join(stmtTable))
        if len(stmtOrder) > 0:
            sqlStmt += " ORDER BY {}".format(",".join(stmtOrder))
        tdenv.DEBUG1("SQL: %s" % sqlStmt)
        
        # finally generate the csv file
        # write header line without quotes
        exportFile.write("{}\n".format(",".join(csvHead)))
        for line in cur.execute(sqlStmt):
            lineCount += 1
            tdenv.DEBUG2("{count}: {values}".format(count=lineCount, values=list(line)))
            exportOut.writerow(list(line))
        tdenv.DEBUG1("{count} {table}s exported".format(count=lineCount, table=tableName))
    
    # Update the DB file so we don't regenerate it.
    os.utime(str(tdb.dbPath))
    
    return lineCount, exportPath
