Simple Python module for accessing the Elite Market Data Network firehose.

Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
 You are free to use, redistribute, or even print and eat a copy of
 this software so long as you include this copyright notice.
 I guarantee there is at least one bug neither of us knew about.

Initially written as part of the TradeDangerous trade calculator.

For problems/issues/suggestions, see https://bitbucket.org/kfsone/tradedangerous/


Example usage:


#! /usr/bin/env python

from emdn.firehose import Firehose

# Create a firehose connection to read from.
firehose = Firehose()

# Read a dozen records with no time limit.
for record in firehose.drink(records=12):
	print("Record: {}/{} at {}/{}. Station wants {}cr, pays {}cr.".format(record.category, record.item, record.station, record.system, record.askingCr, record.payingCr))

# Or in a comprehension:
dozen = [ record for record in firehose.drink(records=12) ]

# Get all the data that arrives in the next 30 seconds.
for record in firehose.drink(timeout=30.00):
	pass

# Get the first burst of data that arrives within 30 seconds,
# but return as soon as we've read all the data that arrived
for record in firehose.drink(timeout=30.00, burst=True):
	pass

# Try and read 100 records but don't wait more than 10 seconds to do it.
for record in firehose.drink(records=100, timeout=10):
	pass

