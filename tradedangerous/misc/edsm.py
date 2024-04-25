#! /usr/bin/env python

"""
based on edsc.py
uses EDSM - https://www.edsm.net/api
"""

import json
import requests


def edsm_log(apiCall, url, params, jsonData=None, error=None):
    """
    Logs an EDSM query and it's response to tmp/edsm.log
    """
    try:
        with open("tmp/edsm.log", "a", encoding="utf-8") as fh:
            print('-'*70, file=fh)
            print("API:", apiCall, file=fh)
            print("REQ:", str(params), file=fh)
            print("URL:", url, file=fh)
            if jsonData:
                print("REP:", json.dumps(jsonData, indent=1), file=fh)
            if error:
                print("ERR:", error)
            print(file=fh)
    except FileNotFoundError:
        pass


class EDSMQueryBase:
    """
    Base class for creating an EDSM Query class, do not use directly.
    
    Derived class must declare "apiCall" which is appended to baseURL
    to form the query URL.
    """
    
    baseURL = "https://www.edsm.net/api-v1/"
    
    def __init__(self, log=False, known=1, coords=1, **kwargs):
        self.log = log
        self.url = self.baseURL + self.apiCall
        self.params = {
            'known': known,
            'coords': coords,
        }
        for k, v in kwargs.items():
            self.params[k] = v
    
    def fetch(self):
        res = requests.get(self.url, self.params)
        self.status = res.status_code
        
        try:
            data = res.json()
        except:
            data = None
            pass
        
        if self.log:
            edsm_log(self.apiCall, res.url, self.params, data)
        
        return data


class StarQuerySingle(EDSMQueryBase):
    """
    Query EDSM System.
    
    provide:
        systemName
    """
    apiCall = "system"

class StarQueryMulti(EDSMQueryBase):
    """
    Query EDSM Systems.
    
    provide:
        systemName
    """
    apiCall = "systems"

class StarQuerySphere(EDSMQueryBase):
    """
    Query EDSM Systems.
    provide:
        systemName or center-coords as x, y and z
        radius N.NN
    """
    apiCall = "sphere-systems"

class DistanceQuery(EDSMQueryBase):
    """
    Request distances from EDSM.
    """
    apiCall = "distances"


if __name__ == "__main__":
    print("Requesting Azrael, coords-known")
    edsq = StarQuerySingle(log=True, systemName="Azrael")
    data = edsq.fetch()
    print("{:<30s} {:11f} {:11f} {:11f}".format(
        data['name'].upper(),
        data['coords']['x'],
        data['coords']['y'],
        data['coords']['z'],
    ))
    
    print("Requesting 10ly sphere of Sol, coords-known")
    edsq = StarQuerySphere(systemName="Sol", radius=10)
    data = edsq.fetch()
    for sysinfo in data:
        print("{:<30s} {:11f} {:11f} {:11f}".format(
            sysinfo['name'].upper(),
            sysinfo['coords']['x'],
            sysinfo['coords']['y'],
            sysinfo['coords']['z'],
        ))
