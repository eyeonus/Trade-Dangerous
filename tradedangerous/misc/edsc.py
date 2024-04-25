#! /usr/bin/env python3

from collections import namedtuple
from urllib.request import Request, urlopen

import json
import requests


def edsc_log(apiCall, params, jsonData=None, error=None):
    """
    Logs an EDSC query and it's response to tmp/edsc.log
    """
    try:
        with open("tmp/edsc.log", "a", encoding="utf-8") as fh:
            print('-'*70, file=fh)
            print("API:", apiCall, file=fh)
            print("REQ:", str(params), file=fh)
            if jsonData:
                print("REP:", json.dumps(jsonData, indent=1), file=fh)
            if error:
                print("ERR:", error)
            print(file=fh)
    except FileNotFoundError:
        pass


class EDSCQueryBase:
    """
    Base class for creating an EDSC Query class, do not use directly.
    
    Derived class must declare "apiCall" which is appended to baseURL
    to form the query URL.
    """
    
    baseURL = "http://edstarcoordinator.com/api.asmx/"
    
    def __init__(self, detail=2, test=False, known=1, confidence=0, **kwargs):
        self.url = self.baseURL + self.apiCall
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
        request = Request(self.url, params, {
                    'Content-Type': 'application/json;charset=utf-8',
                    'Content-Length': len(params)
                })
        
        with urlopen(request, params) as stream:
            self.jsData = stream.read()
        
        data = json.loads(self.jsData.decode())['d']
        inputNo = 0
        self.status = data['status']['input'][inputNo]['status']
        
        edsc_log(self.apiCall, self.params, data)
        
        return data


class StarQuery(EDSCQueryBase):
    """
    Query EDSC Systems.
    """
    apiCall = "GetSystems"


class DistanceQuery(EDSCQueryBase):
    """
    Request distances from EDSC.
    """
    apiCall = "GetDistances"


class SubmissionError(Exception):
    pass


class Status(namedtuple('Status', [
        'source', 'code', 'msg', 'lhs', 'rhs'
        ])):
    pass

class StarSubmissionResult:
    """
    Translates a response the json we get back from EDSC when
    we submit a StarSubmission into something less awful to
    work with.
    
    Attributes:
        valid
            True or False whether the response looked healthy
        
        summary
            A summary of the /parse/; currently either "No Data"
            or "OK". This does NOT represent whether the
            submission itself was successful.
        
        systems
            A dict{ system name: [msgnum, coords] } for systems which
            were reported as being added or updated. See
            translateCode for converting these to text.
            'coords' is either None if the system hasn't been
            trilaterated yet, or an array of [x,y,z]
        
        distances
            A dict{ lhs system: { rhs system: dist } }. It's not
            really very useful but I didn't want to drop the data
            EDSC was sending back to us, just incase.
        
        errors
            A list of SubmissionError objects describing problems
            that were encountered, mostly 304 (distance added but
            failed to verify coordinates) and 305 (distance appears
            to be wrong).
        
        recheck
            A dict{ system name: dist } for systems that had a 305
            error for a distance to "star". They still appear in
            the 'errors' attribute, but this is a short-cut for
            prompting the user to double check a distance from their
            current p0.
    
    """
    
    codeMap = {
        201:        "New Entry",
        202:        "System CR increased",
        203:        "Coordinates calculated",
        301:        "Distance added",
        302:        "Distance CR increased",
        303:        "Added verification",
        304:        "OK: Needs more data",
        305:        "Distance appears to be wrong",
        401:        "CALCULATED",
        402:        "No solution found, more data needed"
    }


    def __init__(self, star, response):
        self.star = star
        self.valid = False
        self.summary = "No Data"
        self.systems = {}
        self.distances = {}
        self.errors = []
        self.recheck = {}
        
        # This line righ there, this is just the beginning of
        # why it's necessary to have this complicated of a
        # wrapper for this json data. Don't forget, we have
        # already peeled off some layers of json around this.
        summary = response['status']['input'][0]['status']
        code, msg = int(summary['statusnum']), summary['msg']
        if code != 0:
            self.valid = False
            self.summary = "Error #{}: {}".format(code, msg)
            self.errors.append(Status(
                    'status', code, msg, None, None
            ))
            return
        
        self.valid = True
        self.summary = "OK"
        
        # We get back an array of things called 'system', which
        # allows EDSC to tell us that something got added. It
        # could be p0 or it could be one of the refs or it could
        # be something that was sitting in EDSCs distances buffer.
        sysArray = response['status']['system']
        for ent in sysArray:
            sysName = ent['system'].upper()
            code = int(ent['status']['statusnum'])
            msg = ent['status']['msg']
            if code in [201, 202, 203]:
                self.systems[sysName] = (code, None)
            else:
                self.errors.append(Status(
                        'system', code, msg, sysName, None,
                ))
        
        # Now the pair-wise distance checks. These are either not
        # very useful/duplicate the systems list, or they tell us
        # about conflicts with pre-existing data.
        # Pairs which generate 305 (distance wrong) that relate
        # to P0 will be added to "recheck" so that the caller can
        # ask their user to provide sanity values.
        distArray = response['status']['dist']
        errPairs = set()
        for ent in distArray:
            lhsName = ent['system1'].upper()
            rhsName = ent['system2'].upper()
            code = int(ent['status']['statusnum'])
            msg = ent['status']['msg']
            if code in [301, 302, 303, 304]:
                if lhsName not in self.distances:
                    self.distances[lhsName] = {}
                try:
                    rhsDists = self.distances[rhsName]
                    if lhsName in rhsDists:
                        continue
                except KeyError:
                    pass
                dist = float(ent['dist'])
                self.distances[lhsName][rhsName] = dist
                if lhsName not in self.systems:
                    self.systems[lhsName] = (code, None)
            else:
                if (lhsName,rhsName,code) in errPairs:
                    continue
                if (rhsName,lhsName,code) in errPairs:
                    continue
                errPairs.add((lhsName,rhsName,code))
                errPairs.add((rhsName,lhsName,code))
                self.errors.append(Status(
                        'dist', code, msg, lhsName, rhsName,
                ))
                if code == 305:
                    if lhsName == star:
                        self.recheck[rhsName] = ent['dist']
                    elif rhsName == star:
                        self.recheck[lhsName] = ent['dist']
        
        # Finally we look thru the trilat array which is telling us
        # how the search for p0's coordinates went on a per-ref
        # basis.
        #
        # Successful trilateration will result in an array of
        # trilats that contain code 401 and the coordinates of
        # p0, one per ref. Since we can't tell what the *other*
        # system is, this is a bit stupid. Probably a bug in edsc.
        triArray = response['status']['trilat']
        for ent in triArray:
            sysName = ent['system'].upper()
            code = int(ent['status']['statusnum'])
            if code == 401:
                try:
                    system = self.systems[sysName]
                    if system[1] is not None:
                        continue
                except KeyError:
                    system = (code, None)
                assert system[1] is None
                coord = ent['coord']
                x, y, z = coord['x'], coord['y'], coord['z']
                self.systems[sysName] = (system[0], [x,y,z])
            elif code == 402:
                pass
            else:
                self.errors.append(Status(
                        'trilat', code, msg, sysName, None,
                ))


    def __str__(self):
        if not self.valid:
            return "ERROR: {}".format(self.summary)
        
        text = ""
        
        if not self.errors:
            text += "Success.\n"
        
        if self.systems:
            text += "+Updates:\n"
            sysNames = list(self.systems.keys())
            sysNames.sort(key=lambda s: self.systems[s][0])
            for sysName in sysNames:
                code, coords = self.systems[sysName]
                sysText = self.translateCode(code)
                if coords is not None:
                    sysText += str(coords)
                text += "|- {:.<30s} {}\n".format(
                    sysName, sysText,
                )
            text += "\n"
        
        if self.errors:
            text += "+Problems:\n"
            errors = sorted(self.errors, key=lambda e: e.rhs or "")
            errors.sort(key=lambda e: e.lhs or "")
            errors.sort(key=lambda e: e.code)
            for err in errors:
                text += "|- {:.<30s} #{} {}".format(
                        err.lhs,
                        err.code,
                        self.translateCode(err.code),
                )
                if err.rhs:
                    text += " <-> " + err.rhs
                text += "\n"
        
        return text
    
    def translateCode(self, code):
        try:
            return self.codeMap[code]
        except KeyError:
            return "Error #{} (unknown)".format(code)



class StarSubmission:
    baseURL = "http://edstarcoordinator.com/api.asmx/"
    apiCall = "SubmitDistances"
    
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
    
    def __repr__(self):
        return (
            "StarSubmission("
                "test={}, star=\"{}\", commander=\"{}\", refs={}"
            ")".format(
                self.test,
                self.name,
                self.commander,
                self.refs,
            )
        )


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
            data['data']['commander'] = self.commander
        
        jsonData = json.dumps(data, indent=None, separators=(',', ':'))
        
        url = self.baseURL + self.apiCall
        req = requests.post(
            url,
            headers=headers,
            data=jsonData
        )
        resp = req.text
        if not resp.startswith('{'):
            edsc_log(self.apiCall, repr(self), error=resp)
            raise SubmissionError("Server Side Error: " + resp)
        
        try:
            respData = json.loads(resp)
        except Exception:
            edsc_log(self.apiCall, repr(self), error=resp)
            raise SubmissionError("Invalid server response: " + resp)
        edsc_log(self.apiCall, repr(self), respData)
        try:
            innerData = respData['d']
        except KeyError:
            raise SubmissionError("Server Error: " + resp)
        
        return innerData


if __name__ == "__main__":
    print("Requesting recent, non-test, coords-known, cr >= 2 stars")
    edsq = StarQuery(test=False, confidence=2, known=1)
    data = edsq.fetch()
    
    if edsq.status['statusnum'] != 0:
        raise Exception("Query failed: {} ({})".format(
                    edsq.status['msg'],
                    edsq.status['statusnum'],
                ))
    
    date = data['date']
    systems = data['systems']
    
    for sysinfo in systems:
        print("{:<30s} {:11f} {:11f} {:11f} {}".format(
            sysinfo['name'].upper(),
            sysinfo['coord'][0],
            sysinfo['coord'][1],
            sysinfo['coord'][2],
            sysinfo['createdate'],
        ))

