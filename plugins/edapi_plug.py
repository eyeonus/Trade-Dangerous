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

__version_info__ = ('3', '7', '0')
__version__ = '.'.join(__version_info__)

# ----------------------------------------------------------------
# Deal with some differences in names between TD, ED and the API.
# ----------------------------------------------------------------

bracket_levels = ('-', 'L', 'M', 'H')

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

    def __init__(self, basename='edapi', debug=False, cookiefile=None):
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

        # Grab the commander profile
        response = self._getURI('profile')
        self.text = response.text
        try:
            self.profile = response.json()
        except:
            sys.exit('Unable to parse JSON response for /profile!\
                     Try with --debug and report this.')

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

        if str(response.url).endswith('user/login'):
            self._doLogin()
            response = self._getBasicURI(uri, values=values)

        if str(response.url).endswith('user/login'):
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
        if str(response.url).endswith('user/login'):
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

        # Sometimes the API is slow to set a session. Wait a bit before
        # continuing.
        time.sleep(2)


class EDDN:
    _gateways = (
        'http://eddn-gateway.elite-markets.net:8080/upload/',
        # 'http://eddn-gateway.ed-td.space:8080/upload/',
    )

    _market_schemas = {
        'production': 'http://schemas.elite-markets.net/eddn/commodity/2',
        'test': 'http://schemas.elite-markets.net/eddn/commodity/2/test',
    }

    _shipyard_schemas = {
        'production': 'http://schemas.elite-markets.net/eddn/shipyard/1',
        'test': 'http://schemas.elite-markets.net/eddn/shipyard/1/test',
    }

    _outfitting_schemas = {
        'production': 'http://schemas.elite-markets.net/eddn/outfitting/1',
        'test': 'http://schemas.elite-markets.net/eddn/outfitting/1/test',
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
        commodities,
        timestamp=0
    ):
        message = {}

        message['$schemaRef'] = self._market_schemas[('test' if self._debug else 'production')]  # NOQA

        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }

        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'commodities': commodities,
        }

        self.postMessage(message, timestamp)

    def publishShipyard(
        self,
        systemName,
        stationName,
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
            'ships': ships,
        }

        self.postMessage(message, timestamp)

    def publishOutfitting(
        self,
        systemName,
        stationName,
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
            'modules': modules,
        }

        self.postMessage(message, timestamp)


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads market and ship vendor data from the Elite Dangerous
    mobile API.
    """

    pluginOptions = {
        'csvs': 'Merge shipyard into into ShipVendor.csv.',
        'name': 'Do not obfuscate commander name for EDDN submit.',
        'save': 'Save the API response (tmp/profile.YYYYMMDD_HHMMSS.json).',
        'edcd': 'Download current FDevIDs from EDCD',
        'eddn': 'Post market prices to EDDN.',
    }

    cookieFile = "edapi.cookies"

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        cookieFilePath = pathlib.Path(ImportPlugin.cookieFile)
        self.cookiePath = tdb.dataPath / cookieFilePath

    def download_fdevids(self):
        """
            Download the current Shipyard and Outfitting data
            from EDCD, see https://github.com/EDCD/FDevIDs
        """
        tdb, tdenv = self.tdb, self.tdenv

        baseUrl = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/"
        downloadList = [
            ('FDevShipyard', 'FDevShipyard.csv', 'shipyard.csv'),
            ('FDevOutfitting', 'FDevOutfitting.csv', 'outfitting.csv'),
        ]

        db = tdb.getDB()
        for tableName, fileTD, fileEDCD in downloadList:
            localPath = tdb.dataPath / pathlib.Path(fileTD)
            transfers.download(
                tdenv,
                baseUrl + fileEDCD,
                str(localPath),
            )
            db.execute("DELETE FROM {}".format(tableName))
            cache.processImportFile(
                tdenv,
                db,
                localPath,
                tableName
            )
            lines, csvPath = csvexport.exportTableToFile(
                tdb,
                tdenv,
                tableName,
            )
            tdenv.NOTE("{} updated.", csvPath)
        db.commit()

    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        # first check for EDCD
        if self.getOption("edcd"):
            # download the current FDevIDs from EDCD
            self.download_fdevids()

        # now load the mapping tables
        itemMap = mapping.FDEVMappingItems(tdb, tdenv)
        shipMap = mapping.FDEVMappingShips(tdb, tdenv)
        yardMap = mapping.FDEVMappingShipyard(tdb, tdenv)
        outfMap = mapping.FDEVMappingOutfitting(tdb, tdenv)

        if self.getOption("eddn"):
            if yardMap.mapCount == 0 or outfMap.mapCount == 0:
                tdenv.NOTE("No Ship or Outfitting mapping for EDDN found.")
                tdenv.NOTE("Please set option 'edcd' to download current mappings.")
                return False

        # Connect to the API, authenticate, and pull down the commander
        # /profile.
        api = EDAPI(cookiefile=str(self.cookiePath))

        # Sanity check that the commander is docked. Otherwise we will get a
        # mismatch between the last system and last station.
        if not api.profile['commander']['docked']:
            print('Commander not docked. Aborting!')
            return False

        # save profile if requested
        if self.getOption("save"):
            saveName = 'tmp/profile.' + time.strftime('%Y%m%d_%H%M%S') + '.json'
            with open(saveName, 'w', encoding="utf-8") as saveFile:
                saveFile.write(api.text)
                print('API response saved to: {}'.format(saveName))

        # Figure out where we are.
        system = api.profile['lastSystem']['name']
        station = api.profile['lastStarport']['name']
        place = '@{}/{}'.format(system.upper(), station)
        print(place)

        # Reload the cache.
        tdenv.DEBUG0("Checking the cache")
        tdb.close()
        tdb.reloadCache()
        tdb.load(
            maxSystemLinkLy=tdenv.maxSystemLinkLy,
        )
        tdb.close()

        # Check to see if this system is in the Stations file
        try:
            station_lookup = tdb.lookupPlace(place)
        except LookupError:
            station_lookup = None

        # The station isn't known. Add it.
        if not station_lookup:
            print('Station unknown.')
            print('Adding:', place)
            lsFromStar = input(
                "Distance from star (enter for 0): "
            ) or 0
            try:
                lsFromStar = int(float(lsFromStar))
            except:
                print("That doesn't seem to be a number. Defaulting to zero.")
                lsFromStar = 0
            blackMarket = input(
                "Black market present (Y, N or enter for ?): "
            ) or '?'
            maxPadSize = input(
                "Max pad size (S, M, L or enter for ?): "
            ) or '?'
            outfitting = input(
                "Outfitting present (Y, N or enter for ?): "
            ) or '?'
            rearm = input(
                "Rearm present (Y, N or enter for ?): "
            ) or '?'
            refuel = input(
                "Refuel present (Y, N or enter for ?): "
            ) or '?'
            repair = input(
                "Repair present (Y, N or enter for ?): "
            ) or '?'
            planetary = input(
                "Planetary station (Y, N or enter for ?): "
            ) or '?'
            # This is unreliable, so ask the user.
            if 'commodities' in api.profile['lastStarport']:
                market = 'Y'
            else:
                market = input(
                    "Commodity market present (Y, N or enter for ?): "
                ) or '?'
            # This is also unreliable, so ask the user.
            if 'ships' in api.profile['lastStarport']:
                shipyard = 'Y'
            else:
                shipyard = input(
                    "Shipyard present (Y, N or enter for ?): "
                ) or '?'
            system_lookup = tdb.lookupSystem(system)
            if tdb.addLocalStation(
                system=system_lookup,
                name=station,
                lsFromStar=lsFromStar,
                blackMarket=blackMarket,
                maxPadSize=maxPadSize,
                market=market,
                shipyard=shipyard,
                outfitting=outfitting,
                rearm=rearm,
                refuel=refuel,
                repair=repair,
                planetary=planetary
            ):
                lines, csvPath = csvexport.exportTableToFile(
                    tdb,
                    tdenv,
                    "Station"
                )
                tdenv.NOTE("{} updated.", csvPath)
                station_lookup = tdb.lookupPlace(place)
            station_lookup = tdb.lookupStation(station, system)
        else:
            # See if we need to update the info for this station.
            print('Station known.')
            lsFromStar = station_lookup.lsFromStar
            blackMarket = station_lookup.blackMarket
            maxPadSize = station_lookup.maxPadSize
            market = station_lookup.market
            shipyard = station_lookup.shipyard
            outfitting = station_lookup.outfitting
            rearm = station_lookup.rearm
            refuel = station_lookup.refuel
            repair = station_lookup.repair
            planetary = station_lookup.planetary

            if lsFromStar == 0:
                lsFromStar = input(
                    "Update distance from star (enter for 0): "
                ) or 0
                lsFromStar = int(lsFromStar)

            if blackMarket is '?':
                blackMarket = input(
                    "Update black market present (Y, N or enter for ?): "
                ) or '?'

            if maxPadSize is '?':
                maxPadSize = input(
                    "Update max pad size (S, M, L or enter for ?): "
                ) or '?'

            if outfitting is '?':
                outfitting = input(
                    "Update outfitting present (Y, N or enter for ?): "
                ) or '?'

            if rearm is '?':
                rearm = input(
                    "Update rearm present (Y, N or enter for ?): "
                ) or '?'

            if refuel is '?':
                refuel = input(
                    "Update refuel present (Y, N or enter for ?): "
                ) or '?'

            if repair is '?':
                repair = input(
                    "Update repair present (Y, N or enter for ?): "
                ) or '?'

            if planetary is '?':
                planetary = input(
                    "Update planetary (Y, N or enter for ?): "
                ) or '?'

            # This is unreliable, so ask the user if unknown.
            if 'commodities' in api.profile['lastStarport']:
                market = 'Y'
            else:
                if market is '?':
                    market = input(
                        "Commodity market present (Y, N or enter for ?): "
                    ) or '?'

            # This is also unreliable, so ask the user if unknown.
            if 'ships' in api.profile['lastStarport']:
                shipyard = 'Y'
            else:
                if shipyard is '?':
                    shipyard = input(
                        "Shipyard present (Y, N or enter for ?): "
                    ) or '?'

            if (
                lsFromStar != station_lookup.lsFromStar or
                blackMarket != station_lookup.blackMarket or
                maxPadSize != station_lookup.maxPadSize or
                market != station_lookup.market or
                shipyard != station_lookup.shipyard or
                outfitting != station_lookup.outfitting or
                rearm != station_lookup.rearm or
                refuel != station_lookup.refuel or
                repair != station_lookup.repair or
                planetary != station_lookup.planetary
            ):
                if tdb.updateLocalStation(
                    station=station_lookup,
                    lsFromStar=lsFromStar,
                    blackMarket=blackMarket,
                    maxPadSize=maxPadSize,
                    market=market,
                    shipyard=shipyard,
                    outfitting=outfitting,
                    rearm=rearm,
                    refuel=refuel,
                    repair=repair,
                    planetary=planetary
                ):
                    lines, csvPath = csvexport.exportTableToFile(
                        tdb,
                        tdenv,
                        "Station",
                    )
                    tdenv.NOTE("{} updated.", csvPath)

        # If a shipyard exists, update the ship vendor list.
        shipList = []
        yardList = []
        if 'ships' in api.profile['lastStarport']:
            if 'shipyard_list' in api.profile['lastStarport']['ships']:
                for ship in api.profile['lastStarport']['ships']['shipyard_list'].values():
                    shipList.append(shipMap.mapID(ship['id'], ship['name']))
                    yardList.append(yardMap.mapID(ship['id'], ship['name']))

            if 'unavailable_list' in api.profile['lastStarport']['ships']:
                for ship in api.profile['lastStarport']['ships']['unavailable_list']:
                    shipList.append(shipMap.mapID(ship['id'], ship['name']))
                    yardList.append(yardMap.mapID(ship['id'], ship['name']))

            if self.getOption("csvs"):
                db = tdb.getDB()
                # first delete all ships
                db.execute(
                    """
                    DELETE FROM ShipVendor
                     WHERE station_id = ?
                    """,
                    [station_lookup.ID]
                )
                # and now add the shipyard list
                for ship in shipList:
                    ship_lookup = tdb.lookupShip(ship)
                    db.execute(
                        """
                        INSERT INTO ShipVendor(ship_id, station_id)
                                        VALUES(?, ?)
                        """,
                        [ship_lookup.ID, station_lookup.ID]
                    )
                db.commit()
                tdenv.NOTE("Updated {} ships in {} shipyard.", len(shipList), place)
                lines, csvPath = csvexport.exportTableToFile(
                    tdb,
                    tdenv,
                    "ShipVendor",
                )

        # Some sanity checking on the market.
        if 'commodities' not in api.profile['lastStarport']:
            print(
                'The API did not return a commodity market for this station.'
            )
            print(
                'If you think this is wrong, try again. The API will '
                'occasionally skip the market.'
            )
            return False

        # Create the import file.
        with open(self.filename, 'w', encoding="utf-8") as f:
            f.write("@ {}/{}\n".format(system, station))
            eddn_market = []
            for commodity in api.profile['lastStarport']['commodities']:
                if commodity['categoryname'] in cat_ignore:
                    continue
                commodity['name'] = itemMap.mapID(commodity['id'], commodity['name'])

                def commodity_int(key):
                    try:
                        commodity[key] = int(commodity[key])
                    except (ValueError, KeyError):
                        commodity[key] = 0

                commodity_int('stock')
                commodity_int('demand')
                commodity_int('demandBracket')
                commodity_int('stockBracket')
                commodity_int('buyPrice')
                commodity_int('sellPrice')

                # Populate EDDN
                if self.getOption("eddn"):
                    eddn_market.append(
                        {
                            "name": commodity['name'],
                            "buyPrice": commodity['buyPrice'],
                            "supply": commodity['stock'],
                            "supplyLevel": EDDN._levels[commodity['stockBracket']],  # NOQA
                            "sellPrice": commodity['sellPrice'],
                            "demand": commodity['demand'],
                            "demandLevel": EDDN._levels[commodity['demandBracket']]  # NOQA
                        }
                    )

                # If stock is zero, list it as unavailable.
                # If the stockBracket is zero, ignore any stock.
                if not commodity['stock'] or not commodity['stockBracket']:
                    commodity['stock'] = '-'
                else:
                    demand = bracket_levels[commodity['stockBracket']]
                    commodity['stock'] = str(commodity['stock'])+demand

                # If demand is zero, list as unknown.
                if not (commodity['demand'] and commodity['demandBracket']):
                    commodity['demand'] = '?'
                else:
                    demand = bracket_levels[commodity['demandBracket']]
                    commodity['demand'] = str(commodity['demand'])+demand

                f.write(
                    "\t\t{} {} {} {} {}\n".format(
                        commodity['name'],
                        commodity['sellPrice'],
                        commodity['buyPrice'],
                        commodity['demand'],
                        commodity['stock'],
                    ))

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
            con._debug = False

            if len(eddn_market):
                print('Posting commodities to EDDN...')
                con.publishCommodities(
                    system,
                    station,
                    eddn_market
                )

            if len(yardList):
                print('Posting shipyard to EDDN...')
                con.publishShipyard(
                    system,
                    station,
                    yardList
                )

            if 'modules' in api.profile['lastStarport']:
                eddn_modules = []
                for module in api.profile['lastStarport']['modules'].values():
                    res = outfMap.mapID(module['id'], None)
                    if res:
                        eddn_modules.append(res)
                    else:
                        # ignore Bobble, Decals and PaintJobs
                        if not module['name'].lower().startswith(
                            ('bobble', 'decal', 'paintjob')
                        ):
                            tdenv.NOTE("Unknown module ID: {}, name: {}", module['id'], module['name'])
                if len(eddn_modules):
                    print('Posting outfitting to EDDN...')
                    con.publishOutfitting(
                        system,
                        station,
                        eddn_modules
                    )

        # We did all the work
        return False
