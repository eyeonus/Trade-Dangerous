#! /usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# Elite Market Data Net :: Command line entry point
#  Demonstrates how to use the firehose. Not intended for end-user use.

print("Running Elite-Market-Data.net (EMDN) module tests.")

try: from firehose import Firehose
except ImportError: from . firehose import Firehose

firehose = Firehose()
print("Firehose ready.")
print()

import time


def test(description, caveat, it):
	test.testNo += 1

	print('8x -->', 'BEGIN Test #{}:'.format(test.testNo), description, '<-- x8')
	print(caveat)
	print()

	totalRecords, lastSecond, recordsThisSecond = 0, 0, 0
	maxRecordsPerSecond = 3
	for rec in it:
		totalRecords += 1
		# throttle how many lines we show
		second = int(time.clock())
		if second != lastSecond:
			if recordsThisSecond > maxRecordsPerSecond:
			 print("... and {} more".format(recordsThisSecond - maxRecordsPerSecond))
			lastSecond, recordsThisSecond = second, 0
		recordsThisSecond += 1
		if recordsThisSecond > maxRecordsPerSecond: continue
		print(rec)

	if totalRecords == 0:
		print("NOTE: No data received.")
	elif recordsThisSecond > maxRecordsPerSecond:
		print("... and {} more".format(recordsThisSecond - maxRecordsPerSecond))

	print('8x <--', 'END Test #{}'.format(test.testNo), description, '--> x8')
	print()
	print()

test.testNo = 0

test("Drink one record only", "This will hang until there is some data.", firehose.drink(records=1))

test("Drink for 30 seconds", "If there's no data, this will do nothing for 30 seconds.", firehose.drink(timeout=30.0))

test("Drink for 60 seconds or 10 records", "If there's no data, this will do nothing for 60 seconds.", firehose.drink(timeout=60.0, records=10))

test("Drink for 90 seconds, 30,000 records, or until the first 'burst' has ended.", "Guess what happens if there's no data?", firehose.drink(timeout=90, records=30000, burst=True))

print("- Done")
