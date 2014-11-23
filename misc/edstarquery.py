#! /usr/bin/env python3

from __future__ import absolute_import, with_statement, print_function, division, unicode_literals

from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

class EDStarQuery(object):
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
            self.params.filter[k] = v

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


if __name__ == "__main__":
    edsq = EDStarQuery(test=False, confidence=0)
    data = edsq.fetch()

    if edsq.status['statusnum'] != 0:
        raise Exception("Query failed: {} ({})".format(
                    edsq.status['msg'],
                    edsq.status['statusnum'],
                ))

    date = data['date']
    systems = data['systems']

    for sysinfo in systems:
        print(sysinfo['id'], sysinfo['name'], sysinfo['coord'])

