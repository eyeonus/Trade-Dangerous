#! /usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# Elite Market Data Net :: Master Module

"""
	"Elite Market Data Net" (EMDN) is a ZeroMQ based service that
	provides a near-realtime feed of market scrapes from the Elite
	Dangerous universe. This feed is called the "firehose".

	emdn.ItemRecord class encapsulates a record as described by
	the EMDN network.

	emdn.Firehose class encapsulates a connection to retrieve
	ItemRecords in an iterative fashion.

	Example:

	  import emdn

	  firehose = emdn.Firehose()
	  # use firehose = emdn.Firehose(ctx=ctx) if you have your own zmq.Context

	  # wait upto 10 seconds and retrieve upto 2 records:
	  for itemRec in firehose.drink(records=2, timeout=10.0)
	  	pass

	  # print everything else we receive
	  for itemRec in firehose.drink():
	  	print(itemRec)
"""

__all__ = [ 'itemrecord', 'firehose' ]
