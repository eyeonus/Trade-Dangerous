#! /usr/bin/env python3

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json

try:
    import requests
except ImportError as e:
    import pip
    print("ERROR: Unable to load the Python 'requests' package.")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        raise e
    pip.main(["install", "--upgrade", "requests"])
    import requests


class StarQuery(object):
    url = 'http://edstarcoordinator.com/api.asmx/GetSystems'

    def __init__(self, detail=2, test=False, known=1, confidence=0, **kwargs):
        self.params = {
            'data': {
                'ver': 2,
                'test': test,
                'outputmode': detail,
                'filter':  {
                    'knownstatus': known,
                    'cr': confidence,
                }
            }
        }
        for k, v in kwargs.items():
            self.params['data']['filter'][k] = v

        self.jsData = None


    def fetch(self):
        params = json.dumps(self.params).encode('utf-8')
        request = Request(EDStarQuery.url, params, {
                    'Content-Type': 'application/json;charset=utf-8',
                    'Content-Length': len(params)
                })

        with urlopen(request, params) as stream:
            self.jsData = stream.read()

        data = json.loads(self.jsData.decode())['d']
        inputNo = 0
        self.status = data['status']['input'][inputNo]['status']

        return data


class SubmissionError(Exception):
    pass


class StarSubmission(object):
    url = "http://edstarcoordinator.com/api.asmx/SubmitDistances"

    def __init__(
            self, star,
            test=False, commander=None,
            refs=None, distances=None,
            ):
        assert isinstance(star, str)
        assert isinstance(test, bool)
        if refs:
            assert isinstance(refs, list)
        self.test = test
        self.name = star.upper()
        self.refs = refs or []
        if distances:
            if isinstance(distances, list):
                for name, dist in distances:
                    self.add_distance(name, dist)
            elif isinstance(distances, dict):
                for name, dist in distances.items():
                    self.add_distance(name, dist)
            else:
                raise SubmissionError("Invalid distances parameter")
        if commander:
            self.commander = commander


    def add_distance(self, name, dist):
        assert isinstance(name, str)
        assert isinstance(dist, (float, int))
        assert name.upper() != self.name

        name = name.upper()
        for i, ref in enumerate(self.refs):
            if ref['name'] == name:
                ref['dist'] = dist
                return

        self.refs.append({'name': name, 'dist': dist})


    def submit(self):
        assert len(self.refs) != 0

        headers = { 'Content-Type': 'application/json; charset=utf-8' }
        data = {
            'data': {
                'test': self.test,
                'ver': 2,
                'p0': { 'name': self.name },
                'refs': self.refs
            },
        }
        if self.commander:
            data['commander'] = self.commander

        jsonData = json.dumps(data, indent=None, separators=(',', ':'))

        req = requests.post(
            self.url,
            headers=headers,
            data=jsonData
        )
        print("done")

        resp = req.text
        if not resp.startswith('{'):
            raise SubmissionError("Server Side Error: " + resp)

        try:
            respData = json.loads(resp)
            return respData['d']
        except Exception:
            raise SubmissionError("Invalid server response: " + resp)


if __name__ == "__main__":
    edsq = StarQuery(test=False, confidence=0)
    data = edsq.fetch()

    if edsq.status['statusnum'] != 0:
        raise Exception("Query failed: {} ({})".format(
                    edsq.status['msg'],
                    edsq.status['statusnum'],
                ))

    date = data['date']
    systems = data['systems']

    for sysinfo in systems:
        print(sysinfo['id'], sysinfo['name'], sysinfo['coord'], sysinfo['createdate'])

