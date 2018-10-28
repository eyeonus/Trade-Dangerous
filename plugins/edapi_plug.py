# ----------------------------------------------------------------
# Import plugin that downloads market and ship vendor data from the
# Elite Dangerous mobile API.
# ----------------------------------------------------------------

import cache
import csvexport
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
import pathlib
import plugins
import pickle
import random
import requests
from requests.utils import dict_from_cookiejar
from requests.utils import cookiejar_from_dict
import sys
import textwrap
import time
import mapping
import transfers
from collections import namedtuple
from asyncio.tasks import sleep


__version_info__ = ('4', '3', '2')
__version__ = '.'.join(__version_info__)

# ----------------------------------------------------------------
# Deal with some differences in names between TD, ED and the API.
# ----------------------------------------------------------------

bracket_levels = ('?', 'L', 'M', 'H')

# Categories to ignore. Drones end up here. No idea what they are.
cat_ignore = [
    'NonMarketable',
]


class EDAPI:
    '''
    A class that handles the Frontier ED API.
    '''

    _agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Mobile/12B411'  # NOQA
    _baseurl = 'https://companion.orerve.net/'
    _basename = 'edapi'
    _cookiefile = _basename + '.cookies'
    _envfile = _basename + '.vars'

    def __init__(
        self,
        basename='edapi',
        debug=False,
        cookiefile=None,
        json_file=None,
        login=False
    ):
        '''
        Initialize
        '''

        # Build common file names from basename.
        self._basename = basename
        if cookiefile:
            self._cookiefile = cookiefile
        else:
            self._cookiefile = self._basename + '.cookies'

        self._envfile = self._basename + '.vars'

        self.debug = debug

        self.login = login

        # If json_file was given, just load that instead.
        if json_file:
            with open(json_file) as file:
                self.profile = json.load(file)
                return

        # if self.debug:
        #     import http.client
        #     http.client.HTTPConnection.debuglevel = 3

        # Setup the HTTP session.
        self.opener = requests.Session()

        self.opener.headers = {
            'User-Agent': self._agent
        }

        # Read/create the cookie jar.
        if os.path.exists(self._cookiefile):
            try:
                with open(self._cookiefile, 'rb') as h:
                    self.opener.cookies = cookiejar_from_dict(pickle.load(h))
            except:
                print('Unable to read cookie file.')

        else:
            with open(self._cookiefile, 'wb') as h:
                pickle.dump(dict_from_cookiejar(self.opener.cookies), h)

        # If force login, kill the user cookie, but keep the machine token
        # intact.
        if self.login:
            self.opener.cookies.pop('CompanionApp', None)

        def getData(dataUrl):
            response = self._getURI(dataUrl)
            try:
                data = response.json()
                self.text.append(response.text)
            except:
                if self.debug:
                    print('   URL:', response.url)
                    print('status:', response.status_code)
                    print('  text:', response.text)
                    txtDebug = ""
                else:
                    txtDebug = "\nTry with --debug and report this."
                sys.exit(
                    "Unable to parse JSON response for /{}!"
                    "\nTry to relogin with the 'login' option."
                    "{}".format(dataUrl, txtDebug)
                )
            return data

        # Grab the commander profile
        self.text = []
        self.profile = getData("profile")

        # Grab the market, outfitting and shipyard data if needed
        portServices = self.profile['lastStarport'].get('services')
        if self.profile['commander']['docked'] and portServices:
            if portServices.get('commodities'):
                res = getData("market")
                if int(res["id"]) == int(self.profile["lastStarport"]["id"]):
                    self.profile["lastStarport"].update(res)
            hasShipyard = portServices.get('shipyard')
            if hasShipyard or portServices.get('outfitting'):
                # the ships for the shipyard are not always returned the first time
                for attempt in range(3):
                    # try up to 3 times
                    res = getData("shipyard")
                    if not hasShipyard or res.get('ships'):
                        break
                    if self.debug:
                        print("No shipyard in response, I'll try again in 5s")
                    time.sleep(5)
                if int(res["id"]) == int(self.profile["lastStarport"]["id"]):
                    self.profile["lastStarport"].update(res)

    def _getBasicURI(self, uri, values=None):
        '''
        Perform a GET/POST to a URI
        '''

        # POST if data is present, otherwise GET.
        if values is None:
            if self.debug:
                print('GET on: ', self._baseurl+uri)
                print(dict_from_cookiejar(self.opener.cookies))
            response = self.opener.get(self._baseurl+uri)
        else:
            if self.debug:
                print('POST on: ', self._baseurl+uri)
                print(dict_from_cookiejar(self.opener.cookies))
            response = self.opener.post(self._baseurl+uri, data=values)

        if self.debug:
            print('Final URL:', response.url)
            print(dict_from_cookiejar(self.opener.cookies))

        # Save the cookies.
        with open(self._cookiefile, 'wb') as h:
            pickle.dump(dict_from_cookiejar(self.opener.cookies), h)

        # Return the response object.
        return response

    def _getURI(self, uri, values=None):
        '''
        Perform a GET/POST and try to login if needed.
        '''

        # Try the URI. If our credentials are no good, try to
        # login then ask again.
        response = self._getBasicURI(uri, values=values)

        if 'Password' in str(response.text):
            self._doLogin()
            response = self._getBasicURI(uri, values=values)

        if 'Password' in str(response.text):
            sys.exit(textwrap.fill(textwrap.dedent("""\
                Something went terribly wrong. The login credentials
                appear correct, but we are being denied access. Sometimes the
                API is slow to update, so if you are authenticating for the
                first time, wait a minute or so and try again. If this
                persists try deleting your cookies file and starting over.
                """)))

        return response

    def _doLogin(self):
        '''
        Go though the login process
        '''
        # First hit the login page to get our auth cookies set.
        response = self._getBasicURI('')

        # Our current cookies look okay? No need to login.
        if str(response.url).endswith('/'):
            return

        # Perform the login POST.
        print(textwrap.fill(textwrap.dedent("""\
              You do not appear to have any valid login cookies set.
              We will attempt to log you in with your Frontier
              account, and cache your auth cookies for future use.
              THIS WILL NOT STORE YOUR USER NAME AND PASSWORD.
              """)))

        print("\nYour auth cookies will be stored here:")

        print("\n"+self._cookiefile+"\n")

        print(textwrap.fill(textwrap.dedent("""\
            It is advisable that you keep this file secret. It may
            be possible to hijack your account with the information
            it contains.
            """)))

        print(
            "\nIf you are not comfortable with this, "
            "DO NOT USE THIS TOOL."
        )
        print()

        values = {}
        values['email'] = input("User Name (email):")
        values['password'] = getpass.getpass()
        response = self._getBasicURI('user/login', values=values)

        # If we end up being redirected back to login,
        # the login failed.
        if 'Password' in str(response.text):
            sys.exit('Login failed.')

        # Check to see if we need to do the auth token dance.
        if str(response.url).endswith('user/confirm'):
            print()
            print("A verification code should have been sent to your "
                  "email address.")
            print("Please provide that code (case sensitive!)")
            values = {}
            values['code'] = input("Code:")
            response = self._getBasicURI('user/confirm', values=values)

        # The API is sometimes very slow to update sessions. Wait a bit...
        time.sleep(2)


class EDDN:
    _gateways = (
        'https://eddn.edcd.io:4430/upload/',
        # 'http://eddn-gateway.ed-td.space:8080/upload/',
    )

    _commodity_schemas = {
        'production': 'https://eddn.edcd.io/schemas/commodity/3',
        'test': 'https://eddn.edcd.io/schemas/commodity/3/test',
    }

    _shipyard_schemas = {
        'production': 'https://eddn.edcd.io/schemas/shipyard/2',
        'test': 'https://eddn.edcd.io/schemas/shipyard/2/test',
    }

    _outfitting_schemas = {
        'production': 'https://eddn.edcd.io/schemas/outfitting/2',
        'test': 'https://eddn.edcd.io/schemas/outfitting/2/test',
    }

    _debug = True

    # As of 1.3, ED reports four levels.
    _levels = (
        'Low',
        'Low',
        'Med',
        'High',
    )

    def __init__(
        self,
        uploaderID,
        noHash,
        softwareName,
        softwareVersion
    ):
        # Obfuscate uploaderID
        if noHash:
            self.uploaderID = uploaderID
        else:
            self.uploaderID = hashlib.sha1(uploaderID.encode('utf-8')).hexdigest()
        self.softwareName = softwareName
        self.softwareVersion = softwareVersion

    def postMessage(
        self,
        message,
        timestamp=0
    ):
        if timestamp:
            timestamp = datetime.fromtimestamp(timestamp).isoformat()
        else:
            timestamp = datetime.now(timezone.utc).astimezone().isoformat()

        message['message']['timestamp'] = timestamp

        url = random.choice(self._gateways)

        headers = {
            'content-type': 'application/json; charset=utf8'
        }

        if self._debug:
            print(
                json.dumps(
                    message,
                    sort_keys=True,
                    indent=4
                )
            )

        r = requests.post(
            url,
            headers=headers,
            data=json.dumps(
                message,
                ensure_ascii=False
            ).encode('utf8'),
            verify=True
        )

        r.raise_for_status()

    def publishCommodities(
        self,
        systemName,
        stationName,
        marketId,
        commodities,
        additional=None,
        timestamp=0
    ):
        message = {}

        message['$schemaRef'] = self._commodity_schemas[('test' if self._debug else 'production')]  # NOQA

        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }

        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'commodities': commodities,
        }
        if additional:
            message['message'].update(additional)

        self.postMessage(message, timestamp)

    def publishShipyard(
        self,
        systemName,
        stationName,
        marketId,
        ships,
        timestamp=0
    ):
        message = {}

        message['$schemaRef'] = self._shipyard_schemas[('test' if self._debug else 'production')]  # NOQA

        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }

        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'ships': ships,
        }

        self.postMessage(message, timestamp)

    def publishOutfitting(
        self,
        systemName,
        stationName,
        marketId,
        modules,
        timestamp=0
    ):
        message = {}

        message['$schemaRef'] = self._outfitting_schemas[('test' if self._debug else 'production')]  # NOQA

        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }

        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'modules': modules,
        }

        self.postMessage(message, timestamp)


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads market and ship vendor data from the Elite Dangerous
    mobile API.
    """

    pluginOptions = {
        'csvs': 'Merge shipyards into ShipVendor.csv.',
        'edcd': 'Call the EDCD plugin first.',
        'eddn': 'Post market, shipyard and outfitting to EDDN.',
        'name': 'Do not obfuscate commander name for EDDN submit.',
        'save': 'Save the API response (tmp/profile.YYYYMMDD_HHMMSS.json).',
        'tdh': 'Save the API response for TDH (tmp/tdh_profile.json).',
        'test': 'Test the plugin with a json file (test=[FILENAME]).',
        'warn': 'Ask for station update if a API<->DB diff is encountered.',
        'login': 'Ask for login credentials.',
    }

    cookieFile = "edapi.cookies"

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        cookieFilePath = pathlib.Path(ImportPlugin.cookieFile)
        self.cookiePath = tdb.dataPath / cookieFilePath

    def askForStationData(self, system, stnName=None, station=None):
        """
        Ask for new or updated station data
        """
        tdb, tdenv = self.tdb, self.tdenv
        askForData = False

        stnDefault = namedtuple(
            'stnDefault', [
                'lsFromStar','market','blackMarket','shipyard','maxPadSize',
                'outfitting','rearm','refuel','repair','planetary',
            ]
        )

        def tellUserAPIResponse(defName, defValue):
            if defValue == "Y":
                tdenv.NOTE("{:>12} in API response", defName)
            else:
                tdenv.NOTE("{:>12} NOT in API response", defName)

        def getYNfromObject(obj, key):
            return "Y" if key in obj else "N"

        # defaults from API response are not reliable!
        checkStarport = self.edAPI.profile['lastStarport']
        defMarket     = getYNfromObject(checkStarport, 'commodities')
        defShipyard   = getYNfromObject(checkStarport, 'ships')
        defOutfitting = getYNfromObject(checkStarport, 'modules')
        tellUserAPIResponse("'Outfitting'", defOutfitting)
        tellUserAPIResponse("'ShipYard'", defShipyard)
        tellUserAPIResponse("'Market'", defMarket)

        def warnAPIResponse(checkName, checkYN):
            # no warning if unknown
            if checkYN == "?": return False
            warnText = (
                "The station should{s} have a {what}, "
                "but the API did{d} return one."
            )
            if checkYN == "Y":
                s, d = "", "n't"
            else:
                s, d = "n't", ""

            tdenv.WARN(warnText, what=checkName, s=s, d=d)
            return True if self.getOption('warn') else False

        # station services since ED update 2.4
        checkServices = checkStarport.get('services', None)
        if checkServices:
            if station:
                tdenv.NOTE('Station known.')
                stnlsFromStar = station.lsFromStar
                stnmaxPadSize = station.maxPadSize
                stnplanetary  = station.planetary
            else:
                tdenv.NOTE('Station unknown.')
                stnlsFromStar = 0
                stnmaxPadSize = "?"
                stnplanetary  = "?"
            tdenv.NOTE("Found station services.")
            if checkStarport.get('outpostType', None) == 'starport':
                # only the big one can be detected
                stnmaxPadSize = "L"
                stnplanetary  = "N"
            defStation = stnDefault(
                lsFromStar = stnlsFromStar,
                market = getYNfromObject(checkServices, 'commodities'),
                blackMarket = getYNfromObject(checkServices, 'blackmarket'),
                shipyard = getYNfromObject(checkServices, 'shipyard'),
                maxPadSize = stnmaxPadSize,
                outfitting = getYNfromObject(checkServices, 'outfitting'),
                rearm = getYNfromObject(checkServices, 'rearm'),
                refuel = getYNfromObject(checkServices, 'refuel'),
                repair = getYNfromObject(checkServices, 'repair'),
                planetary = stnplanetary,
            )
        elif station:
            tdenv.NOTE('Station known.')
            defStation = stnDefault(
                lsFromStar = station.lsFromStar,
                market = defMarket if station.market == "?" else station.market,
                blackMarket = station.blackMarket,
                shipyard = defShipyard if station.shipyard == "?" else station.shipyard,
                maxPadSize = station.maxPadSize,
                outfitting = defOutfitting if station.outfitting == "?" else station.outfitting,
                rearm = station.rearm,
                refuel = station.refuel,
                repair = station.repair,
                planetary = station.planetary,
            )
        else:
            tdenv.NOTE('Station unknown.')
            defStation = stnDefault(
                lsFromStar  = 0,   market     = defMarket,
                blackMarket = "?", shipyard   = defShipyard,
                maxPadSize  = "?", outfitting = defOutfitting,
                rearm       = "?", refuel     = "?",
                repair      = "?", planetary  = "?",
            )

        warning = False
        if defStation.outfitting != defOutfitting:
            warning |= warnAPIResponse('outfitting', defStation.outfitting)
        if defStation.shipyard != defShipyard:
            warning |= warnAPIResponse('shipyard', defStation.shipyard)
        if defStation.market != defMarket:
            warning |= warnAPIResponse('market', defStation.market)
        if warning:
            tdenv.WARN("Please update station data with correct values.")
            tdenv.WARN("(Fields will be marked with an leading asterisk '*')")
            askForData = True
        if ((defStation.lsFromStar == 0) or ("?" in defStation)):
           askForData = True

        newStation = {}
        for key in defStation._fields:
            newStation[key] = getattr(defStation, key)

        if askForData:
            tdenv.NOTE("Values in brackets are the default.")
            lsFromStar = input(
                " Stn/Ls..............[{}]: ".format(defStation.lsFromStar)
            ) or defStation.lsFromStar
            try:
                lsFromStar = int(float(lsFromStar)+0.5)
            except:
                print("That doesn't seem to be a number. Defaulting to zero.")
                lsFromStar = defStation.lsFromStar
            newStation['lsFromStar'] = lsFromStar

            for askText, askField, markValue in [
                ('Pad Size....(s,m,l) ', 'maxPadSize',  defStation.maxPadSize),
                ('Planetary.....(y,n) ', 'planetary',   defStation.planetary),
                ('B/Market......(y,n) ', 'blackMarket', defStation.blackMarket),
                ('Refuel........(y,n) ', 'refuel',      defStation.refuel),
                ('Repair........(y,n) ', 'repair',      defStation.repair),
                ('Restock.......(y,n) ', 'rearm',       defStation.rearm),
                ('Outfitting....(y,n) ', 'outfitting',  defOutfitting),
                ('Shipyard......(y,n) ', 'shipyard',    defShipyard),
                ('Market........(y,n) ', 'market',      defMarket),
            ]:
                defValue = getattr(defStation, askField)
                if defValue != markValue:
                    mark = "*"
                else:
                    mark = " "
                askValue = input(
                    "{}{}[{}]: ".format(mark, askText, defValue)
                ) or defValue
                newStation[askField] = askValue

        else:
            def _detail(value, source):
                detail = source[value]
                if detail == '?':
                    detail += ' [unknown]'
                return detail

            ls = newStation['lsFromStar']
            print(" Stn/Ls....:", ls, '[unknown]' if ls == 0 else '')
            print(" Pad Size..:", _detail(newStation['maxPadSize'], tdb.padSizes))
            print(" Planetary.:", _detail(newStation['planetary'], tdb.planetStates))
            print(" B/Market..:", _detail(newStation['blackMarket'], tdb.marketStates))
            print(" Refuel....:", _detail(newStation['refuel'], tdb.marketStates))
            print(" Repair....:", _detail(newStation['repair'], tdb.marketStates))
            print(" Restock...:", _detail(newStation['rearm'], tdb.marketStates))
            print(" Outfitting:", _detail(newStation['outfitting'], tdb.marketStates))
            print(" Shipyard..:", _detail(newStation['shipyard'], tdb.marketStates))
            print(" Market....:", _detail(newStation['market'], tdb.marketStates))

        exportCSV = False
        if not station:
            station = tdb.addLocalStation(
                system=system,
                name=stnName,
                lsFromStar=newStation['lsFromStar'],
                blackMarket=newStation['blackMarket'],
                maxPadSize=newStation['maxPadSize'],
                market=newStation['market'],
                shipyard=newStation['shipyard'],
                outfitting=newStation['outfitting'],
                rearm=newStation['rearm'],
                refuel=newStation['refuel'],
                repair=newStation['repair'],
                planetary=newStation['planetary'],
            )
            exportCSV = True
        else:
            # let the function check for changes
            if tdb.updateLocalStation(
                station=station,
                lsFromStar=newStation['lsFromStar'],
                blackMarket=newStation['blackMarket'],
                maxPadSize=newStation['maxPadSize'],
                market=newStation['market'],
                shipyard=newStation['shipyard'],
                outfitting=newStation['outfitting'],
                rearm=newStation['rearm'],
                refuel=newStation['refuel'],
                repair=newStation['repair'],
                planetary=newStation['planetary'],
            ):
                exportCSV = True

        if exportCSV:
            lines, csvPath = csvexport.exportTableToFile(
                tdb,
                tdenv,
                "Station",
            )
            tdenv.DEBUG0("{} updated.", csvPath)
        return station

    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        # first check for EDCD
        if self.getOption("edcd"):
            # Call the EDCD plugin
            try:
                import plugins.edcd_plug as EDCD
            except:
                raise plugins.PluginException("EDCD plugin not found.")
            tdenv.NOTE("Calling the EDCD plugin.")
            edcdPlugin = EDCD.ImportPlugin(tdb, tdenv)
            edcdPlugin.options["csvs"] = True
            edcdPlugin.run()
            tdenv.NOTE("Going back to EDAPI.\n")

        # now load the mapping tables
        itemMap = mapping.FDEVMappingItems(tdb, tdenv)
        shipMap = mapping.FDEVMappingShips(tdb, tdenv)

        # Connect to the API, authenticate, and pull down the commander
        # /profile.
        if self.getOption("test"):
            tdenv.WARN("#############################")
            tdenv.WARN("###  EDAPI in test mode.  ###")
            tdenv.WARN("#############################")
            apiED = namedtuple('EDAPI', ['profile','text'])
            try:
                proPath = pathlib.Path(self.getOption("test"))
            except TypeError:
                raise plugins.PluginException(
                    "Option 'test' must be a file name"
                )
            if proPath.exists():
                with proPath.open() as proFile:
                    proData = json.load(proFile)
                    if isinstance(proData, list):
                        # since 4.3.0: list(profile, market, shipyard)
                        testProfile = proData[0]
                        for data in proData[1:]:
                            if int(data["id"]) == int(testProfile["lastStarport"]["id"]):
                                testProfile["lastStarport"].update(data)
                    else:
                        testProfile = proData
                    api = apiED(
                        profile = testProfile,
                        text = '{{"mode":"test","file":"{}"}}'.format(str(proPath))
                    )
            else:
                raise plugins.PluginException(
                    "JSON-file '{}' not found.".format(str(proPath))
                )
        else:
            api = EDAPI(
                cookiefile=str(self.cookiePath),
                login=self.getOption('login'),
                debug=tdenv.debug,
            )
        self.edAPI = api

        tdh_path = pathlib.Path('tmp/tdh_profile.json')
        if self.getOption("tdh"):
            self.options["save"] = True
            if tdh_path.exists():
                tdh_path.unlink()
        # save profile if requested
        if self.getOption("save"):
            saveName = tdh_path if self.getOption("tdh") else 'tmp/profile.' + time.strftime('%Y%m%d_%H%M%S') + '.json'
            with open(saveName, 'w', encoding="utf-8") as saveFile:
                if isinstance(api.text, list):
                    # since 4.3.0: list(profile, market, shipyard)
                    saveFile.write("[{}]".format(",".join(api.text)))
                else:
                    saveFile.write(api.text)
                print('API response saved to: {}'.format(saveName))

        # If TDH is calling the plugin, nothing else needs to be done
        # now that the file has been created.
        if self.getOption("tdh"):
            return False
        
        # Sanity check that the commander is docked. Otherwise we will get a
        # mismatch between the last system and last station.
        if not api.profile['commander']['docked']:
            print('Commander not docked. Aborting!')
            return False

        # Figure out where we are.
        sysName = api.profile['lastSystem']['name']
        stnName = api.profile['lastStarport']['name']
        marketId = int(api.profile['lastStarport']['id'])
        print('@{}/{} (ID: {})'.format(sysName.upper(), stnName, marketId))

        # Reload the cache.
        tdenv.DEBUG0("Checking the cache")
        tdb.close()
        tdb.reloadCache()
        tdb.load(
            maxSystemLinkLy=tdenv.maxSystemLinkLy,
        )
        tdb.close()

        # Check to see if this system is in the database
        try:
            system = tdb.lookupSystem(sysName)
        except LookupError:
            raise plugins.PluginException(
                "System '{}' unknown.".format(sysName)
            )

        # Check to see if this station is in the database
        try:
            station = tdb.lookupStation(stnName, system)
        except LookupError:
            station = None

        # New or update station data
        station = self.askForStationData(system, stnName=stnName, station=station)

        # If a shipyard exists, make the ship lists
        shipCost = {}
        shipList = []
        eddn_ships = []
        if ((station.shipyard == "Y") and
            ('ships' in api.profile['lastStarport'])
        ):
            if 'shipyard_list' in api.profile['lastStarport']['ships']:
                if len(api.profile['lastStarport']['ships']['shipyard_list']):
                    for ship in api.profile['lastStarport']['ships']['shipyard_list'].values():
                        shipName = shipMap.mapID(ship['id'], ship['name'])
                        shipCost[shipName] = ship['basevalue']
                        shipList.append(shipName)
                        eddn_ships.append(ship['name'])

            if 'unavailable_list' in api.profile['lastStarport']['ships']:
                for ship in api.profile['lastStarport']['ships']['unavailable_list']:
                    shipName = shipMap.mapID(ship['id'], ship['name'])
                    shipCost[shipName] = ship['basevalue']
                    shipList.append(shipName)
                    eddn_ships.append(ship['name'])

        if self.getOption("csvs"):
            addRows = delRows = 0
            db = tdb.getDB()
            if station.shipyard == "N":
                # delete all ships if there is no shipyard
                delRows = db.execute(
                    """
                    DELETE FROM ShipVendor
                     WHERE station_id = ?
                    """,
                    [station.ID]
                ).rowcount

            if len(shipList):
                # and now update the shipyard list
                # we go through all ships to decide if a ship needs to be
                # added or deleted from the shipyard
                for shipID in tdb.shipByID:
                    shipName = tdb.shipByID[shipID].dbname
                    if shipName in shipList:
                        # check for ship discount, costTD = 100%
                        # python builtin round() uses "Round half to even"
                        # but we need commercial rounding, so we do it ourself
                        costTD = tdb.shipByID[shipID].cost
                        costED = int((shipCost[shipName]+5)/10)*10
                        if costTD != costED:
                            prozED = int(shipCost[shipName]*100/costTD+0.5)-100
                            tdenv.NOTE(
                                "CostDiff {}: {} != {} ({}%)",
                                shipName, costTD, costED, prozED
                            )
                        # add the ship to the shipyard
                        shipSQL = (
                            "INSERT OR IGNORE"
                             " INTO ShipVendor(station_id, ship_id)"
                           " VALUES(?, ?)"
                        )
                        tdenv.DEBUG0(shipSQL.replace("?", "{}"), station.ID, shipID)
                        addRows += db.execute(shipSQL, [station.ID, shipID]).rowcount
                    else:
                        # delete the ship from the shipyard
                        shipSQL = (
                            "DELETE FROM ShipVendor"
                            " WHERE station_id = ?"
                              " AND ship_id = ?"
                        )
                        tdenv.DEBUG0(shipSQL.replace("?", "{}"), station.ID, shipID)
                        delRows += db.execute(shipSQL, [station.ID, shipID]).rowcount

            db.commit()
            if (addRows + delRows) > 0:
                if addRows > 0:
                    tdenv.NOTE(
                        "Added {} ships in '{}' shipyard.",
                        addRows, station.name()
                    )
                if delRows > 0:
                    tdenv.NOTE(
                        "Deleted {} ships in '{}' shipyard.",
                        delRows, station.name()
                    )
                lines, csvPath = csvexport.exportTableToFile(
                    tdb,
                    tdenv,
                    "ShipVendor",
                )
                tdenv.DEBUG0("{} updated.", csvPath)

        # If a market exists, make the item lists
        itemList = []
        eddn_market = []
        if ((station.market == "Y") and
            ('commodities' in api.profile['lastStarport'])
        ):
            for commodity in api.profile['lastStarport']['commodities']:
                if commodity['categoryname'] in cat_ignore:
                    continue

                if commodity.get('legality', '') != '':
                    # ignore if present and not empty
                    continue

                locName = commodity.get('locName', commodity['name'])
                itmName = itemMap.mapID(commodity['id'], locName)

                def commodity_int(key):
                    try:
                        ret = int(float(commodity[key])+0.5)
                    except (ValueError, KeyError):
                        ret = 0
                    return ret

                itmSupply      = commodity_int('stock')
                itmDemand      = commodity_int('demand')
                itmSupplyLevel = commodity_int('stockBracket')
                itmDemandLevel = commodity_int('demandBracket')
                itmBuyPrice    = commodity_int('buyPrice')
                itmSellPrice   = commodity_int('sellPrice')

                if itmSupplyLevel == 0 or itmBuyPrice == 0:
                    # If there is not stockBracket or buyPrice, ignore stock
                    itmBuyPrice = 0
                    itmSupply = 0
                    itmSupplyLevel = 0
                    tdSupply = "-"
                    tdDemand = "{}{}".format(
                        itmDemand,
                        bracket_levels[itmDemandLevel]
                    )
                else:
                    # otherwise don't care about demand
                    itmDemand = 0
                    itmDemandLevel = 0
                    tdDemand = "?"
                    tdSupply = "{}{}".format(
                        itmSupply,
                        bracket_levels[itmSupplyLevel]
                    )

                # ignore items without supply or demand bracket (TD only)
                if itmSupplyLevel > 0 or itmDemandLevel > 0:
                    itemTD = (
                        itmName,
                        itmSellPrice, itmBuyPrice,
                        tdDemand, tdSupply,
                    )
                    itemList.append(itemTD)

                # Populate EDDN
                if self.getOption("eddn"):
                    itemEDDN = {
                        "name":          commodity['name'],
                        "meanPrice":     commodity_int('meanPrice'),
                        "buyPrice":      commodity_int('buyPrice'),
                        "stock":         commodity_int('stock'),
                        "stockBracket":  commodity['stockBracket'],
                        "sellPrice":     commodity_int('sellPrice'),
                        "demand":        commodity_int('demand'),
                        "demandBracket": commodity['demandBracket'],
                    }
                    if len(commodity['statusFlags']) > 0:
                        itemEDDN["statusFlags"] = commodity['statusFlags']
                    eddn_market.append(itemEDDN)

        if itemList:
            # Create the import file.
            with open(self.filename, 'w', encoding="utf-8") as f:
                # write System/Station line
                f.write("@ {}/{}\n".format(sysName, stnName))

                # write Item lines (category lines are not needed)
                for itemTD in itemList:
                    f.write("\t\t%s %s %s %s %s\n" % itemTD)

            tdenv.ignoreUnknown = True
            cache.importDataFromFile(
                tdb,
                tdenv,
                pathlib.Path(self.filename),
            )

        # Import EDDN
        if self.getOption("eddn"):
            con = EDDN(
                api.profile['commander']['name'],
                self.getOption("name"),
                'EDAPI Trade Dangerous Plugin',
                __version__
            )
            if self.getOption("test"):
                con._debug = True
            else:
                con._debug = False

            if eddn_market:
                print('Posting commodities to EDDN...')
                eddn_additional = {}
                if 'economies' in api.profile['lastStarport']:
                    eddn_additional['economies'] = []
                    for economy in api.profile['lastStarport']['economies'].values():
                        eddn_additional['economies'].append(economy)
                if 'prohibited' in api.profile['lastStarport']:
                    eddn_additional['prohibited'] = []
                    for item in api.profile['lastStarport']['prohibited'].values():
                        eddn_additional['prohibited'].append(item)

                con.publishCommodities(
                    sysName,
                    stnName,
                    marketId,
                    eddn_market,
                    additional=eddn_additional
                )

            if eddn_ships:
                print('Posting shipyard to EDDN...')
                con.publishShipyard(
                    sysName,
                    stnName,
                    marketId,
                    eddn_ships
                )

            if ((station.outfitting == "Y") and
                ('modules' in api.profile['lastStarport'] and
                len(api.profile['lastStarport']['modules']))
            ):
                eddn_modules = []
                for module in api.profile['lastStarport']['modules'].values():
                    # see: https://github.com/EDSM-NET/EDDN/wiki
                    addModule = False
                    if module['name'].startswith(('Hpt_', 'Int_')) or module['name'].find('_Armour_') > 0:
                        if module.get('sku', None) in (
                            None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'
                        ):
                            if module['name'] != 'Int_PlanetApproachSuite':
                                addModule = True
                    if addModule:
                        eddn_modules.append(module['name'])
                    elif self.getOption("test"):
                        tdenv.NOTE("Ignored module ID: {}, name: {}", module['id'], module['name'])
                if eddn_modules:
                    print('Posting outfitting to EDDN...')
                    con.publishOutfitting(
                        sysName,
                        stnName,
                        marketId,
                        sorted(eddn_modules)
                    )

        # We did all the work
        return False
