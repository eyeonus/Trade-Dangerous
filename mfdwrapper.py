#!/usr/bin/env python
#---------------------------------------------------------------------
# Copyright (C) Oliver 'kfsone' Smith 2014 <oliver@kfs.org>:
#  You are free to use, redistribute, or even print and eat a copy of
#  this software so long as you include this copyright notice.
#  I guarantee there is at least one bug neither of us knew about.
#---------------------------------------------------------------------
# TradeDangerous :: Modules :: Multi-function display wrapper
#
#   Multi-Function Display wrappers
#   

class DummyMFD(object):
    """
        Base class for the MFD drivers, implemented as no-ops so that
        you can always use all MFD functions without conditionals.
    """

    def __init__(self):
        pass


    def finish(self):
        """
            Close down the driver.
        """
        pass


    def display(self, line1, line2="", line3="", delay=None):
        """
            Display data to the MFD.
            Arguments: 1-3 lines of text plus optional pause in seconds.
        """
        pass


class X52ProMFD(DummyMFD):
    """
        Wrapper for the Saitek X52 Pro MFD.
    """

    def __init__(self):
        try:
            import saitek.X52Pro
            self.doObj = saitek.X52Pro.SaitekX52Pro()
        except DLLError as e:
            print("{}: error#{}: Unable to initialize the Saitek X52 Pro module: {}".format(__name__, e.error_code, e.msg), file=sys.stderr)
            sys.exit(1)

        self.page = self.doObj.add_page('TD')
        self.display('TradeDangerous', 'INITIALIZING')


    def finish(self):
        self.doObj.finish()


    def display(self, line1, line2="", line3="", delay=None):
        self.page[0], self.page[1], self.page[2] = line1, line2, line3
        if delay:
        	import time
        	time.sleep(delay)
