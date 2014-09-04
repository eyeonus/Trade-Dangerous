#! /usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# Elite Market Data Net :: Modules :: Main Module

try: from firehose import Firehose
except ImportError: from . firehose import Firehose

def capture(filename=None, records=None, firehose=None, uri=None, ctx=None):
    """
        Capture from a firehose to a file.

        Named Arguments:
            filename -- Name of the file to write to. Default: emdn.csv
            records  -- Maximum number of records. Default: unlimited.
            firehose -- Use a pre-existing firehose.
            uri      -- Override default URI if creating our own firehose.
            ctx      -- Use a pre-existing zmq Context if creating or own firehose.

        Returns:
            Number of records retrieved
    """

    filename = filename or "emdn.csv"

    recordCount = 0
    with open(filename, 'w') as csvFile:
        firehose = firehose or Firehose(uri=uri, ctx=ctx)
        while not records or recordCount < records:
            line = firehose.read()
            csvFile.write(line)
            csvFile.write("\n")
            recordCount += 1

    return recordCount
