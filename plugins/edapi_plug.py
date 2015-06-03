# ----------------------------------------------------------------
# Import plugin that downloads market and ship vendor data from the
# Elite Dangerous mobile API.
# ----------------------------------------------------------------

import cache
import csvexport
import getpass
import os
import pathlib
import plugins
import pickle
import requests
from requests.utils import dict_from_cookiejar
from requests.utils import cookiejar_from_dict
import sys
import time
import textwrap

# ----------------------------------------------------------------
# Deal with some differences in names between TD, ED and the API.
# ----------------------------------------------------------------

bracket_levels = ('-', 'L', 'M', 'H')

# This translates what the API calls a ship into what TD calls a
# ship.

ship_names = {
    'Adder': 'Adder',
    'Anaconda': 'Anaconda',
    'Asp': 'Asp',
    'CobraMkIII': 'Cobra',
    'Eagle': 'Eagle',
    'Empire_Fighter': 'Empire_Fighter',
    'Empire_Trader': 'Clipper',
    'Federation_Dropship': 'Dropship',
    'Federation_Fighter': 'Federation_Fighter',
    'FerDeLance': 'Fer-de-Lance',
    'Hauler': 'Hauler',
    'Orca': 'Orca',
    'Python': 'Python',
    'SideWinder': 'Sidewinder',
    'Type6': 'Type 6',
    'Type7': 'Type 7',
    'Type9': 'Type 9',
    'Viper': 'Viper',
    'Vulture': 'Vulture',
}

# Categories to ignore. Drones end up here. No idea what they are.
cat_ignore = [
    'NonMarketable',
]

# TD has different names for these.
cat_correct = {
    'Narcotics': 'Legal Drugs'
}

# TD has different names for these.
comm_correct = {
    'Agricultural Medicines': 'Agri-Medicines',
    'Atmospheric Extractors': 'Atmospheric Processors',
    'Auto Fabricators': 'Auto-Fabricators',
    'Basic Narcotics': 'Narcotics',
    'Bio Reducing Lichen': 'Bioreducing Lichen',
    'Hazardous Environment Suits': 'H.E. Suits',
    'Heliostatic Furnaces': 'Microbial Furnaces',
    'Marine Supplies': 'Marine Equipment',
    'Non Lethal Weapons': 'Non-Lethal Weapons',
    'Terrain Enrichment Systems': 'Land Enrichment Systems',
}


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
            # Make an attempt at rate limiting requests to the API
            # Please don't disable this.
            delta = time.time()-os.path.getmtime(self._cookiefile)
            if delta < 10:
                sys.exit('You must wait at least 10 seconds between queries ' +
                         'to the API. Try again in about {} seconds'.format
                         (int(10-delta)))
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
                persists try using --debug and report this.
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


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads market and ship vendor data from the Elite Dangerous
    mobile API.
    """

    cookieFile = "edapi.cookies"

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)

        self.filename = self.defaultImportFile
        cookieFilePath = pathlib.Path(ImportPlugin.cookieFile)
        self.cookiePath = tdb.dataPath / cookieFilePath

    def run(self):
        tdb, tdenv = self.tdb, self.tdenv

        # Connect to the API, authenticate, and pull down the commander
        # /profile.
        api = EDAPI(cookiefile=str(self.cookiePath))

        # Sanity check that the commander is docked. Otherwise we will get a
        # mismatch between the last system and last station.
        if not api.profile['commander']['docked']:
            print('Commander not docked. Aborting!')
            return False

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

        print(station_lookup)

        # The station isn't known. Add it.
        if not station_lookup:
            print('Station unknown.')
            print('Adding:', place)
            lsFromStar = input(
                "Distance from star (enter for 0): "
            ) or 0
            lsFromStar = int(lsFromStar)
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
            # This is unreliable, so default to unknown.
            if 'commodities' in api.profile['lastStarport']:
                market = 'Y'
            else:
                market = '?'
            # This is also unreliable, so default to unknown.
            if 'ships' in api.profile['lastStarport']:
                shipyard = 'Y'
            else:
                shipyard = '?'
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
                repair=repair
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
            lsFromStar = station_lookup.lsFromStar
            blackMarket = station_lookup.blackMarket
            maxPadSize = station_lookup.maxPadSize
            market = station_lookup.market
            shipyard = station_lookup.shipyard
            outfitting = station_lookup.outfitting
            rearm = station_lookup.rearm
            refuel = station_lookup.refuel
            repair = station_lookup.repair

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

            # This is unreliable, so default to unchanged.
            if 'commodities' in api.profile['lastStarport']:
                market = 'Y'

            # This is also unreliable, so default to unchanged.
            if 'ships' in api.profile['lastStarport']:
                shipyard = 'Y'

            if (
                lsFromStar != station_lookup.lsFromStar or
                blackMarket != station_lookup.blackMarket or
                maxPadSize != station_lookup.maxPadSize or
                market != station_lookup.market or
                shipyard != station_lookup.shipyard or
                outfitting != station_lookup.outfitting or
                rearm != station_lookup.rearm or
                refuel != station_lookup.refuel or
                repair != station_lookup.repair
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
                    repair=repair
                ):
                    lines, csvPath = csvexport.exportTableToFile(
                        tdb,
                        tdenv,
                        "Station",
                    )
                    tdenv.NOTE("{} updated.", csvPath)

        # If a shipyard exists, update the ship vendor list.
        if 'ships' in api.profile['lastStarport']:
            ships = list(
                api.profile['lastStarport']['ships']['shipyard_list'].keys()
            )
            for ship in api.profile['lastStarport']['ships']['unavailable_list']:
                ships.append(ship['name'])
            db = tdb.getDB()
            for ship in ships:
                ship_lookup = tdb.lookupShip(ship_names[ship])
                db.execute(
                    """
                    REPLACE INTO ShipVendor
                    (ship_id, station_id)
                    VALUES
                    (?, ?)
                    """,
                    [ship_lookup.ID, station_lookup.ID]
                )
                db.commit()
            tdenv.NOTE("Updated {} ships in {} shipyard.", len(ships), place)
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
            for commodity in api.profile['lastStarport']['commodities']:
                if commodity['categoryname'] in cat_ignore:
                    continue
                if commodity['categoryname'] in cat_correct:
                    commodity['categoryname'] = cat_correct[commodity['categoryname']]
                if commodity['name'] in comm_correct:
                    commodity['name'] = comm_correct[commodity['name']]

                f.write("\t+ {}\n".format(commodity['categoryname']))

                # If stock is zero, list it as unavailable.
                if commodity['stock'] == 0:
                    commodity['stock'] = '-'
                else:
                    demand = bracket_levels[int(commodity['stockBracket'])]
                    commodity['stock'] = str(int(commodity['stock']))+demand

                # If demand is zero, zero out the sell price.
                if commodity['demand'] == 0:
                    commodity['demand'] = '?'
                    commodity['sellPrice'] = 0
                else:
                    demand = bracket_levels[int(commodity['demandBracket'])]
                    commodity['demand'] = str(int(commodity['demand']))+demand

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

        # We did all the work
        return False
