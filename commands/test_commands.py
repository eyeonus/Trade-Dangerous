#! /usr/bin/env python
# Noses test file

import commands
import sys
from nose.tools import raises
from commands.exceptions import *

prog = "trade.py"

class TestFixture(object):
	def setUp(self):
		self.c = commands.CommandIndex()

	def tearDown(self):
		del self.c

	@raises(UsageError)
	def test_dashh(self):
		self.c.parse([prog, '-h'])

	@raises(UsageError)
	def test_local_dashh(self):
		self.c.parse([prog, 'local', '-h'])

	@raises(CommandLineError)
	def test_invalid_cmd(self):
		self.c.parse([prog, 'fnarg'])

	@raises(CommandLineError)
	def test_local_no_args(self):
		self.c.parse([prog, 'local'])

	@raises(CommandLineError)
	def test_local_dashv(self):
		self.c.parse([prog, 'local', '-v'])

	def test_local_validsys(self):
		self.c.parse([prog, 'local', 'ibootis'])

	def test_local_validsys_dashv(self):
		self.c.parse([prog, 'local', 'ibootis', '-v'])
