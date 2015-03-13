#! /usr/bin/env python

"""
Provides a simple API for streaming data from EDDB in essentially raw format.

Example:
    import misc.eddb
    for sysdata in misc.eddb.SystemsQuery():
        print(sysdata)

Original author: oliver@kfs.org
"""

import json
import sys
import transfers

BASE_URL = "http://eddb.io/archive/v2/"
COMMODITIES_JSON = BASE_URL + "commodities.json"
SYSTEMS_JSON = BASE_URL + "systems.json"
STATIONS_EXT_JSON = BASE_URL + "stations.json"
STATIONS_LITE_JSON = BASE_URL + "stations_lite.json"


class EDDBQuery(object):
    """
    Base class for querying an EDDB data set and converting the
    JSON results into an iterable stream.

    Example:
        for entity in EDDBQuery():
            print(entity)
    """

    url = None      # Define in derived classes

    def __init__(self):
        assert self.url
        self.jsonData = transfers.get_json_data(self.url)

    def __iter__(self):
        return iter(self.jsonData)

class CommoditiesQuery(EDDBQuery):
    """
    Streams Commodities data from EDDB.

    Example:
        for comm in CommoditiesQuery():
            print(comm['name'])
    """
    url = COMMODITIES_JSON

class SystemsQuery(EDDBQuery):
    """
    Streams System data from EDDB.

    Example:
        for system in SystemsQuery():
            print(system['name'])
    """
    url = SYSTEMS_JSON

class StationsQuery(EDDBQuery):
    """
    Streams Station data from EDDB without trade data.

    Example:
        for station in StationsQuery():
            print(station['name'])
    """
    url = STATIONS_LITE_JSON

    # EDDB black market is null (unknown), 0 (No) or 1 (Yes)
    marketConversion = {None:'?', 0:'N', 1:'Y'}

    # EDDB pad size is null (unknown), 10 (small), 20 (medium) or 30 (large)
    padConversion = {None:'?', 10:'S', 20:'M', 30:'L'}

class StationsExtQuery(StationsQuery):
    """
    Streams extended Station data from EDDB with trade data.

    Example:
        for station in StationsExtQuery():
            print(station['name'])
    """
    url = STATIONS_EXT_JSON

