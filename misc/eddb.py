#! /usr/bin/env python

"""
Preliminary, hacky script to retrieve Systems and Stations
from EDDB.

Original author: oliver@kfs.org
"""

from __future__ import absolute_import
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import json
import pathlib
import sys
import time
import transfers

class JsonQuery(object):
    """
    Crappy wrapper around a json query.
    """

    def __init__(
            self,
            url,
            outFile=None,
            timestamp=None,
            escapeTrans=None,
            ):
        """
            url
                The JSON resource to be retrieved,
            outfile [optional]
                Where to write translations
            timestamp [optional]
                Override the default "timestamp" value
            escapeTrans [optional]
                Override the default escape translation ("'" -> "''")

            If outfile is specified and is a string or a Path, it will
            be opened in write mode and presented in ".out". If it is
            not None, it is stored in ".out". If it is "None", then
            the value of sys.stdout is stored in ".out".
        """
        self.url = url
        self.escapeTrans = escapeTrans or str.maketrans({"'": "''"})
        self.timestamp = timestamp or time.strftime('%Y-%m-%d %H:%M:%S')

        if outFile is None:
            self.out = sys.stdout
        elif isinstance(outFile, str):
            self.out = open(outFile, "w")
        elif isinstance(outFile, pathlib.Path):
            self.out = outFile.open("w")
        else:
            self.out = outFile

    def fetch_data(self):
        """
        Downloads the data and yields each entry of the resulting
        array of dictionaries.

        Yields:
            dict(...)
        """
        self.jsonData = transfers.retrieve_json_data(self.url)
        for ent in self.jsonData:
            ent['name']  = ent['name'].translate(self.escapeTrans)
            yield ent


def fetch_systems(outFile=None):
    """ Load the Systems json data. Returns dict(id: name) """

    query = JsonQuery(
        url='http://eddb.io/archive/v2/systems.json',
        outFile=outFile,
    )
    mask = "'{}',{},{},{},'EDDB','"+query.timestamp+"'"

    print(
        "unq:name,"
        "pos_x,"
        "pos_y,"
        "pos_z,"
        "name@Added.added_id,"
        "modified",
        file=query.out
    )
    systems = {}
    for ent in query.fetch_data():
        # each sysent is a dictionary
        sysName = ent['name'].upper()
        x, y, z = ent['x'], ent['y'], ent['z']

        print(mask.format(sysName, x, y, z), file=query.out)

        systems[int(ent['id'])] = sysName

    if outFile:
        print('Generated "{}"'.format(outFile))

    return systems

def fetch_stations(systems, outFile=None):
    """ Fetch Stations json - requires a dict(id: name) of systems. """

    query = JsonQuery(
        'http://eddb.io/archive/v2/stations_lite.json',
        outFile=outFile,
    )
    mask = "'{}','{}','{}','{}','{}'"

    # EDDB black market is null (unknown), 0 (No) or 1 (Yes)
    marketConvert = {None:'?', 0:'N', 1:'Y'}

    # EDDB pad size is null (unknown), 10 (small), 20 (medium) or 30 (large)
    padConvert = {None:'?', 10:'S', 20:'M', 30:'L'}

    print(
        "unq:name@System.system_id,"
        "unq:name,"
        "ls_from_star,"
        "blackmarket,"
        "max_pad_size",
        file=query.out
    )
    for ent in query.fetch_data():
        # each sysent is a dictionary
        sysID = int(ent['system_id'])
        sysName = systems[sysID]
        stnName = ent['name']
        distToStar = ent['distance_to_star']
        blackMarket = ent['has_blackmarket']
        mlps = ent['max_landing_pad_size']

        lsFromStar = int(distToStar) if distToStar else 0
        blackMarket = marketConvert[blackMarket]
        pad = padConvert[mlps]

        print(mask.format(sysName, stnName, lsFromStar, blackMarket, pad), file=query.out)

    if outFile:
        print('Generated "{}"'.format(outFile))


def fetch_data(systemsFile=None, stationFile=None):
    """ Fetch systems and station data. """

    systems = fetch_systems(systemsFile or 'tmp/Systems.eddb.csv')
    fetch_stations(systems, stationFile or 'tmp/Stations.eddb.csv')


if __name__ == "__main__":
    fetch_data()
